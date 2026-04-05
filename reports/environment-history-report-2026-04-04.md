# Multiagent 環境構築史レポート

改訂:
- 2026-04-04 expanded edition

対象:
- `logs/multiagent/.agent-index.jsonl`
- `docs/design-philosophy.md`
- `docs/design-philosophy.en.md`
- core scripts / docs の git 履歴

作成:
- codex-1

ダブルチェック:
- gemini-1 による独立観点レビューを反映済み
- claude による独立観点レビューを反映済み

## 1. 要約

このレポートの結論を先に言うと、`multiagent-local` の歴史は単なる chat UI 改修史ではない。実際には、以下の順序で環境が拡張・再定義されている。

1. tmux を低レベル実行基盤として使う multiagent substrate
2. `agent-send` と session 単位 JSONL ログ
3. `agent-index --chat` による chat-first な人間側 UI
4. brief / memory / save log / trace / file preview を備えた運用 UI
5. Hub による session lifecycle 管理
6. iPhone / mobile を前提とした UI と HTTPS / LAN アクセス
7. Tailscale / Cloudflare / public edge による外部到達性
8. add-agent / remove-agent / multiple instances / revive による動的 topology
9. voice / camera / pane trace / remote access による physical-world 接続
10. pane/surface 境界、mobile browser reality、state preservation で繰り返される堅牢化

さらに重要なのは、`docs/design-philosophy.md` / `docs/design-philosophy.en.md` がこの進化の「出発点」ではなく、かなりの部分が実装された後に、その方向性を言語化・正当化・整理するために追加された文書だという点である。したがって、この環境の歴史は

- 先に実装が走り
- 途中で設計思想が文章化され
- その後、その思想が新しい実装を解釈する枠組みとして使われる

という順序で読むのが最も正確である。

また、本レポートは最新日付を特権化しない。3/6-3/8 の基盤成立、3/8-3/10 の trace / mobile / file preview の泥臭い修正、3/13-3/16 の Hub 抽出と multiple instances、3/19-3/25 の public reach / registry / topology、3/26-3/31 の AGENT / philosophy / stdin-only transport / PWA、4/4 の camera mode と revive hardening は、いずれも対等な価値を持つフェーズとして扱う。

## 2. ソースと信頼度

このレポートは 3 種類のソースを突き合わせている。

### 2.1 主要ソース

- `logs/multiagent/.agent-index.jsonl`
  - 期間: `2026-03-08 01:26:27` から `2026-04-04 19:13:17`
  - 総レコード数: 20,431
- `docs/design-philosophy.md`
  - 設計思想の日本語版
- `docs/design-philosophy.en.md`
  - 設計思想の英語版
- git 履歴
  - とくに `bin/multiagent`, `bin/agent-send`, `bin/agent-index`, `docs/design-philosophy.md`, `docs/design-philosophy.en.md` の履歴

### 2.2 信頼度の層

- 高信頼:
  - JSONL 内の timestamp 付き会話
  - system の commit 通知
  - git の commit date と commit title
- 中信頼:
  - 会話から復元される「なぜその修正が必要だったか」という因果
- 低信頼:
  - 実装意図を思想文書へどこまで意識的に対応づけていたかという心理的解釈

### 2.3 重要な制約

- JSONL の冒頭時点で環境はすでに存在している。
- 冒頭の user 発話が「session を kill して同名で revive したが覚えているか」であるため、完全な初回構築はログの前にある。
- ただし `2026-03-25 19:13-19:33` ごろに大量の過去 commit が system message として replay されており、そこに git 実日時を重ねることで前史はかなり復元できる。

## 3. 定量プロフィール

### 3.1 活動期間

- 対象期間: 28 日
- 最初の記録日: `2026-03-08`
- 最後の記録日: `2026-04-04`

### 3.2 発言者別レコード数

上位は次の通り。

- `user`: 9,017
- `codex`: 4,426
- `system`: 2,293
- `claude`: 1,641
- `gemini`: 1,030
- `copilot`: 684
- `cursor`: 577
- `codex-1`: 466
- `gemini-1`: 107
- `opencode`: 53
- `qwen`: 46

この分布から、環境の主開発者が user と codex であり、claude / gemini が補助実装・対案・検証に強く関与していたことが分かる。

### 3.3 日別活動量

日別件数の多い日は以下。

- `2026-03-25`: 1,901
- `2026-03-10`: 1,531
- `2026-03-12`: 1,257
- `2026-03-14`: 1,234
- `2026-03-09`: 1,184
- `2026-03-21`: 1,115
- `2026-03-29`: 1,105

`2026-03-25` が突出しているのは、過去 commit replay と registry / topology / docs / quickstart / transport 層の整備が重なっているためである。

### 3.4 system イベント数

system メッセージの集計から、運用がどこに集中していたかも見える。

- `Send Brief`: 133
- `Save Log`: 97
- `Save Memory`: 49
- `Load Memory`: 23

これは「brief / memory / log を分離して扱う layered records モデル」が理論ではなく、日常運用にまで入っていたことを示す。

