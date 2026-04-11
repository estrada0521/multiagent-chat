import re

path = 'lib/agent_index/hub_core.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    (r'def repo_sessions\(self\):', r'def repo_sessions(self) -> list[dict]:'),
    (r'def archived_sessions\(self, active_names=None\):', r'def archived_sessions(self, active_names: set[str] | list[str] | None = None) -> list[dict]:'),
    (r'def archived_session_records\(self, active_names=None\) -> dict\[str, dict\]:', r'def archived_session_records(self, active_names: set[str] | list[str] | None = None) -> dict[str, dict]:'),
    (r'def session_agent_statuses\(self, session_name: str, agents: list\[str\]\):', r'def session_agent_statuses(self, session_name: str, agents: list[str]) -> dict[str, str]:'),
    (r'def compute_hub_stats\(self, active_sessions, archived_sessions_data\):', r'def compute_hub_stats(self, active_sessions: list[dict], archived_sessions_data: list[dict]) -> dict:'),
    (r'def load_hub_settings\(self\):', r'def load_hub_settings(self) -> dict:'),
    (r'def save_hub_settings\(self, raw\):', r'def save_hub_settings(self, raw: dict) -> dict:'),
    (r'def stop_chat_server\(self, session_name: str\):', r'def stop_chat_server(self, session_name: str) -> None:'),
    (r'def ensure_chat_server\(self, session_name: str\):', r'def ensure_chat_server(self, session_name: str) -> tuple[bool, int, str]:'),
    (r'def revive_archived_session\(self, session_name: str\):', r'def revive_archived_session(self, session_name: str) -> tuple[bool, str]:'),
    (r'def kill_repo_session\(self, session_name: str\):', r'def kill_repo_session(self, session_name: str) -> tuple[bool, str]:'),
    (r'def delete_archived_session\(self, session_name: str\):', r'def delete_archived_session(self, session_name: str) -> tuple[bool, str]:'),
]

for old, new in replacements:
    content = re.sub(old, new, content, count=1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
