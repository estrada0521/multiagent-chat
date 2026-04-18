from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index import hub_server
from agent_index.hub_chat_supervisor_core import chat_launch_session_dir
from agent_index.state_core import local_runtime_log_dir


class _ChatRuntimeStub:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def session_index_path(self, session_name: str, workspace: str, explicit_log_dir: str):
        return None


class HubPendingPathTests(unittest.TestCase):
    def test_write_pending_session_files_uses_canonical_runtime_log_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            original_repo_root = hub_server.repo_root
            try:
                hub_server.repo_root = repo_root
                state = hub_server._write_pending_session_files("demo", str(repo_root), ["claude"])
            finally:
                hub_server.repo_root = original_repo_root

            session_dir = local_runtime_log_dir(repo_root) / "demo"
            self.assertEqual(Path(state["session_dir"]), session_dir)
            self.assertTrue((session_dir / ".agent-index.jsonl").is_file())
            self.assertTrue((session_dir / ".meta").is_file())
            self.assertTrue((session_dir / ".pending-launch.json").is_file())
            self.assertFalse((repo_root / "logs" / "demo").exists())

    def test_chat_launch_session_dir_uses_canonical_runtime_log_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runtime = _ChatRuntimeStub(repo_root)

            session_dir = chat_launch_session_dir(runtime, "demo", str(repo_root), "")

            self.assertEqual(session_dir, local_runtime_log_dir(repo_root) / "demo")
            self.assertTrue(session_dir.is_dir())
            self.assertFalse((repo_root / "logs" / "demo").exists())


if __name__ == "__main__":
    unittest.main()
