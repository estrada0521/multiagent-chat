from __future__ import annotations

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

    def search_files(self, query: str = "", limit: int = 60, *, force_refresh: bool = False):
        return self.file_runtime.search_files(query, limit=limit, force_refresh=force_refresh)

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
