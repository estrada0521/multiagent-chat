# マルチエージェント環境: Agent 向けガイド

このドキュメントは、このリポジトリの **tmux ベースのマルチエージェント session で動作する agent** のための操作リファレンスです。

> **優先順位:** chat の指示、プロジェクト固有の指示、エディタレベルの指示、システム指示とこのドキュメントの間で矛盾がある場合は、常にそれらの指示をこのドキュメントより優先してください。

---

## 1. 最初に知るべきこと

この環境では、各 agent は通常独自の tmux pane で動作します。
user や他の参加者が Hub で読むべき内容は、pane にだけ出力するのではなく、**`agent-send`** 経由で送ってください。

まずは基本を確認してください：

```bash
env | rg '^MULTIAGENT|^TMUX'
```

このドキュメント（または workspace 側の `docs/AGENT.md` / `docs/AGENT.ja.md`）を user から受け取った場合は、**一度だけ** 読んで理解したことを報告してください。報告も `agent-send` を使います。

後でコンパクトなコマンドチートシートだけが必要な場合は、次を実行してください：

```bash
agent-help
```

例：

```bash
printf '%s' 'docs/AGENT.ja.md を読みました。agent-send によるメッセージの届け方、添付、ログの扱いを理解しました。' | agent-send user
```

主要な環境変数：

| Variable                 | 意味                             |
| ------------------------ | -------------------------------- |
| `MULTIAGENT_SESSION`     | 現在の session 名                |
| `MULTIAGENT_AGENT_NAME`  | あなたの agent 名                |
| `MULTIAGENT_AGENTS`      | 参加している agent の一覧        |
| `MULTIAGENT_WORKSPACE`   | workspace のパス                 |
| `MULTIAGENT_LOG_DIR`     | ログディレクトリ                 |
| `MULTIAGENT_TMUX_SOCKET` | tmux socket                      |
| `MULTIAGENT_PANE_*`      | 各 agent および user の pane ID  |
| `TMUX_PANE`              | あなた自身の pane ID             |

session の構成をプログラムから確認するには：

```bash
multiagent context --json
```

`multiagent context` が失敗する場合、`MULTIAGENT_SESSION` が古い可能性があります。`--session <name>` を明示するか、環境変数を確認してください。

---

## 2. 連絡のルール

### 守ること

| ルール | 内容 |
| ------ | ---- |
| **Hub に載せる配送** | Hub に表示させたい本文は、**必ず `agent-send` で `user` または他の agent に送る**。それだけを pane 出力に頼らない |
| **メッセージ本文** | 特殊文字や改行を壊さないよう、本文は **stdin 経由** で渡す |
| **添付** | メッセージ本文に **`[Attached: 相対パス]`** を含める |
| **`$` を含む語** | シェル変数・パスなど **`$` を含む語はバッククォートでインラインコード化**する。さもないと Hub 上で数式として解釈される。例: `` `$HOME` ``、`` `$PATH` `` |

### 基本形

```bash
printf '%s' 'message body' | agent-send <target>
```

target の例：

- `user`
- `claude`
- `codex`
- `gemini`
- `claude,codex`

---

## 3. `agent-send` の使い方

### `user` へ送る

```bash
printf '%s' '了解しました。' | agent-send user
```

### 別の agent へ送る

```bash
printf '%s' '該当箇所はこちらです。' | agent-send gemini
```

### 別トピックとして送る

```bash
printf '%s' '追加で別件を調べます。' | agent-send user
```

### PATH に `agent-send` がない場合

`[Attached: ...]` の書き方と、`agent-send` コマンドのパスは別問題です。コマンドが見つからないときは **絶対パス** を使ってください。

```bash
printf '%s' 'hello' | /path/to/repo/bin/agent-send user
```

## 4. ファイルの添付

### 原則

ファイルを参照するときは、**メッセージ本文に `[Attached: path]` と書く**。

### ガイドライン

| ガイドライン | 内容 |
| ------------ | ---- |
| **相対パス** | **workspace からの相対パス**を使う。絶対パスは正しく解決されないことがある |
| **独立した行** | `[Attached: docs/AGENT.md]` は単独の行に置くのがよい |
| **本文の中に** | 「添付しました」だけでは不十分。**`[Attached: ...]`** の形式が必須 |

良い例：

```bash
printf '%s' '変更を入れました。

[Attached: docs/AGENT.md]' | agent-send user
```

悪い例：

