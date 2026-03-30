# multiagent-chat beta 1.0.2

English version: [beta-1.0.2.md](beta-1.0.2.md)

公開日: 2026-03-31

このノートは、beta 1.0.1 の更新ノートを追加した 2026-03-29 の commit `595bf9a` 以降の変更をまとめたものです。

## 主な更新

### installable Hub と background notification

- Hub と chat に installable manifest と共通 service worker が入り、HTTPS 配信時は Home Screen / browser app shelf に追加できるようになりました。
- Hub Settings に `App Install & Notifications` ブロックを追加し、install 案内、通知 permission、test notification をまとめて扱えるようにしました。
- browser notification は Hub 中心に集約され、1 つの Hub install で active session 全体の background agent reply を受け取れるようになりました。
- Apple Web Push 配信は、VAPID subject を実在 host ベースに切り替え、Safari / WebKit subscription で通る CA bundle を使うようにして安定化しました。

### Chat の動き、scroll、Pane Trace の磨き込み

- agent reply の streaming reveal を引き締め、その後も scroll lock や anchor 復元を繰り返し修正して、新着 message で viewport が引っ張られにくくなりました。
- 埋め込み Pane Trace と popup Pane Trace は、overflow tab、font size、狭幅レイアウト、モバイル側のグレー背景、badge / icon 位置合わせまで含めて desktop / mobile 両方で何度も調整しました。
- agent instance icon は base agent icon を共有しつつ numeric subscript を載せる形になり、message spacing、gutter、thinking indicator 周辺の見た目も整理しました。
- Hub / chat には `Bold mode` setting も追加しました。

### 安定性、セキュリティ、内部整理

- `agent-send` は JSONL 書き込み時に flock を取り、成功した delivery だけを記録するようにしました。
- pane reset 検知は content hashing ベースに強化し、app-bundle refactor 後の reload-safe external chat bundle も復旧しました。
- inline Python の command injection リスクを塞ぎ、bash / Python の複数経路で error handling を厳しめにしました。
- chat の HTML template を生成済み asset blob から切り出し、front-end の改修や復旧作業を追いやすくしました。

### セットアップ、CLI 対応、docs

- quickstart は Kimi CLI の導入まで扱うようになり、README でも実運用前に必要な 1 回の `kimi login` を明記しました。
- README に更新 / 削除手順と堅牢性セクションを追加しました。
- 技術詳細、更新ノート、実装寄り docs を拡充し、現在の Hub / chat / tmux 復旧モデルを追いやすくしました。

## そのほか

- `.cursor/` を既定で ignore するようにしました。
- 使われていない UI 残骸や空の overview file も整理しました。
- mobile / desktop 全体の見直しの流れの中で、header や action surface の細かな polish も進めました。
