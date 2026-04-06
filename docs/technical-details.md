# multiagent-chat 技術詳細

英語版: [docs/technical-details.en.md](technical-details.en.md)

この文書は、[README.md](../README.md) で説明している機能を、実装側の構成とデータフローに寄せて説明するためのものです。ユーザー向けの使い方ではなく、`bin/` と `lib/agent_index/` が何を担当し、session・message・log がどのように流れるかをまとめています。

## 0. 実装の見取り図

`multiagent-chat` の主要な責務は、session の作成、message の配送、Hub / chat UI の配信、file / log / export の補助に分かれています。


| ファイル                                | 役割                                                                                                             |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `bin/multiagent`                    | tmux session 作成、agent pane 配置、agent 追加 / 削除、pane log 保存                                                        |
| `bin/agent-send`                    | agent / `others` への message 配送、`[From: ...]` header の自動付与、`msg_id` / `reply-to` metadata の生成、JSONL 追記 |
| `bin/agent-index`                   | Hub、chat UI、Stats、Settings、upload / trace / export などの HTTP endpoint                                           |
| `lib/agent_index/chat_core.py`      | chat server の runtime、message payload、pane status、trace、save log                                               |
| `lib/agent_index/chat_assets.py`    | chat UI の HTML / CSS / JavaScript、composer、brief / memory、Pane Trace                                           |
| `lib/agent_index/hub_core.py`       | active / archived session の収集、Hub preview、Stats 集計                                                             |
| `lib/agent_index/file_core.py`      | file preview、raw file 配信、external editor 起動                                                                    |
| `lib/agent_index/export_core.py`    | static HTML export 生成                                                                                          |
| `lib/agent_index/push_core.py`      | VAPID key 管理、browser push subscription、Hub / session 通知 monitor                                                |
| `lib/agent_index/state_core.py`     | Hub settings、chat port、thinking time の永続化                                                                      |
| `lib/agent_index/agent_registry.py` | 対応 agent CLI 一覧、起動 / resume 設定、icon 情報                                                                         |
| `lib/agent_index/static/pwa/`       | Hub / chat の PWA 用 service worker、manifest、install asset                                                       |
| `bin/multiagent-public-edge`        | Cloudflare 向け reverse proxy（public session access 用）                                                           |


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

`agent-send` はこの環境の agent 間 message transport です。message を pane に直接打ち込むだけではなく、同じ内容を `.agent-index.jsonl` に構造化して保存し、`msg_id`、`targets`、`reply_to` を保持します。

session の解決順は `MULTIAGENT_SESSION`、現在の tmux session、workspace に対して一意に見つかる active session、最後に起動時 state file です。target は `others`、base agent 名、instance 名、カンマ区切り fan-out を扱います。`claude` を指定するとその session 内の `claude-*` 全 instance に配送し、`claude-1` を指定するとその instance だけに送ります。

送信時には `msg_id` が新しく生成され、通常 path では送信元 sender に基づく `[From: ...]` header が自動補完されます。`msg_id` と `reply_to` は pane 本文ではなく JSONL entry 側に保持され、`reply_to` があるときは既存 JSONL から元 message を引いて `reply_preview` も作ります。JSONL 側の entry は次のような形です。

```json
{
  "timestamp": "2026-03-26 14:20:16",
  "session": "multiagent",
  "sender": "codex",
  "targets": ["claude-1", "claude-2"],
  "message": "[From: codex] 共有します。",
  "msg_id": "4dc1d8a6c0f2",
  "reply_to": "afe4a1c21f2e",
  "reply_preview": "user: docs/AGENT.md を読んで..."
}
```

`agent-send` は target 解決後、実際に成功した delivery だけを JSONL に記録します。tmux pane への paste-buffer が失敗した target は log に残さず、部分成功なら成功分だけが記録されます。

### `/send` と direct-provider path

chat UI からの通常送信は `POST /send` を通り、`ChatRuntime.send_message()` が target pane へ直接配送しつつ `sender="user"` の JSONL entry を追記します。`/memo` は pane 配送を行わず user 宛てメモ entry を直接 JSONL に残します。これに対して `/gemini` や `/gemma` のような direct-provider command は tmux pane を target にしません。`multiagent-gemini-direct-run` や `multiagent-ollama-direct-run` を起動し、normalized provider events を同じ chat timeline へ流します。

## 1.5. Thinking / Pane Trace