### 3.5 user の指示先

user が直接多く指示していた相手は次の通り。

- `codex`: 3,842
- `claude`: 1,671
- `gemini`: 1,036
- `copilot`: 948
- `cursor`: 646
- `codex-1`: 478

この分布から見えるのは、user が agent を単なる並列 worker としてではなく、役割の違う相手として使い分けていたことである。`codex` / `codex-1` は主実装担当、`claude` と `gemini` は原因分析・独立レビュー・別案の確認先として使われる場面が多い。実際、3/25 の Hub / iframe 問題や 4/4 の revive 分析では、user 自身が「Gemini が解決した」「Claude にも振る」と明示的に routing している。

### 3.6 user 発話に現れる要求の型

user 発話に特定語がどれだけ出るかを見ると、要求の重心がかなりはっきり見える。

- `コミット`: 780
- `スマホ`: 496
- `もっと`: 211
- `余白`: 209
- `戻して`: 190
- `教えて`: 161
- `原因`: 114

この数字は重要である。ここで driving force になっているのは、抽象的な「新機能が欲しい」だけではない。

- まず commit checkpoint を頻繁に要求する
- mobile / smartphone で実際に使えることを執拗に要求する
- spacing / padding / alignment を細かく詰める
- うまくいかなければ躊躇なく rollback を要求する
- 実装前に explanation や root cause を求める

つまり、この環境は「agent が勝手に育てた system」ではなく、user の反復的な要求、却下、差し戻し、言い換えに押されて形を獲得している。

## 4. 設計思想文書群そのものの成立史

`docs/design-philosophy.md` / `docs/design-philosophy.en.md` の履歴を突き合わせると、設計思想文書群の節目は次の通りである。

- `2026-03-27 06:14:50` `8626a7b` `docs: add design philosophy guide`
- `2026-03-31 10:36:01` `8815156` `feat(pwa): add notification deep links and update design philosophy`
- `2026-04-04 04:19:41` `cff0750` `docs: refresh readme and agent references`

ここから分かるのは次の 3 点である。

### 4.1 設計思想は「前提仕様」ではなく「後追いの結晶」

3 月 27 日の時点で、すでに以下は実装済みだった。

- multiagent scripts
- `agent-send`
- chat-based `agent-index`
- markdown rendering
- status / trace / reply / search / filter
- memory / brief / save log
- mobile 対応
- LAN access
- Hub の原型
- multiple instance への着手

つまり design philosophy は、ほぼ白紙の状態から未来像を示した文書ではなく、「すでにかなり育ってしまった環境が、何を目指しているのか」を整理し直すために追加された文書である。

### 4.2 3/31 更新は「多機能化は不純ではない」と明示する補強

3/31 の diff では、次の重要な一文が加わっている。

- `pure versus impure does not mean "few features" versus "many features."`

さらに、

- Hub
- structured logs
- session continuity
- mobile access

は anti-pure ではないと明示される。

これは 3/31 時点で PWA / install / notifications / deep links まで入り、表面的には環境がかなり「大きなアプリケーション」に見え始めたため、設計思想側が「多機能化そのものは思想に反しない」と定義し直したものだと読める。

### 4.3 3/31 更新で新設された「durable substrate vs temporary scaffolding」が重要

この更新で追加されたのが、

- `Do not confuse durable substrate with temporary scaffolding`

という節である。

これは単なる文言追加ではない。後述するように、3 月下旬から導入された

- dynamic topology
- registry
- agent-managed topology
- public edge / notifications / PWA

の増大が、単なる feature growth ではなく「どこまでが durable substrate で、どこからが今日のモデル都合の一時足場か」という線引きを必要とする段階に入ったことを意味している。

## 5. 前史: git 履歴から復元する 3/6-3/7

JSONL の前にある前史は、git 履歴からかなり正確に復元できる。

## 5.1 2026-03-06: substrate と transport の誕生

`bin/multiagent` と `bin/agent-send` の最初期履歴。

- `2026-03-06 19:15:55` `3c26f0a` `Initialize multiagent scripts`
- `2026-03-06 20:48:45` `4113e1c` `Refine multiagent dev session and messaging workflow`
- `2026-03-06 20:53:23` `c5764f6` `Fix agent-send for bash 3.2`
- `2026-03-06 20:59:40` `cf055c0` `Add agent message index`
- `2026-03-06 21:07:25` `703d497` `Store agent index under log directories`
- `2026-03-06 21:12:36` `c3441ed` `Store agent index inside session log folders`
- `2026-03-06 22:24:40` `7399d6e` `Record external agent-send messages as user`

この日で成立したのは、

- tmux-based session substrate
- thin message transport
- per-session structured logging

の 3 点である。

## 5.2 2026-03-07: chat-first への転換

- `2026-03-07 01:16:30` `01936cc` `Add chat-based agent index UI`
- `2026-03-07 01:54:43` `0344ff1` `Polish agent index chat view`
- `2026-03-07 03:34:37` `6d389c9` `Auto-open chat in user pane`
- `2026-03-07 03:59:52` `1466a11` `Fix agent-index chat startup fallback`

