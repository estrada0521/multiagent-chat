# multiagent-chat

tmux ベースのローカル multi-agent chat/workbench です。複数の AI エージェントを同一セッションに並べ、Hub と chat UI から会話・送信・ログ確認を行えます。

<p align="center">
  <img src="screenshot/Hub_Top-portrait.png" alt="Hub overview" width="250">
  <img src="screenshot/message_body-portrait.png" alt="Chat UI" width="250">
  <img src="screenshot/new_session-portrait.png" alt="New session from mobile" width="250">
</p>

## 何ができるか

### チャット

この環境の中心は chat UI です。ユーザー目線では、大きく「メッセージ本体」「入力部分」「ヘッダー部分」に分かれています。

単なるメッセンジャーではなく、複数エージェントを相手にした作業画面として設計されています。会話の流れを追うだけでなく、誰に送るか、どのファイルを渡すか、いまの session がどの状態にあるかを 1 画面の中で扱えます。

<p align="center">
  <img src="screenshot/atamrk_command-portrait.png" alt="@ command autocomplete" width="230">
  <img src="screenshot/slash_command-portrait.png" alt="Slash commands" width="230">
  <img src="screenshot/import-portrait.png" alt="Import attachments" width="230">
</p>

メッセージ本体では、

- user と agent の会話を時系列で追える
- `msg-id` に紐づく reply を扱える
- `[Attached: ...]` を含むメッセージからファイル参照をたどれる
- 構造化された chat log をそのまま残せる

会話はただ上から読むだけではなく、あとから辿り返すことも前提にしています。`msg-id` による reply の紐付けがあるので、並列に話が進んでいても文脈を失いにくく、添付されたファイルもその場で参照できます。

入力部分は次の 4 つに整理できます。

1. スラッシュコマンド
`/memo`、`/silent`、`/brief` など、送信前に session の文脈や挙動を整えるための入口です。単なるショートカットではなく、brief や memory のような session 資産に触れる導線でもあります。

2. アットマークコマンド
`@` による file path autocomplete です。ローカルファイルをそのまま会話の対象に持ち込めるので、エージェントに対して「このファイルを見て」と言うためのコストがかなり低くなっています。

<p align="center">
  <img src="screenshot/brief-portrait.png" alt="Brief workflow" width="230">
  <img src="screenshot/file_preview-portrait.png" alt="File preview" width="230">
  <img src="screenshot/Git_diff-portrait.png" alt="Git diff" width="230">
</p>

3. インポート
Import ボタンからファイルを渡せます。添付したファイルはそのままチャットの流れの中に残るので、一時的なアップロードではなく、後から追えるやり取りの一部として扱えます。

4. ブリーフ
Brief は session 固有の再利用テンプレートです。毎回長い指示を書き直さなくても、保存済みの brief を選んで複数エージェントへ渡せます。

入力欄まわり全体としては、`agent-send` を背後に使った送信、target selection、raw send、音声入力、添付ファイルプレビューなども含んでいます。つまりこの欄は単なる送信フォームではなく、会話を始める前の準備と、会話に文脈を持ち込むための作業面です。

ヘッダー部分は次の 2 つに分けて考えると分かりやすいです。

1. ヘッダー内のモデル
コミット履歴やファイルメニューのように、今の作業内容や参照対象を確認するための導線です。会話だけでは見えない repo 側の状態を、すぐ上の UI から確認できます。

2. ヘッダー内のセッション機能
エージェント追加とエージェント削除です。session の構成そのものをチャットから離れずに調整できます。

<p align="center">
  <img src="screenshot/Add_agent-portrait.png" alt="Add agent" width="230">
  <img src="screenshot/remove_agent-portrait.png" alt="Remove agent" width="230">
</p>

ヘッダーは装飾ではなく、session 制御と参照系操作の入口です。会話の周辺にある操作をそこへ集めることで、tmux pane を直接触らなくても、かなりの範囲を UI 上で完結できます。

この chat UI の背後にある基本の仕組みが `agent-send` です。単に複数 pane を並べるだけでなく、**user と agent、agent 同士の会話を明示的にルーティング**できます。tmux pane の存在を露出しすぎず、会話系の操作を chat UI に寄せているのがポイントです。

### Hub

Hub は session 全体を見るための入口です。

chat UI が 1 つの session の作業面だとすると、Hub は session 全体を見渡すためのホームです。active / archived をまたいで状態を確認し、どこから再開するかを決める場所になっています。

<p align="center">
  <img src="screenshot/Stats-portrait.png" alt="Stats page" width="230">
</p>

- active / archived session の一覧
- latest preview つきの session overview
- session ごとの chat UI への導線
- new session の作成
- settings
- statistics ページ

を持っています。

