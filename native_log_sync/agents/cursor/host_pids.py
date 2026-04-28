"""PIDs for Cursor IDE host processes (Electron), not tmux pane processes.

agent-transcripts/store.db and jsonl fds are typically held by Cursor.app helpers,
not by the shell PID from #{pane_pid}; resolution must union these into lsof scope.
"""

from __future__ import annotations

import subprocess
import sys


def pids_running_cursor_app() -> set[str]:
    """Return PIDs whose argv matches Cursor bundle paths (observation via pgrep)."""
    patterns: list[str]
    if sys.platform == "darwin":
        # Matches .../Cursor.app/Contents/MacOS/Cursor, Helper (Renderer), GPU, etc.
        patterns = [r"Cursor\.app/Contents"]
    elif sys.platform.startswith("linux"):
        patterns = [
            r"/usr/share/cursor",
            r"/opt/Cursor",
            r"/usr/lib/cursor",
        ]
    else:
        return set()

    out: set[str] = set()
    for pat in patterns:
        proc = subprocess.run(
            ["pgrep", "-f", pat],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            continue
        for line in proc.stdout.splitlines():
            w = line.strip()
            if w.isdigit():
                out.add(w)
    return out
