#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Raspberry Pi "do-anything" AI agent powered by OpenAI gpt-5-nano.

Usage:
  export OPENAI_API_KEY="sk-..."
  python3 agent.py
  >>> in /home/pi create test.sh that runs apt update and upgrade

Notes:
- Set SAFE_MODE=False if you want maximum power (no confirmations).
- Commands execute via `bash -lc` so pipes/redirection/heredocs work.
"""

import os
import sys
import re
import json
import subprocess
from pathlib import Path
from textwrap import dedent

# -------------------------- Config -------------------------------------------

# Model and temperature can be overridden via environment variables so users
# can experiment with different small models without modifying the source.
# Default to the tiny "gpt-5-nano" model but allow alternatives (e.g.
# "gpt-4o-mini") via the MODEL environment variable.
MODEL = os.getenv("MODEL", "gpt-5-mini")
TEMPERATURE = float(os.getenv("TEMPERATURE", "1"))
SAFE_MODE = False  # True = confirm on risky commands; False = run raw
RISKY_PATTERNS = [
    r"\brm\s+-rf\s+/\b",
    r"\bmkfs\.",
    r"\bdd\s+if=",
    r"\b:>\s*/",
    r"\bchmod\s+777\s+/(?:\S*)",
    r"\bchown\s+-R\s+\S+\s+/(?:\S*)",
    r"\bparted\b",
    r"\bfdisk\b",
    r"\bsudo\s+passwd\b",
    r"\biptables\b",
    r"\bufw\b.*\breset\b",
]

SYSTEM_PROMPT = dedent("""
You are an automation agent running in a linux OS.
The user will describe a task in natural language. You must reply with JSON ONLY (no backticks, no extra prose).
JSON schema (exact keys):
{
  "explanation": "one short sentence explaining your plan solution or response",
  "commands": ["bash command 1", "bash command 2", "..."]
}
Rules:
- Prefer idempotent commands when reasonable.
- If you need to write multi-line files or scripts, use safe Bash heredocs (with EOF) and set executable bits when needed.
- Use REAL newlines in commands. Do NOT emit literal "\\n" characters; write multi-line commands as actual multi-line text.
- Default to using the current user's home directory for relative paths.
- When interacting with Docker containers, first inspect the running containers
  (e.g. `docker ps` or `docker compose ps`) to determine the exact names before
  issuing subsequent commands.
- When diagnosing network services, confirm you are probing the correct
  service and port. Verify port mappings and test from both the host and any
  relevant containers instead of trusting responses from unrelated ports.
- For Docker networking issues, inspect container networks (`docker network ls`,
  `docker network inspect`) and test connectivity from within containers using
  `docker exec <container> ping -c1 <host>`.
- Expect a wide range of Linux troubleshooting scenarios (e.g. package
  management failures, Docker daemon issues, service misconfigurations,
  permission problems) and craft commands accordingly.
- Approach each assignment like an investigation. Before concluding that
  something is missing or broken, gather evidence with status checks, log
  inspection, and configuration review. Prefer read-only, information-gathering
  commands first and escalate to disruptive actions only when necessary.
- When working with PM2 or similar process managers, list applications (e.g.
  `pm2 list` or `pm2 status`) to confirm exact names, then capture meaningful
  log output (such as the last 200 lines via `pm2 logs <name> --lines 200` or
  by reading files under `~/.pm2/logs`). If the requested name is not present,
  broaden the search by looking for related names or directories before
  reporting failure.
- If an initial command does not yield the expected evidence, plan follow-up
  commands that widen the investigation rather than stopping immediately.
- Use the explanation field to outline the reasoning and investigative steps
  you will take, not just restate the request. Format it as a short numbered
  list whenever you are planning multiple commands.
- If you ultimately cannot fulfill the request, report every place you looked
  and suggest next investigative steps instead of giving a terse failure.
