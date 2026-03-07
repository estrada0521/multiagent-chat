# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Multiagent 環境

あなたは **tmux セッション** 上で Claude・Codex・Gemini・Copilot と並行して動作しています。
セッション名: `multiagent`（環境変数 `MULTIAGENT_SESSION` でも確認可能）

## 他のエージェントにメッセージを送る

`agent-send` コマンドを使います。このコマンドはすでに PATH に追加済みです。

```bash
agent-send <claude|codex|gemini|copilot|others|claude,codex> "メッセージ"
```

もし `agent-send` が見つからない場合は絶対パスで実行できます：

```bash
"${MULTIAGENT_BIN_DIR}/agent-send" <target> "メッセージ"
```

詳細は [AGENTS.md](./AGENTS.md) を参照してください。

## アーキテクチャ概要

このリポジトリは tmux ベースのマルチ AI エージェント実行環境です。

### 主なスクリプト (`bin/`)

| ファイル | 役割 |
|---------|------|
| `bin/multiagent` | 本体。tmux セッションの作成・管理・各 agent pane の起動を行う |
| `bin/multiagent-dev` | 実験用シンラッパー。実体は `bin/multiagent` に委譲する |
| `bin/agent-send` | 指定 target の tmux pane にメッセージを送信し、ログに記録する |
| `bin/agent-index` | 通信ログ (`agent-index.jsonl`) を表示・追尾する |
| `bin/multiagent-user-shell` | user pane 用のインタラクティブシェル起動スクリプト |

### セッション構造

- tmux セッション名 = デフォルトでカレントディレクトリ名
- 各 agent (claude / codex / gemini / copilot) は専用 pane で起動
- user pane は `--user-pane top|bottom|none` で制御（デフォルト: `top:1`）
- pane ID は tmux 環境変数 (`MULTIAGENT_PANE_CLAUDE` 等) に保存

### ログ構造

```
logs/
  <session>_<作成日yymmdd>_<更新日yymmdd>/
    claude.log      # 各 agent へ送ったメッセージ
    claude.ans      # 各 agent からの応答
    .agent-index.jsonl  # 全通信の構造化ログ
    .meta           # 詳細メタ情報
```

## 開発ルール

- `bin/multiagent` は **保護対象**。直接変更しない
- 新機能は `bin/multiagent-dev` にのみ追加する
- テストは専用セッション名（例: `multiagent-dev-test`）を使う

## テストコマンド

```bash
# 文法チェック
bash -n bin/multiagent-dev

# ヘルプ確認
bin/multiagent-dev --help

# 基本動作確認
bin/multiagent-dev list
bin/multiagent-dev status

# 分離起動テスト
bin/multiagent-dev --session multiagent-dev-test --agents codex --log-dir "$PWD/logs-dev-test" --detach

# 後始末
bin/multiagent-dev kill --session multiagent-dev-test
```

詳細は [MULTIAGENT_DEV_TESTING.md](./MULTIAGENT_DEV_TESTING.md) を参照。

## `multiagent` サブコマンド一覧

```
list [--verbose]          現在の workspace に紐づくセッション一覧
status [--all]            セッション状態表示
resume [--latest]         既存セッションに再アタッチ
kill [--all]              セッション削除
rename --to <name>        セッション名変更
brief [--session NAME]    各 agent へ通信機能の説明を送信
```

## user pane のショートカット（`multiagent-user-shell` 内）

```bash
brief [session]   # agent-send で brief を送る
follow            # agent-index --follow
idx               # agent-index
kill              # 現在セッションを kill
```
