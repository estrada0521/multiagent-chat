# multiagent-chat 技術詳細

英語版: [docs/technical-details.en.md](technical-details.en.md)

この文書は、[README.md](../README.md) で説明している機能を、実装側の構成とデータフローに寄せて説明するためのものです。ユーザー向けの使い方ではなく、`bin/` と `lib/agent_index/` が何を担当し、session・message・log がどのように流れるかをまとめています。

## 0. 実装の見取り図

`multiagent-chat` の主要な責務は、session の作成、message の配送、Hub / chat UI の配信、file / log / export の補助に分かれています。

| ファイル | 役割 |
|------|------|
| `bin/multiagent` | tmux session 作成、agent pane 配置、agent 追加 / 削除、pane log 保存 |
| `bin/agent-send` | `user` / agent / `others` への message 配送、`msg-id` と `reply-to` の付与、JSONL 追記 |
| `bin/agent-index` | Hub、chat UI、Stats、Settings、upload / trace / export などの HTTP endpoint |
| `lib/agent_index/chat_core.py` | chat server の runtime、message payload、pane status、trace、save log |
| `lib/agent_index/chat_assets.py` | chat UI の HTML / CSS / JavaScript、composer、brief / memory、Pane Trace |
| `lib/agent_index/hub_core.py` | active / archived session の収集、Hub preview、Stats 集計 |
| `lib/agent_index/file_core.py` | file preview、raw file 配信、external editor 起動 |
| `lib/agent_index/export_core.py` | static HTML export 生成 |
| `lib/agent_index/state_core.py` | Hub settings、chat port、thinking time の永続化 |
| `lib/agent_index/agent_registry.py` | 対応 agent CLI 一覧、起動 / resume 設定、icon 情報 |

現在の session ごとの保存レイアウトは次のようになります。

```text
logs/<session>/
  .agent-index.jsonl
  .agent-index-commit-state.json
  .meta
  *.ans
  *.log
  uploads/
  brief/
    brief_<name>.md
  memory/
    <agent>/
      memory.md
      memory.jsonl
```

これに加えて、repo 共有ではない状態は `state_core.py` 経由でローカル state directory に保存されます。macOS では `~/Library/Application Support/multiagent/<repo-hash>/`、Linux では `$XDG_STATE_HOME/multiagent/<repo-hash>/` が基準です。

## 1. New Session / Message Body

`bin/multiagent` は tmux session を作成し、workspace、log directory、tmux socket、pane ID、agent 一覧を `MULTIAGENT_*` 環境変数として session に書き込みます。同じ base agent が複数回指定された場合は、`claude-1`、`claude-2` のように instance suffix を付けて pane 変数を一意にします。`multiagent add-agent` と `multiagent remove-agent` もこのレイヤの操作です。

chat UI は `bin/agent-index` から session ごとに配信され、`ChatRuntime.payload()` が `session`、`workspace`、`port`、`targets`、`entries` をまとめた JSON を返します。message body 側は `chat_assets.py` でこの payload を描画し、`sender`、`targets`、`msg-id`、`reply-to`、`reply_preview` を bubble の下部メタ情報へ展開します。KaTeX と Mermaid の render も同じ front-end で行います。

### `agent-send`

`agent-send` はこの環境の message transport です。message を pane に直接打ち込むだけではなく、同じ内容を `.agent-index.jsonl` に構造化して保存します。これにより、user-to-agent、agent-to-user、agent-to-agent のすべてが同一形式の log になります。

session の解決順は `MULTIAGENT_SESSION`、現在の tmux session、workspace に対して一意に見つかる active session、最後に起動時 state file です。target は `user`、`others`、base agent 名、instance 名、カンマ区切り fan-out を扱います。`claude` を指定するとその session 内の `claude-*` 全 instance に配送し、`claude-1` を指定するとその instance だけに送ります。

送信時には `msg_id` が新しく生成され、本文が `[From: ...]` で始まる場合はその header に `msg-id` と `reply-to` が注入されます。`reply_to` があるときは、既存 JSONL から元 message を引いて `reply_preview` も作ります。JSONL 側の entry は次のような形です。

```json
{
  "timestamp": "2026-03-26 14:20:16",
  "session": "multiagent",
  "sender": "codex",
  "targets": ["claude-1", "claude-2"],
  "message": "[From: codex | msg-id: 4dc1d8a6c0f2] 共有します。",
  "msg_id": "4dc1d8a6c0f2",
  "reply_to": "afe4a1c21f2e",
  "reply_preview": "user: docs/AGENT.md を読んで..."
}
```

