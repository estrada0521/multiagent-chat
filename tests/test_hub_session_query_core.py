from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
from agent_index.hub_session_query_core import archived_sessions, session_index_paths
from agent_index.state_core import local_runtime_log_dir, local_state_dir


class _RuntimeStub:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.central_log_dir = local_runtime_log_dir(repo_root)

    def chat_port_for_session(self, session_name: str) -> int:
        return 0


class HubSessionQueryCoreTests(unittest.TestCase):
    def test_session_index_paths_ignore_repo_logs_legacy_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runtime = _RuntimeStub(repo_root)

            legacy_index = repo_root / "logs" / "demo" / ".agent-index.jsonl"
            legacy_index.parent.mkdir(parents=True, exist_ok=True)
            legacy_index.write_text('{"sender":"claude","message":"old"}\n', encoding="utf-8")

            self.assertEqual(session_index_paths(runtime, "demo"), [])

    def test_archived_sessions_ignore_repo_logs_legacy_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runtime = _RuntimeStub(repo_root)

            legacy_dir = repo_root / "logs" / "demo_250101_010101"
            legacy_dir.mkdir(parents=True, exist_ok=True)
            (legacy_dir / ".meta").write_text(
                json.dumps(
                    {
                        "session": "demo",
                        "workspace": str(repo_root),
                        "created_at": "2025-01-01 01:01:01",
                        "updated_at": "2025-01-01 01:01:01",
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(archived_sessions(runtime), [])

    def test_archived_sessions_keep_workspace_archives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runtime = _RuntimeStub(repo_root)

            workspace_root = local_state_dir(repo_root) / "workspaces" / "demo-123456789abc"
            archive_dir = workspace_root / "demo_250101_010101"
            archive_dir.mkdir(parents=True, exist_ok=True)
            (archive_dir / ".meta").write_text(
                json.dumps(
                    {
                        "session": "demo",
                        "workspace": str(repo_root),
                        "created_at": "2025-01-01 01:01:01",
                        "updated_at": "2025-01-01 01:01:01",
                    }
                ),
                encoding="utf-8",
            )

            records = archived_sessions(runtime)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["name"], "demo")


if __name__ == "__main__":
    unittest.main()
