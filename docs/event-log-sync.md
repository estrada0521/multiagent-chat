# Event Log Sync 詳説

英語版: [docs/event-log-sync.en.md](event-log-sync.en.md)

この文書は、provider の native log が `logs/<session>/.agent-index.jsonl` に同期される仕組みと、instance 間で claim がどう移るかを実装寄りにまとめたものです。

## 1. 同期ループの全体像

chat server は JSONL 同期専用のスレッド（`_periodic_jsonl_sync`）を約 1 秒間隔で回します。各 tick で行うことは次の通りです。

1. session が inactive ならスキップ
2. `.agent-index-sync.lock` を non-blocking flock で取得（同一 session の多重同期を防止）
3. active agent 一覧を読み、`first_seen` を初期化
4. 削除済み agent の stale claim を prune し、recent target に基づく handoff を適用
5. provider ごとに native log/DB を解決して `_sync_*` を実行
6. `.agent-index-sync-state.json` を heartbeat 保存

この同期はブラウザ polling と独立しているため、chat タブを開いていなくても JSONL 追記は進みます。

## 2. cursor と claim のモデル

`ChatRuntime` は `logs/<session>/.agent-index-sync-state.json` に同期状態を保存します。

- file 系 provider: `NativeLogCursor(path, offset)`
- OpenCode: `OpenCodeCursor(session_id, last_msg_id)`
- `agent_first_seen_ts`

重要ルール:

- **path 束縛 cursor:** path が切り替わったら新 path の末尾へ anchor し、古い履歴を再読しない
- **first-seen gate:** 新規 bind 時に古い mtime の file を掴みにくくする
- **bind backfill window:** bind 直後は短い時間窓（約 45 秒）を再走査して初回返信取りこぼしを防ぐ
- **global claim guard:** 他 session の active claim を TTL 付きで参照し、同じ native path の二重 claim を抑制
- **inode ベース比較:** path 文字列ではなく file identity 優先で比較（alias path 問題を軽減）
- **msg_id preload dedup:** 再起動時に既存 JSONL の `msg_id` を preload して重複追記を防ぐ

## 3. Provider ごとの取り込み

| Provider | 主な source | 取り込みの要点 |
| --- | --- | --- |
| Claude | `~/.claude/projects/-<slug>/*.jsonl` | workspace hint + slug variant、慎重な git-root fallback、bind backfill |
| Codex | `~/.codex/sessions/**/rollout-*.jsonl` | `session_meta.cwd` で workspace 一致、reasoning/event 取り込み |
| Cursor | `~/.cursor/projects/.../*.jsonl` と `~/.cursor/chats/<workspace-md5>/*/store.db` | JSONL + SQLite 両対応、store.db 初回 bind は baseline seed |
| Copilot | active state 配下の `events.jsonl` | `assistant.message` のみ取り込み |
| Qwen | `~/.qwen/projects/-<slug>/chats/*.jsonl` | `thought` part 判定、同 base 複数時の strict first-bind |
| Gemini | `~/.gemini/tmp/<workspace>/chats/session-*.json` | file rewrite 型（変更時は全 JSON 再parse） |
| OpenCode | `~/.local/share/opencode/opencode.db` | SQLite `session/message/part` を session claim で管理 |

### Claude

- pane workspace hint を優先しつつ、slug variant（raw / underscore->hyphen / sanitize）を探索
- git-root fallback は遅延 + 条件付きで誤 bind を抑制
- bind 直後に backfill window を維持して初回返信の取りこぼしを回収

### Codex

- `response_item` / `event_msg` を取り込み
- `reasoning` と `agent_reasoning` は `kind="agent-thinking"` で保存
- bind 直後に recent scan を実施

### Cursor

- JSONL transcript と `store.db` を両方扱う
- `store.db` 初回 bind 時は既存行を「既読 baseline」として `msg_id` だけ seed し、履歴の一括 flood を防止

### Copilot

- `assistant.message` の `content` を取り込み
- `messageId` / event id を dedup key に利用

### Qwen

- assistant `message.parts` から text を抽出
- `thought=true` のみなら `kind="agent-thinking"` を付与
- 同 base 複数 instance がいる場合は strict first-bind モードを使う

### Gemini

- Gemini 側は session JSON を都度書き換えるため、offset は「変更検知」に使い、変更時は全体再parse
- 空プレースホルダは skip して次 tick で再評価
- thought part または planning 形式（`I will ...` など）で `kind="agent-thinking"` を付与

### OpenCode

- workspace に一致する session のうち、他 instance に claim されていない最新 session を選ぶ
- file offset ではなく `session_id + last_msg_id` で進捗管理
- session 切替時は first-seen/backfill 境界で旧履歴の全再生を抑える

## 4. claim drift を抑える仕組み

provider 同期の前に次の 2 つを適用します。

1. **`prune_sync_claims_to_active_agents(...)`**  
   remove-agent 後に残る stale claim を削除し、`claude` <-> `claude-1` のような alias 移行も補正
2. **`apply_recent_targeted_claim_handoffs(...)`**  
   recent single-target 送信を見て、同 base 共有 claim を明示 target instance へ handoff

これにより add/remove/restart 後の attribution drift を抑えます。

## 5. thinking 種別の扱い

`agent-thinking` は 2 経路で入ります。

- provider 側の型情報（reasoning / thought part など）を同期時に保存
- 既存 entry に `kind` がない場合、read-time 推定で planning 文（`I will ...`）を thinking 扱いにする

後者は JSONL を書き換えず表示時に補う方式です。

## 6. Sync Status が空/ずれるときの確認

1. 対象 session の chat server が active か
2. `logs/<session>/.agent-index-sync-state.json` の cursor / `agent_first_seen_ts`
3. 同じ native path を他 active session が claim していないか
4. workspace hint（特に Claude/Cursor/Qwen/Gemini の path 解決）
5. 明示 target 送信が必要なケースで handoff が発火しているか

主な確認対象:

- `logs/<session>/.agent-index.jsonl`
- `logs/<session>/.agent-index-sync-state.json`
- `logs/<session>/.agent-index-sync.lock`

## 7. 新しい provider を追加するとき

1. `chat_sync_providers_core.py`（必要に応じて `chat_sync_providers_qwen_gemini_core.py` のような分割 provider モジュール）に `sync_<provider>_assistant_messages(...)` adapter を追加し、`chat_core.py` では薄い `_sync_<provider>_assistant_messages(...)` wrapper を接続
2. cursor/claim モデル（file cursor or logical cursor）を定義
3. `chat_server.py` の `_periodic_jsonl_sync` dispatch に組み込む
4. `tests/test_sync_cursors.py` に bind/rebind/stale-claim/dedup/backfill の回帰を追加
5. runtime hint を出す場合は軽量・非ブロッキングを維持