人間側の primary surface が pane grid ではなく chat に置き直されたのはこの日である。

## 5.3 2026-03-07 午後: 基本 UI と observability

- `608543b` Markdown rendering
- `3449d17` status panel
- `90b4048` pane diff ベース status 判定
- `a2d93e5` copy button
- `6ab5009` agent SVG icons

このあたりで、人間は raw pane を常時見なくても message stream から十分な観測ができるようになり始める。

## 5.4 2026-03-07 夜: 運用フローの原型

- `a1e531f` save command
- `ce188dd` `--fresh`
- `6c60482` auto-mode
- `22afc6d` thread/reply support
- `22b7da8` reply button
- `0340a51` jump highlight

すでにこの段階で

- start fresh
- save state
- auto-approve
- threaded conversation

が入っており、ただのログビューアではない。

## 6. 3/8 以降の詳細な生会話史

ここからは JSONL に実際のやり取りが残っている。

この章では commit や feature だけでなく、user が何を要求し、どの方向を拒否し、どの言い方で agent を押していたかも同時に見る。実際、この project は conversation-driven development の色が非常に強い。

## 6.1 2026-03-08 未明: first visible state

ログ冒頭時点で user はすでに revive 後の session を操作している。

最初の visible issue:

- composer 下の巨大な余白
- statusline の高さ
- shell の高さ計算

ここで重要なのは、最初から「session 全体を再起動する」のではなく「`agent-index --chat` のプロセスだけ再起動すれば UI 差分が反映する」という運用知識が出てくることだ。これは runtime substrate と human-facing view が分離していることを示す。

## 6.2 2026-03-08 01:45-03:00: Pane Trace 誕生

この時間帯は Pane Trace 機能の成立過程そのものになっている。

### 6.2.1 第一段階

- agent status を thinking / approval / running / idle に詳細化

### 6.2.2 第二段階

- その詳細化をやめて `running / idle` に戻す
- 代わりに status 行ホバーで pane 出力を見せる

### 6.2.3 第三段階

- `.ans` 末尾利用
- ANSI 色保持
- tooltip から固定プレビューへ
- hover 中の定期更新

### 6.2.4 第四段階: 不具合との戦い

この機能に伴い、次の根本原因が発見される。

- `capture-pane -e` による ANSI まわりの崩れ
- `capture-pane -J` による折り返し結合
- terminal width まで空白パディングされる tmux の挙動
- browser 側 `white-space` 設定との干渉
- `ansi_up` が dim をうまく処理しない

この時期の修正は、Pane Trace が「pane をそのまま見せる UI」ではなく、「pane という substrate を chat 側から観測するインターフェース」であることを示している。設計思想で言うなら、pane は execution layer であり、人間側 primary surface はあくまで chat である。

会話の流れとしても、これは user の要求変更に強く駆動されている。user は一度「アイドリング状態の詳細化」を振った後、すぐに「種類を分けるのではなく pane の出力をまんまトレースしたい」と方針を切り替え、さらに「右上は元の状態に戻して」と要求する。つまり Pane Trace は、開発側が思いついた補助機能ではなく、user が detail taxonomy を却下し、raw pane visibility を求めた結果として生まれた。

## 6.3 2026-03-08 昼: brief / memory / save log の制度化

この日から human-facing chat は本格的な operator console になる。

追加された主なもの:

- display limit `50 -> 500`
- `@` file autocomplete
- Memory
- Load Memory
- Save Memory
- Send Brief
- Save Log

発生した問題:

- `message is required`
- Enter が送られない
- Brief が 1 分かかる
- 特定 agent にしか届かない
- `SESSION_LOG_DIR` unbound
- `agent-send` が別 JSONL に書いて chat に出ない

ここで重要なのは、「brief」「memory」「log」が別個のレイヤとして UI に現れたことだ。これは後の design philosophy に書かれる layered records を先に実装していたことを意味する。

しかも発端は、user が「次回から同じミスが起こらないようにするため brief を調整できるか」と尋ねたことだった。つまり制度化の起点には、単なる convenience ではなく「同じ失敗を繰り返さない運用」を作りたいという user 側の意志がある。

## 6.4 2026-03-08 午後: 環境の自己記述

この日に作られた資料:

- `MULTIAGENT_DETAILED_GUIDE.md`
- `SELF_INTRO.md`

それぞれが説明している対象:

- session 管理
- `multiagent`
- `agent-send`
- `agent-index`
- `multiagent-auto-mode`
- `multiagent-user-shell`
- chat UI
- logs
- HTTP endpoints

つまり、この時点で環境は「使えるもの」から「説明可能なもの」へ移る。

## 6.5 2026-03-08 夕方: static export と LAN/mobile 化

### 6.5.1 static export

流れ:

- read-only snapshot を `/tmp` に生成
- `agent-index` の HTML/CSS/JS を流用した single HTML へ進化
- `target` ボタン再現
- CDN 依存除去
- `window.__EXPORT_PAYLOAD__` と trace 埋め込み

