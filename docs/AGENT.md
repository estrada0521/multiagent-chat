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

この文書や、workspace 側の `docs/AGENT.md` を user から送られて読んだ場合は、読み終えたあとに **内容を把握したことを user へ 1 回報告する**。報告も pane 直打ちではなく `agent-send` で送る。

例:

```bash
printf '%s' '[From: codex] docs/AGENT.md を読みました。この環境での返答経路、--reply、添付、ログ参照の前提を把握しました。' | agent-send --reply <msg-id> user
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
| **複数行本文** | 箇条書きやコードブロックのような **複数行 Markdown は heredoc で `agent-send` に流す**。`\n` を含む 1 行文字列 `printf` に無理やり詰めない |

### 基本形

```bash
printf '%s' '本文' | agent-send <target>
```

宛先例:

- `user`
- `claude`
- `codex`
- `gemini`
- `claude,codex`

返信にする場合:

```bash
printf '%s' '対応しました。' | agent-send --reply <msg-id> user
```

複数行の本文を安全に送る場合:

~~~bash
cat <<'EOF' | agent-send --reply <msg-id> user
[From: codex] 確認しました。

1. 1点目
2. 2点目

```bash
rg -n "agent-send" docs/AGENT.md
```
EOF
~~~

この形なら、改行、バッククォート、箇条書き、`[Attached: ...]` を壊しにくい。

---

## 3. `agent-send` の実践

### `user` へ返信する

```bash
printf '%s' '[From: codex] 確認しました。' | agent-send --reply <msg-id> user
```

### 他エージェントへ送る

```bash
printf '%s' '[From: codex] 該当箇所はここです。' | agent-send gemini
```

### 新規トピックとして送る

```bash
printf '%s' '[From: codex] 追加調査を始めます。' | agent-send user
```

### PATH が通っていないとき

`[Attached: ...]` の話と、`agent-send` コマンド自体のパスの話は別です。コマンドが見つからないだけなら、**コマンドの絶対パス**で呼ぶ。

```bash
printf '%s' 'hello' | /path/to/repo/bin/agent-send user
```

### `[From: ...]` ヘッダについて

先頭の `[From: ...]` は、プロジェクトやセッションのルールがあればそれに従う。

- 同じ pane 名で送るなら、本文先頭に `[From: codex]` のように書けば十分なことが多い
- 別名を明示したいツールでは、`MULTIAGENT_AGENT_NAME` を送信側 `agent-send` に渡す必要があることがある

例:

```bash
export MULTIAGENT_AGENT_NAME=cursor
printf '%s' '[From: cursor] 更新しました。' | agent-send --reply <msg-id> user
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

[Attached: docs/AGENT.md]' | agent-send --reply <msg-id> user
```

避けたい例:

```bash
printf '%s' '[From: codex] 変更しました。

[Attached: /absolute/path/to/docs/AGENT.md]' | agent-send user
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

## 6. Session Brief

この環境では、`docs/AGENT.md` とは別に **session 固有 brief** を持てる。

役割の違い:

| ファイル種別 | 役割 |
|------|------|
| `docs/AGENT.md` | repo / multiagent 環境の**恒久ルール** |
| session brief | その session だけで使う**追加指示・テンプレート** |

session brief は、**特定 agent 固有の設定**というより、session 内で再利用できる brief テンプレート群として扱う。

### 保存先

通常は次のように保存される:

```text
<ログディレクトリ>/<セッション名>/brief/brief_<name>.md
```

例:

```text
logs/multiagent/brief/brief_default.md
logs/multiagent/brief/brief_strict.md
logs/multiagent/brief/brief_research.md
```

### 運用方針

- brief は **session 固有**。恒久ルールはできるだけ `docs/AGENT.md` に寄せる
- brief は **再利用可能なテンプレート**。必要に応じて複数 agent に送ってよい
- brief は人間が作ってもよいし、必要なら **エージェントが作成・更新してもよい**
- ただし、repo 全体で通用する常設ルールを brief に溜めすぎない

### UI とコマンド

- chat UI の `/brief` や `/brief set <name>` は、保存済み brief の表示・編集に使う
- Brief ボタンは、保存済み brief から選んで selected target に送るために使う
- つまり、**表示・編集・送信は同じ brief 正本を参照する**

---

## 7. セッション・tmux・ログ

| 項目 | 内容 |
|------|------|
| 既定セッション名 | 通常は `multiagent` |
| 別セッション指定 | `MULTIAGENT_SESSION` または `agent-send --session <name>` |
| ソケット | `MULTIAGENT_TMUX_SOCKET` |
| ログ保存先 | 通常は `<ログディレクトリ>/<セッション名>/.agent-index.jsonl` |
| ワークスペース | `MULTIAGENT_WORKSPACE` |

tmux や複数クローンをまたいで作業しているときは、**ソケット**と**ワークスペース**の取り違えに注意する。

---

## 8. 最低限の運用フロー

1. `env | rg '^MULTIAGENT|^TMUX'` で自分のセッションを確認する
2. 受信メッセージの `msg-id` を読む
3. 返信なら `agent-send --reply <msg-id> ...` で返す
4. ファイルを共有するなら本文に `[Attached: relative/path]` を入れる
5. 履歴確認は `agent-index` か `.agent-index.jsonl` を使う

---

## 9. 関連ドキュメント

| パス | 内容 |
|------|------|
| `README.md` | public 向けの概要と起動方法 |
| `docs/cloudflare-quick-tunnel.md` | public 公開まわりの基本手順 |
| `docs/cloudflare-access.md` | public Hub を Cloudflare Access で保護する方法 |
| `docs/cloudflare-daemon.md` | public tunnel の常駐運用 |

internal な補助メモや editor / agent 固有の指示ファイルは、必要なら別管理にする。public 向けの恒久文書からは安易に参照しない。
