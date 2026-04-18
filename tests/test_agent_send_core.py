from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index.agent_send_core import AgentSendError, AgentSendRuntime, ensure_session_index_mirror


class AgentSendCoreTests(unittest.TestCase):
    def test_resolve_session_name_prefers_workspace_match(self) -> None:
        runtime = AgentSendRuntime(
            repo_root=_bootstrap.REPO_ROOT,
            script_dir=_bootstrap.REPO_ROOT / "bin",
            env={},
            cwd="/tmp/workspace",
        )
        with patch.object(runtime, "list_sessions", return_value=["s1", "s2"]), patch.object(
            runtime,
            "session_workspace_value",
            side_effect=lambda session: str(runtime.cwd) if session == "s1" else "/tmp/other",
        ), patch.object(runtime, "matching_repo_sessions", return_value=[]):
            self.assertEqual(runtime.resolve_session_name(), "s1")

    def test_resolve_session_name_errors_on_multiple_workspace_matches(self) -> None:
        runtime = AgentSendRuntime(
            repo_root=_bootstrap.REPO_ROOT,
            script_dir=_bootstrap.REPO_ROOT / "bin",
            env={},
            cwd="/tmp/workspace",
        )
        with patch.object(runtime, "list_sessions", return_value=["s1", "s2"]), patch.object(
            runtime,
            "session_workspace_value",
            return_value=str(runtime.cwd),
        ):
            with self.assertRaises(AgentSendError) as ctx:
                runtime.resolve_session_name()
        self.assertIn("Multiple sessions exist for this workspace", str(ctx.exception))

    def test_ensure_session_index_mirror_keeps_canonical_file_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "logs" / "demo" / ".agent-index.jsonl"
            canonical.parent.mkdir(parents=True, exist_ok=True)
            canonical.write_text(
                json.dumps({"msg_id": "a", "message": "one", "sender": "codex"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            mirror_base = root / "workspace-logs"
            mirror = mirror_base / "demo" / ".agent-index.jsonl"
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.write_text(
                "\n".join(
                    [
                        json.dumps({"msg_id": "a", "message": "one", "sender": "codex"}, ensure_ascii=False),
                        json.dumps({"msg_id": "b", "message": "two", "sender": "claude"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            ensure_session_index_mirror(canonical, mirror_base, "demo")

            entries = [json.loads(line) for line in canonical.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual({entry["msg_id"] for entry in entries}, {"a"})
            self.assertFalse(mirror.is_symlink())

    def test_ensure_session_index_mirror_recovers_self_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "logs" / "demo" / ".agent-index.jsonl"
            canonical.parent.mkdir(parents=True, exist_ok=True)
            canonical.symlink_to(canonical)

            ensure_session_index_mirror(canonical, root / "workspace-logs", "demo")

            self.assertTrue(canonical.exists())
            self.assertFalse(canonical.is_symlink())


if __name__ == "__main__":
    unittest.main()
