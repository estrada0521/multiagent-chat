from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from agent_index import hub_server


class HubCronsTemplateTests(unittest.TestCase):
    """Regression tests for hub_crons_html after template extraction.

    The 687-line HTML literal that used to live inline in
    hub_server.hub_crons_html was moved to hub_crons_template.html.
    These tests pin the rendering contract so the extraction does not drift.
    """

    @classmethod
    def setUpClass(cls) -> None:
        hub_server.initialize_from_argv([".", "bin/agent-index", "9999", "multiagent"])

    def test_empty_render_basic_shape(self) -> None:
        out = hub_server.hub_crons_html(jobs=[], session_records=[])
        self.assertTrue(out.startswith("<!doctype html>"))
        self.assertTrue(out.rstrip().endswith("</html>"))
        self.assertIn("Cron · Hub", out)
        self.assertIn("No cron jobs yet.", out)

    def test_all_placeholders_are_substituted(self) -> None:
        out = hub_server.hub_crons_html(jobs=[], session_records=[])
        # Every __TOKEN__ placeholder defined in the template must be replaced.
        for token in (
            "__CHAT_THEME__",
            "__STARFIELD_ATTR__",
            "__HUB_MANIFEST_URL__",
            "__PWA_ICON_192_URL__",
            "__APPLE_TOUCH_ICON_URL__",
            "__HUB_HEADER_CSS__",
            "__HUB_HEADER_HTML__",
            "__HUB_HEADER_JS__",
            "__NOTICE_HTML__",
            "__FORM_ID__",
            "__FORM_NAME__",
            "__FORM_TIME__",
            "__FORM_PROMPT__",
            "__FORM_ENABLED_VALUE__",
            "__FORM_ROW_HTML__",
            "__FORM_EXPANDED__",
            "__SESSION_OPTIONS__",
            "__AGENT_OPTIONS__",
            "__CRON_ROWS__",
            "__CRON_TOTAL__",
            "__CRON_ENABLED__",
            "__CRON_PAUSED__",
            "__CRON_SESSIONS_JSON__",
            "__CRON_ALL_AGENTS_JSON__",
            "__PREFERRED_AGENT__",
        ):
            self.assertNotIn(token, out, f"unreplaced placeholder: {token}")

    def test_job_row_rendering(self) -> None:
        job = {
            "id": "j1",
            "name": "Daily poke",
            "session": "s1",
            "agent": "claude",
            "schedule_label": "Daily 09:00",
            "enabled": True,
            "prompt": "hello world",
            "time": "09:00",
        }
        out = hub_server.hub_crons_html(
            jobs=[job],
            session_records=[{"name": "s1", "agents": ["claude"], "status": "active"}],
        )
        self.assertIn("Daily poke", out)
        self.assertIn("hello world", out)
        self.assertIn("Daily 09:00", out)
        self.assertIn('data-job-id="j1"', out)
        self.assertNotIn("No cron jobs yet.", out)

    def test_edit_form_prefill(self) -> None:
        job = {
            "id": "j2",
            "name": "Backup",
            "session": "s2",
            "agent": "codex",
            "schedule_label": "Daily 03:00",
            "enabled": False,
            "prompt": "run backup",
            "time": "03:00",
        }
        out = hub_server.hub_crons_html(
            jobs=[job],
            session_records=[{"name": "s2", "agents": ["codex"], "status": "active"}],
            edit_job=job,
        )
        self.assertIn("Edit Cron", out)
        self.assertIn("Backup", out)
        self.assertIn("run backup", out)
        self.assertIn('value="0"', out)  # form_enabled_value for disabled job

    def test_notice_html_rendering(self) -> None:
        out = hub_server.hub_crons_html(
            jobs=[],
            session_records=[],
            notice="Cron saved.",
        )
        self.assertIn("Cron saved.", out)
        self.assertIn('class="notice"', out)

    def test_stats_counts(self) -> None:
        jobs = [
            {"id": "a", "name": "j", "session": "s", "agent": "c", "schedule_label": "Daily", "enabled": True, "prompt": "x"},
            {"id": "b", "name": "j", "session": "s", "agent": "c", "schedule_label": "Daily", "enabled": False, "prompt": "x"},
            {"id": "c", "name": "j", "session": "s", "agent": "c", "schedule_label": "Daily", "enabled": True, "prompt": "x"},
        ]
        out = hub_server.hub_crons_html(jobs=jobs, session_records=[])
        # total=3, enabled=2, paused=1 appear as placeholder substitutes in the stats bar.
        # We assert the string forms appear at least once in the rendered HTML.
        self.assertIn(">3<", out)
        self.assertIn(">2<", out)
        self.assertIn(">1<", out)


if __name__ == "__main__":
    unittest.main()