`agent-send` は target 解決後、実際に成功した delivery だけを JSONL に記録します。tmux pane への paste-buffer が失敗した target は log に残さず、部分成功なら成功分だけが記録されます。

### `/send` と raw path

chat UI からの通常送信は `POST /send` を通り、`ChatRuntime.send_message()` から `agent-send` を呼びます。これに対して raw / silent path は `agent-send` を経由せず、tmux pane へ直接 paste-buffer します。`Raw Send` ボタンや `/raw` は、`[From: User]` や `msg-id` を付けずに text を一度だけ流したいときのための分岐です。

## 1.5. Thinking / Pane Trace

`ChatRuntime.agent_statuses()` は各 pane の直近 20 行を `tmux capture-pane` で取り、前回 snapshot と比較して `running` / `idle` / `dead` / `offline` を判定します。内容が変わった直後は grace period のあいだ `running` を維持し、変化が止まると `idle` へ戻します。集計結果は `state_core.update_thinking_totals_from_statuses()` に渡され、session / agent ごとの thinking time が加算されます。

Pane Trace は `GET /trace?agent=<name>&lines=<n>` で取得します。`trace_content()` は `tmux capture-pane -p -e` を使い、tail mode では最後の数十行だけ、重い path では長い scrollback を返します。front-end は local / LAN では 100ms、public host 上では 1.5 秒間隔で現在表示中の tab だけを poll します。

thinking row と Pane Trace が別物である点も実装上は重要です。thinking row は status の可視化で、Pane Trace は tmux pane の text snapshot です。前者は lightweight な状態表示、後者は pane 内容の確認です。

## 2. 入力欄

composer は `chat_assets.py` 内の overlay と quick action 群で構成されています。通常は閉じておき、モバイルでは `O` ボタン、デスクトップでは `O` ボタンまたは middle click で開きます。textarea の下には send button、mic button、raw send、brief / memory / save log / pane control が並びます。

### slash command

slash command の一覧は front-end の `SLASH_COMMANDS` 配列で管理されており、実行先は `/send` または front-end の専用処理です。

| command | technical behavior |
|------|------|
| `/memo [text]` | `user` 自身を target にして send。本文が空でも Import 添付があれば送信可 |
| `/raw <text>` | `POST /send` を `silent=true` で呼び、tmux pane へ直接 paste |
| `/brief` | `default` brief の editor modal を開く |
| `/brief set <name>` | `brief_<name>.md` を開く |
| `/model` | 対象 pane に `model` を送る |
| `/up [count]` | 対象 pane に上移動を送る |
| `/down [count]` | 対象 pane に下移動を送る |
| `/restart` | `ChatRuntime.restart_agent_pane()` を呼ぶ |
| `/resume` | agent registry の resume flag で pane を再開 |
| `/interrupt` | 対象 pane に `Escape` |
| `/enter` | 対象 pane に `Enter` |

### `@` と Import

`@` 補完は workspace path を会話へ差し込むための front-end 機能です。file existence の確認には `/files-exist` が使われます。Import は別の経路で、`POST /upload` にファイル本体を送り、`logs/<session>/uploads/<timestamp>_<hex>.<ext>` へ保存します。保存後は workspace 相対 path が返され、chat 本文には file card として出ます。

### brief と memory

brief は `bin/agent-index` 側の `/briefs`、`GET /brief-content`、`POST /brief-content` で管理されます。名前は `brief_<name>.md` に正規化され、保存先は `logs/<session>/brief/` です。Brief ボタンは一覧を取得し、選択した brief の本文を `silent=true` で selected targets に順送します。

memory は `logs/<session>/memory/<agent>/memory.md` が現在値、`memory.jsonl` が履歴です。Memory ボタンを押すと最初に `POST /memory-snapshot` が走り、更新前の `memory.md` が `memory.jsonl` に append されます。その後、front-end が agent に対して `memory.md` を更新する instruction を送ります。Load は逆向きで、現在の `memory.md` を読み出して agent に送ります。

## 3. Header

### Branch Menu

branch menu の data source は chat server 側の git overview endpoint です。現在の branch、dirty state、commit 一覧、diff chunk を JSON で取り、front-end が panel と carousel を描画します。`ChatRuntime.ensure_commit_announcements()` は `git log -1` と前回 state を比べ、commit が進んでいれば `kind="git-commit"` の system entry を JSONL に追加します。Stats の commit 集計はこの system entry を基準にしています。

