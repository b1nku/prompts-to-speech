"""Install/uninstall a macOS launchd LaunchAgent so the runtime starts on boot
and restarts on failure.

A LaunchAgent (not a LaunchDaemon) is used on purpose: agents run inside the
logged-in user's GUI session, which is what audio playback (afplay) needs. For an
unattended headless Mac mini, enable automatic login so the session exists on boot.
"""

import os
import plistlib
import subprocess
import sys

LABEL = "local.prompts-to-speech"


def plist_path() -> str:
    return os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")


def agent_installed() -> bool:
    return os.path.exists(plist_path())


def _build_plist(script_path: str) -> dict:
    script_path = os.path.abspath(script_path)
    workdir = os.path.dirname(script_path)
    logs = os.path.join(workdir, "logs")
    os.makedirs(logs, exist_ok=True)
    return {
        "Label": LABEL,
        # --no-install: the launchd-managed instance must never try to re-install.
        "ProgramArguments": [sys.executable, script_path, "--no-install"],
        "WorkingDirectory": workdir,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": os.path.join(logs, "stdout.log"),
        "StandardErrorPath": os.path.join(logs, "stderr.log"),
    }


def install_agent(script_path: str) -> None:
    """Write the plist and load it into the user's launchd domain."""
    path = plist_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        plistlib.dump(_build_plist(script_path), f)
    print(f"Wrote {path}")

    domain = f"gui/{os.getuid()}"
    # Boot out any previous instance first so re-installing is idempotent.
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"],
                   capture_output=True)
    result = subprocess.run(["launchctl", "bootstrap", domain, path],
                            capture_output=True, text=True)
    if result.returncode != 0:
        # Older macOS fallback.
        result = subprocess.run(["launchctl", "load", "-w", path],
                                capture_output=True, text=True)
    if result.returncode != 0:
        print(f"launchctl failed: {result.stderr.strip()}", file=sys.stderr)
        print("The plist is written; you can load it manually with:", file=sys.stderr)
        print(f"  launchctl bootstrap {domain} {path}", file=sys.stderr)
    else:
        print(f"Loaded launchd agent '{LABEL}'. It will start on boot and restart on failure.")


def uninstall_agent() -> None:
    """Stop the agent and remove its plist."""
    path = plist_path()
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"],
                   capture_output=True)
    if os.path.exists(path):
        os.unlink(path)
        print(f"Removed {path} and stopped agent '{LABEL}'.")
    else:
        print(f"No agent installed at {path}.")
