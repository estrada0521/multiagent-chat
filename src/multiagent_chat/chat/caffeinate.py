from __future__ import annotations

import logging
import subprocess

_ARGS = ["caffeinate", "-s"]
_proc: subprocess.Popen | None = None


def status() -> dict:
    global _proc
    if _proc is not None and _proc.poll() is None:
        return {"active": True}
    _proc = None
    try:
        result = subprocess.run(["pgrep", "-x", "caffeinate"], capture_output=True)
        if result.returncode == 0:
            return {"active": True}
    except Exception as exc:
        logging.error("caffeinate status check failed: %s", exc)
    return {"active": False}


def toggle() -> dict:
    global _proc
    if status()["active"]:
        if _proc is not None:
            _proc.terminate()
            _proc = None
        else:
            subprocess.run(["killall", "caffeinate"], capture_output=True, check=False)
        return {"active": False}
    ensure_active()
    return {"active": True}


def ensure_active() -> None:
    global _proc
    if status()["active"]:
        return
    _proc = subprocess.Popen(_ARGS, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
