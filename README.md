# multiagent-chat

tmux ベースのローカル multi-agent chat/workbench です。複数の AI エージェントを同一セッションに並べ、Hub と chat UI から会話・送信・ログ確認を行えます。

## 何ができるか

### 0. 全体説明 / Remote Control

PC だけでなく、同一 LAN 上のスマホからも Hub と chat UI を開けます。画面構成は共通で、Hub が session 一覧と管理、chat UI が 1 session の作業面です。スマホ側でも既存 session の確認、新規 session 作成、chat UI の操作をそのまま行えます。

### 1. New Session / Body

新規 session は Hub から作成します。workspace path は UI から指定でき、スマホでも入力できます。同じ base agent を複数回追加することもでき、重複した instance には `-1`, `-2` の suffix が付きます。chat body は user と agent だけでなく、agent 同士のやり取りも表示対象です。

<p align="center">
  <img src="screenshot/new_session-portrait.png" alt="Create new session" width="320">
  <img src="screenshot/message_body-portrait.png" alt="Chat message body" width="320">
</p>

chat body では本文のコピー、`reply-to` を付けた返信の開始、返信元や返信先への移動、`[Attached: ...]` や `@path/to/file` からのファイル参照ができます。本文レンダラは見出し、段落、箇条書き、引用、インラインコード、コードブロック、表、KaTeX による LaTeX 数式、Mermaid ダイアグラムを扱います。`msg-id`、`reply-to`、ファイル参照、コピー導線が UI 上に出ています。

### 1.5. Thinking / Pane Trace

thinking 行は、現在実行中の agent があるときに表示されます。Pane Trace は pane 側の表示を追うための画面で、LAN / local では 100ms ごと、public 経由では 1.5s ごとに更新されます。PC の `Terminal` は Pane Trace ではなく terminal 本体を開く導線です。

<p align="center">
  <img src="screenshot/thinking.png" alt="Thinking state" width="320">
  <img src="screenshot/Pane_trace-portrait.png" alt="Pane trace" width="320">
</p>

### 2. 入力形式

入力欄はモバイルでは丸い `O` ボタンから開きます。PC では `O` ボタンに加えて、ホイール押し込みでも開けます。入力欄はオーバーレイとして開くため、通常時はメッセージ表示領域を大きく取っています。

#### スラッシュコマンド

現在の slash command:

| コマンド | 動作 |
|------|------|
| `/memo [text]` | 自分宛メモ。本文省略時は Import 添付のみでも送信可 |
| `/silent <text>` | ヘッダなしの one-shot raw send |
| `/brief` / `/brief set <name>` | brief の表示・編集 |
| `/restart` | 選択中 agent の再起動 |
| `/resume` | 選択中 agent の再開 |
| `/interrupt` | 選択中 agent に Esc 送信 |
| `/enter` | 選択中 agent に Enter 送信 |

#### アットマークコマンド

`@` による file path autocomplete です。workspace 内のファイルを path 指定で参照できます。

#### インポート

Import は workspace 内ファイルの参照ではなく、ローカル端末側のファイルを workspace へアップロードする導線です。スマホでは端末に保存された画像などを直接取り込めます。PC ではドラッグアンドドロップにも対応しています。image はサムネイル表示され、それ以外は拡張子付きカードで表示されます。取り込んだファイルは会話に添付され、workspace 配下へ保存されます。

#### ブリーフ

brief は session 固有テンプレートです。保存済み brief を選んで再送できます。brief は session ごとに保存され、恒久ルールは `docs/AGENT.md`、session 固有の文脈や使い回す指示は brief に置く形になります。

`docs/AGENT.md` との違い:

| ファイル | 役割 |
|------|------|
| `docs/AGENT.md` | repo / multiagent 環境で共通の恒久ルール |
| brief | その session だけで使う追加指示、テンプレート、運用メモ |

入力方法:

