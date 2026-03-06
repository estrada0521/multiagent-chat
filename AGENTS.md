# Multiagent 環境

このワークスペースでは、tmux 上で Claude・Codex・Gemini・Copilot の4つの AI Agent が同時に動いています。

## 他のエージェントにメッセージを送る

```bash
agent-send <target> "メッセージ"
```

`agent-send` は現在の multiagent セッションを自動解決し、そのセッション内の pane にだけ送信します。別セッションを明示指定する機能はありません。
送信記録は各セッションのログフォルダ内の `.agent-index.jsonl` に保存され、`agent-index` で確認できます。
brief を送ると、各 agent には [`AGENT_BRIEFING.md`](/Users/okadaharuto/Library/CloudStorage/OneDrive-HiroshimaUniversity/OneDrive/test/multiagent/AGENT_BRIEFING.md) を読むよう指示されます。

`<target>` は以下のいずれか：

| target | 送信先 |
|--------|--------|
| `claude` または `1` | Claude |
| `codex` または `2` | Codex |
| `gemini` または `3` | Gemini |
| `copilot` または `4` | Copilot |
| `others` | 自分以外の全員 |
| `claude,codex` | 複数指定 |

### 例

```bash
# Claudeに質問する
agent-send claude "このコードのバグを見つけて"

# Copilotに依頼する
agent-send copilot "テストを書いて"

# 自分以外の全員に送る
agent-send others "作業完了を報告してください"

# 複数指定
agent-send claude,codex "確認してください"

# 通信履歴を見る
agent-index

# 通信履歴を追いかける
agent-index --follow

# 特定 agent 関連だけ見る
agent-index --agent codex
```
