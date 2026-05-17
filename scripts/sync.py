#!/usr/bin/env python3
"""Sync script: docgen → lint → format check → build → commit → push → backup.

Reads the commit message from .git/COMMIT_EDITMSG (write it before running).
Aborts if the message is identical to .git/COMMIT_EDITMSG.old (stale guard).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


_LOG_FILE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "8trax/sync.log"
_COMMIT_MSG = Path(".git/COMMIT_EDITMSG")
_COMMIT_MSG_OLD = Path(".git/COMMIT_EDITMSG.old")
_BACKUP_PY = Path(__file__).parent / "backup.py"

_REMINDER = """\
Don't forget to check and update:
\tprivate/TODO.md
\t.git/COMMIT_EDITMSG
...before you commit!\
"""


def _run(*cmd: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(cmd), check=check, text=True)  # noqa: S603


def _run_capture(*cmd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(cmd), capture_output=True, text=True)  # noqa: S603


def _abort(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    print(_REMINDER)
    time.sleep(3)

    if not _COMMIT_MSG.exists():
        _abort("'.git/COMMIT_EDITMSG' not found — write a commit message before running sync.")

    if _COMMIT_MSG_OLD.exists() and _COMMIT_MSG.read_bytes() == _COMMIT_MSG_OLD.read_bytes():
        _abort(
            "'.git/COMMIT_EDITMSG' is identical to the previous commit message.\n"
            "Write a new commit message before running sync."
        )

    status = _run_capture("git", "status", "--porcelain")
    has_changes = bool(status.stdout.strip())

    _run("git", "status")

    if not has_changes:
        print("✅ No changes to sync.")
        return

    print("🔄 Changes detected. Syncing...")

    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_FILE.open("w") as log:

        def tee(text: str) -> None:
            print(text, end="")
            log.write(text)

        def run_tee(*cmd: str) -> None:
            result = subprocess.run(list(cmd), capture_output=True, text=True)  # noqa: S603
            tee(result.stdout)
            if result.stderr:
                tee(result.stderr)
            if result.returncode != 0:
                raise SystemExit(result.returncode)

        run_tee("cargo", "clippy", "--", "-D", "warnings")
        run_tee("cargo", "fmt", "--check")
        run_tee("cargo", "build", "--release")
        run_tee("git", "add", "-v", ".")

        commit = subprocess.run(["git", "commit", f"--file={_COMMIT_MSG}"], capture_output=True, text=True)  # noqa: S603, S607
        tee(commit.stdout)
        if commit.stderr:
            tee(commit.stderr)

        if commit.returncode == 0:
            _COMMIT_MSG_OLD.write_bytes(_COMMIT_MSG.read_bytes())
            run_tee("git", "push", "-u", "origin", "main")
            run_tee(sys.executable, str(_BACKUP_PY), "backup")
            tee("✅ Sync complete.\n")
        else:
            tee("❌ Commit failed — check output above.\n")
            sys.exit(commit.returncode)


if __name__ == "__main__":
    main()
