# Multiagent 環境 概要

## 何これ？

複数の AI エージェント（Claude・Codex・Gemini・Copilot）を **tmux** 上で同時に動かし、チャット UI からまとめて操作できる開発支援環境です。

---

## 構成

```
┌─────────────────────────────────────────┐
│           ブラウザ（Chat UI）             │
│   http://localhost:8225  （PC / iPhone） │
└────────────────┬────────────────────────┘
                 │ HTTP
┌────────────────▼────────────────────────┐
│      agent-index --chat（Python）        │
│  ・メッセージ配信  ・ファイルビューア     │
│  ・エクスポート    ・ファイル補完         │
└────────────────┬────────────────────────┘
                 │ agent-send（tmux）
     ┌───────────┼───────────┐
     ▼           ▼           ▼
  claude      codex       gemini      copilot
  （tmux pane ごとに独立して動作）
```

---

## 主要コマンド

### セッション起動
```bash
multiagent start          # tmux セッション + チャットUI を起動
multiagent start mywork   # セッション名を指定
```

### エージェントへのメッセージ送信
```bash
# 基本（stdin が標準）
printf '%s' 'コードをレビューして' | agent-send --stdin claude
printf '%s' 'テスト書いて' | agent-send --stdin gemini,codex
printf '%s' '作業完了した？' | agent-send --stdin others

# 特定メッセージへの返信（スレッド維持）
printf '%s' '返信内容' | agent-send --reply <msg-id> --stdin claude
```

### チャット UI 確認
```bash
agent-index --chat          # ブラウザで開くチャット画面を起動
agent-index                 # メッセージ一覧をターミナルに表示
agent-index --agent claude  # Claude のログだけ表示
# ※ --follow は永久にブロックするので使わない
```

---

## チャット UI の機能

| 機能 | 説明 |
|------|------|
| メッセージ送信 | 下部コンポーザーから全エージェントまたは特定エージェントに送信 |
| ターゲット選択 | チップ形式で送信先を複数選択可能 |
| ファイル添付 | `@` を入力するとファイル補完ドロップダウンが出現 |
| 添付ファイル一覧 | ヘッダーの 📁 ボタンで会話内の添付ファイルを一覧表示・閲覧 |
| Thinking パネル | エージェント名タップで処理中の出力をリアルタイム表示 |
| エクスポート | 右メニュー → Export で完全スタンドアロン HTML を生成 |
| 検索・フィルター | エージェント別フィルター + キーワード検索 |
| Auto モード | 確認ダイアログを自動承認するモニター機能 |
| iPhone 対応 | 同 WiFi の iPhone Safari からアクセス可能 |

---

## ファイル添付

メッセージに `[Attached: path/to/file]` を含めると、チャット UI でファイルカードとして表示され、クリックでビューアが開きます。

```bash
printf '%s' '[From: claude] 結果です [Attached: output/result.py]' | agent-send --stdin user
```

---

## メッセージの記録

全メッセージは `logs/<session>/.agent-index.jsonl` に JSONL 形式で保存されます。

```json
{
  "timestamp": "2026-03-14 12:00:00",
  "sender": "claude",
  "targets": ["user"],
  "message": "...",
  "msg_id": "abc123"
}
```

---

## ディレクトリ構成

```
multiagent/
├── bin/
│   ├── multiagent          # セッション起動・管理スクリプト
│   ├── agent-index         # チャット UI サーバー（Python + HTML/JS 埋め込み）
│   ├── agent-send          # メッセージ送信スクリプト
│   └── multiagent-auto-mode  # 自動承認モニター
├── logs/
│   └── <session>/
│       ├── .agent-index.jsonl  # 全メッセージログ
│       ├── claude.log          # Claude ペインの出力
│       ├── gemini.log          # Gemini ペインの出力
│       └── ...
└── CLAUDE.md               # Claude 向け環境設定
```

---

## エージェント間の協調

各エージェントは独立した tmux pane で動いており、互いに `agent-send` でメッセージを送り合えます。ユーザーは Chat UI から全体を俯瞰しながら、タスクを各エージェントに割り振ったり、成果物を確認したりします。

```
User ──→ claude  "設計してください"
claude ──→ codex "この設計でテストを書いて"
codex  ──→ user  "テスト書きました [Attached: test.py]"
```

---

## ポート番号

ポートはセッション名の MD5 から決定論的に計算されます：

```
port = 8200 + (MD5(session_name) % 700)
```

同じセッション名なら常に同じポートになるため、iPhone のブックマークが使い回せます。

---

## Hub

複数のセッションを横断して管理する**コントロールパネル**です。

```bash
agent-index --hub          # Hub サーバーを起動（ポート 8788 固定）
agent-index --hub-port N   # ポートを変更して起動
```

ブラウザで `http://localhost:8788` を開くとアクセスできます（iPhone 同 WiFi 可）。

### ページ構成

| ページ | URL | 内容 |
|--------|-----|------|
| Hub | `/` | ホーム。Resume / Stats / Settings へのナビゲーション |
| Resume Sessions | `/resume` | アクティブ・アーカイブ済みセッション一覧。タップでチャット UI を再起動して復帰 |
| Stats | `/stats` | 全セッション横断の統計（メッセージ数・コミット数・Thinking 時間・ワークスペース数など） |
| Settings | `/settings` | デフォルトテーマ・エージェントフォントモード・メッセージ表示件数などのグローバル設定 |

### Stats で見られる主な指標

- アクティブ / アーカイブ済みセッション数
- 総チャット数・総メッセージ数・総コミット数
- ワークスペース数
- エージェントごとの累計 Thinking 時間（`.thinking-time.json` から集計）

### Hub と Chat UI の違い

| | Chat UI | Hub |
|-|---------|-----|
| 用途 | 1 セッションのリアルタイム操作 | 複数セッションの管理・統計閲覧 |
| ポート | セッション名の MD5 から自動計算 | 固定 8788 |
| 起動 | `agent-index --chat` | `agent-index --hub` |