`ChatRuntime.agent_statuses()` は各 pane の直近 20 行を `tmux capture-pane` で取り、前回 snapshot と比較して `running` / `idle` / `dead` / `offline` を判定します。内容が変わった直後は grace period のあいだ `running` を維持し、変化が止まると `idle` へ戻します。集計結果は `state_core.update_thinking_totals_from_statuses()` に渡され、session / agent ごとの thinking time が加算されます。

Pane Trace は `GET /trace?agent=<name>&lines=<n>` で取得します。`trace_content()` は `tmux capture-pane -p -e` を使い、tail mode では最後の数十行だけ、重い path では長い scrollback を返します。front-end は local / LAN では 100ms、public host 上では 1.5 秒間隔で現在表示中の tab だけを poll します。

デスクトップの Pane Trace popup は複数のレイアウトモードに対応しています。single pane、horizontal / vertical split、3 pane 配置、4 pane grid があり、各スロットは割り当てられた agent を独立してポーリングします。agent の割り当てはタブクリックやアイコンのドラッグアンドドロップで変更でき、追加スロット分のポーリング interval はレイアウト変更時に生成・破棄されます。

ポーリング更新時は auto-scroll しません。スクロールを最下部に戻すのは初回読み込みと明示的な agent 切り替え時だけです。ユーザーが最下部から 48px 以上離れた位置までスクロールすると、DOM 更新自体を一時停止し、テキスト選択やコピーがポーリングによって妨げられないようにしています。最下部に戻ると自動的に更新が再開します。

pane 出力中の ANSI escape sequence は `AnsiUp` ライブラリでクライアント側で HTML に変換されます。trace dot（`●`）は iOS でのレンダリング差異を避けるため、専用の `<span>` でラップしています。

thinking row と Pane Trace が別物である点も実装上は重要です。thinking row は status の可視化で、Pane Trace は tmux pane の text snapshot です。前者は lightweight な状態表示、後者は pane 内容の確認です。

## 2. 入力欄

composer は `chat_assets.py` 内の overlay と quick action 群で構成されています。通常は閉じておき、モバイルでは `O` ボタン、デスクトップでは `O` ボタンまたは middle click で開きます。textarea の下には send button、mic button、Import、brief / memory / save log / pane control が並びます。

### slash command

slash command の一覧は front-end の `SLASH_COMMANDS` 配列で管理されており、実行先は `/send` または front-end の専用処理です。


| command             | technical behavior                                   |
| ------------------- | ---------------------------------------------------- |
| `/memo [text]`      | `user` 自身を target にして send。本文が空でも Import 添付があれば送信可   |
| `/cron`             | 現在の session / target を埋めた quick-create Cron flow を開く |
| `/gemini <text>`    | direct Gemini runner を起動し、provider events を chat に流す |
| `/gemma <text>`     | Ollama runner を起動する。`/gemma:model` で model 名を上書き可 |
| `/brief`            | `default` brief の editor modal を開く                   |
| `/brief set <name>` | `brief_<name>.md` を開く                                |
| `/load`             | 現在の `memory.md` を selected agent に送る               |
| `/memory`           | selected agent に memory 更新要求を送る                    |
| `/model`            | 対象 pane に `model` を送る                                |
| `/up [count]`       | 対象 pane に上移動を送る                                      |
| `/down [count]`     | 対象 pane に下移動を送る                                      |
| `/restart`          | `ChatRuntime.restart_agent_pane()` を呼ぶ               |
| `/resume`           | agent registry の resume flag で pane を再開              |
| `/ctrlc`            | 対象 pane に `Ctrl+C`                                   |
| `/interrupt`        | 対象 pane に `Escape`                                   |
| `/enter`            | 対象 pane に `Enter`                                    |


### `@` と Import

`@` 補完は workspace path を会話へ差し込むための front-end 機能です。file existence の確認には `/files-exist` が使われます。Import は別の経路で、`POST /upload` にファイル本体を送り、`logs/<session>/uploads/<timestamp>_<hex>.<ext>` へ保存します。保存後は workspace 相対 path が返され、chat 本文には file card として出ます。

添付カードは送信前にリネームできます。カードをタップすると popup が開き、ラベルを入力できます。送信時に `POST /rename-upload` がディスク上のファイルを指定ラベルにリネームし（拡張子は維持）、送信メッセージは新しいファイル名を参照します。ラベルはサーバー側でサニタイズされ、制御文字・パス区切り・非ワード文字は除去または置換され、80 文字で切り詰められます。衝突時はランダムな短い suffix が付加されます。

