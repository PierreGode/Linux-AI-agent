# Linux-AI-agent
An AI agent that will execute tasks in your system.

## Notes

The agent now includes guidance to avoid mixing up service ports. When
troubleshooting networked applications such as Docker containers, verify the
expected port mapping and test connectivity from both the host and any peer
containers.

After running its planned commands, the agent now double‑checks whether the
task is complete. When it believes the job is finished, it prints a concise
summary of what was accomplished and then exits.

## Scenario Library

See [SCENARIOS.md](SCENARIOS.md) for fifty example Linux issues ranging from
package manager failures to Docker misconfigurations. They can be used to test
and harden the agent against a wide variety of real‑world situations.

## Network Scenario Testing

Run `./run_docker_network_scenarios.py` to evaluate the agent against five
common Docker network failure scenarios.