意味:

- session continuity は live process だけに依存しない
- 会話を durable artifact として外に持ち出せる

### 6.5.2 LAN/mobile

確定的な節目:

- `0.0.0.0` bind
- `Network access: http://192.168.x.x:PORT/`
- iPhone CSS
- 16px textarea

これは design philosophy の `Treat mobile as a precondition` を、文書化より前に実装で先取りした例である。

## 6.6 2026-03-08 夜から 2026-03-09: iPhone Safari の泥臭い現実

この時期は mobile が secondary client でないことの証明でもあり、同時に Safari が design ideal をどれだけ実装側へ圧力として返すかの記録でもある。

発生した課題:

- viewport unit のズレ
- horizontal overflow
- automatic zoom
- `visualViewport` 追従
- keyboard で shell が縮む
- HTTPS-Only で添付ファイルが開けない

対策:

- `100%` sizing
- `overflow-x: clip`
- `min-width: 0`
- modal file preview
- background / glass / layout の mobile 専用調整

design philosophy は mobile を precondition と言うが、実装史を見ると、その実現は大量の Safari 依存調整に支えられている。

ここで見逃せないのは、user が mobile を単なる viewport としてではなく、生活状況として語っている点である。`一階の部屋で Mac を閉じ、二階のベッドで Safari から戻りたい` という発話は象徴的で、mobile requirement は responsive CSS の話ではなく、「その場にいなくても session に戻れること」を意味している。

## 6.7 2026-03-09: 添付、ファイル閲覧、通知、音

3/9 は file / notification / composer UX の日である。

目立つ変化:

- file attachment viewer
- PDF の mobile 対応
- modal preview による HTTPS-Only 回避
- target selection persistence
- sound notifications
- Web Audio API 化
- reply / copy / message reveal の UX 微調整

このあたりは chat-first surface が「message text」だけではなく、「file」「sound」「preview」「reply motion」を含む総合 UI になっていく過程である。

## 6.8 2026-03-12 から 2026-03-13: Hub 誕生と thinking UI

system commit notification が入り始めたことで、Hub の成立がはっきり追える。

主要コミット:

- `f10f3e3` commit system message
- `ea63ed5` mobile session resume hub
- `dc17f3a` archived session revive flow
- `88e0892` active session kill
- `804d786` cleanup chat servers on kill/revive

同時に thinking UI も大量に調整される。

- inline thinking indicator
- per-agent split
- shimmer / pulse / glow / float
- reload handshake 安定化

この時点で Hub は単なる entry page ではなく、session lifecycle controller になっている。

## 6.9 2026-03-14: 機能爆発と構造抽出

この日は architecture extraction の節目。

抽出:

- `hub_core`
- `chat_core`
- `state_core`
- `export_core`
- assets

機能追加:

- attached files panel
- export HTML
- thinking pane
- hub stats
- HTTPS via `mkcert`
- voice input
- camera photo attachment
- multiple file selection

これは surface feature の日であると同時に、`agent-index` 巨大単一ファイルを subsystem へ分ける日でもある。

対話面では、この日から user の要求がさらに精密になる。色味、フォント、日本語表示、Pane サイズ、表の外側余白まで細かく指示しつつ、Hub や Pane の不具合については「編集する前に教えて」「確度も書いて」と求める。つまり user は aesthetic direction を与えるだけでなく、analysis-before-edit の規律も system に課している。

## 6.10 2026-03-15 から 2026-03-16: multiple instances と mobile Hub

主な節目:

- mobile Hub revamp
- chat auto-save
- thinking pane / mic / scroll の iOS 修正
- multiple instances support
- thinking time aggregate
- display settings expansion
- `grok` support

特に `multiple instances of the same agent` は後の 4/4 障害の遠因でもある。複数 instance を first-class にしたことで、revive は「agent 名の集合」ではなく「instance topology」を復元する必要を持つようになった。

## 6.11 2026-03-17 から 2026-03-19: Hub / preview / public reach

この期間では 2 つの軸が伸びる。

### 6.11.1 Hub / file preview / chrome

- archived delete
- file opening behavior
- header / composer glass
- local hub access fixes

### 6.11.2 public reach

- Tailscale serve
- Cloudflare quick tunnel
- named tunnel
- Cloudflare Access
- public edge hardening

これは design philosophy の `Build local-first and add public reach later` と綺麗に対応する。実際の順序は

1. local
2. LAN
3. local HTTPS
4. public edge

であり、public が foundation になっていない。

## 6.12 2026-03-20 から 2026-03-22: server-owned state, heartbeat, registry, add-agent

主要な深化:

- settings を server-owned 化
- heartbeat tracking
- Mermaid
- syntax highlighting
- favicon
- pin state server-side
- add-agent
- terminal attach / socket handling
- agent registry 一元化

この段階で system は「単一の chat renderer」ではなく、

- runtime state
- hub state
- agent registry
- transport
- preview

を持つ platform へ近づく。

## 6.13 2026-03-23 から 2026-03-25: theme, topology, revive metadata, more agents

