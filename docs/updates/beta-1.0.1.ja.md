# multiagent-chat beta 1.0.1

English version: [beta-1.0.1.md](beta-1.0.1.md)

公開日: 2026-03-29

このノートは、README に最初に `beta 1.0` と記載した 2026-03-26 の commit `941ce5b` 以降の変更をまとめたものです。

## 主な更新

### Pane Trace と session 表示

- デスクトップでは thinking 行から専用の Pane Trace popup を開けるようになりました。
- popup 側は横幅、タブ、split 表示、window 単位の扱いが整理され、Pane Trace viewer としてかなり使いやすくなりました。
- モバイル Pane Trace は、PC popup に寄せたグレー背景を含めて見た目を揃え直しました。
- tmux session の厳密一致と Pane Trace の agent 切り替えまわりを見直し、別 session 取り違えのリスクを減らしました。
- iOS の dot 描画や popup 周辺の細かな表示崩れも修正しました。

### Chat の速度と Reload 安定性

- chat 描画は一括読み込みから message の逐次読み込みへ寄せ、2000 件規模を作業範囲として扱えるようにしました。
- 共通の chat CSS / JS を外出しし、任意 vendor は lazy-load 化し、local/public の両経路で同じ逐次読み込みロジックを共有して初回ページ負荷も下げました。
- public 側の Reload が local 側の Hub や chat を巻き込まないようにしました。
- branch overview は一括取得ではなく逐次読み込みになりました。

### Composer、添付、message 体験

- Import カードは送信前に popup から rename / label 指定できるようになりました。
- rename した upload は chat 上でも選んだラベルを保ち、従来の timestamp prefix 付き命名は落とすようにしました。
- message の出現アニメーションとモバイルの scroll pinning を見直し、送信直後の不安定さを減らしました。
- code block には copy button が付き、scrollbar layout と shell variable 周辺の数式レンダリングも安全寄りに修正しました。
- attach autocomplete で hidden file を再び拾えるようにし、3D preview も復旧しました。

### 安定性とセットアップ

- tmux timeout を単純な「session 消失」と見なさず、不調状態として扱うようにし、過剰な auto-revive を防ぐようにしました。
- pane log の autosave は、capture が一時的に短くなっても既存内容を消しにくいようにしました。
- 新規 session 作成時は、その時点の repo の `docs/AGENT.md` を `workspace/docs/AGENT.md` に反映するようにしました。
- duplicate agent instance、古い Python、Grok の readiness/auth 判定、tmux socket 復旧まわりも相性改善を入れました。

### Local HTTPS、public access、docs

- quickstart と Hub に local HTTPS onboarding を追加し、`mkcert` 案内や追加 SAN 指定にも対応しました。
- public access、chat command、design philosophy、technical details の docs を拡充しました。
- README は英語版を基準に整理しつつ、日本語 README を並行して用意し、相互リンクも明確にしました。

## そのほか

- pane 直送用の composer command を追加しました。
- branch menu で未コミット差分の要約も見えるようになりました。
- session / Pane Trace まわりの screenshot も現在の UI に合わせて更新しました。