| 操作 | 内容 |
|------|------|
| `/brief` | `default` brief を表示・編集 |
| `/brief set <name>` | `brief_<name>.md` を表示・編集 |
| Brief ボタン | 保存済み brief を選んで selected targets へ送信 |

<p align="center">
  <img src="screenshot/slash_command-portrait.png" alt="Slash commands" width="180">
  <img src="screenshot/atamrk_command-portrait.png" alt="@ command autocomplete" width="180">
  <img src="screenshot/import-portrait.png" alt="Import attachments" width="180">
  <img src="screenshot/brief-portrait.png" alt="Brief workflow" width="180">
</p>

スラッシュコマンドは composer の中で送信方法や session の状態を切り替えるための入口です。`@` は workspace 内のファイル参照を会話へ差し込み、Import はローカル端末側のファイルを workspace へアップロードします。brief は session 固有テンプレートで、保存済み brief の再送や編集に使います。恒久ルールは `docs/AGENT.md`、session 固有の文脈や運用メモは brief に置く形です。

### 3. ヘッダー部分

ヘッダーにはブランチメニュー、ファイルメニュー、エージェント追加 / 削除があります。

#### 3-1. ブランチメニュー

ブランチメニューでは現在の git 状態、commit 履歴、diff を見られます。diff 内のファイル名はクリックすると外部エディタへ移動します。

<p align="center">
  <img src="screenshot/branch_menu.png" alt="Branch menu" width="300">
  <img src="screenshot/Git_diff-portrait.png" alt="Git diff view" width="300">
</p>

ブランチメニューでは現在の git 状態、commit 履歴、diff を見られます。diff 内のファイル名はクリックすると外部エディタへ移動します。

#### 3-2. ファイルメニュー

ファイルメニューでは参照されたファイルの一覧、Markdown / コード / sound など複数形式のプレビュー、外部エディタへの移動、右側の矢印から参照元メッセージへの移動を扱います。

<p align="center">
  <img src="screenshot/file_menu.png" alt="File menu" width="240">
  <img src="screenshot/file_preview-portrait.png" alt="Markdown preview" width="240">
  <img src="screenshot/sound.png" alt="Sound file preview" width="240">
</p>

ファイルメニューでは参照されたファイルの一覧、Markdown / コード / sound など複数形式のプレビュー、外部エディタへの移動、右側の矢印から参照元メッセージへの移動を扱います。

#### 3-3. エージェント追加 / 削除

agent の追加 / 削除は session 構成を変更します。変更後は一度 `Reload` を推奨します。

<p align="center">
  <img src="screenshot/Add_agent-portrait.png" alt="Add agent" width="320">
  <img src="screenshot/remove_agent-portrait.png" alt="Remove agent" width="320">
</p>

同一 base agent の複数 instance も扱えます。重複時は `claude-1`, `claude-2` のような名前になります。

### 4. HubTop / Stats / Settings

#### HubTop

HubTop では active / archived session 一覧、最新状態プレビュー、chat UI への導線、New Session、Stats、Settings を扱います。

#### Stats

| カード | 内容 |
|------|------|
| Messages | 総メッセージ数、sender 別、session 別 |
| Thinking Time | 総 thinking time、agent 別、session 別 |
| Activated Agents | 一定数以上メッセージした agent 数 |
| Commits | 総 commit 数、session 別 |

日別グリッド:

- Messages per day
- Thinking time per day

#### Settings

| 区分 | 項目 |
|------|------|
| Theme | Theme |
| Chat Fonts | User Messages, Agent Messages |
| Text | Message Text Size |
| Reopen default | Default Message Count |
| Chat Defaults | Auto mode, Awake (prevent sleep), Sound notifications, Read aloud (TTS) |
| Visual Effects | Starfield background |
| Black Hole Text Opacity | User Messages, Agent Messages |

<p align="center">
  <img src="screenshot/Hub_Top-portrait.png" alt="Hub top" width="240">
  <img src="screenshot/Stats-portrait.png" alt="Stats page" width="240">
  <img src="screenshot/settings-portrait.png" alt="Settings" width="240">
