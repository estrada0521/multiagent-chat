# マルチエージェント環境: Agent 向けガイド

このドキュメントは、このリポジトリの **tmux ベースのマルチエージェント session で動作する agent** のための操作リファレンスです。

> **優先順位:** chat の指示、プロジェクト固有の指示、エディタレベルの指示、システム指示とこのドキュメントの間で矛盾がある場合は、常にそれらの指示をこのドキュメントより優先してください。

---

## 1. 最初に知るべきこと

この環境では、各 agent は通常独自の tmux pane で動作します。
人間向けの返信は、この pane での通常の assistant 出力として返してください（native event log が直接 index されます）。**`agent-send` は他 agent 宛てルーティング専用**です。

まずは基本を確認してください：

```bash
env | rg '^MULTIAGENT|^TMUX'
```

このドキュメント（または workspace 側の `docs/AGENT.md` / `docs/AGENT.ja.md`）を user から受け取った場合は、**一度だけ** 読んで理解したことを通常の assistant 応答で報告してください。

後でコンパクトなコマンドチートシートだけが必要な場合は、次を実行してください：

```bash
agent-help
```

例：

`docs/AGENT.ja.md を読みました。メッセージの届け方とログの扱いを理解しました。`

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
| **Hub に載せる配送** | 人間向け返信は pane の通常 assistant 出力で返す。**`agent-send` は他 agent 宛てのみ** |
| **メッセージ本文** | 特殊文字や改行を壊さないよう、本文は **stdin 経由** で渡す |
| **`$` を含む語** | シェル変数・パスなど **`$` を含む語はバッククォートでインラインコード化**する。さもないと Hub 上で数式として解釈される。例: `` `$HOME` ``、`` `$PATH` `` |

### 基本形

```bash
printf '%s' 'message body' | agent-send <target>
```

target の例：

- `claude`
- `codex`
- `gemini`
- `claude,codex`

---

## 3. `agent-send` の使い方（agent 間専用）

### 人間向け返信

人間向けの返信は pane の通常 assistant 出力で返します。`agent-send user` は使いません。

### 別の agent へ送る

```bash
printf '%s' '該当箇所はこちらです。' | agent-send gemini
```

### PATH に `agent-send` がない場合

コマンドが見つからないときは **絶対パス** を使ってください。

```bash
printf '%s' 'hello' | /path/to/repo/bin/agent-send gemini
```

## 4. `agent-index` でログを見る

### 会話履歴

```bash
agent-index
```

agent で絞り込み：

```bash
agent-index --agent codex
```

生の `jsonl` を読む場合は、まず次を優先します：

```text
<MULTIAGENT_INDEX_PATH>
```

### 注意

```bash
agent-index --follow
```

これは **ブロックして終了しません**。安易に使わないでください。pane 内で実行するとその pane がロックされます。

---

## 5. Session、tmux、ログ

| 項目 | 内容 |
| ---- | ---- |
| 既定の session 名 | 多くの場合 `multiagent` |
| session の上書き | `MULTIAGENT_SESSION` または `agent-send --session <name>` |
| socket | `MULTIAGENT_TMUX_SOCKET` |
| ログの場所 | canonical は `MULTIAGENT_INDEX_PATH`（workspace 側は symlink mirror の場合あり） |
| workspace | `MULTIAGENT_WORKSPACE` |

複数の tmux session や複数 clone をまたぐときは、**socket** と **workspace** の取り違えに注意してください。

---

## 6. Agent 構成の変更

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

## 7. 最低限の運用フロー

1. `env | rg '^MULTIAGENT|^TMUX'` で session を確認する
2. 人間向け返信は通常 assistant 出力、他 agent 宛てのみ `agent-send`
3. shell 変数やパスに `$` を含む語はインラインコード化する
4. `agent-index` または `.agent-index.jsonl` で履歴を確認する

---

## 8. 関連ドキュメント

| Path | 説明 |
| ---- | ---- |
| `README.md` | ローカル用概要とクイックスタート（英語） |
| `README_jp.md` | ローカル用概要とクイックスタート（日本語） |
| `docs/design-philosophy.md` | この workbench の設計方針 |
| `docs/technical-details.md` | 内部構造、配送、保存形式の詳細 |

内部メモやエディタ / agent 向けの個別指示は別管理にし、公開向けの恒久ドキュメントから安易に参照しないでください。