### Camera mode

Camera mode は header menu の `Camera` から開く mobile-first overlay です。`openCameraMode()` が target agent を決め、full-screen の `getUserMedia()` surface を開き、その上に最近の agent reply を重ねて表示します。

撮影画像は生 blob のまま送るのではなく、`captureCameraModeFrameBlob()` で video frame を canvas に落とし、`resizeCameraModeBlob()` で縮小（現状 max side 1280px、JPEG quality 0.7）した後、`POST /upload` で `logs/<session>/uploads/` に保存し、最後に `POST /send` で通常の `[Attached: ...]` message として selected target に送ります。同じ overlay 内の voice input は Web Speech API と hybrid waveform を使い、別 audio stream を開ける環境では live Web Audio の波形に切り替え、競合や policy 制約で取れない環境では CSS fallback animation を維持します。

### brief と memory

brief は `bin/agent-index` 側の `/briefs`、`GET /brief-content`、`POST /brief-content` で管理されます。名前は `brief_<name>.md` に正規化され、保存先は `logs/<session>/brief/` です。Brief ボタンは一覧を取得し、選択した brief の本文を `silent=true` で selected targets に順送します。

memory は `logs/<session>/memory/<agent>/memory.md` が現在値、`memory.jsonl` が履歴です。Memory ボタンを押すと最初に `POST /memory-snapshot` が走り、更新前の `memory.md` が `memory.jsonl` に append されます。その後、front-end が agent に対して `memory.md` を更新する instruction を送ります。Load は逆向きで、現在の `memory.md` を読み出して agent に送ります。

## 3. Header

### Branch Menu

branch menu の data source は chat server 側の git overview endpoint です。現在の branch、dirty state、commit 一覧、diff chunk を JSON で取り、front-end が panel と carousel を描画します。commit 一覧はページネーション対応で、`/git-branch-overview` は `offset` と `limit` パラメータを受け付け、デフォルト 50 件ずつ commit を返します。front-end はリスト末尾の sentinel 要素に `IntersectionObserver` を設定し、末尾到達時に次ページを自動取得します。`Load more` ボタンによる手動読み込みも可能です。これにより、初回表示時に `git log --stat` を全履歴に対して走らせることを避けています。

未コミット差分は commit 履歴の上に表示されます。`git diff HEAD` と `git diff --cached` からインラインで diff を描画します。

`ChatRuntime.ensure_commit_announcements()` は `git log -1` と前回 state を比べ、commit が進んでいれば `kind="git-commit"` の system entry を JSONL に追加します。Stats の commit 集計はこの system entry を基準にしています。

### File Menu

file menu は `FileRuntime` が担当します。raw file 配信は `/file-raw`、text content は `/file`、editor handoff は `/open-file-in-editor` です。`FileRuntime` は extension と file 内容から preview mode を選び、Markdown、画像、PDF、動画、音声、plain text を切り替えます。

Markdown preview は `marked` で HTML 化したあと、`img src` の相対 path をその Markdown file 基準で再解決し、`/file-raw?path=...` に変換します。`Open in Editor` は `MULTIAGENT_EXTERNAL_EDITOR` があればそれを優先し、なければ CotEditor / VS Code / xdg-open などの fallback を選びます。

### Add / Remove Agent

agent add / remove modal は front-end で target 候補を出し、実際の変更は `multiagent add-agent` と `multiagent remove-agent` に渡します。同じ command は session 内で動作中の agent からも使えます。pane 起動時に `MULTIAGENT_SESSION` と `MULTIAGENT_TMUX_SOCKET` を export しているため、agent 側ではそのまま現在の session を対象にできます。

ここで変わるのは tmux pane 構成と `MULTIAGENT_AGENTS` で、既存 `.agent-index.jsonl` は保持されます。さらに、構成変更に成功すると `kind="session-topology"` の system entry を JSONL に append するため、header menu からの変更と agent 側からの変更が同じ chat timeline に残ります。self-remove の場合は、pane が即座に消えても後続の environment 更新が中断されないよう、`multiagent remove-agent` が detached helper に処理を委譲します。

chat UI 側で `Reload` を推奨しているのは、visible targets と pane 状態を新しい構成に揃えるためです。

## 4. Hub / Stats / Settings

