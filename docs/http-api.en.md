# HTTP API Reference (Hub + Chat)

This document summarizes the HTTP routes currently implemented in:

- `lib/agent_index/hub_server.py`
- `lib/agent_index/chat_server.py`

The APIs are local-first and are primarily consumed by the Hub and chat UI frontends.

## 1. Base URLs

- **Hub server**: `http(s)://<host>:<hub_port>/`
- **Chat server** (direct): `http(s)://<host>:<chat_port>/`
- **Chat via Hub proxy**: `http(s)://<host>:<hub_port>/session/<session_name>/...`

`/session/<session_name>/...` on Hub transparently proxies to that session's chat server.

## 2. Common behavior

- Most JSON endpoints return `application/json; charset=utf-8`.
- Most JSON responses include `{"ok": true|false, ...}` on mutating APIs.
- Errors typically use:
  - `400` for validation errors / invalid JSON
  - `403` for forbidden file access
  - `404` for missing resources
  - `500` for runtime failures
- There is no built-in auth layer in these handlers; treat them as trusted local surfaces.

## 3. Hub API

### GET routes

| Path | Purpose | Request shape | Response |
|---|---|---|---|
| `/sessions` | Active/archived session lists | Query: none | `{ sessions, active_sessions, archived_sessions, tmux_state, tmux_detail }` |
| `/open-session` | Ensure chat server and return/open chat URL | Query: `session`, optional `format=json` | JSON `{ ok, chat_url, session_record }` or `302` redirect |
| `/revive-session` | Revive archived session then open chat | Query: `session`, optional `format=json` | JSON `{ ok, chat_url, session_record }` or `302` redirect |
| `/kill-session` | Kill active session | Query: `session` | `302 /` on success |
| `/delete-archived-session` | Delete archived session logs/metadata | Query: `session` | `302 /` on success |
| `/dirs` | Directory browser data for New Session UI | Query: optional `path` | `{ path, parent, home, entries[] }` |
| `/push-config` | Browser notification config | Query: none | `{ enabled, public_key }` |
| `/notify-sound` | OGG sound preview | Query: optional `name` | OGG bytes or `404` |
| `/hub-logo` | Hub logo asset | Query: none | `image/webp` or `404` |
| `/hub.webmanifest` | Hub PWA manifest | Query: none | Manifest JSON |
| `/` `/index.html` | Hub home page | Query: none | HTML |
| `/settings` | Settings page | Query: optional `saved=1` | HTML |
| `/new-session` | New Session page | Query: none | HTML |
| `/session/<session>/...` | Proxy to chat server GET route | Path + query forwarded | Upstream chat response |

### POST routes

| Path | Purpose | Request shape | Response |
|---|---|---|---|
| `/restart-hub` | Queue hub restart | Body: none | `{ ok: true }` |
| `/start-session` | Create detached session from UI selections | JSON `{ workspace, session_name?, agents[] }` | `{ ok, session, chat_url, session_record }` |
| `/mkdir` | Create directory for workspace picker | JSON `{ path }` | `{ ok, path }` |
| `/settings` | Save hub settings | Form data | `302 /settings?saved=1` |
| `/push/subscribe` | Register hub push subscription | JSON `{ subscription, client_id?, user_agent?, hidden? }` | `{ ok, ... }` |
| `/push/unsubscribe` | Remove hub push subscription | JSON `{ endpoint }` | `{ ok, removed }` |
| `/push/presence` | Update hub client presence | JSON `{ client_id, visible?, focused?, endpoint? }` | `{ ok }` |
| `/session/<session>/...` | Proxy to chat server POST route | Body + headers forwarded | Upstream chat response |

## 4. Chat API

### GET routes

