#!/usr/bin/env python3
"""Collect a broad set of diagnostic data into a timestamped log file.

The script is intended to run before launching the interactive AI agent so the
model can reference a recent snapshot of the system state.  It executes a large
set of read-only commands covering general system details, package manager
status, networking, Docker, and service health.  Each command is wrapped with
metadata (timestamp, exit code, stderr) to make the log easy to skim and search.

Usage examples::

    python3 collect_diagnostics.py                       # write to diagnostics-<ts>.log
    python3 collect_diagnostics.py --output path/to/log  # custom output path
    python3 collect_diagnostics.py --sections system network

If a command is missing on the host, the script records that fact instead of
failing.  This makes it safe to run the script on minimal distributions.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List, Tuple

# ------------------------------ Command catalog -------------------------------

Command = Tuple[str, str]


def _supports_systemctl() -> bool:
    """Return True when systemd/systemctl appears to be available."""

    return shutil.which("systemctl") is not None and Path("/run/systemd/system").exists()


def _supports_docker() -> bool:
    """Return True when the Docker CLI is available."""

    return shutil.which("docker") is not None


def _supports_podman() -> bool:
    return shutil.which("podman") is not None


def _supports_kubectl() -> bool:
    return shutil.which("kubectl") is not None


def _common_commands() -> List[Command]:
    """Commands always worth running regardless of the host environment."""

    return [
        ("uname -a", "Kernel and architecture"),
        ("cat /etc/os-release", "Distribution release info"),
        ("uptime", "System uptime/load"),
        ("date", "Current time"),
        ("who -a", "Logged-in users"),
        ("id", "Current user identity"),
        ("df -h", "Disk usage"),
        ("free -h", "Memory usage"),
        ("ps aux --sort=-%cpu | head -n 20", "Top processes by CPU"),
        ("ps aux --sort=-%mem | head -n 20", "Top processes by memory"),
        ("journalctl -p err -n 200", "Last 200 error-level journal entries"),
        ("dmesg | tail -n 200", "Kernel ring buffer tail"),
    ]


def _package_commands() -> List[Command]:
    cmds = [
        ("which apt", "Apt availability"),
        ("apt-cache policy", "Apt policy"),
        ("apt-get -s upgrade", "Apt upgrade simulation"),
        ("which yum", "Yum availability"),
        ("yum check-update", "Yum updates"),
        ("which dnf", "Dnf availability"),
        ("dnf check-update", "Dnf updates"),
        ("which pacman", "Pacman availability"),
        ("pacman -Qu", "Pacman pending upgrades"),
        ("which apk", "APK availability"),
        ("apk version", "APK version info"),
    ]
    return cmds


def _network_commands() -> List[Command]:
    cmds = [
        ("ip address", "Network interfaces"),
        ("ip route", "Routing table"),
        ("ss -tulpn", "Listening sockets"),
        ("resolvectl status", "Resolver configuration"),
        ("cat /etc/resolv.conf", "Resolver fallback"),
        ("ping -c 4 8.8.8.8", "Ping external DNS (8.8.8.8)"),
        ("ping -c 4 1.1.1.1", "Ping external DNS (1.1.1.1)"),
        ("ping -c 4 localhost", "Ping localhost"),
        ("traceroute 8.8.8.8", "Traceroute to 8.8.8.8"),
        ("systemd-resolve --statistics", "systemd-resolved stats"),
    ]
    return cmds


def _service_commands() -> List[Command]:
    cmds = []
    if _supports_systemctl():
        cmds.extend(
            [
                ("systemctl status", "Systemd overall status"),
                ("systemctl list-units --type=service --state=failed", "Failed services"),
                ("systemctl list-timers", "Active timers"),
                ("systemctl list-sockets", "Listening sockets via systemd"),
                ("loginctl list-sessions", "Active sessions"),
            ]
        )
    else:
        cmds.append(("service --status-all", "SysV service status"))
    return cmds


def _container_commands() -> List[Command]:
    cmds: List[Command] = []
    if _supports_docker():
        cmds.extend(
            [
                ("docker info", "Docker daemon info"),
                ("docker ps -a", "Docker containers"),
                ("docker images", "Docker images"),
                ("docker network ls", "Docker networks"),
                ("docker volume ls", "Docker volumes"),
            ]
        )
    if _supports_podman():
        cmds.extend(
            [
                ("podman info", "Podman info"),
                ("podman ps -a", "Podman containers"),
            ]
        )
    if _supports_kubectl():
        cmds.extend(
            [
                ("kubectl config get-contexts", "Kubectl contexts"),
                ("kubectl get nodes -o wide", "Kubernetes nodes"),
                ("kubectl get pods --all-namespaces", "Kubernetes pods"),
            ]
        )
    return cmds


def build_catalog() -> List[Tuple[str, List[Command]]]:
    """Return a list of (section_name, commands)."""

    sections = [
        ("system", _common_commands()),
        ("packages", _package_commands()),
        ("network", _network_commands()),
        ("services", _service_commands()),
        ("containers", _container_commands()),
    ]
    return sections


# ------------------------------ Logging helpers -------------------------------


def timestamp() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def ensure_parent(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def resolve_output_path(output: str | None) -> Path:
    if output:
        return Path(output).expanduser().resolve()
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / f"diagnostics-{ts}.log"


def run_command(cmd: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if not env.get("PATH"):
        env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    return subprocess.run(
        cmd,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def write_header(fp, output_path: Path, sections: Iterable[str]) -> None:
    fp.write("# Diagnostic Snapshot\n")
    fp.write(f"# Generated: {timestamp()}\n")
    fp.write(f"# Output file: {output_path}\n")
    fp.write(f"# Sections: {', '.join(sections)}\n")
    fp.write("# Host: {}\n".format(Path('/etc/hostname').read_text().strip() if Path('/etc/hostname').exists() else 'unknown'))
    fp.write("\n")


def log_command(fp, section: str, command: Command) -> None:
    cmd, description = command
    fp.write(f"## [{section}] {description}\n")
    fp.write(f"$ {cmd}\n")
    start = timestamp()
    result = run_command(cmd)
    fp.write(f"- timestamp: {start}\n")
    fp.write(f"- exit_code: {result.returncode}\n")
    stdout = result.stdout.rstrip()
    stderr = result.stderr.rstrip()
    if stdout:
        fp.write("--- stdout ---\n")
        fp.write(stdout + "\n")
    else:
        fp.write("--- stdout: <empty> ---\n")
    if stderr:
        fp.write("--- stderr ---\n")
        fp.write(stderr + "\n")
    else:
        fp.write("--- stderr: <empty> ---\n")
    fp.write("\n")


def available_sections() -> List[str]:
    return [name for name, _ in build_catalog()]


# ------------------------------ CLI interface --------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect a comprehensive set of diagnostic data into a log file.",
    )
    parser.add_argument(
        "--output",
        help="Path to write the log file. Default is diagnostics-<timestamp>.log in the current directory.",
    )
    parser.add_argument(
        "--sections",
        nargs="+",
        choices=available_sections(),
        help="Subset of sections to gather (default is all).",
    )
    return parser.parse_args()


def filter_sections(
    sections: List[Tuple[str, List[Command]]], selections: Iterable[str] | None
) -> List[Tuple[str, List[Command]]]:
    if not selections:
        return sections
    desired = set(selections)
    return [(name, cmds) for name, cmds in sections if name in desired]


def collect(output: Path, selected_sections: Iterable[str] | None) -> Path:
    catalog = build_catalog()
    filtered = filter_sections(catalog, selected_sections)
    ensure_parent(output)
    with output.open("w", encoding="utf-8") as fp:
        write_header(fp, output, [name for name, _ in filtered])
        for section, commands in filtered:
            if not commands:
                fp.write(f"## [{section}] No commands available on this system.\n\n")
                continue
            for command in commands:
                log_command(fp, section, command)
    return output


def main() -> None:
    args = parse_args()
    output_path = resolve_output_path(args.output)
    final_path = collect(output_path, args.sections)
    print(f"Diagnostics collected in {final_path}")


if __name__ == "__main__":
    main()