`HubRuntime` は active tmux sessions と archived log directories の両方を見ます。active 側は tmux session とその environment から、archived 側は log directory と `.meta`、`.agent-index.jsonl` から情報を集めます。Hub preview に出る latest message は `latest_message_preview()` で `[From: ...]` header や `[Attached: ...]` を削って短くしています。

Stats は `HubRuntime.build_stats_payload()` で集計します。message は `msg_id` を優先キーとして deduplicate し、sender 別・session 別に数えます。commit は `git-commit` system entry の `commit_hash` で deduplicate します。thinking time は `state_core.py` が持つ session / daily aggregate を読み、agent instance 名は base agent 名へ collapse して表示します。

settings は `state_core.load_hub_settings()` と `save_hub_settings()` を通ります。Hub / chat 共通の設定は repo-local ではなく local state directory に保存されます。chat port override は `.chat-ports.json`、Hub settings は `.hub-settings.json`、thinking time は `.thinking-time.json` と `.thinking-runtime.json` に分かれています。

install prompt と browser notification も現在は Hub 側に集約されています。`bin/agent-index` は `hub.webmanifest`、`app.webmanifest`、`service-worker.js`、Settings 上の install / permission UI をまとめて配信し、push subscription の永続化は `push_core.py` が local state directory 配下で担当します。`HubPushMonitor` は active session ごとの `.agent-index.jsonl` を tail し、`user` / `system` sender を除いた agent reply だけを検出して `/session/<name>/?follow=1` へ飛ぶ通知を組み立てます。

この Hub 中心モデルが必要なのは、service worker と通知 permission の単位が HTTPS origin ごとだからです。実運用では Hub を 1 回 install して subscription すれば十分で、各 session chat を個別 install しなくても background reply をまとめて受け取れます。Hub subscription が存在する間は session 側 push monitor は送信を止め、Hub が repo 全体の通知受け口になります。

## 5. Logs / Export

`multiagent save` は各 pane を `tmux capture-pane -p -e` で `.ans` に保存し、ANSI escape を落とした `.log` を別に生成します。session root の `.meta` には created / updated timestamp と overwrite 履歴が残ります。chat server は background thread で約 120 秒おきに `runtime.save_logs(reason="autosave")` を呼びます。

`.agent-index.jsonl` と pane logs の役割は分かれています。JSONL は message routing の canonical log で、pane logs は terminal 表示の snapshot です。Hub preview、Stats、reply preview、agent-to-agent 履歴の再構成は JSONL を基準にし、Pane Trace や `.log` / `.ans` は pane 側の text を確認したいときに使います。

`ExportRuntime` は chat payload を埋め込んだ standalone HTML を生成します。icon data URI、利用可能なら font data、CDN fallback の script / CSS を埋め込み、`/messages` や `/trace` などの fetch を export 内部の payload に差し替えます。結果として、export 後の HTML は chat header を持たない静的 viewer として単独で開けます。

## 6. 堅牢性と復旧

### tmux コマンドラッパー

`hub_core.py` からのすべての tmux subprocess 呼び出しは `tmux_run()` を経由します。この関数は `TmuxRunResult` dataclass を返し、`args`、`returncode`、`stdout`、`stderr`、`timed_out` フラグを持ちます。デフォルトタイムアウトは読み取り操作で 2 秒、`kill-session` のような破壊的操作で 4 秒です。タイムアウト時は `timed_out=True`、`returncode=124`（慣例的なタイムアウト終了コード）が設定されます。この結果オブジェクトは `subprocess.CompletedProcess` と duck-type 互換なので、`.returncode` や `.stdout` を参照する既存コードはそのまま動きます。

### unhealthy と missing の区別

session クエリ（`repo_sessions_query()`、`active_session_records()`）は `RepoSessionsQueryResult` を返し、`state` フィールドは `"ok"` または `"unhealthy"`、加えて任意の `detail` 文字列を持ちます。`"unhealthy"` は tmux コマンドがタイムアウトした場合にのみ設定され、session が存在しないなどの正常な非ゼロ終了では設定されません。この区別により、tmux server が遅いだけなのに「session が消えた」と誤認することを防ぎます。`"unhealthy"` 時は Hub が 404 ではなく HTTP 503 を返し、UI は一時障害メッセージを表示します。

### Session revive のガード

`revive_archived_session()` は起動前に一連の事前チェックを実行します。

