# Multiagent 環境

あなたは **tmux セッション** 上で Claude・Codex・Gemini・Copilot と並行して動作しています。
セッション名: `multiagent`（環境変数 `MULTIAGENT_SESSION` でも確認可能）

## 他のエージェントにメッセージを送る

`agent-send` コマンドを使います。このコマンドはすでに PATH に追加済みです。

```bash
agent-send <claude|codex|gemini|copilot|all> "メッセージ"
```

もし `agent-send` が見つからない場合は絶対パスで実行できます：

```bash
"${MULTIAGENT_BIN_DIR}/agent-send" <target> "メッセージ"
```

詳細は [AGENTS.md](./AGENTS.md) を参照してください。