| Path | Purpose | Request shape | Response |
|---|---|---|---|
| `/messages` | Timeline payload (main polling API) | Query: `limit?`, `before_msg_id?`, `around_msg_id?`, `light=1?` | Chat payload JSON |
| `/message-entry` | Single message by ID | Query: `msg_id`, optional `light=1` | `{ entry }` or `404` |
| `/normalized-events` | Normalized event list for message | Query: `msg_id` | JSON or `404` |
| `/session-state` | Runtime/session/agent state snapshot | Query: none | `{ server_instance, session, active, targets, statuses, ... }` |
| `/sync-status` | Native-log cursor/claim sync state | Query: none | Sync status JSON |
| `/agents` | Current target agent statuses | Query: none | Agent status JSON |
| `/trace` | Pane trace tail for agent | Query: `agent`, optional `lines` or `tail` | `{ content }` |
| `/pane-trace-popup` | Pane trace popup HTML | Query: `agent?`, `agents?`, `bg?`, `text?` | HTML |
| `/files` | Referenced file list | Query: none | File list JSON |
| `/file-content` | Text/metadata view for file | Query: `path` | JSON or `403/404` |
| `/file-view` | Rendered file preview page | Query: `path`, optional `embed=1` | HTML or `403/404` |
| `/file-openability` | Editor-openable check | Query: `path` | `{ editable: bool }` |
| `/file-raw` | Raw file bytes with Range support | Query: `path`, header `Range?` | Raw bytes / `206` / `416` |
| `/memory-path` | Memory file info for agent | Query: `agent?` | `{ path, history_path, content }` |
| `/git-branch-overview` | Branch/commit overview | Query: `offset?`, `limit?` | JSON |
| `/git-diff` | Diff for HEAD or commit | Query: `hash?` | `{ diff }` |
| `/export` | Session HTML export download | Query: `limit?` | HTML attachment |
| `/hub-settings` | Chat-facing settings projection | Query: none | JSON settings |
| `/push-config` | Chat push config | Query: none | `{ enabled, public_key }` |
| `/caffeinate` | Awake status | Query: none | Caffeinate status JSON |
| `/auto-mode` | Auto mode status | Query: none | Auto mode status JSON |
| `/notify-sounds` | Notification sound choices (shuffled subset) | Query: none | JSON filename list |
| `/notify-sounds-all` | All notification sound files | Query: none | JSON filename list |
| `/notify-sound` | Fetch one OGG file | Query: `name?` | OGG bytes or `404` |
| `/icon/<name>` | Agent icon asset | Path param | SVG or `404` |
| `/font/<name>` | Font asset | Path param | TTF or `404` |
| `/hub-logo` | Hub logo asset | Query: none | `image/webp` or `404` |
| `/chat-assets/chat-app.js` | Chat JS bundle | Query: none | JS |
| `/chat-assets/chat-app.css` | Chat CSS bundle | Query: none | CSS |
| `/app.webmanifest` | Chat PWA manifest | Query: none | Manifest JSON |
| `/` `/index.html` | Chat page | Query: optional `follow=1` | HTML |

### POST routes

| Path | Purpose | Request shape | Response |
|---|---|---|---|
| `/send` | Send chat message | JSON `{ target, message, reply_to?, silent?, raw? }` | `{ ok, ... }` |
| `/new-chat` | Queue chat server restart | Body: none | `{ ok, restarting, detail, port }` |
| `/add-agent` | Add agent instance to session | JSON `{ agent }` | `{ ok, agent, message, targets }` |
| `/remove-agent` | Remove agent instance from session | JSON `{ agent }` | `{ ok, agent, message, targets }` |
| `/log-system` | Append system timeline entry | JSON `{ message }` | `{ ok }` |
| `/memory-snapshot` | Persist memory snapshot for agent | JSON `{ agent, reason? }` | `{ ok, ...snapshot metadata }` |
| `/save-logs` | Persist session logs | Query: `reason?` | Runtime save result JSON |
| `/upload` | Upload binary/blob into session uploads | Headers: `Content-Type`, `X-Filename`; raw body | `{ ok, path }` |
| `/rename-upload` | Rename uploaded file label | JSON `{ path, label }` | `{ ok, path }` |
| `/open-terminal` | Open macOS Terminal attached to tmux session | Body: none | `{ ok }` |
| `/open-finder` | Open workspace in Finder | Body: none | `{ ok, path }` |
| `/files-exist` | Existence check for path list | JSON `{ paths: [...] }` | Existence map JSON |
| `/open-file-in-editor` | Open file in editor integration | JSON `{ path, line? }` | `{ ok, ... }` |
| `/git-commit-file` | Commit one file | JSON `{ path, message, agent? }` | Git result JSON |
| `/git-commit-all` | Commit all staged/working changes | JSON `{ message, agent? }` | Git result JSON |
| `/git-restore-file` | Restore file from git | JSON `{ path }` | Git result JSON |
| `/caffeinate` | Toggle Awake | Body: none | Toggle result JSON |
| `/auto-mode` | Toggle Auto mode | Body: none | `{ ok, active }` |
| `/push/subscribe` | Register chat push subscription | JSON `{ subscription, client_id?, user_agent?, hidden? }` | `{ ok, ... }` |
| `/push/unsubscribe` | Remove chat push subscription | JSON `{ endpoint }` | `{ ok, removed }` |
| `/push/presence` | Update chat client presence | JSON `{ client_id, visible?, focused?, endpoint? }` | `{ ok }` |

## 5. Notes for contributors

- Route handling is currently explicit `if parsed.path == ...` dispatch.
- Hub-level `/session/<session>/...` proxying is implemented in `_proxy_session_request`.
- When adding a route, keep behavior mirrored for both direct chat port access and hub-proxied access.