1. tmux の健全性を確認。`"unhealthy"` なら即座に中止し、詳細なエラーメッセージを返す。
2. session が既に active かどうかを確認。active なら再起動せず成功を返す。
3. archived record から保存された workspace path と agent 構成を取得。
4. workspace directory が存在しアクセス可能であることを検証。

起動後は 150ms 間隔で最大 80 回（約 12 秒間）ポーリングします。ポーリング間に tmux の健全性を再確認し、起動中に tmux が不調になった場合は無限待ちせず中止します。

### Pane log の保護

`bin/multiagent` の `_save_pane_logs_to_dir()` は、各 pane capture をまず一時ファイル（`${ans_file}.tmp.$$`）に書き出してから既存 snapshot とサイズを比較します。旧ファイルが 1 KB 超かつ新しい capture がその半分未満の場合に保護が発動し、旧 `.ans` / `.log` を `${instance}.${timestamp}.protected.ans` / `.protected.log` にコピーしてから上書きします。stderr にも新旧バイト数付きの警告が出力されます。

この仕組みは、agent プロセスの再起動、tmux pane のクリア、session の再作成などによる pane リセットを検知します。これがなければ、2 分ごとの autosave サイクルが充実した terminal 履歴をほぼ空のバッファで黙って置き換えてしまいます。

### Delete のパス検証

`hub_core.py` の `delete_session()` はターゲットパスを解決し、許可されたルートの whitelist と照合します。whitelist には central log directory、legacy log directory、local state workspace directory が含まれます。解決後のパスがすべての許可ルートの外にある場合、削除は拒否されます。これにより、細工された session 名によるパストラバーサル攻撃や意図しないディレクトリの削除を防ぎます。

### `.meta` の構造

各 session directory には `_update_session_meta()` が管理する `.meta` JSON ファイルがあります。

```json
{
  "session": "multiagent",
  "workspace": "/path/to/workspace",
  "created_at": "2026-03-29 10:15:32",
  "updated_at": "2026-03-29 12:30:00",
  "overwrite_count": 5,
  "agents": ["claude", "codex", "gemini"],
  "overwrites": [
    {"timestamp": "2026-03-29 10:15:32", "reason": "initial"},
    {"timestamp": "2026-03-29 10:17:22", "reason": "autosave"},
    {"timestamp": "2026-03-29 12:30:00", "reason": "manual"}
  ]
}
```

`created_at` は保存を跨いで維持されます。`updated_at` と `overwrites` 配列は毎回の保存で追記されます。`reason` フィールドは `"initial"`、`"autosave"`、`"manual"`、`"kill"` などのライフサイクルイベントを区別し、各 snapshot がいつ・なぜ取られたかを再構成できるようにしています。

## 7. LAN / Public Access

`bin/agent-index` は chat server と Hub server の両方を持ち、証明書が与えられている場合は HTTPS で listen します。Hub 起動時には local URL と LAN URL が表示され、session ごとの chat URL は `/session/<name>/` になります。

外部公開は `bin/multiagent-cloudflare` と `bin/multiagent-public-edge` が担当します。public edge は Cloudflare とローカルの Hub / chat server の間に立つ軽量 reverse proxy で、URL パス中の session 名に基づいてリクエストを適切なローカルポートに転送します。`lib/agent_index/file_core.py` を通じて、ローカル chat server と同じ逐次メッセージ読み込みロジックを共有しています。

Quick Tunnel は一時 URL を取り、named tunnel は固定 hostname と DNS を扱います。`access-enable` / `access-disable` は Cloudflare Access 用 metadata と config を更新し、`daemon-install` は public edge を login 後も維持する watchdog を入れます。どの path も local Hub / chat の URL 体系を変えるのではなく、public hostname を前段に足す構成です。

public edge もローカル Hub と同じ tmux 健全性認識を適用します。tmux が不調のとき、session ページは revive を試みず 503 を返します。public edge 経由の session revive も、処理前に tmux の健全性をチェックします。

## 関連文書

- [README.md](../README.md): 公開向けの機能説明
- [docs/design-philosophy.md](design-philosophy.md): なぜその構成を選んでいるか
- [docs/AGENT.md](AGENT.md): この環境で動く agent 向けガイド
- [docs/cloudflare-quick-tunnel.md](cloudflare-quick-tunnel.md): Quick Tunnel / named tunnel
- [docs/cloudflare-access.md](cloudflare-access.md): public Hub と Access
- [docs/cloudflare-daemon.md](cloudflare-daemon.md): public daemon
