# HTTP API リファレンス（Hub + Chat）

この文書は、現在の HTTP ルートを次の実装に基づいて整理したものです。

- `lib/agent_index/hub_server.py`
- `lib/agent_index/chat_server.py`

## 1. ベースURL

- **Hub**: `http(s)://<host>:<hub_port>/`
- **Chat 直アクセス**: `http(s)://<host>:<chat_port>/`
- **Hub 経由 Chat**: `http(s)://<host>:<hub_port>/session/<session_name>/...`

Hub の `/session/<session_name>/...` は対象 session の chat server へ透過プロキシします。

## 2. 共通仕様

- JSON API は基本 `application/json; charset=utf-8` を返します。
- 変更系 API は `{"ok": true|false, ...}` 形式が中心です。
- 主なエラーコード:
  - `400`: 入力不正 / invalid json
  - `403`: file access 禁止
  - `404`: 対象なし
  - `500`: 実行時エラー
- サーバ側ハンドラ自体には認証層がないため、基本は trusted local/LAN 環境で使い、外部公開するなら外側でアクセス制御してください。

## 3. Hub API

### GET

| Path | 用途 | 入力 | 出力 |
|---|---|---|---|
| `/sessions` | active/archived 一覧 + 統計 | なし | `{ sessions, active_sessions, archived_sessions, stats, tmux_state, tmux_detail }` |
| `/open-session` | chat server 起動確認 + URL返却 | `session`, `format=json?` | JSON or `302` |
| `/revive-session` | archived 復帰 + chat URL返却 | `session`, `format=json?` | JSON or `302` |
| `/kill-session` | active session 停止 | `session` | 成功時 `302 /` |
| `/delete-archived-session` | archived session 削除 | `session` | 成功時 `302 /` |
| `/dirs` | New Session 用ディレクトリ一覧 | `path?` | `{ path, parent, home, entries[] }` |
| `/push-config` | push 設定取得 | なし | `{ enabled, public_key }` |
| `/notify-sound` | 通知音 OGG | `name?` | OGG / `404` |
| `/hub-logo` | Hub ロゴ | なし | `image/webp` |
| `/hub.webmanifest` | Hub PWA manifest | なし | Manifest JSON |
| `/` `/index.html` | Hub top | なし | HTML |
| `/resume` | Resume 画面 | なし | HTML |
| `/stats` | Stats 画面 | なし | HTML |
| `/crons` | Cron 管理画面 | `edit?`, `notice?`, `session?`, `agent?` | HTML |
| `/settings` | Settings 画面 | `saved?` | HTML |
| `/new-session` | New Session 画面 | なし | HTML |
| `/session/<session>/...` | chat server への GET プロキシ | path/query | upstream 応答 |

### POST

| Path | 用途 | 入力 | 出力 |
|---|---|---|---|
| `/restart-hub` | Hub 再起動キュー | なし | `{ ok: true }` |
| `/start-session` | UI 経由で新規 session 起動 | JSON `{ workspace, session_name?, agents[] }` | `{ ok, session, chat_url, session_record }` |
| `/mkdir` | ディレクトリ作成 | JSON `{ path }` | `{ ok, path }` |
| `/settings` | Hub 設定保存 | form | `302 /settings?saved=1` |
| `/crons/save` | Cron 保存 | form (`id?`, `name`, `time`, `session`, `agent`, `prompt`, `enabled`) | `/crons` へ redirect |
| `/crons/delete` | Cron 削除 | form `{ id }` | `/crons` へ redirect |
| `/crons/toggle` | Cron 有効/無効 | form `{ id, enabled }` | `/crons` へ redirect |
| `/crons/run` | Cron 即時実行 | form `{ id }` | `/crons` へ redirect |
| `/push/subscribe` | Hub push 登録 | JSON `{ subscription, client_id?, user_agent?, hidden? }` | `{ ok, ... }` |
| `/push/unsubscribe` | Hub push 解除 | JSON `{ endpoint }` | `{ ok, removed }` |
| `/push/presence` | Hub push presence 更新 | JSON `{ client_id, visible?, focused?, endpoint? }` | `{ ok }` |
| `/session/<session>/...` | chat server への POST プロキシ | body/headers | upstream 応答 |

## 4. Chat API

### GET

