# Multiagent 環境: エージェント向けガイド

この文書は、このリポジトリの **tmux ベース multiagent セッション内で動くエージェント**向けの運用メモです。

> **優先順位:** チャット、プロジェクト固有指示、エディタ内指示、システム指示に矛盾がある場合は、常にそちらを優先する。

---

## 1. 最初に把握すること

この環境では、エージェントは通常それぞれ独立した tmux pane で動く。
ユーザーや他エージェントへの返答は、pane に直接打つのではなく **`agent-send` で送る**。

まず最低限、次を確認する。

```bash
env | rg '^MULTIAGENT|^TMUX'
```

ここで分かる主な情報:

| 変数 | 意味 |
|------|------|
| `MULTIAGENT_SESSION` | 現在のセッション名 |
| `MULTIAGENT_AGENT_NAME` | 自分のエージェント名 |
| `MULTIAGENT_AGENTS` | 参加エージェント一覧 |
| `MULTIAGENT_WORKSPACE` | ワークスペース |
| `MULTIAGENT_LOG_DIR` | ログディレクトリ |
| `MULTIAGENT_TMUX_SOCKET` | tmux ソケット |
| `MULTIAGENT_PANE_*` | 各エージェント・ユーザーの pane ID |
| `TMUX_PANE` | 自分の pane ID |

現在のセッション構成を機械的に見たいときは:

```bash
multiagent context --json
```

`multiagent context` が失敗する場合は `MULTIAGENT_SESSION` がずれていることがある。その場合は `--session <name>` を付けるか、環境変数を確認する。

---

## 2. コミュニケーションの原則

### 必ず守ること

| ルール | 内容 |
|--------|------|
| **返答経路** | **`user` や他エージェントへの返答は必ず `agent-send` で送る**。pane にユーザー向け本文を直接出さない |
| **返信の紐付け** | **明確に特定メッセージへの返信なら `--reply <msg-id>` を付ける** |
| **`msg-id` の扱い** | `msg-id` を毎回暗記しておく必要はない。分からない、拾えない、曖昧なときは `--reply` を省略してよい |
| **本文の渡し方** | 特殊文字や改行を壊さないため、本文は **stdin で渡す** |
| **添付の書き方** | ファイル添付はオプションではなく、本文に **`[Attached: relative/path]`** と書く |

### 基本形

```bash
printf '%s' '本文' | agent-send --stdin <target>
```

宛先例:

- `user`
- `claude`
- `codex`
- `gemini`
- `claude,codex`

返信にする場合:

```bash
printf '%s' '対応しました。' | agent-send --reply <msg-id> --stdin user
```

---

## 3. `agent-send` の実践

### `user` へ返信する

```bash
printf '%s' '[From: codex] 確認しました。' | agent-send --reply <msg-id> --stdin user
```

### 他エージェントへ送る

```bash
printf '%s' '[From: codex] 該当箇所はここです。' | agent-send --stdin gemini
```

### 新規トピックとして送る

```bash
printf '%s' '[From: codex] 追加調査を始めます。' | agent-send --stdin user
```

### PATH が通っていないとき

`[Attached: ...]` の話と、`agent-send` コマンド自体のパスの話は別です。コマンドが見つからないだけなら、**コマンドの絶対パス**で呼ぶ。

```bash
printf '%s' 'hello' | /path/to/repo/bin/agent-send --stdin user
```

### `[From: ...]` ヘッダについて

先頭の `[From: ...]` は、プロジェクトやセッションのルールがあればそれに従う。

- 同じ pane 名で送るなら、本文先頭に `[From: codex]` のように書けば十分なことが多い
- 別名を明示したいツールでは、`MULTIAGENT_AGENT_NAME` を送信側 `agent-send` に渡す必要があることがある

例:

```bash
export MULTIAGENT_AGENT_NAME=cursor
printf '%s' '[From: cursor] 更新しました。' | agent-send --reply <msg-id> --stdin user
```

`MULTIAGENT_AGENT_NAME=... printf ... | agent-send ...` のように **`printf` 側だけ**に付けても、パイプ右側の `agent-send` には渡らないので注意。

---

## 4. 添付ファイルの書き方

### 原則

`agent-send` に `--attach` のような添付専用オプションはない。**本文中に `[Attached: path]` を書く**のが正規手順。

### 守るべき点

| 方針 | 内容 |
|------|------|
| **相対パス** | **ワークスペース相対で書く**。絶対パスはうまく解決されないことがある |
| **単独行** | `[Attached: docs/AGENT.md]` は単独行で置くと安定しやすい |
| **本文に含める** | 「Attached と書くだけ」ではだめ。**`[Attached: ...]` の形そのもの**が必要 |

良い例:

```bash
printf '%s' '[From: codex] 変更しました。

[Attached: docs/AGENT.md]' | agent-send --reply <msg-id> --stdin user
```

避けたい例:

```bash
printf '%s' '[From: codex] 変更しました。

[Attached: /absolute/path/to/docs/AGENT.md]' | agent-send --stdin user
```

---

## 5. `agent-index` とログの見方

### 会話履歴を見る

```bash
agent-index
```

特定エージェントだけを見る:

```bash
agent-index --agent codex
```

`jsonl` を直接読む場合、通常の保存先は次です。

```text
<MULTIAGENT_LOG_DIR>/<MULTIAGENT_SESSION>/.agent-index.jsonl
```

### 重要な注意

```bash
agent-index --follow
```

これは**ブロックして戻らない**ので、調査目的で常用しない。特に pane 内で実行すると、その pane を張り付かせやすい。

### `msg-id` を探したいとき

- 受信メッセージのヘッダ `[From: sender | msg-id: ...]` を見る
- `agent-index` や `.agent-index.jsonl` を検索する
- 必要なら `rg` でログを引く

例:

```bash
rg -n 'msg-id|reply-to|docs/AGENT.md' logs/multiagent/.agent-index.jsonl
```

---

## 6. セッション・tmux・ログ

| 項目 | 内容 |
|------|------|
| 既定セッション名 | 通常は `multiagent` |
| 別セッション指定 | `MULTIAGENT_SESSION` または `agent-send --session <name>` |
| ソケット | `MULTIAGENT_TMUX_SOCKET` |
| ログ保存先 | 通常は `<ログディレクトリ>/<セッション名>/.agent-index.jsonl` |
| ワークスペース | `MULTIAGENT_WORKSPACE` |

tmux や複数クローンをまたいで作業しているときは、**ソケット**と**ワークスペース**の取り違えに注意する。

---

## 7. 最低限の運用フロー

1. `env | rg '^MULTIAGENT|^TMUX'` で自分のセッションを確認する
2. 受信メッセージの `msg-id` を読む
3. 返信なら `agent-send --reply <msg-id> --stdin ...` で返す
4. ファイルを共有するなら本文に `[Attached: relative/path]` を入れる
5. 履歴確認は `agent-index` か `.agent-index.jsonl` を使う

---

## 8. 関連ドキュメント

| パス | 内容 |
|------|------|
| `docs/cursor-to-user-chat.md` | Cursor から user へ返す最小例 |
| `.github/copilot-instructions.md` | multiagent 全般の補助指示 |
