#!/usr/bin/env python3
import openai
import os
import subprocess
import shlex
import json
from pathlib import Path

openai.api_key = os.getenv("OPENAI_API_KEY")

SYSTEM_PROMPT = """
You are an AI agent running on a Raspberry Pi.
- User will give you natural language tasks.
- Always respond with JSON only, no extra text.
- JSON format:
  {
    "explanation": "short reason",
    "commands": ["list", "of", "shell", "commands"]
  }
- Commands must be safe and executable on Raspberry Pi OS.
- Default to creating files/scripts in the user's home folder when asked.
"""

def run_commands(cmds):
    for cmd in cmds:
        print(f"[Executing] {cmd}")
        try:
            subprocess.run(shlex.split(cmd), check=True)
        except subprocess.CalledProcessError as e:
            print(f"[Error] {e}")

def agent(task):
    response = openai.ChatCompletion.create(
        model="gpt-5-nano",  # or gpt-4o-mini if preferred
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task}
        ]
    )
    content = response["choices"][0]["message"]["content"]
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print("Invalid JSON from model:", content)
        return
    print("[AI] " + data["explanation"])
    run_commands(data["commands"])

if __name__ == "__main__":
    while True:
        task = input(">>> ")
        if task.lower() in ["exit", "quit"]:
            break
        agent(task)
