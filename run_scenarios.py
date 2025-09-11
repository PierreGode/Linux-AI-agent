#!/usr/bin/env python3
"""Run the agent against a subset of scenarios from SCENARIOS.md.

This script loads the scenario descriptions, picks the first N entries, and
feeds them to the agent. The agent's explanation and command outputs are
printed so humans can evaluate performance.
"""

from __future__ import annotations

import re
from pathlib import Path
import sys
import agent

SCENARIOS_FILE = Path(__file__).with_name("SCENARIOS.md")
DEFAULT_COUNT = 5


def load_scenarios(path: Path = SCENARIOS_FILE) -> list[str]:
    """Extract scenario descriptions from SCENARIOS.md."""
    scenarios: list[str] = []
    for line in path.read_text().splitlines():
        match = re.match(r"\d+\.\s+(.*)", line)
        if match:
            scenarios.append(match.group(1).strip())
    return scenarios


def run(n: int = DEFAULT_COUNT) -> None:
    scenarios = load_scenarios()[:n]
    for idx, desc in enumerate(scenarios, 1):
        print(f"\n=== Scenario {idx}: {desc} ===")
        messages = [{"role": "system", "content": agent.SYSTEM_PROMPT}]
        # Wrap scenario as a task for the agent
        task = f"Investigate and resolve: {desc}"
        messages.append({"role": "user", "content": task})
        try:
            plan = agent.plan_commands(messages)
            print("[AI]", plan.get("explanation", ""))
            output = agent.run_commands(plan["commands"])
            if output.strip():
                print(output)
        except Exception as exc:
            print(f"[Agent error] {exc}")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_COUNT
    run(count)
