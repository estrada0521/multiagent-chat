from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _bootstrap  # noqa: F401
from agent_index import state_core


class StateCoreTests(unittest.TestCase):
    def test_local_state_dir_uses_darwin_root(self) -> None:
        repo_root = Path("/tmp/example-repo")
        fake_home = Path("/Users/tester")
        expected_hash = hashlib.sha1(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:12]
        with patch.object(state_core.sys, "platform", "darwin"), patch("pathlib.Path.home", return_value=fake_home):
            path = state_core.local_state_dir(repo_root)
        self.assertEqual(
            path,
            fake_home / "Library" / "Application Support" / "multiagent" / expected_hash,
        )

    def test_local_state_dir_uses_xdg_root_on_linux(self) -> None:
        repo_root = Path("/tmp/example-repo")
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir) / "home"
            xdg_root = Path(tmpdir) / "state-root"
            expected_hash = hashlib.sha1(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:12]
            with patch.object(state_core.sys, "platform", "linux"), patch(
                "pathlib.Path.home", return_value=fake_home
            ), patch.dict(os.environ, {"XDG_STATE_HOME": str(xdg_root)}, clear=False):
                path = state_core.local_state_dir(repo_root)
            self.assertEqual(path, xdg_root / "multiagent" / expected_hash)

    def test_save_chat_port_override_round_trips(self) -> None:
        repo_root = Path("/tmp/example-repo")
        session_name = "demo"
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir) / "home"
            with patch.object(state_core.sys, "platform", "darwin"), patch(
                "pathlib.Path.home", return_value=fake_home
            ):
                self.assertEqual(
                    state_core.resolve_chat_port(repo_root, session_name),
                    state_core.default_chat_port(session_name),
                )
                state_core.save_chat_port_override(repo_root, session_name, 9123)
                self.assertEqual(state_core.resolve_chat_port(repo_root, session_name), 9123)

    def test_resolve_chat_port_does_not_create_state_dir_on_read(self) -> None:
        repo_root = Path("/tmp/example-repo")
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir) / "home"
            with patch.object(state_core.sys, "platform", "darwin"), patch(
                "pathlib.Path.home", return_value=fake_home
            ):
                state_dir = state_core.local_state_dir(repo_root)
                self.assertFalse(state_dir.exists())
                state_core.resolve_chat_port(repo_root, "demo")
                self.assertFalse(state_dir.exists())

    def test_apply_hub_settings_clamps_and_derives_defaults(self) -> None:
        settings = dict(state_core.HUB_SETTINGS_DEFAULTS)
        updated = state_core._apply_hub_settings(
            {
                "agent_message_font": "preset-gothic",
                "message_text_size": "99",
                "chat_sound": "1",
                "bold_mode_mobile": "on",
                "bold_mode_desktop": "off",
            },
            settings,
        )
        self.assertEqual(updated["theme"], "black-hole")
        self.assertEqual(updated["agent_font_mode"], "gothic")
        self.assertEqual(updated["agent_message_font"], "preset-gothic")
        self.assertEqual(updated["message_text_size"], 18)
        self.assertTrue(updated["chat_sound"])
        self.assertTrue(updated["bold_mode_mobile"])
        self.assertFalse(updated["bold_mode_desktop"])

    def test_apply_hub_settings_ignores_legacy_bold_mode(self) -> None:
        settings = dict(state_core.HUB_SETTINGS_DEFAULTS)
        updated = state_core._apply_hub_settings(
            {"bold_mode": "on"},
            settings,
        )
        self.assertFalse(updated["bold_mode_mobile"])
        self.assertFalse(updated["bold_mode_desktop"])

    def test_apply_hub_settings_accepts_external_editor(self) -> None:
        settings = dict(state_core.HUB_SETTINGS_DEFAULTS)
        updated = state_core._apply_hub_settings(
            {"external_editor": "coteditor"},
            settings,
        )
        self.assertEqual(updated["external_editor"], "coteditor")

    def test_apply_hub_settings_accepts_external_editor_app_value(self) -> None:
        settings = dict(state_core.HUB_SETTINGS_DEFAULTS)
        updated = state_core._apply_hub_settings(
            {"external_editor": "app:Antigravity"},
            settings,
        )
        self.assertEqual(updated["external_editor"], "app:Antigravity")

    def test_apply_hub_settings_invalid_external_editor_falls_back(self) -> None:
        settings = dict(state_core.HUB_SETTINGS_DEFAULTS)
        updated = state_core._apply_hub_settings(
            {"external_editor": "unknown-editor"},
            settings,
        )
        self.assertEqual(updated["external_editor"], "vscode")

if __name__ == "__main__":
    unittest.main()
