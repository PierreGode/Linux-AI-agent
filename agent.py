#!/usr/bin/env python3
import argparse
import os
import re
import shlex
import subprocess
from pathlib import Path
from textwrap import dedent

HOME = str(Path.home())

# ---- Simple tool layer -------------------------------------------------------

def run(cmd: str, check=True, capture=False, cwd=None):
    """Run a shell command safely with subprocess (no shell=True)."""
    if isinstance(cmd, str):
        args = shlex.split(cmd)
    else:
        args = cmd
    if capture:
        return subprocess.run(args, check=check, cwd=cwd, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
    else:
        return subprocess.run(args, check=check, cwd=cwd)

def write_file(path: str, content: str, make_executable: bool = False):
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    if make_executable:
        p.chmod(p.stat().st_mode | 0o111)
    return str(p)

# ---- Action: Create Google Coral install script ------------------------------

def action_create_coral_install_script(dest: str = "~/coral_install.sh"):
    """
    Create a robust install script for Google Coral USB/PCIe on Raspberry Pi OS (64-bit),
    and a Python 3.9 virtual environment via pyenv for pycoral.
    """
    script = dedent(f"""\
        #!/usr/bin/env bash
        set -euo pipefail

        echo "[i] Google Coral setup for Raspberry Pi OS (64-bit)"
        echo "[i] This will install: apt deps, Google Coral runtime (libedgetpu1-std), pyenv (Python 3.9), and pycoral."

        if [[ "$(uname -m)" != "aarch64" ]]; then
          echo "[!] This script is intended for 64-bit Raspberry Pi OS (aarch64)."
          echo "    Current arch: $(uname -m)"
          exit 1
        fi

        # --- Essentials -------------------------------------------------------
        sudo apt-get update
        sudo apt-get install -y --no-install-recommends \\
          curl ca-certificates gnupg apt-transport-https lsb-release \\
          build-essential pkg-config git \\
          libssl-dev zlib1g-dev libbz2-1.0 libbz2-dev libreadline-dev \\
          libsqlite3-dev wget llvm libncursesw5-dev xz-utils tk-dev \\
          libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

        # --- Add Coral APT repo & runtime ------------------------------------
        # Note: If Google changes repo keys/URLs in the future, check Coral docs.
        if ! grep -q "packages.cloud.google.com/apt" /etc/apt/sources.list /etc/apt/sources.list.d/* 2>/dev/null; then
          echo "[i] Adding Google Coral APT repository..."
          echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | \\
            sudo tee /etc/apt/sources.list.d/coral-edgetpu.list >/dev/null
          curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
        else
          echo "[i] Coral APT repository already present."
        fi

        sudo apt-get update
        # Install the standard (not -max) runtime; you can switch later with update-alternatives
        sudo apt-get install -y libedgetpu1-std

        # --- pyenv + Python 3.9 ----------------------------------------------
        if [[ ! -d "$HOME/.pyenv" ]]; then
          echo "[i] Installing pyenv..."
          git clone https://github.com/pyenv/pyenv.git "$HOME/.pyenv"
        fi

        if ! grep -q 'PYENV_ROOT' "$HOME/.bashrc"; then
          cat >> "$HOME/.bashrc" <<'EOF'
        export PYENV_ROOT="$HOME/.pyenv"
        command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
        EOF
        fi

        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"

        PY39="3.9.18"
        if ! pyenv versions --bare | grep -Fxq "$PY39"; then
          echo "[i] Building Python $PY39 (this can take a while)..."
          CFLAGS="-O3" pyenv install "$PY39"
        fi

        # Create/refresh a dedicated env for Coral work
        ENV_NAME="coral-py39"
        if pyenv versions --bare | grep -Fxq "$ENV_NAME"; then
          echo "[i] pyenv virtualenv {ENV_NAME} exists."
        else
          pyenv virtualenv "$PY39" "$ENV_NAME"
        fi
        pyenv local "$ENV_NAME"

        # Ensure pip is fresh
        python -m pip install --upgrade pip wheel setuptools

        # Install pycoral (includes tflite runtime wheels for manyarm targets)
        python -m pip install --upgrade pycoral

        # --- Udev rules / permissions ----------------------------------------
        # libedgetpu package typically installs required udev rules.
        # Re-trigger udev so the device permissions are applied if USB is connected.
        if command -v udevadm >/dev/null 2>&1; then
          sudo udevadm control --reload-rules
          sudo udevadm trigger
        fi

        cat <<'EONOTE'
        [✓] Coral runtime installed: libedgetpu1-std
        [✓] Python env ready: pyenv virtualenv 'coral-py39'
        [✓] pycoral installed

        Usage:
          cd ~
          # Activate env in current shell:
          export PYENV_ROOT="$HOME/.pyenv"
          export PATH="$PYENV_ROOT/bin:$PATH"
          eval "$(pyenv init -)"
          pyenv local coral-py39
          python -c "import pycoral; print('pycoral OK')"

        If you have a Coral USB Accelerator connected, verify it shows up:
          lsusb | grep -i "Google" || true

        You can later switch runtime flavor:
          sudo apt-get install libedgetpu1-max
          sudo update-alternatives --config libedgetpu1-std

        EONOTE
        """)
    path = write_file(dest, script, make_executable=True)
    return f"Created: {path}"

# ---- Router from natural language -> actions --------------------------------

INTENT_MAP = [
    # (pattern, function, kwargs)
    (r"create (a )?google coral install script", action_create_coral_install_script, {}),
    (r"create.*coral.*script", action_create_coral_install_script, {}),
]

def resolve_intent(task: str):
    t = task.lower().strip()
    for pattern, func, kwargs in INTENT_MAP:
        if re.search(pattern, t):
            return func, kwargs
    return None, None

# ---- Main -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Mini AI agent to execute safe tasks on your Raspberry Pi."
    )
    parser.add_argument("task", help="Plain-English instruction, e.g. 'create a google coral install script in home folder'")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not execute shell commands (for actions that run commands).")
    args = parser.parse_args()

    func, kwargs = resolve_intent(args.task)
    if func is None:
        print("[!] Sorry, I don't recognize that task yet.")
        print("    Try: 'create a google coral install script in home folder'")
        return

    # For now our action only writes a file; no shell risk. Execute directly.
    result = func(**kwargs)
    print(result)

if __name__ == "__main__":
    main()