この時期は成熟と複雑化が同時に進む。

### 6.13.1 theme / shell / visual language

- `:root` theme 統一
- SpaceX 風ヘッダー
- soft-light
- black-hole
- mobile / desktop palette alignment

### 6.13.2 topology と metadata

- `OpenCode` 追加
- `Qwen` 追加
- `Aider` 追加
- `.meta` に `MULTIAGENT_AGENTS`
- `remove-agent`
- pane log 保存

### 6.13.3 onboarding / quickstart

- quickstart local HTTPS
- hub onboarding
- `docs/AGENT.md`
- context subcommand
- session guide 配布

ここで substrate と docs が再接続される。設計思想でいう low-flavor substrate は、単に裸の tmux という意味ではなく、tmux を中心にしつつも、その上で復帰・配布・導線を整えた状態へ進んでいる。

同時に、この期間は user の rollback discipline が最も強く見える時期でもある。iframe と full-page 遷移の実験に対して、user は `やはり戻して下さい`、`余計な変更勝手に入れないで`、`Public はそのままで良い` と繰り返し言う。つまり user が求めていたのは大改造ではなく、scope を絞った surgical fix であり、環境史の一部はこの「変更範囲を限定しろ」という圧力に押されて整流されている。

## 6.14 2026-03-26 から 2026-03-31: AGENT guide, philosophy, stdin-only transport, PWA

この期間は設計の自己意識が強まる時期である。

節目:

- `2026-03-26` `feat(multiagent): add context subcommand and AGENT.md`
- `2026-03-26` `feat: distribute session agent guide and brief rules`
- `2026-03-27` `docs: add design philosophy guide`
- `2026-03-28` `refactor: make agent-send stdin-only`
- `2026-03-31` installable PWA, browser notifications, deep links
- `2026-03-31` `feat(multiagent): let agents manage session topology`

この並びは非常に示唆的である。

- まず AGENT guide によって environment rules が repo-local に定着する
- 次に philosophy が環境の方向性を宣言する
- その直後に `agent-send` がより stdin-only に純化される
- 一方で topology management は agent 自身にも開く

さらに、この期間には単なる「文書化」以上の実装上の結晶化がある。

- 3/27 local HTTPS onboarding と quickstart が入り、mobile / secure context 前提が明文化される
- 3/28 `agent-send` が stdin-only になり、transport を足し算ではなく引き算で整える
- 3/28-3/30 Pane Trace popup / split view / scroll lock / streaming reveal / instance-scoped icons が続き、chat surface が見た目だけでなく interaction 単位で磨かれる
- 3/31 PWA install, notifications, deep links が入り、mobile が「見るだけ」ではなく再入場・再接続の入口になる
- 3/31 topology serialization と agent-managed topology が入り、人間と agent の双方が session topology を動かせるようになる

つまり、ここには

- transport を薄くして純化する動き
- docs / onboarding / notifications / topology を durable layer として整理する動き

の両方が共存している。

## 6.15 2026-04-04: camera mode と revive failure

4/4 は、この期間の終端にある一日ではあるが、歴史の頂点というより、すでに進んでいた二つの流れが同日に濃く可視化された日として読む方が正確である。

### 6.15.1 camera mode

system commits:

- `d1679f1` `feat(chat): add camera mode and direct ollama plumbing`
- `4bb4976` overlay layout fixes
- `6083a68` camera mode polish
- `ff6f139` live waveform
- `357e37c` landscape layout refine

会話から見える実装内容:

- camera overlay
- thinking / targets / replies の重ね合わせ
- voice waveform
- iframe `allow="camera; microphone; clipboard-write"`
- `Permissions-Policy`
- iPhone Safari 上の secure context / permission 問題

この日の user 発話は、camera mode をどのような operating mode にしたいかを極めて細かく規定している。`デザインを最小化する`、`完全にチャットに合わせて`、`下側の余白は完全に無くして`、`同じものを使って良い` といった指示は、user が novelty より alignment を重視していたことを示す。一方で `もっとかっこいい感じにできる？ お任せ` のように、局所的には裁量も渡す。つまり user は「大枠は厳密に固定し、局所の演出だけ自由にする」という独特の設計姿勢で camera mode を押し進めている。

### 6.15.2 revive failure

`codex-1` 系 instance が再起動後に増殖した。

これは state preservation と revive hardening の一事例であり、Pane Trace や Safari 対応と同じく、substrate と human-facing surface のつなぎ目で起きた堅牢化作業として位置づけるのが適切である。

## 6.16 会話から見える user の駆動力

ここまでの時系列を、機能ではなく conversation の型としてまとめ直すと、少なくとも 5 つの特徴がある。

### 6.16.1 exactness が convenience より強い

user は頻繁に `余白`、`揃えて`、`完全に0`、`同じものを使って良い` と要求する。これは単に見た目にうるさいという意味ではない。system が chat-first である以上、微妙なズレや余白の不一致は「同じ surface であるはずなのに別物に見える」という違和感になる。3/8 の composer 下余白、3/14 の Pane サイズ、4/4 の camera mode alignment は、いずれもこの exactness 要求に押されて詰められている。

