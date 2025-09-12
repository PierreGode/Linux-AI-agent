#!/usr/bin/env python3
"""Run the agent against Docker network-related scenarios."""

from __future__ import annotations

from pathlib import Path
import re
import agent

SCENARIOS_FILE = Path(__file__).with_name("SCENARIOS.md")
SCENARIO_NUMBERS = [28, 29, 33, 51, 52]


def load_selected_scenarios(path: Path, numbers: list[int]) -> list[str]:
    """Load scenarios by their list numbers."""
    mapping: dict[int, str] = {}
    for line in path.read_text().splitlines():
        match = re.match(r"(\d+)\.\s+(.*)", line)
        if match:
            mapping[int(match.group(1))] = match.group(2).strip()
    return [mapping[n] for n in numbers if n in mapping]


def run() -> None:
    scenarios = load_selected_scenarios(SCENARIOS_FILE, SCENARIO_NUMBERS)
    for idx, desc in enumerate(scenarios, 1):
        print(f"\n=== Scenario {idx}: {desc} ===")
        messages = [{"role": "system", "content": agent.SYSTEM_PROMPT}]
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
    run()