### File Menu

file menu は `FileRuntime` が担当します。raw file 配信は `/file-raw`、text content は `/file`、editor handoff は `/open-file-in-editor` です。`FileRuntime` は extension と file 内容から preview mode を選び、Markdown、画像、PDF、動画、音声、plain text を切り替えます。

Markdown preview は `marked` で HTML 化したあと、`img src` の相対 path をその Markdown file 基準で再解決し、`/file-raw?path=...` に変換します。`Open in Editor` は `MULTIAGENT_EXTERNAL_EDITOR` があればそれを優先し、なければ CotEditor / VS Code / xdg-open などの fallback を選びます。

### Add / Remove Agent

agent add / remove modal は front-end で target 候補を出し、実際の変更は `multiagent add-agent` と `multiagent remove-agent` に渡します。ここで変わるのは tmux pane 構成と `MULTIAGENT_AGENTS` で、既存 `.agent-index.jsonl` は保持されます。chat UI 側で `Reload` を推奨しているのは、visible targets と pane 状態を新しい構成に揃えるためです。

## 4. Hub / Stats / Settings

`HubRuntime` は active tmux sessions と archived log directories の両方を見ます。active 側は tmux session とその environment から、archived 側は log directory と `.meta`、`.agent-index.jsonl` から情報を集めます。Hub preview に出る latest message は `latest_message_preview()` で `[From: ...]` header や `[Attached: ...]` を削って短くしています。

Stats は `HubRuntime.build_stats_payload()` で集計します。message は `msg_id` を優先キーとして deduplicate し、sender 別・session 別に数えます。commit は `git-commit` system entry の `commit_hash` で deduplicate します。thinking time は `state_core.py` が持つ session / daily aggregate を読み、agent instance 名は base agent 名へ collapse して表示します。

settings は `state_core.load_hub_settings()` と `save_hub_settings()` を通ります。Hub / chat 共通の設定は repo-local ではなく local state directory に保存されます。chat port override は `.chat-ports.json`、Hub settings は `.hub-settings.json`、thinking time は `.thinking-time.json` と `.thinking-runtime.json` に分かれています。

## 5. Logs / Export

`multiagent save` は各 pane を `tmux capture-pane -p -e` で `.ans` に保存し、ANSI escape を落とした `.log` を別に生成します。session root の `.meta` には created / updated timestamp と overwrite 履歴が残ります。chat server は background thread で約 120 秒おきに `runtime.save_logs(reason="autosave")` を呼びます。

`.agent-index.jsonl` と pane logs の役割は分かれています。JSONL は message routing の canonical log で、pane logs は terminal 表示の snapshot です。Hub preview、Stats、reply preview、agent-to-agent 履歴の再構成は JSONL を基準にし、Pane Trace や `.log` / `.ans` は pane 側の text を確認したいときに使います。

`ExportRuntime` は chat payload を埋め込んだ standalone HTML を生成します。icon data URI、利用可能なら font data、CDN fallback の script / CSS を埋め込み、`/messages` や `/trace` などの fetch を export 内部の payload に差し替えます。結果として、export 後の HTML は chat header を持たない静的 viewer として単独で開けます。

## 6. LAN / Public Access

`bin/agent-index` は chat server と Hub server の両方を持ち、証明書が与えられている場合は HTTPS で listen します。Hub 起動時には local URL と LAN URL が表示され、session ごとの chat URL は `/session/<name>/` になります。

外部公開は `bin/multiagent-cloudflare` が担当します。Quick Tunnel は一時 URL を取り、named tunnel は固定 hostname と DNS を扱います。`access-enable` / `access-disable` は Cloudflare Access 用 metadata と config を更新し、`daemon-install` は public edge を login 後も維持する watchdog を入れます。どの path も local Hub / chat の URL 体系を変えるのではなく、public hostname を前段に足す構成です。

## 関連文書

- [README.md](../README.md): 公開向けの機能説明
- [docs/design-philosophy.md](design-philosophy.md): なぜその構成を選んでいるか
- [docs/AGENT.md](AGENT.md): この環境で動く agent 向けガイド
- [docs/cloudflare-quick-tunnel.md](cloudflare-quick-tunnel.md): Quick Tunnel / named tunnel
- [docs/cloudflare-access.md](cloudflare-access.md): public Hub と Access
- [docs/cloudflare-daemon.md](cloudflare-daemon.md): public daemon
