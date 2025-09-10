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

MODEL = "gpt-5-nano"  # or "gpt-4o-mini" if you prefer
TEMPERATURE = 1
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
  "explanation": "one short sentence explaining your plan, solution or response",
  "commands": ["bash command 1", "bash command 2", "..."]
}
Rules:
- Prefer idempotent commands when reasonable.
- If you need to write multi-line files or scripts, use safe Bash heredocs (with EOF) and set executable bits when needed.
- Use REAL newlines in commands. Do NOT emit literal "\\n" characters; write multi-line commands as actual multi-line text.
- Default to using the current user's home directory for relative paths.
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
    for raw in commands:
        cmd = normalize_command(str(raw))
        print(f"[Executing] {cmd if '\\n' not in raw else '(multiline command)'}")
        if SAFE_MODE and (cmd.startswith("sudo") or is_risky(cmd)):
            if not confirm("This looks privileged or risky. Run it anyway?"):
                print("[Skipped]")
                continue
        # Use bash -lc so redirection, pipes and heredocs work
        proc = subprocess.run(["bash", "-lc", cmd])
        if proc.returncode != 0:
            print(f"[Error] Command failed with code {proc.returncode}")
            break

def plan_commands(task: str) -> dict:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ],
    )
    content = resp.choices[0].message.content
    data = json.loads(_extract_json(content))
    if not isinstance(data.get("commands"), list):
        raise ValueError("No 'commands' array from model.")
    return data

# -------------------------- Main loop ----------------------------------------

def main():
    print("AI Agent ready. Type a task (or 'exit').")
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
            plan = plan_commands(task)
            print("[AI]", plan.get("explanation", ""))
            run_commands(plan["commands"])
        except Exception as e:
            print(f"[Agent error] {e}")

if __name__ == "__main__":
    main()
