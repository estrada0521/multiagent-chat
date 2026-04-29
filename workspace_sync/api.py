from __future__ import annotations

import threading
import time
from pathlib import Path

from multiagent_chat.files.runtime import FileRuntime
from . import git as workspace_git
from .watch import start_workspace_fsevents_watcher


class WorkspaceSyncApi:
    def __init__(
        self,
        *,
        workspace: str | Path,
        allowed_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
        repo_root: str | Path,
        index_path: str | Path,
        runtime,
    ) -> None:
        self.workspace = str(workspace)
        self.repo_root = Path(repo_root).resolve()
        self.index_path = Path(index_path)
        self.runtime = runtime
        self._sync_event_condition = threading.Condition()
        self._sync_event_seq = 0
        self._git_cache_version = 0
        self.file_runtime = FileRuntime(
            workspace=workspace,
            allowed_roots=allowed_roots,
            repo_root=repo_root,
        )
        workspace_git.configure(
            workspace=self.workspace,
            repo_root=self.repo_root,
            index_path=self.index_path,
            runtime=runtime,
        )
        try:
            self.file_runtime.refresh_file_list_cache()
        except Exception:
            pass
        start_workspace_fsevents_watcher(self)

    def raw_response_metadata(self, rel: str, range_header: str = "") -> dict:
        return self.file_runtime.raw_response_metadata(rel, range_header)

    def stream_raw_response(self, metadata: dict, write) -> None:
        self.file_runtime.stream_raw_response(metadata, write)

    def file_content(self, rel: str):
        return self.file_runtime.file_content(rel)

    def openability(self, rel: str) -> dict[str, str | bool | None]:
        return self.file_runtime.openability(rel)

    def file_view(self, rel: str, **kwargs):
        return self.file_runtime.file_view(rel, **kwargs)

    def list_files(self, *, force_refresh: bool = False):
        return self.file_runtime.list_files(force_refresh=force_refresh)

    def refresh_file_index_cache(self):
        return self.file_runtime.refresh_file_list_cache()

    def invalidate_git_cache(self) -> None:
        workspace_git.invalidate_branch_overview_cache()
        with self._sync_event_condition:
            self._git_cache_version += 1

    def _workspace_sync_state_locked(self) -> dict[str, int | float]:
        file_state = self.file_runtime.file_list_cache_state()
        return {
            "seq": int(self._sync_event_seq),
            "file_version": int(file_state.get("version") or 0),
            "git_version": int(self._git_cache_version),
            "updated_at": float(file_state.get("updated_at") or 0.0),
        }

    def workspace_sync_state(self) -> dict[str, int | float]:
        with self._sync_event_condition:
            return self._workspace_sync_state_locked()

    def publish_sync_event(self) -> dict[str, int | float]:
        with self._sync_event_condition:
            self._sync_event_seq += 1
            state = self._workspace_sync_state_locked()
            state["published_at"] = time.time()
            self._sync_event_condition.notify_all()
            return state

    def wait_for_sync_event(self, after_seq: int, timeout: float = 15.0) -> dict[str, int | float] | None:
        deadline = time.monotonic() + max(0.1, float(timeout or 15.0))
        with self._sync_event_condition:
            while self._sync_event_seq <= int(after_seq):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._sync_event_condition.wait(timeout=remaining)
            state = self._workspace_sync_state_locked()
            state["published_at"] = time.time()
            return state

    def search_files(self, query: str = "", limit: int = 60, *, force_refresh: bool = False):
        return self.file_runtime.search_files(query, limit=limit, force_refresh=force_refresh)

    def resolve_file_references(self, queries: list[str]) -> dict[str, str]:
        return self.file_runtime.resolve_file_references(queries)

    def list_dir(self, rel: str = ""):
        return self.file_runtime.list_dir(rel)

    def files_exist(self, paths: list[str]) -> dict[str, bool]:
        return self.file_runtime.files_exist(paths)

    def open_in_editor(self, rel: str, line: int = 0, *, allow_native_log_home: bool = False):
        return self.file_runtime.open_in_editor(rel, line=line, allow_native_log_home=allow_native_log_home)

    def open_diff_in_editor(self, rel: str, *, commit_hash: str = ""):
        return self.file_runtime.open_diff_in_editor(rel, commit_hash=commit_hash)

    def git_branch_overview(self, *, offset=0, limit=50, force_refresh: bool = False):
        return workspace_git.git_branch_overview(offset=offset, limit=limit, force_refresh=force_refresh)

    def git_diff_files(self, *, commit_hash: str = ""):
        return workspace_git.git_diff_files(commit_hash=commit_hash)

    def git_restore_file(self, *, rel_path: str):
        return workspace_git.git_restore_file(rel_path=rel_path)