### 6.16.2 mobile は仕様ではなく生活文脈である

user は smartphone を抽象的 client として扱わない。Mac を閉じたまま bed から Safari で戻りたい、ホーム画面 Web アプリ化すればタブを消せる、iPhone の角丸や safe area の見え方が気になる、といった発話が繰り返される。ここでは「mobile support」が単なる responsiveness ではなく、「人が場所を移動しても同じ session continuity を持てること」を意味している。

### 6.16.3 まず説明しろ、という規律が強い

user は何度も `まだ実装せずに、教えて`、`編集する前に教えて`、`原因を調査して` と言う。これは保守的というより、変更と理解を分離したいという姿勢である。3/14 の Hub / Pane 問題、3/25 の Local/Public 差分、4/4 の revive 分析では、実装前説明を要求することで、environment が guess-and-patch ではなく reason-and-then-edit に寄せられている。

### 6.16.4 rollback と scope discipline が厳しい

`戻して` が 190 回出ることは象徴的である。user は失敗そのものより、余計な変更や scope の逸脱を嫌う。3/25 の Hub / iframe では `Public はそのまま`、`余計な変更勝手に入れないで` と釘を刺し、4/4 の camera mode でも `画像等の位置は変えないように注意` と範囲を限定する。結果としてこの環境は、前進だけでなく rollback の反復によって形を整えている。

### 6.16.5 user 自身が multi-agent router である

user は agent を対等な worker 群として放置しない。`Gemini に投げて`、`Claude にも振ってください`、`Gemini が解決してくれました` といった発話に見えるように、user 自身が routing, comparison, acceptance を行っている。したがって、この環境の multi-agent 性は system 機能だけでなく、user の運用作法そのものによって成立している。

## 7. 設計思想から見た実装史

ここからは `docs/design-philosophy.md` / `docs/design-philosophy.en.md` と実装史の対応を明示する。

## 7.1 agent side as low-flavor substrate

思想:

- tmux は polished terminal product ではなく runtime substrate
- sessions / panes / sockets / env / capture-pane を直接使えることが重要

実装史上の対応:

- 3/6 `Initialize multiagent scripts`
- 3/7-3/8 pane diff / capture-pane ベース status
- 3/8-3/9 trace tooltip / pane trace の成熟
- 3/14 `hub_core` / `chat_core` / `state_core` / `export_core` 抽出
- 3/20 terminal attach socket handling 修理
- 3/22 agent-send の tmux socket bypass 修理
- 3/27 `recover tmux socket from TMUX env`
- 3/28 stdin-only transport への純化
- pane log 保存や color env normalization

解釈:

この環境は pane を隠蔽していない。人間の primary surface は chat だが、agent side は最後まで tmux primitives に近いまま維持されている。

3/14 の core 抽出も、この思想の延長で読むべきである。ここで行われたのは「高機能な UI を足すために substrate を捨てる」ことではなく、`agent-index` に混線していた責務を分け、substrate / state / surface の境界をコード構造でも見通しやすくしたことだった。3/28 の stdin-only 化も同様で、agent 側の実行面をさらに味付けの少ない primitive に戻している。

## 7.2 chat-first human surface

思想:

- pane grid ではなく message stream が primary

実装史上の対応:

- 3/7 chat-based `agent-index`
- reply / jump / search / filter
- file cards / file preview
- system messages for brief/save/memory
- Pane Trace が sidebar / popup / panel として付属

解釈:

実装史を見ても、「pane grid を人間 UI の中心にする」方向の大きな試みはほぼ存在しない。むしろ raw pane は常に trace, popup, pane viewer など補助窓として扱われている。

## 7.3 thin transport

思想:

- `agent-send <target>` + text payload を中心に据える
- richer meaning は message convention に押し出す

実装史上の対応:

- `[Attached: path]` を transport ではなく本文規約として採用
- file card / preview は UI 側で解釈
- 3/14 `Deprecate inline agent-send text mode`
- 3/28 `make agent-send stdin-only`
- `docs/AGENT.md` でも stdin 経由を強調

解釈:

これは philosophy と実装がかなり綺麗に一致している領域である。機能は増えているが、transport 自体は太らせていない。

## 7.4 layered records

思想:

- `docs/AGENT.md`
- brief
- memory
- `.agent-index.jsonl`
- `.log` / `.ans` / Pane Trace

を混ぜない

実装史上の対応:

- 3/8 Memory / Load / Save / Brief / Save Log
- 133 回の Send Brief
- 97 回の Save Log
- 49 回の Save Memory
- 23 回の Load Memory
- docs / guide / SELF_INTRO / detailed guide の整備

解釈:

この環境の continuity は一つの巨大メモではなく、多層の記録媒体に依存している。設計思想は後からそれを定義したが、運用はすでに先行していた。

