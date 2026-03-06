# Multiagent 環境

このワークスペースでは、tmux 上で Claude・Codex・Gemini・Copilot の4つの AI Agent が同時に動いています。

## 他のエージェントにメッセージを送る

```bash
agent-send <target> "メッセージ"
```

`<target>` は以下のいずれか：

| target | 送信先 |
|--------|--------|
| `claude` または `1` | Claude |
| `codex` または `2` | Codex |
| `gemini` または `3` | Gemini |
| `copilot` または `4` | Copilot |
| `all` | 全員 |

### 例

```bash
# Claudeに質問する
agent-send claude "このコードのバグを見つけて"

# Copilotに依頼する
agent-send copilot "テストを書いて"

# 全員に送る
agent-send all "作業完了を報告してください"
```
