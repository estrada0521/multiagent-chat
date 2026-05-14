from pathlib import Path
import unittest


class NoCssImportantTest(unittest.TestCase):
    def test_repo_has_no_important_css_declarations(self):
        repo = Path(__file__).resolve().parents[1]
        banned = b"!" + b"important"
        ignored_dirs = {
            ".git",
            "__pycache__",
            ".multiagent-chat-diff",
            "logs",
            "logs-dev",
            "tauri_app/src-tauri/target",
            "tauri_app/src-tauri/gen",
        }
        offenders: list[str] = []
        for path in repo.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(repo).as_posix()
            if "__pycache__" in path.parts:
                continue
            if any(rel == item or rel.startswith(f"{item}/") for item in ignored_dirs):
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if banned in data:
                offenders.append(rel)
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