重要なのは、3/8 の UI が最初からこれらを別ボタンとして出していたことである。`Brief` は session ごとの半静的な追加指示、`Memory` は agent ごとの要約、`Save Log` は会話や pane の状態を別ファイルへ確定する操作であり、役割が異なる。ここで user は「一つのノートを書き換え続ける」のではなく、目的ごとに違う層へ書き込む運用へ導かれている。これは philosophy 6 の最も直接的な embodiment の一つである。

## 7.5 session continuity over process continuity

思想:

- immortal process を守るのでなく、session を復帰可能にする

実装史上の対応:

- `--fresh`
- save command
- auto-mode resume restart
- hub resume / archived revive / kill
- `Kill` と `Delete` の分離
- log directory simplification
- `.meta` に agent list 保存

補足:

ログには `Kill` は runtime stop、`Delete` は archived logs を消す、という説明が明示的にある。

解釈:

この思想は一貫して強い。3/25 に `.meta` へ agents list を保存する判断が入るのも、3/16 に multiple instances を first-class にした結果、「どの topology を revive すべきか」を session 側で持つ必要が生まれたからである。つまり revive は単なる process 再起動ではなく、session topology の再構成へ進化している。

4/4 の revive 障害も、この節の一事例として読むのが最も自然である。起きたことは、`.meta` の破損で revive 側が `.log` / `.ans` fallback に落ち、過去 instance の残骸まで current topology と見なしたことだった。修正 commit `89e48be` は `raw_decode()` fallback と mtime-based filtering によって partial corruption から session continuity を救済した。ここで注目すべきなのは「思想との衝突」より、「process より session を守る」設計が live state preservation をどこまで要求するかが具体化した点である。

言い換えると、この環境はすでに `Kill` / `Revive` / `Delete` / archived logs / `.meta` を通じて continuity を session 単位で扱っており、4/4 はその durable substrate をさらに硬くする作業が visible になった一日だった。

## 7.6 mobile as a precondition

思想:

- mobile は二軍クライアントではない

実装史上の対応:

- 3/8 LAN + iPhone support
- 3/8-3/9 Safari layout/keyboard fixes
- 3/13 mobile session resume hub
- 3/14 local HTTPS
- 3/15-3/16 mobile Hub redesign
- 3/22 mobile pane viewer
- 3/31 PWA install / notifications / Apple Web Push

解釈:

これは思想文書の中でも最も実装上の裏付けが厚い。実装史のかなりの部分は mobile に割かれている。

## 7.7 physical-world input

思想:

- system を画面の中に閉じ込めない
- camera / voice / files / remote access で現実を session に入れる

実装史上の対応:

- 3/14 voice input
- 3/14 camera photo attachment
- uploads の session-local 保存
- 4/4 camera mode
- 4/4 waveform と live visibility

解釈:

この思想も、かなり具体的に実装へ落ちている。しかも camera / voice は単なる gadget ではなく、message attachment と session log に繋がる durable form として組み込まれている。

特に 3/14 の camera attachment は重要で、これは「その場で撮る」ことより、「撮った断片を session-local な uploads と message body に残し、後から複数 agent が読める状態にする」ことを意味する。4/4 の camera mode はその延長にあり、physical-world ingress を一時的な便利機能ではなく、chat / logs / permissions / mobile layout を含む一つの operating mode へ押し広げたものと見なせる。

## 7.8 local-first, public later

思想:

- core workflow は local/LAN first
- public access は追加 layer

実装史上の対応:

- 3/8 LAN access
- 3/14 mkcert local HTTPS
- 3/19 Tailscale
- 3/19 Cloudflare tunnels / Access
- 3/27 local HTTPS quickstart
- 3/31 PWA / push

解釈:

これは chronology がそのまま思想を裏づける典型例である。public edge は明確に後段で足されている。

## 8. 補助的に見える境界と堅牢化パターン

主軸は前章の embodiment だが、補助的に「どこで hardening が必要になったか」を見ておくと、各原則が現実に降りたときの形がよりはっきりする。

## 8.1 多機能化それ自体は anti-pure ではない

3/31 に philosophy 側が明示した通り、この project は

- Hub
- logs
- session continuity
- mobile access

を anti-pure と見なしていない。

したがって、feature が増えたこと自体を「思想からの逸脱」と読むのは不正確である。重要なのは、その feature が substrate を濁す方向か、人間側 surface や continuity を強める方向かである。

## 8.2 dynamic topology は durable substrate の深化である

multiple instances, add/remove-agent, registry, topology serialization は、この環境が `easy human intervention` を durable にする過程として読める。

特に

- 3/16 multiple instances
- 3/21 add-agent
- 3/25 `.meta` 保存と `remove-agent`
- 3/27 duplicate instance support
- 3/31 agent-managed topology

の流れは、「複数 agent がいる」だけでなく、「その編成そのものを session の一部として扱う」地点まで環境が進んだことを示している。

## 8.3 thin transport と rich viewing layer は役割分担である

`agent-send` は薄いままだが、Hub / chat / file preview / Pane Trace / reply / system message は厚くなっている。これは矛盾ではなく役割分担である。

