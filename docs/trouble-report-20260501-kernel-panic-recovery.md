# トラブルレポート: macOS カーネルパニック後の multiagent セッション復旧

- **日時**: 2026-05-01
- **影響**: multiagent-local / multiagent-cloudflare / multiagent-cloudflare-edge セッション全滅

---

## 発生した事象

`backend_core` 移行作業中に macOS がカーネルパニックを起こし強制再起動。
tmux セッション 3 つ（multiagent-local, multiagent-cloudflare, multiagent-cloudflare-edge）が全て Archived 状態になった。
Revive を試みたが Hub の UI が loading のまま進まず、チャットサーバーが起動しなかった。

### カーネルパニックの概要

```
panic(cpu 2 caller 0xfffffe00420f0084):
  os_refcnt: overflow (count=268435456, max=268435455) @refcnt.c:68
Panicked task: pid 652: syspolicyd
OS version: 25E253 (Darwin 25.4.0 / macOS Sequoia 15.4)
```

- **原因**: `syspolicyd`（Gatekeeper / XProtect）内部の参照カウントがオーバーフロー
- **誘因**: 大量ファイルの書き込み・インストールによる Gatekeeper の並列検証処理が集中
- **判定**: macOS カーネル側のバグ。ユーザーコードの問題ではない

---

## 復旧作業

### 1. 起動スクリプトの import パス修正

`backend_core` Phase 3 移行でモジュールが移動されていたが、
`ops/multiagent/multiagent` のインライン Python が旧パスのままだった。

#### 修正① `local_runtime_log_dir` のインポート先変更

- **ファイル**: `ops/multiagent/multiagent` (旧 L53)
- **変更前**: `from multiagent_chat.runtime.state import local_runtime_log_dir`
- **変更後**: `from backend_core.access.settings import local_runtime_log_dir`
- `sys.path.insert(0, str(repo_root))` も追加（`backend_core` はリポジトリルート直下のため）

**移行の背景**: commit `8d678dd` で `src/multiagent_chat/runtime/state.py` → `backend_core/access/settings.py` にリネーム。

#### 修正② `multiagent_chat.multiagent.tmux` のインポート先変更（9箇所）

- **ファイル**: `ops/multiagent/multiagent`
- **変更前**: `from multiagent_chat.multiagent.tmux import <func>`
- **変更後**: `from backend_core.tmux.window import <func>`
- 各 heredoc に `sys.path.insert(0, str(repo_root))` も追加

**移行の背景**: commit `351c33b` で `src/multiagent_chat/multiagent/tmux.py` → `backend_core/tmux/window.py` にリネーム。

対象関数（全9件）:
`retile_session_preserving_user_panes`, `create_user_pane_band`, `window_target_for_pane`,
`configure_window_size`, `create_agent_window`, `split_agent_pane`,
`configure_agent_pane_defaults`, `kill_window_target`, `kill_pane_target`

### 2. `native_log_sync` の未対応エージェントによるクラッシュ修正

チャットサーバー起動時に `ModuleNotFoundError: No module named 'native_log_sync.agents.kimi'` が発生。

- **ファイル**: `native_log_sync/agents/__init__.py`
- **原因**: `kimi` がエージェントレジストリに追加されたが `native_log_sync/agents/kimi/` が未作成
- **修正**: `_agent_module()` に `ModuleNotFoundError` の try/except を追加し `None` を返すよう変更。
  `resolve_binding` / `load_idle_events` でも `None` チェックを追加。

```python
# 修正後
def _agent_module(agent: str):
    base = str(agent or "").strip().lower().split("-", 1)[0]
    try:
        return import_module(f"native_log_sync.agents.{base}")
    except ModuleNotFoundError:
        return None
```

### 3. エージェントペインの手動復旧

tmux セッション自体は起動できたが、再起動後の Revive では各ウィンドウにエージェントプロセスが存在しなかった。
Hub UI から全エージェントを手動で Remove → Add しなおすことで復旧。

---

## 根本原因の整理

| # | 問題 | 原因 | カテゴリ |
|---|------|------|----------|
| 1 | 起動スクリプトが旧モジュールパスを参照 | `backend_core` 移行時に `ops/` の更新が漏れた | 移行漏れ |
| 2 | `kimi` エージェントが `native_log_sync` を持たずクラッシュ | 新エージェント追加時のスタブ未作成 | 新機能追加漏れ |
| 3 | 再起動後にエージェントプロセスが存在しない | tmux セッション再生成でプロセスが空 | Revive の既知の制限 |

---

## 再発防止メモ

- `backend_core` への移行作業時は `ops/multiagent/multiagent` 内のインライン Python も必ず確認する
- 新エージェントをレジストリに追加する際は `native_log_sync/agents/<agent>/` スタブを同時に作成する（または `__init__.py` の `None` ハンドリングで吸収済みのため動作は継続するが、idle/runtime イベントは取得されない）
- macOS でファイルを大量書き込みする前は Time Machine 除外を設定しておくと Gatekeeper の負荷を軽減できる可能性がある