- Do ask follow-up questions only if needed; decide and output runnable commands.
- Keep explanations short but informative.
- when asked to find issues prefer responding with an answer over running commands.
- when asked to execute tasks think one more time before running commands.
""").strip()

# -------------------------- OpenAI client ------------------------------------

try:
    from openai import OpenAI
except Exception:
    sys.stderr.write("ERROR: openai>=1.0.0 not installed. Install with:\n  python3 -m pip install --upgrade openai\n")
    sys.exit(1)

if not os.getenv("OPENAI_API_KEY"):
    sys.stderr.write(
        "ERROR: OPENAI_API_KEY is not set. Export it and rerun:\n"
        '  export OPENAI_API_KEY="sk-..."\n'
    )
    sys.exit(1)

client = OpenAI()  # reads OPENAI_API_KEY from env

# -------------------------- Helpers ------------------------------------------

def _extract_json(s: str) -> str:
    """Strip code fences if any and return first {...} block."""
    s = s.strip()
    # remove fenced blocks if present
    s = re.sub(r"^```[a-zA-Z]*\n", "", s)
    s = re.sub(r"\n```$", "", s)
    # quick path
    try:
        json.loads(s)
        return s
    except Exception:
        pass
    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m:
        raise ValueError("Model did not return JSON.")
    return m.group(0)

def is_risky(cmd: str) -> bool:
    for pat in RISKY_PATTERNS:
        if re.search(pat, cmd):
            return True
    return False

def confirm(prompt: str) -> bool:
    try:
        ans = input(f"{prompt} [y/N]: ").strip().lower()
        return ans in {"y", "yes"}
    except (EOFError, KeyboardInterrupt):
        return False

def _unwrap_outer_quotes(cmd: str) -> str:
    """If the entire command is wrapped in matching single or double quotes, unwrap it."""
    if len(cmd) >= 2 and ((cmd[0] == cmd[-1] == '"') or (cmd[0] == cmd[-1] == "'")):
        return cmd[1:-1]
    return cmd

def normalize_command(cmd: str) -> str:
    """
    Normalize model-emitted commands so Bash handles heredocs and newlines correctly.
    - Convert literal escape sequences like \\n, \\t, \\r into real characters.
    - Ensure heredocs end with a newline so the terminator is seen.
    - Unwrap one pair of surrounding quotes if the whole string is quoted.
    """
    original = cmd
    cmd = _unwrap_outer_quotes(cmd)

    # Replace common escaped sequences with real characters.
    # Do this conservatively to avoid over-decoding arbitrary escapes.
    cmd = cmd.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")

    # If a heredoc is present, make sure the string ends with a newline.
    if "<<" in cmd and not cmd.endswith("\n"):
        cmd = cmd + "\n"

    # Optional: trim trailing spaces on lines (helps if EOF has spaces)
    lines = cmd.splitlines()
    lines = [ln.rstrip() for ln in lines]
    cmd = "\n".join(lines)
    return cmd

def run_commands(commands):
    """Run a sequence of commands in the same Bash shell so state persists."""
    outputs = []
    placeholder_re = re.compile(r"<[\w-]+>")
    # Spawn a single login shell; variables persist across commands.  Some
    # environments wipe out PATH via shell init scripts, so provide a safe
    # default if it's missing to ensure basic utilities remain accessible.
    env = os.environ.copy()
    if not env.get("PATH"):
        env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    shell = subprocess.Popen(
        ["bash", "-l"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    try:
        for raw in commands:
            cmd = normalize_command(str(raw))
            if placeholder_re.search(cmd) and "<<" not in cmd:
                print("[Skipped placeholder]", cmd)
                outputs.append(f"$ {cmd}\n[Skipped placeholder]")
                continue
            print("[Executing]" + (f" {cmd}" if "\n" not in raw else "\n(multiline command)"))
            if SAFE_MODE and (cmd.startswith("sudo") or is_risky(cmd)):
                if not confirm("This looks privileged or risky. Run it anyway?"):
                    print("[Skipped]")
                    outputs.append(f"$ {cmd}\n[Skipped]")
                    continue
            # Send the command and a sentinel to capture its exit code
            shell.stdin.write(cmd + "\n")
            shell.stdin.write("echo __CMD_EXIT:$?\n")
            shell.stdin.flush()

            collected = []
            exit_code = 0
            # Read until we see the sentinel
            while True:
                line = shell.stdout.readline()
                if line == "":
                    break
                if line.startswith("__CMD_EXIT:"):
                    exit_code = int(line.strip().split(":", 1)[1])
                    break
                print(line, end="")
                collected.append(line)

            cmd_output = f"$ {cmd}\n" + "".join(collected)
            if exit_code != 0:
                error_msg = f"[Error] Command failed with code {exit_code}"
                print(error_msg)
                cmd_output += f"\n{error_msg}\n"
            outputs.append(cmd_output)
    finally:
        try:
            shell.stdin.close()
        except Exception:
            pass
        shell.terminate()
        shell.wait()
    return "\n".join(outputs)

def plan_commands(messages: list) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        messages=messages,
    )
    content = resp.choices[0].message.content
    data = json.loads(_extract_json(content))
    if not isinstance(data.get("commands"), list):
        raise ValueError("No 'commands' array from model.")
    messages.append({"role": "assistant", "content": content})
    return data


def assess_completion(messages: list) -> dict:
    """Ask the model if the task is finished and get a short summary."""
    check = {
        "role": "user",
        "content": (
            "Determine if the original task is complete based on the prior"
            " conversation and command outputs. Respond with JSON including"
            " a boolean 'done' field and a short 'summary' of what was" 
            " achieved."
        ),
    }
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        messages=messages + [check],
    )
    content = resp.choices[0].message.content
    data = json.loads(_extract_json(content))
    messages.append({"role": "assistant", "content": content})
    return data

# -------------------------- Main loop ----------------------------------------

def main():
    print("AI Agent ready. Type a task (or 'exit').")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        try:
            task = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if task.lower() in {"exit", "quit"}:
            break
        if not task:
            continue
        try:
            messages.append({"role": "user", "content": task})
            plan = plan_commands(messages)
            print("[AI]", plan.get("explanation", ""))
            output = run_commands(plan["commands"])
            if output.strip():
                messages.append({"role": "user", "content": output})
            result = assess_completion(messages)
            if result.get("summary"):
                print("[AI]", result["summary"])
            if result.get("done"):
                break
        except Exception as e:
            print(f"[Agent error] {e}")

if __name__ == "__main__":
    main()