transport は text と path convention に留め、その上の viewing layer で人間に必要な richness を引き受ける。この分業が一貫しているため、surface が肥大しても transport は比較的純度を保てた。

## 8.4 browser reality は mobile-first を現実化するコストである

Safari / iOS 向けの調整は多いが、それは mobile-first の誤りというより、その理念を実在のブラウザ層に落とし込むコストとして現れている。

`visualViewport`, secure context, iframe permission, Apple Web Push といった patch 群は、mobile を前提に置いたことの副産物ではなく、その前提を本当に守ろうとした結果である。

## 8.5 時期をまたいで繰り返し現れる「堅牢化の型」

時期を平らに扱うために、代表的な hardening episode を 3 つだけ並べる。

### A. 3/8 Trace / ANSI / whitespace

- `capture-pane` をそのまま chat surface に持ち込むと、空白パディングや折り返しの癖が可視化される
- ここでは substrate fidelity を保ちつつ、人間に読める trace へ整形する必要があった

### B. 3/9 iOS HTTPS-Only / file preview

- local-first な file preview は、そのままでは iOS Safari の secure context 制約に阻まれる
- modal overlay や local HTTPS は、「ローカルで完結する環境」を mobile 現実へ通すための hardening だった

### C. 4/4 `.meta` / revive / topology reconstruction

- session continuity を強く取ると、revive は topology の current snapshot 復元まで担う
- `.meta` 破損時に `.log` / `.ans` fallback が stale instance を拾ったことで、state preservation の hardening が必要になった

この 3 つは別々の事件ではない。いずれも「substrate と human-facing surface の境界で漏れた現実を、その都度 durable に繋ぎ直す」作業である。

## 9. 実装史から見た設計思想の成立順

重要なのは、思想と実装が同時に出てきたわけではないことだ。

実際の順序はおおむねこうである。

1. 3/6-3/7
   - substrate, transport, chat, logging
2. 3/8-3/10
   - trace, layered records, mobile, file preview, export
3. 3/13-3/16
   - Hub, thinking UI, architecture extraction, voice/camera, multiple instances
4. 3/19-3/25
   - public reach, registry, topology, pane logs, onboarding
5. 3/26-3/31
   - AGENT, philosophy, stdin-only transport, quickstart, PWA, notifications
6. 4/4
   - camera mode と revive hardening

したがって、`docs/design-philosophy.md` / `.en.md` は

- 実装を先導した blueprint

というより、

- すでに育っていた environment の方向性を抽出し、その後の実装を読むための charter

として理解する方が正確である。

## 10. この環境は何になっていたか

対象ログの終端で、multiagent 環境は次のような層を持つようになっていた。

### 10.1 agent side

- tmux session / pane / socket
- pane capture
- agent CLI runtime
- auto-mode
- add/remove agent
- multiple instances

### 10.2 transport

- `agent-send`
- stdin-only text payload
- reply metadata
- attachment syntax in message body

### 10.3 record layer

- `docs/AGENT.md`
- brief
- memory
- `.agent-index.jsonl`
- `.log` / `.ans`
- `.meta`

### 10.4 human-facing surface

- chat UI
- reply / jump / search / filter
- file preview
- Pane Trace
- Hub
- stats
- settings
- topology / PWA / notifications

### 10.5 world-facing edge

- LAN access
- local HTTPS
- Tailscale
- Cloudflare
- camera
- microphone
- phone browser

これを一言で言えば、

「tmux を substrate にした session-oriented multi-agent workspace を、chat-first / mobile-capable / world-open な surface で包んだもの」

である。

## 11. 結論

この環境の歴史は、次の 4 つの流れの合流として理解するのが最も正確である。

### 11.1 substrate の純化

`agent-send` の薄さ、stdin-only 化、tmux socket/pane/capture 直結、pane logs。

### 11.2 human surface の豊富化

chat UI, Hub, file preview, Pane Trace, mobile UX, PWA, notifications。

### 11.3 continuity の多層化

brief, memory, logs, `.meta`, archived sessions, revive。

### 11.4 physical/world reach の拡張

LAN, HTTPS, Tailscale, Cloudflare, voice, camera, phone。

この 4 つは別々の追加機能ではない。`docs/design-philosophy.md` / `.en.md` が後から言語化した通り、同じ方向の別表現である。

補助的に見るべき境界としては、Safari 現実への適応、rich viewing layer の肥大化、dynamic topology の state preservation などが残る。しかしそれらは主題ではなく、この環境が理念をかなり高い密度で実装してきたことの裏返しとして現れている。

それゆえ、この履歴は単なる feature list ではなく、`multiagent-chat` が「何を目指す環境なのか」を、実装の積み重ねとして示す具現化史として読むべきである。

## 12. 追記メモ

この expanded edition は、初版レポートに対して以下を追加した。

- git 実日時での前史復元
- `docs/design-philosophy.md` / `.en.md` の成立史
- philosophy 各節と実装史の明示的対応
- 4/4 の独立章を廃し、session continuity の一事例へ再配置
- gemini-1 と claude の独立レビューを踏まえた再構成
