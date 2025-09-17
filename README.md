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

To remain reliable even on systems with a misconfigured environment, the agent
ensures a safe default `PATH` is present before executing any commands.

## Capturing Diagnostics Up Front

Some issues are easier to diagnose when the agent has a comprehensive snapshot
of the system state to reference. The `collect_diagnostics.py` helper script
captures large amounts of read-only information (system details, package
manager status, networking, services, containers) into a timestamped log.

Run it before launching the interactive agent and keep the resulting log handy
for the conversation:

```
python3 collect_diagnostics.py
# or choose a custom location / subset of sections
python3 collect_diagnostics.py --output /tmp/diag.log --sections system network
```

The log records the exit code and stderr for every command, so missing tools or
permissions are clearly documented for later review.

## Scenario Library

See [SCENARIOS.md](SCENARIOS.md) for fifty example Linux issues ranging from
package manager failures to Docker misconfigurations. They can be used to test
and harden the agent against a wide variety of real‑world situations.

## Network Scenario Testing

Run `./run_docker_network_scenarios.py` to evaluate the agent against five
common Docker network failure scenarios.
