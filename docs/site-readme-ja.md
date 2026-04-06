# multiagent-chat

Claude、Codex、Gemini、Copilot、Cursor、その他を — ひとつの session で、互いに会話させながら動かす。

`multiagent-chat` は、マルチエージェント開発のためのローカルファースト workbench です。各 AI agent に独立した実行環境を与えつつ、デスクトップでもモバイルでも使える単一の chat interface から session を操作できます。

クラウド依存なし。フレームワークのロックインなし。tmux と chat UI と構造化ログだけ。

[GitHub](https://github.com/estrada0521/multiagent-chat) · [詳細 README](readme/) · [設計思想](design-philosophy/) · [English](../) · [エクスポートサンプル →](/multiagent-chat/sample/)

---

## なぜこの環境を作ったか

マルチエージェントの構成を組もうとすると、大抵ふたつの選択肢に分かれます。モデルが進化すると壊れる固定的な orchestration フレームワークか、誰が何を言ったか追えなくなる生の terminal か。

この project は別の道を取ります。AI 側はできるだけ素の実行基盤に寄せます — tmux pane、stdin/stdout、環境変数。人間側にはまともな chat interface を用意します — 返信、ファイル参照、モバイルアクセス付き。両者をつなぐのは薄い message transport（`agent-send`）と構造化ログ（`.agent-index.jsonl`）だけです。

結果として、8 エージェントを並列で動かし、スマホから orchestrate し、それでもすべての行を `git blame` で追えます。

## はじめかた

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

これだけです。quickstart が依存関係を確認し、利用可能な agent CLI のインストールを案内し、Hub を起動します。表示された URL をブラウザで開いてください。

> **必要なもの:** `python3`、`tmux`、macOS または Linux。

## 中心にある考え方

### 1 session、複数 agent

Hub から session を作り、agent を選び、workspace を指定。各 agent は専用の tmux window を持ちます。あなたが見るのは、user-to-agent、agent-to-user、agent-to-agent のすべてを含む統一されたチャットタイムラインです。

現在の registry には `claude`、`codex`、`gemini`、`kimi`、`copilot`、`cursor`、`grok`、`opencode`、`qwen`、`aider` が含まれます。同じ agent の複数インスタンス（`claude-1`、`claude-2`）も可能。session の途中で agent を追加・削除しても履歴は失われません。

### chat であって terminal ではない

主画面は chat UI であり、terminal の壁ではありません。メッセージは送信者、宛先、返信チェーン、ファイル添付を持ちます。レンダラは Markdown、コードブロック、テーブル、LaTeX、Mermaid に対応。読むのは会話であって、scrollback ではありません。

terminal は消えていません — Pane Trace から 1 クリックで見られます。LAN 上で 100ms リフレッシュのライブビューアです。ただし、常にそこを見つめている必要はありません。

### 構造化ログであって一時的な出力ではない

すべてのメッセージは `.agent-index.jsonl` に完全なメタデータ付きで残ります。pane 出力は `.log` / `.ans` に別途保存。git commit も同じタイムラインに記録されます。session state、brief、per-agent memory もそれぞれ独立した層を持ちます。

つまり、session を自己完結型 HTML ファイルとしてエクスポートでき、commit とそれを生んだ会話を突き合わせられ、再起動後もまさに中断した地点から再開できます。

## 何ができるか

### 1. New Session / Message Body

Hub から session を作成。ワークスペースピッカーはデスクトップでもモバイルでも同じように動きます。message body には user メッセージ、agent 返信、agent 同士の協業がすべて 1 つのビューに表示されます。

各メッセージはコピー、返信、ソースへのジャンプ、インラインファイルナビゲーションに対応。multi-target 送信と返信チェーンは構造化ログに保存されます。

### 1.5. Thinking / Pane Trace

agent が動いている間、thinking 行がリアルタイムの状態を表示します — `Ran`、`Edited`、`ReadFile`、`Grepped` といった runtime hint 付き。タップすると Pane Trace が開き、agent が実際に何をしているかを見られます。

デスクトップでは popup で複数 agent の split view が可能。モバイルではインラインで開きます。どちらも tmux の window 切り替えより快適です。

### 2. Composer / Input Modes

composer は slash command（`/brief`、`/cron`、`/gemini`、`/restart`）、`@` による workspace ファイルの autocomplete、デバイスからのファイルインポートに対応。brief テンプレートと per-agent memory も同じ画面から管理できます。

コマンドの全リスト: [docs/chat-commands.en.md](docs/chat-commands.en.md)

### 2.5. Camera Mode

スマホのカメラを何かに向けて — ホワイトボード、基板、画面上のバグ — そのまま agent に送信。カメラオーバーレイはファインダー上に agent の返信をリアルタイムで重ねて表示するので、アプリを切り替えずに visual な会話ができます。

音声入力も同じオーバーレイで動作。写真はリサイズ・アップロードされ、通常のメッセージパスで配信されるので、他の添付と同じようにタイムラインに表示されます。

### 3. Branch Menu / File Menu

ヘッダーには、コードとファイルのコンテキストを chat フロー内に保つ 2 つのナビゲーションメニューがあります。

**Branch Menu** は現在のブランチ、git 状態、最近のコミット、diff を表示します。未コミットの変更がコミット履歴の上に表示されます。変更ファイルごとにエディタで開く、個別コミット、`HEAD` への復元が可能で、ワークツリー全体の一括コミットにも対応します。

**File Menu** は session 中に参照されたすべてのファイルを集約します。Markdown、コード、画像、音声のインラインプレビューと、`Open in Editor` による外部エディタへのハンドオフに対応。ファイルはカテゴリごとに件数・サイズ付きでグループ化され、各エントリからファイルを参照したメッセージに直接ジャンプできます。

### 4. Hub / Stats / Settings

Hub は active と archived の session を管理します。`Kill` は session を停止しますがログは保持、後から `Revive` 可能。`Delete` は保存された履歴を完全に削除。Stats はメッセージ数、thinking time、activated agents、commit 数を session 横断で追跡します。

Settings ではテーマ、フォント、文字サイズ、Auto mode（agent の許可プロンプト自動承認）、Awake、通知音 / browser notification、TTS 読み上げを制御。

### 5. Session Export

session を自己完結型の static HTML ファイルとしてエクスポート可能。エクスポートは添付を含む全会話を保持し、サーバーなしでオフライン閲覧できます。

**[エクスポートサンプルを見る →](sample/)**

## 設計方針

この project は、人間と AI agent の協業について特定の考え方に基づいて作られています。要約すると:

- **AI 側: pure な substrate。** agent は最小限の、装飾のない実行環境で動く。workflow engine も、固定された skill 階層も、モデルの進歩とともに劣化する scaffolding もない。
- **人間側: chat interface。** terminal 中心ではなく message 中心。デスクトップでもモバイルでも同じように動く。
- **transport は薄く。** `agent-send` がテキストを運ぶ。UI が解釈する。重い message bus はない。
- **画面の外へ。** camera、voice、remote access は一級市民 — workspace はデスクの上に閉じていない。

設計思想の全文: [docs/design-philosophy.md](docs/design-philosophy.md)

## モバイル & リモートアクセス

同じ Hub と chat UI が LAN 上のどのブラウザからでも使えます。外部からのアクセスには、Cloudflare tunnel のパスが同梱されています:

```bash
# 一時テスト（一時 URL）
bin/multiagent-cloudflare quick-start

# 自分のドメインで安定ホスト名
bin/multiagent-cloudflare named-setup multiagent your-hostname.com
bin/multiagent-cloudflare named-start
```

LAN デバイスでの secure browser feature（通知、マイク、PWA インストール）には local HTTPS も利用可能。

## コマンド

| コマンド | 用途 |
|---|---|
| `./bin/quickstart` | 依存チェック付きで Hub を起動 |
| `./bin/multiagent` | session の作成・再開・一覧・保存 |
| `./bin/agent-index` | Hub、chat UI、Stats、Settings |
| `./bin/agent-send` | agent 間の構造化メッセージ送信 |
| `./bin/agent-help` | agent 向けコマンド早見表 |

## アップデート

```bash
cd ~/multiagent-chat
git pull --ff-only
./bin/quickstart
```

既存の session、ログ、archived 履歴はそのまま保持されます。

## ドキュメント

- [docs/design-philosophy.md](docs/design-philosophy.md) — この環境がこう作られている理由
- [docs/chat-commands.en.md](docs/chat-commands.en.md) — コマンドとクイックアクションの全リファレンス
- [docs/technical-details.en.md](docs/technical-details.en.md) — session、transport、ログ、export、state の技術詳細
- [docs/AGENT.md](docs/AGENT.md) — session 内で動く agent のための操作ガイド
- [docs/updates/README.md](docs/updates/README.md) — リリースノート

---

<sub>beta 1.0.6 · [最新の変更](docs/updates/beta-1.0.6.ja.md)</sub>
