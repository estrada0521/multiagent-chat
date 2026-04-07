# multiagent-chat beta 1.0.7

English version: [beta-1.0.7.md](beta-1.0.7.md)

公開日: 2026-04-07

このリリースは `beta 1.0.6` 以降の変更をまとめたもので、chat の安定性と thinking/runtime の可視性改善に重点を置いています。

## 主な更新

### thinking 判定を provider 横断と既存ログ読込に拡張

- 既存 `.agent-index.jsonl` の読込時に kind 推定を行うようになり、`I will ...` のような計画文をログ書き換えなしで `agent-thinking` として表示できます。
- Gemini は thought フラグ付き content part と、短い計画系プレフィックスの両方で `agent-thinking` に分類します。
- Qwen の thought-only assistant part はスキップせず `kind="agent-thinking"` として index します。
- Codex の reasoning payload（`response_item.reasoning` / `event_msg.agent_reasoning`）も `kind="agent-thinking"` として取り込みます。

### thinking 表示をシンプル化し、描画を堅牢化

- フロント側の thinking グループ統合表示（実験実装）を削除しました。
- `agent-thinking` は通常行として描画しつつ、文字サイズを小さめ・行間を狭めたコンパクト表示に統一しました。
- 同一 agent の `agent-thinking` が連続する場合、2件目以降はメタ行を非表示にして縦方向のノイズを削減します。
- 予期しない描画エラー時にチャット全体が空白化しないよう、防御的なフォールバック描画経路を追加しました。

### runtime と system event の見え方を改善

- Copilot の `apply_patch` runtime 表示は、パッチヘッダを解析して `Edit(path)` / `Create(path)` / `Delete(path)` のファイル単位表示に分解します。
- `/restart` と `/resume` は `kind="agent-control"` の system entry としてチャット履歴に記録されるようになりました。

### リンク色の役割を明確化

- 外部 URL は専用の赤系カラーで表示します。
- インラインのファイル参照リンクは既存のファイルリンク色を維持します。