```bash
printf '%s' '変更を入れました。

[Attached: /absolute/path/to/docs/AGENT.md]' | agent-send user
```

---

## 5. `agent-index` でログを見る

### 会話履歴

```bash
agent-index
```

agent で絞り込み：

```bash
agent-index --agent codex
```

生の `jsonl` を読む場合の既定の場所：

```text
<MULTIAGENT_LOG_DIR>/<MULTIAGENT_SESSION>/.agent-index.jsonl
```

### 注意

```bash
agent-index --follow
```

これは **ブロックして終了しません**。安易に使わないでください。pane 内で実行するとその pane がロックされます。

---

## 6. Session Brief

この環境では `docs/AGENT.md` に加え、**session 単位の brief** を使えます。

役割の比較：

| 種類 | 役割 |
| ---- | ---- |
| `docs/AGENT.md` | リポジトリ / マルチエージェント環境向けの **恒久ルール** |
| session brief | **1 つの session に閉じた** 追加指示・テンプレート |

Brief は複数 agent に再利用できるテンプレートであり、agent ごとの設定ファイルではありません。

### 保存場所

Brief は通常、次の配下に保存されます：

```text
<log directory>/<session name>/brief/brief_<name>.md
```

例：

```text
logs/multiagent/brief/brief_default.md
logs/multiagent/brief/brief_strict.md
logs/multiagent/brief/brief_research.md
```

### ガイドライン

- Brief は **session スコープ** です。恒久ルールは可能なら `docs/AGENT.md` 側へ
- Brief は **再利用テンプレート** です。必要に応じて複数 agent に送る
- Brief の作成・更新は人間でも agent でもよい
- リポジトリ全体の恒久ルールを brief に溜め込まない

### UI とコマンド

- chat UI の `/brief` または `/brief set <name>` で保存済み brief の閲覧・編集
- Brief ボタンで、選択中の宛先に保存済み brief を送れる
- 閲覧・編集・送信は同じ brief ソースを参照する

---

## 7. Session、tmux、ログ

| 項目 | 内容 |
| ---- | ---- |
| 既定の session 名 | 多くの場合 `multiagent` |
| session の上書き | `MULTIAGENT_SESSION` または `agent-send --session <name>` |
| socket | `MULTIAGENT_TMUX_SOCKET` |
| ログの場所 | 多くの場合 `<log directory>/<session name>/.agent-index.jsonl` |
| workspace | `MULTIAGENT_WORKSPACE` |

複数の tmux session や複数 clone をまたぐときは、**socket** と **workspace** の取り違えに注意してください。

---

## 8. Agent 構成の変更

session 内の agent は、`multiagent` の既存サブコマンドで直接変更できます。chat 側で独自プロトコルを増やさないでください。

agent インスタンスを追加：

```bash
multiagent add-agent --agent claude
```

特定の実行中インスタンスを削除：

```bash
multiagent remove-agent --agent claude-2
```

メモ：

- `add-agent` は **`claude`、`codex`、`gemini` などのベース名** を取る
- `remove-agent` は **`claude`、`claude-2`、`codex-3` などのインスタンス名** を取る
- 稼働中の pane 内では `MULTIAGENT_SESSION` と `MULTIAGENT_TMUX_SOCKET` があるため `--session` は省略できることが多い
- 最後の 1 体の agent は削除できない
- 自分自身のインスタンスを削除すると、コマンド成功後すぐに pane が閉じる
- これらの変更は `.agent-index.jsonl` に `system` エントリとしても追記され、chat のタイムラインに topology 変更が残る

---

## 9. 最低限の運用フロー

1. `env | rg '^MULTIAGENT|^TMUX'` で session を確認する
2. `agent-send` で user または他の agent にメッセージを送る
3. ファイルを共有するときは本文に `[Attached: 相対パス]` を含める
4. `agent-index` または `.agent-index.jsonl` で履歴を確認する

---

## 10. 関連ドキュメント

| Path | 説明 |
| ---- | ---- |
| `README.md` | 概要とクイックスタート（英語） |
| `README_jp.md` | 概要とクイックスタート（日本語） |
| `docs/cloudflare-quick-tunnel.md` | Cloudflare quick tunnel のセットアップ |
| `docs/cloudflare-access.md` | Cloudflare Access で Hub を保護する |
| `docs/cloudflare-daemon.md` | 公開トンネルをデーモンとして動かす |

内部メモやエディタ / agent 向けの個別指示は別管理にし、公開向けの恒久ドキュメントから安易に参照しないでください。
