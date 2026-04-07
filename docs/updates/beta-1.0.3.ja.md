# multiagent-chat beta 1.0.3

English version: [beta-1.0.3.md](beta-1.0.3.md)

公開日: 2026-04-01

このノートは、beta 1.0.2 のリリース準備を行った 2026-03-31 の commit `55220dd` 以降の変更をまとめたものです。

## 主な更新

### Hub 中心の PWA 導線が実用段階に入った

- install 済み Hub の通知から、単なる inbox 風バナーではなく元の session へ deep link で戻れるようになりました。
- local HTTPS の iPhone / iPad 向け導線を整理し、local PWA icon の更新や、LAN install でも外部 editor 連携が崩れにくい route 処理を入れました。
- 通知の受け口は引き続き 1 つの Hub install に集約しつつ、各 session chat は個別 install 不要の deep-link 先として扱えるようになっています。

### agent 自身が session topology を変えられるようになった

- agent は pane 内から `multiagent add-agent` と `multiagent remove-agent` を直接実行でき、現在の session と tmux socket を自動で使います。
- topology 変更は session ごとに直列化され、UI 側と agent 側から同時に add/remove が走っても instance 名や tmux state が競合しにくくなりました。
- 新しく増えた instance が `agent-send`、topology command、message format の流儀をすぐ確認できるよう、agent 向け helper も追加しました。

### chat UI の運用導線を強化した

- header menu から Finder と Pane Trace に直接入れるようになり、デスクトップでは terminal 本体に戻らなくても移動しやすくなりました。
- branch / worktree surface にはファイル単位の操作と worktree 全体 commit を追加し、commit の system entry も正しい agent に紐づくよう修正しました。
- file 参照はカテゴリタブ、件数、サイズ表示が入り、file menu とタブ列の挙動も見直しました。
- slash command picker は一度入れたカテゴリ分けを外し、再び軽い一覧型に戻して lookup を速くしました。
- auto-mode handling と worktree 側 UI も追って修正し、承認系の挙動や commit action のフィードバックを整理しました。

### Gemini direct bridge と live runtime hint

- tmux pane を経由しない Gemini direct chat bridge を追加し、probe 経路とその後の調整も入れて、chat UI から直接 Gemini を叩けるようにしました。
- thinking 行の下には、Codex / Gemini / Cursor の pane 出力から拾えた `Ran`、`Edited`、`ReadFile`、`Grepped` などの軽量 runtime hint を表示できるようになりました。
- slash command surface は再びシンプルに寄せ、runtime hint 行では tool keyword をより見やすく強調しています。

### docs と agent 向けガイドも拡充した

- `docs/gemini-direct-api.*` を追加し、direct runner、runtime JSONL sidecar、Gemini bridge の現時点の制約をまとめました。
- `docs/AGENT.md`、technical details、design philosophy も更新し、message routing、notification model、topology control を operator と agent の両視点で追えるようにしました。
- session に新しく入った agent が最短で流儀を掴めるよう、コマンド中心の `bin/agent-help` も追加しました。

## そのほか

- local PWA と app-bundle の reload 安定性を、LAN / installed-app の edge case を踏まえて再調整しました。
- worktree action、auto-mode handling、branch attribution には細かな修正をいくつも入れました。
- README、design philosophy、technical docs も更新し、Hub 中心の通知モデルと session topology 制御を追いやすくしました。
