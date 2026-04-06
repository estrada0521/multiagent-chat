# multiagent-chat beta 1.0.6

English version: [beta-1.0.6.md](beta-1.0.6.md)

公開日: 2026-04-06

このリリースは `beta 1.0.5` 以降の変更をまとめたもので、メッセージ配送方針の根本的な転換を含みます。

## 主な更新

### `agent-send user` を廃止

- `agent-send` の target は **agent 宛てのみ**（`others`、base 名、instance 名、fan-out）になりました。
- `agent-send user` を実行すると、移行ガイダンス付きの明示エラーを返します。
- session briefing、`agent-help`、agent guide ドキュメントを新方針に合わせて全面更新しました。

### 人間向けの会話を event-log-first で取り込む経路へ統一

- 人間向け返信は pane 上の通常 assistant 出力とし、native event log から index する方針に切り替えました。
- chat `/send` は `agent-send user` を経由せず、target pane への直接配送と user 送信 entry の JSONL 追記を行います。
- `/memo` は `targets=["user"]` の entry を JSONL に直接書く形で維持しています。

### session JSONL の正本経路を標準化し、耐障害性を強化

- `MULTIAGENT_INDEX_PATH` を基準に canonical path を優先する運用へ統一しました。
- workspace 側の経路は symlink mirror + migrate 時の merge で追随させます。
- 自己参照 symlink を含む破損 `.agent-index.jsonl` を検知・回復するガードと backup 復元を追加しました。

### Hub preview と同期安定性を改善

- Hub の latest preview は canonical index を優先して参照し、最新表示の不一致を抑えました。
- native log バインド時の claim 永続化を前倒しし、heartbeat と restart/resume 時の cache 無効化を追加しました。
- Cursor transcript fallback に git-root slug も加え、親子 workspace での取りこぼしを減らしました。

### ドキュメントを `beta 1.0.6` に更新

- README / site / full-readme / technical docs を新配送モデルに合わせて更新しました。
- 更新履歴 index の最新リンクを 1.0.6 へ差し替えました。