</p>

HubTop では active / archived session 一覧、最新状態プレビュー、chat UI への導線、New Session、Stats、Settings を扱います。Stats では総メッセージ数、thinking time、activated agents、commit 数を見られ、日別グリッドとして Messages per day と Thinking time per day が並びます。Settings では Theme、Chat Fonts、Message Text Size、Default Message Count、Auto mode、Awake、Sound notifications、Read aloud (TTS)、Starfield background、Black Hole Text Opacity を設定できます。

### 5. ログ機能について

ログは 2 層です。

| ファイル | 役割 |
|------|------|
| `.agent-index.jsonl` | chat メッセージの構造化ログ |
| `*.log` / `*.ans` | pane 側ログ |

`.agent-index.jsonl` では `sender`, `targets`, `msg-id`, `reply-to` を追えます。pane 側ログでは terminal の表示内容を追えます。会話ログと実行痕跡が分かれて残ります。

### 6. 外からのアクセスについて

同一 Wi-Fi / LAN 上のスマホから Hub を開けます。スマホ側でも New Session と chat UI 操作が可能です。独自ドメインや Cloudflare を使った公開構成は追加設定が必要です。

## 典型的な使い方

1. `./bin/quickstart` で Hub を起動する
2. Hub から session を開く
3. chat UI で target agent を選び、依頼を送る
4. 必要に応じて Brief / Memory を使って指示や文脈を整理する
5. 作業後も session とログを残し、あとで再開する

## 典型的なユースケース

- 複数 agent に同時に調査や実装を振る
- user と agent、agent 同士の会話を 1 つの session に集約する
- 長い会話の途中で Brief / Memory を整理し直す
- スマホから既存 session を追い、必要なら新規 session も作る
- 作業結果をログや export HTML として残す

## 主な構成

### Session ベース

作業単位は tmux session です。各 agent は独立した pane で動き、Hub では active / archived をまとめて扱えます。

### Chat UI とログ

chat UI は単なる送信欄ではなく、target selection、message log、session 状態、quick actions、添付ファイル導線をまとめた作業画面です。ログは `.agent-index.jsonl` に残るため、あとから検索や追跡ができます。

### Brief と Memory

- Brief: session 固有の再利用テンプレート
- Memory: agent ごとの要約状態

Brief は selected targets にまとめて送れます。Memory は現在の `memory.md` と、更新前スナップショットの `memory.jsonl` に分かれています。

### ローカル中心、必要なら public 化

通常はローカルで使い、必要なときだけ Cloudflare 経由で Hub を外部公開できます。public 化しても、ローカル利用の流れを置き換える設計ではありません。

## Quickstart

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

`./bin/quickstart` は次を行います。

- `python3` と `tmux` の存在確認
- 必要なら依存の案内または対話的インストール
- エージェント CLI の確認
- multiagent セッションのセットアップ
- Hub / chat UI の起動

起動後は通常、Hub 一覧または chat UI がローカルで開ける状態になります。

## Requirements

- `python3`
- `tmux`
- macOS または Linux

macOS では Homebrew が入っていると導入が楽です。

## Main Commands

- `./bin/quickstart`: 依存確認つきで Hub を起動
- `./bin/multiagent`: セッション作成・再開・操作
- `./bin/agent-index`: セッション一覧、chat UI、ログ閲覧
- `./bin/agent-send`: user や他 agent へのメッセージ送信

## Docs

- [docs/AGENT.md](docs/AGENT.md): この環境で動くエージェント向けの運用ガイド
- [docs/cloudflare-quick-tunnel.md](docs/cloudflare-quick-tunnel.md): Cloudflare Quick Tunnel / named tunnel
- [docs/cloudflare-access.md](docs/cloudflare-access.md): public Hub に Cloudflare Access を掛ける方法
- [docs/cloudflare-daemon.md](docs/cloudflare-daemon.md): public tunnel の常駐運用