新しい session を起こす導線もここにあります。既存の session をただ一覧するだけではなく、次に何を始めるか、どの構成で立ち上げるか、必要なら settings や stats をどう参照するかまで含めて Hub に寄せています。

また、local / public の状態を踏まえた導線もあり、スマホからでも session 一覧や新規 session 作成に触れます。

### ログ

ログ系は大きく 2 層あります。

<p align="center">
  <img src="screenshot/Pane_trace-portrait.png" alt="Pane trace" width="250">
</p>

- `.agent-index.jsonl`
  chat メッセージそのものを残す構造化ログ
- `*.log` / `*.ans`
  pane capture を保存する terminal 側ログ

これにより、

- chat の流れ
- pane 上で何が起きていたか
- archived session の再読
- export 用の元データ

をまとめて扱えます。チャットだけでなく、**pane の痕跡まで含めて残せる**のが特徴です。`.agent-index.jsonl` は会話の意味的な流れを追うのに向いていて、pane trace は「実際に pane 内で何が起きていたか」を見るのに向いています。両方あることで、会話と実行のズレを後から確認できます。

### バックエンド系

表からは見えにくいですが、運用を支える機能もあります。

<p align="center">
  <img src="screenshot/settings-portrait.png" alt="Runtime settings" width="230">
</p>

- Auto-mode
  permission prompt を検知して自動承認する補助機構
- Awake mode
  `caffeinate` を使って sleep を防ぐ
- Sound notifications
  通知音、commit 音、時刻指定音などを鳴らせる
- mobile / public access
  スマホからの remote control や public Hub 運用
- export
  session を standalone HTML として持ち出す

この層は README では見えにくい部分ですが、実運用ではかなり効きます。permission prompt で止まりやすい場面を補助したり、長時間実行のために sleep を防いだり、音で状態変化を拾えたりと、multi-agent セッションを放置運転しやすくする仕掛けが入っています。単なるチャット画面ではなく、**長時間の multi-agent 運用を支える土台**まで含んでいます。

## 典型的な使い方

1. `./bin/quickstart` で Hub を起動する
2. Hub から session を開く
3. chat UI で target agent を選び、依頼を送る
4. 必要に応じて Brief / Memory を使って指示や文脈を整理する
5. 作業後も session とログを残し、あとで再開する

## 典型的なユースケース

- 複数 agent に同時に調査や実装を振る
- user と agent、agent 同士の会話を 1 つの session に集約する
- 長い会話の途中で Brief / Memory を整理し直す
- スマホから既存 session を追い、必要なら新規 session も作る
- 作業結果をログや export HTML として残す

## 主な構成

### Session ベース

作業単位は tmux session です。各 agent は独立した pane で動き、Hub では active / archived をまとめて扱えます。

### Chat UI とログ

chat UI は単なる送信欄ではなく、target selection、message log、session 状態、quick actions、添付ファイル導線をまとめた作業画面です。ログは `.agent-index.jsonl` に残るため、あとから検索や追跡ができます。

### Brief と Memory

- Brief: session 固有の再利用テンプレート
- Memory: agent ごとの要約状態

Brief は selected targets にまとめて送れます。Memory は現在の `memory.md` と、更新前スナップショットの `memory.jsonl` に分かれています。

### ローカル中心、必要なら public 化

通常はローカルで使い、必要なときだけ Cloudflare 経由で Hub を外部公開できます。public 化しても、ローカル利用の流れを置き換える設計ではありません。

## Quickstart

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

`./bin/quickstart` は次を行います。

- `python3` と `tmux` の存在確認
- 必要なら依存の案内または対話的インストール
- エージェント CLI の確認
- multiagent セッションのセットアップ
- Hub / chat UI の起動

起動後は通常、Hub 一覧または chat UI がローカルで開ける状態になります。

## Requirements

- `python3`
- `tmux`
- macOS または Linux

macOS では Homebrew が入っていると導入が楽です。

## Main Commands

- `./bin/quickstart`: 依存確認つきで Hub を起動
- `./bin/multiagent`: セッション作成・再開・操作
- `./bin/agent-index`: セッション一覧、chat UI、ログ閲覧
- `./bin/agent-send`: user や他 agent へのメッセージ送信

## Docs

- [docs/AGENT.md](docs/AGENT.md): この環境で動くエージェント向けの運用ガイド
- [docs/cloudflare-quick-tunnel.md](docs/cloudflare-quick-tunnel.md): Cloudflare Quick Tunnel / named tunnel
- [docs/cloudflare-access.md](docs/cloudflare-access.md): public Hub に Cloudflare Access を掛ける方法
- [docs/cloudflare-daemon.md](docs/cloudflare-daemon.md): public tunnel の常駐運用