| Path | 用途 | 入力 | 出力 |
|---|---|---|---|
| `/messages` | メインタイムライン取得 | `limit?`, `before_msg_id?`, `around_msg_id?`, `light=1?` | chat payload JSON |
| `/message-entry` | 単一メッセージ取得 | `msg_id`, `light=1?` | `{ entry }` |
| `/normalized-events` | メッセージ正規化イベント取得 | `msg_id` | JSON |
| `/session-state` | session/agent runtime 状態 | なし | `{ server_instance, session, active, targets, statuses, ... }` |
| `/sync-status` | native-log 同期カーソル状態 | なし | JSON |
| `/agents` | target agent 状態 | なし | JSON |
| `/trace` | pane trace 取得 | `agent`, `lines?` or `tail?` | `{ content }` |
| `/pane-trace-popup` | Pane Trace popup HTML | `agent?`, `agents?`, `bg?`, `text?` | HTML |
| `/files` | 参照ファイル一覧 | なし | JSON |
| `/file-content` | ファイル内容 JSON | `path` | JSON |
| `/file-view` | ファイル preview HTML | `path`, `embed=1?` | HTML |
| `/file-openability` | エディタで開けるか判定 | `path` | `{ editable }` |
| `/file-raw` | Raw bytes（Range 対応） | `path`, `Range?` | bytes / `206` / `416` |
| `/memory-path` | memory.md 情報 | `agent?` | `{ path, history_path, content }` |
| `/git-branch-overview` | branch/commit 概要 | `offset?`, `limit?` | JSON |
| `/git-diff` | diff 取得 | `hash?` | `{ diff }` |
| `/export` | 静的HTML export | `limit?` | HTML attachment |
| `/hub-settings` | chat で使う設定取得 | なし | JSON |
| `/push-config` | push 設定取得 | なし | `{ enabled, public_key }` |
| `/caffeinate` | Awake 状態 | なし | JSON |
| `/auto-mode` | Auto mode 状態 | なし | JSON |
| `/notify-sounds` | 通知音候補 | なし | filename 配列 |
| `/notify-sounds-all` | 通知音全件 | なし | filename 配列 |
| `/notify-sound` | 通知音ファイル | `name?` | OGG |
| `/icon/<name>` | アイコン配信 | path | SVG |
| `/font/<name>` | フォント配信 | path | TTF |
| `/hub-logo` | Hub ロゴ配信 | なし | WEBP |
| `/chat-assets/chat-app.js` | chat JS | なし | JS |
| `/chat-assets/chat-app.css` | chat CSS | なし | CSS |
| `/app.webmanifest` | chat PWA manifest | なし | Manifest JSON |
| `/` `/index.html` | chat 本体ページ | `follow=1?` | HTML |

### POST

| Path | 用途 | 入力 | 出力 |
|---|---|---|---|
| `/send` | メッセージ送信 | JSON `{ target, message, reply_to?, silent?, raw? }` | `{ ok, ... }` |
| `/new-chat` | chat server 再起動キュー | なし | `{ ok, restarting, detail, port }` |
| `/add-agent` | agent instance 追加 | JSON `{ agent }` | `{ ok, agent, message, targets }` |
| `/remove-agent` | agent instance 削除 | JSON `{ agent }` | `{ ok, agent, message, targets }` |
| `/log-system` | system timeline 追記 | JSON `{ message }` | `{ ok }` |
| `/memory-snapshot` | memory snapshot 保存 | JSON `{ agent, reason? }` | `{ ok, ... }` |
| `/save-logs` | session log 保存 | query `reason?` | save result JSON |
| `/upload` | uploads 保存 | headers `Content-Type`, `X-Filename`; raw body | `{ ok, path }` |
| `/rename-upload` | upload ファイル名変更 | JSON `{ path, label }` | `{ ok, path }` |
| `/open-terminal` | macOS Terminal を tmux attach で起動 | なし | `{ ok }` |
| `/open-finder` | workspace を Finder で開く | なし | `{ ok, path }` |
| `/files-exist` | 複数 path 存在確認 | JSON `{ paths: [...] }` | 存在判定 JSON |
| `/open-file-in-editor` | エディタでファイルを開く | JSON `{ path, line? }` | `{ ok, ... }` |
| `/git-commit-file` | 単一ファイル commit | JSON `{ path, message, agent? }` | Git 結果 JSON |
| `/git-commit-all` | 全体 commit | JSON `{ message, agent? }` | Git 結果 JSON |
| `/git-restore-file` | ファイル restore | JSON `{ path }` | Git 結果 JSON |
| `/caffeinate` | Awake トグル | なし | toggle 結果 JSON |
| `/auto-mode` | Auto mode トグル | なし | `{ ok, active }` |
| `/push/subscribe` | chat push 登録 | JSON `{ subscription, client_id?, user_agent?, hidden? }` | `{ ok, ... }` |
| `/push/unsubscribe` | chat push 解除 | JSON `{ endpoint }` | `{ ok, removed }` |
| `/push/presence` | chat push presence 更新 | JSON `{ client_id, visible?, focused?, endpoint? }` | `{ ok }` |

## 5. 実装メモ

- ルーティングは `if parsed.path == ...` で明示的に分岐しています。
- Hub の `/session/<session>/...` は `_proxy_session_request` で chat server へ転送します。
- 新しい chat API を足す場合は、直アクセスと Hub 経由アクセスの両方で動く前提で追加してください。
