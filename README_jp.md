# multiagent-chat beta 1.0.5

English version: [README.md](README.md)

更新履歴: [docs/updates/README.md](docs/updates/README.md) / [beta 1.0.5 日本語](docs/updates/beta-1.0.5.ja.md)

`multiagent-chat` は、tmux session を単位に複数の AI agent を並べて動かし、Hub と chat UI から同じ session を管理するためのローカル workbench です。`bin/multiagent` は window 0 を人間用 terminal とし、各 agent instance に専用の tmux window を与える session を作成し、`bin/agent-index` が Hub / chat UI / log viewer を提供し、`bin/agent-send` が user・agent・agent 間のメッセージを構造化して流します。

会話ログは `.agent-index.jsonl`、pane 側の表示は `.log` と `.ans` に残ります。Hub から session の作成・再開・統計確認・設定変更を行い、chat UI からターゲット選択、返信、ファイル参照、brief、memory、pane 操作、export をまとめて扱えます。PC だけでなく、同一 LAN 上のスマホからも同じ Hub / chat UI を開けます。

この環境は、session を停止しても後から再開できることと、文脈を 1 つの可変メモに寄せず層ごとに保持することを前提にしています。恒久ルール、session 固有の指示、agent ごとの要約、構造化された会話ログ、pane 側の直接 capture を分けることで、長期運用時にも参照先を失いにくい構成になっています。

<table align="center">
  <tr>
    <td align="center" valign="middle">
      <img src="mac.png" alt="multiagent-chat on Mac" width="420">
    </td>
    <td align="center" valign="middle">
      <img src="iPhone.png" alt="multiagent-chat on iPhone" width="210">
    </td>
  </tr>
</table>

Hub と chat UI はデスクトップブラウザとスマホブラウザの両方から開けます。Mac 側で session を立ち上げ、そのまま同じ Hub / chat UI を手元の PC でもスマホでも参照する使い方を前提にしています。

## 何ができるか

| 領域 | 内容 |
|------|------|
| Hub | active / archived session 一覧、New Session、Resume、Stats、Settings、Cron |
| Chat UI | user と agent、agent 同士の会話、返信、添付、ファイル参照、brief / memory、pane 操作、runtime ヒント表示、スマホ向けの camera mode |
| Logs | `.agent-index.jsonl` の構造化メッセージログ、`.log` / `.ans` の pane capture、static HTML export |
| Backend | Auto mode、Awake、通知音と browser notification、Hub / chat の PWA 導線、Cron による定時実行、Gemini direct bridge、experimental な Ollama / Gemma direct path、任意の public 公開（Cloudflare は実装済み） |

現在の agent registry には `claude`、`codex`、`gemini`、`kimi`、`copilot`、`cursor`、`grok`、`opencode`、`qwen`、`aider` が入っています。同じ base agent を複数回起動することもでき、その場合は `claude-1`、`claude-2` のような instance 名になります。agent 同士は `agent-send` を通じて通信し、メッセージは共有の `.agent-index.jsonl` に追記されます。つまり agent 間の協業も user-to-agent と同じ構造化ログに残り、全参加者のやりとりが 1 つのタイムラインで保存されます。

### 1. New Session / Message Body

<p align="center">
  <img src="screenshot/new_session-portrait.png" alt="Create new session" width="320">
  <img src="screenshot/message_body-portrait.png" alt="Chat message body" width="320">
</p>

New Session は Hub から作成します。workspace path は UI から入力でき、スマホ側からでも同じ画面で指定できます。新しい session では operator terminal を tmux window 0 に置き、各 agent instance に個別の tmux window を割り当てます。base agent の重複起動にも対応しており、同じ CLI を複数 agent window に割り当てたい場合は自動的に suffix 付きの instance 名が付きます。

workspace picker は、直接 path を打つ入力欄、recent path、folder browser を 1 つの流れにまとめています。手入力とフォルダ参照を同じ New Session 画面で切り替えられるため、スマホでもデスクトップでも workspace 指定を崩さず使えます。

workspace 側に `docs/AGENT.md` が無ければ、session 作成時に repo の `docs/AGENT.md` が `workspace/docs/AGENT.md` として複製されます。新しい session を開いた直後は、その `docs/AGENT.md` を最初の message で agent に送って、この環境での communication と command の前提を共有する使い方を想定しています。起動後に短い command cheatsheet だけ見たい場合は `agent-help` も使えます。

message body には user から agent への依頼だけでなく、agent 同士のやり取りも同じ時系列で並びます。各 message には `msg-id`、送信者、宛先、`reply-to` が付き、本文のコピー、返信開始、返信元メッセージへのジャンプ、返信先メッセージへのジャンプを UI から行えます。`[Attached: path]` や `@path/to/file` で参照されたファイルも message の中から辿れます。

本文レンダラは見出し、段落、箇条書き、引用、インラインコード、コードブロック、表のほか、KaTeX による LaTeX 数式と Mermaid ダイアグラムを扱います。`agent-send` で流れた user-to-agent、agent-to-user、agent-to-agent の message は同じ JSONL に残り、複数 target を指定した送信でも `targets` と `reply-to` がそのまま保存されるので、tmux pane の表示だけに依存せず履歴を追えます。

### 1.5. Thinking / Pane Trace

<p align="center">
  <img src="screenshot/thinking.png" alt="Thinking state" width="320">
  <img src="screenshot/Pane_trace-portrait.png" alt="Pane trace" width="320">
  <img src="screenshot/pane_trace_pc.png" alt="Pane trace desktop window" width="420">
</p>

agent が動作中のときは thinking 行が出ます。モバイルではこの行を押すと埋め込みの Pane Trace viewer を開けます。デスクトップでは同じ行を押すと、選択中 agent の Pane Trace が popup window で開きます。Pane Trace は pane 側の表示を軽量に追う viewer で、LAN / local では 100ms ごと、public 経由では 1.5 秒ごとに更新されます。チャット本文が JSONL 側の記録なら、Pane Trace は tmux pane 側の最新表示を確認するための画面です。デスクトップの popup では split view で複数 agent を同時に監視でき、タブやドラッグアンドドロップで agent を切り替え・並び替えできます。

tmux の terminal 本体と比べると、デスクトップの Pane Trace popup は browser 側の viewer として最適化されており、scrollback が滑らかで、agent 切り替えや text の選択・コピーも行いやすくなっています。

provider adapter や pane parser が tool activity を認識できる場合は、thinking 行の下に `Ran`、`Edited`、`ReadFile`、`Grepped` などの短い runtime ヒントも表示されます。これらは canonical な `.agent-index.jsonl` に残す履歴ではなく、あくまで live UI 補助として扱っています。

デスクトップでは header menu の `Terminal` から tmux session に attach した terminal 本体を開きます。window 0 が operator terminal で、各 agent window には通常の tmux window 切り替えで移動できます。モバイルでは同じ導線が Pane Trace につながるので、スマホ側からでも各 agent pane の様子を追えます。

### 2. 入力欄

<p align="center">
  <img src="screenshot/slash_command-portrait.png" alt="Slash commands" width="180">
  <img src="screenshot/atamrk_command-portrait.png" alt="@ command autocomplete" width="180">
  <img src="screenshot/import-portrait.png" alt="Import attachments" width="180">
  <img src="screenshot/brief-portrait.png" alt="Brief workflow" width="180">
</p>

入力欄はオーバーレイとして開きます。モバイルでは丸い `O` ボタンから、デスクトップでは `O` ボタンに加えてホイール押し込みからも開けます。閉じている間は本文表示領域を広く取り、必要なときだけ composer を開く構成です。

slash command は composer 内の送信形式や pane 操作の入口です。現在の command は次のとおりです。

- `/memo`: 自分宛メモです。本文が空でも Import 添付だけで送れます
- `/cron`: 現在の session / target を埋めた Cron 作成画面を開きます
- `/gemini <text>`: direct Gemini bridge で prompt を実行します
- `/gemma <text>`: local model の direct path で実行します。`/gemma:モデル名` で model 名を切り替えられます
- `/brief`: `default` brief を開きます
- `/brief set <name>`: `brief_<name>.md` を開きます
- `/load`: 現在の `memory.md` を selected agent に送ります
- `/memory`: selected agent に `memory.md` の更新を指示します
- `/model`: 選択中 pane に `model` を送ります
- `/up [count]` / `/down [count]`: 選択中 pane に上下移動を送ります
- `/restart` / `/resume` / `/ctrlc` / `/interrupt` / `/enter`: 選択中 agent pane に対する操作です

command や quick action の一覧は [docs/chat-commands.md](docs/chat-commands.md) に分けてあります。README には概要だけを残し、詳細は補助 docs 側に寄せています。

`/gemini` と `/gemma` は通常の pane 駆動 agent とは別系統です。同じ chat タイムラインに結果を返しますが、pane 側の memory や file mutation tool、CLI 固有機能を自動では引き継ぎません。

`@` は workspace 内ファイルの path autocomplete です。入力中に候補が出るので、会話中でファイルを相対 path のまま参照できます。Import は workspace 内ファイルの参照ではなく、ローカル端末側のファイルを session の uploads へ持ち込む導線です。スマホでは端末内の画像やファイルを直接取り込み、PC ではドラッグアンドドロップにも対応します。画像はサムネイル、その他のファイルは拡張子付きカードで表示されます。

brief は session ごとの再利用テンプレートです。恒久ルールを書く `docs/AGENT.md` と違い、brief はその session のためだけに置く追加指示や定型文を扱います。保存先は `logs/<session>/brief/brief_<name>.md` で、`/brief` か `/brief set <name>` で編集し、Brief ボタンから保存済み brief を selected targets へ送れます。`docs/AGENT.md` が repo / 環境全体の運用ルールなら、brief は session-local の作業文脈です。

同じ quick action 群には `Load` と `Save Memory` もあります。memory は `logs/<session>/memory/<agent>/memory.md` に現在値を持ち、更新前の状態は `memory.jsonl` に snapshot として蓄積されます。brief が session に共有する追加指示なら、memory は agent ごとの要約状態です。

### 2.5. Camera Mode

モバイルでは header menu から `Camera` を開けます。通常の composer を経由する代わりに、live camera feed、選択中 target agent、最近の agent reply、即時撮影用 shutter を 1 つの overlay にまとめた画面です。desktop からも確認用に同じ surface を開けます。

撮影画像は upload 前に縮小され、その後は通常の uploads と構造化 message path を通って送信されるため、履歴は普通の chat と同じく `.agent-index.jsonl` に残ります。同じ overlay 内で voice input も使えます。Web Audio が取れる環境では live microphone energy に反応する waveform が動き、mobile browser の制約で並列 audio 解析が取れない場合も、止まって見えないよう fallback waveform を出します。

### 3. Header

デスクトップでは header menu から `Finder` と `Pane Trace` に直接入れるようになっており、session の移動を terminal 本体の再表示に頼り切らずに行えます。

#### 3-1. Branch Menu

<p align="center">
  <img src="screenshot/branch_menu.png" alt="Branch menu" width="300">
  <img src="screenshot/Git_diff-portrait.png" alt="Git diff view" width="300">
</p>

branch menu には現在の branch、git 状態、最近の commit 履歴、diff が出ます。現在の未コミット差分は commit 履歴や diff navigation より上に表示されます。各変更ファイルには editor を開く、個別 commit、`HEAD` への復元があり、さらに worktree 全体向けの `All` commit もあります。diff に出てくるファイル名はそのまま外部エディタへの導線になっているので、会話の途中で変更ファイルへ飛べます。chat UI の外へ一度戻らなくても、どの commit / diff が発生しているかを session 単位で確認できます。

#### 3-2. File Menu

<p align="center">
  <img src="screenshot/file_menu.png" alt="File menu" width="240">
  <img src="screenshot/file_preview-portrait.png" alt="Markdown preview" width="240">
  <img src="screenshot/sound.png" alt="Sound file preview" width="240">
</p>

file menu には、その session で参照されたファイルの一覧が集まります。Markdown、コード、画像、音声などに応じた preview があり、`Open in Editor` で外部エディタへ移動できます。ファイルはカテゴリ別にまとまり、件数とサイズ表示も付きます。右側の矢印からは、そのファイルが参照された元 message へ戻れます。

Markdown preview は本文側の renderer に寄せた表示になっており、`![...](path)` のような相対 path のローカル画像参照も解決します。さらに、設定済みの agent font を引き継ぎ、preview 内から dark / light を切り替えられます。コード系ファイルは plain text viewer、sound file は専用 preview で確認できます。chat 本文で触れたファイルを、会話の流れを保ったまま別画面で読むための入口です。

#### 3-3. Add / Remove Agent

<p align="center">
  <img src="screenshot/Add_agent-portrait.png" alt="Add agent" width="320">
  <img src="screenshot/remove_agent-portrait.png" alt="Remove agent" width="320">
</p>

header menu から agent を追加・削除できます。追加時も削除時も `.agent-index.jsonl` の既存会話ログは消えず、session の tmux window 構成だけが変わります。agent を追加すると新しい agent window が作られ、削除するとその instance の window だけが消えます。base agent を複数 instance 使う場合もここから増やせます。構成変更後は `Reload` を一度行うと、target 一覧や UI 状態が揃います。

同じ基盤操作は agent pane 内からも使えます。agent 自身が `multiagent add-agent --agent <base>` や `multiagent remove-agent --agent <instance>` を実行でき、現在の pane に入っている `MULTIAGENT_SESSION` / `MULTIAGENT_TMUX_SOCKET` をそのまま使います。構成変更は `.agent-index.jsonl` に `system` entry として追記されるため、header menu から行った変更と agent 側から行った変更が同じ時系列に残ります。

また、topology 変更は session ごとに直列化されます。複数 pane や UI から同時に add / remove が走っても、instance 名の採番や tmux state 更新は 1 件ずつ順番に適用されます。加えて、各 topology 変更の前に stale な `MULTIAGENT_AGENTS` / `MULTIAGENT_PANE_*` を実際の tmux window と突き合わせて整合するため、すでに消えている instance や壊れた state を引きずったまま次の add/remove が走りにくくなっています。

### 4. Hub / Stats / Settings

<p align="center">
  <img src="screenshot/Hub_Top-portrait.png" alt="Hub top" width="240">
  <img src="screenshot/Stats-portrait.png" alt="Stats page" width="240">
  <img src="screenshot/settings-portrait.png" alt="Settings" width="240">
</p>

Hub は active / archived session 一覧を管理する入口です。active session では workspace path、agent 構成、chat 数、chat port を見ながらそのまま chat UI を開けます。archived session は別一覧に残り、再開可能なものは revive できます。Hub から New Session、Resume Sessions、Stats、Settings、Cron へ移動します。

active session に対する `Kill` は tmux session と chat server を止める操作で、保存済み log や workspace metadata は残ります。そのため、Kill 後の session は archived 側に回り、あとで `Revive` して同じ session 名・workspace・agent 構成で起こし直せます。`Delete` は archived session に対してだけ使う操作で、保存されている log directory と関連する thinking data を消すため、Delete 後は Revive できません。停止と消去を分けているのは、「一旦止める」と「履歴ごと消す」を別の操作として扱うためです。

Stats では Messages、Thinking Time、Activated Agents、Commits のカードが出ます。Messages は sender 別と session 別、Thinking Time は agent 別と session 別、Commits は session 別の内訳を持ちます。加えて `Messages per day` と `Thinking time per day` の日別グリッドがあり、複数 session にまたがる作業量の推移をまとめて見られます。

Settings では Hub と chat UI の既定値をまとめて変えられます。Auto mode は agent の自律実行そのものではなく、agent がコマンド実行 permission を求めたときに、その prompt を自動承認するためのモードです。初回起動時は Auto mode、Awake、Sound notifications、Read aloud (TTS) は off なので、必要なものだけ Settings で on にして使います。

| 項目 | 内容 |
|------|------|
| Theme | Hub / chat UI のテーマ切り替え |
| User Messages / Agent Messages | user bubble と agent bubble のフォントを別々に指定 |
| Message Text Size | message 本文、file card、inline code、code block、table にまとめて反映 |
| Default Message Count | chat を再度開いたときに最初に表示する件数 |
| Auto mode | agent の command permission prompt を自動承認するモード |
| Awake (prevent sleep) | 端末の sleep 防止 |
| Sound notifications | `sounds/` 内の OGG を使う通知音 |
| Browser notifications | Hub を受け口にして全 session の background reply を受ける web push |
| Read aloud (TTS) | ブラウザ側の読み上げ |
| Bold mode | Hub / chat 全体で message text を太字化 |
| Starfield background | Black Hole theme 向けの星空背景 |
| Black Hole Text Opacity | Black Hole theme 上での user / agent message の文字不透明度 |

通知音は `sounds/` 配下の OGG ファイルをそのまま使います。`notify_*.ogg` を通常通知としてランダム再生し、`commit.ogg`、`awake.ogg`、`mictest.ogg`、`HH-MM.ogg` のような名前付きファイルも扱えます。好きな音声へ差し替える方法は [sounds/README.md](sounds/README.md) を参照してください。

HTTPS 配信時には Hub Settings に `App Install & Notifications` ブロックが現れます。想定している使い方は、Hub 自体を Home Screen / app shelf に追加し、そこで browser notification を許可して、その 1 つの Hub install を全 session 用の通知受け口にする形です。background reply のために各 session chat を個別に install する必要はありません。通知をタップすると元の session へ deep link で戻れるようになっており、対応環境では app icon から New Session や Stats への shortcut も使えます。

#### 4-1. Cron

Cron ページでは、既存の session と agent を対象に、1 日 1 回の prompt を定時実行できます。各 job には名前、実行時刻、対象 session、対象 agent、prompt 本文を保存し、個別の enable / disable、`Run Now`、削除を Hub 上から行えます。

Cron の実行経路は専用 transport ではなく、通常どおり pane と `agent-send` を使います。つまり、定時実行の結果も通常の user-to-agent 作業と同じ chat タイムラインへ戻ります。scheduler は pending run を追跡し、一定時間 reply が来なければ 1 回 reminder を送り、それでも返答が無ければ timeout として記録します。

### 5. Logs / Export

この repo では、長期一貫性と履歴参照のための保存先を役割ごとに分けています。repo / 環境全体の恒久ルールは `docs/AGENT.md`、session ごとに使い回す指示は brief、agent ごとの要約は memory、会話本体は `.agent-index.jsonl`、pane 側の表示は `*.ans` と `*.log` に残ります。`docs/AGENT.md` は静的、brief は半静的、memory は更新を伴う要約、JSONL は構造化された message log、pane capture は terminal 側の直接記録という役割分担です。

`agent-send` で流れた message は `sender`、`targets`、`msg-id`、`reply-to` を含む `.agent-index.jsonl` に追記され、pane log には `.meta` が付き、更新時刻や overwrite 履歴も残ります。

chat server は active session に対して pane log を約 2 分ごとに autosave し、chat UI の `Save Log` から即時保存もできます。これにより、会話の構造化ログと terminal の見た目ログを別々に辿れます。Pane Trace は最新の tail を見るための live viewer で、`.log` / `.ans` は後から残すための snapshot です。autosave はサーバー側で動くため、ブラウザのタブが開いているかどうかに依存しません。

session 中に行われた git commit も記録されます。workspace に触る各 commit はハッシュとメッセージ付きで残るため、会話ログとコード履歴を後から突き合わせることができます。

header menu の `Export` は、指定した件数ぶんの recent chat を static HTML としてダウンロードします。ローカルで確認用の HTML を切り出したいときや、保存用に持ち出したいときに使えます。出力される HTML は自己完結しており、chat server が動いていなくてもオフラインで開けます。最近の修正で standalone HTML の見た目も live chat にかなり近づき、添付の多い export でも PC とスマホの両方で崩れにくくなりました。

### 6. 堅牢性と復旧

この環境の session は中断に耐えられるように設計されています。意図的に停止された session、tmux が一時的に応答しない状態、session が存在しない状態をそれぞれ区別し、復旧処理が元の問題より悪い結果を招かないようにしています。

#### Pane log の保護

chat server は約 2 分ごとに pane の capture を autosave します。保存のたびに、新しい capture をまず一時ファイルに書き出し、既存の snapshot とサイズを比較します。旧ファイルが 1 KB 超かつ新しい capture がその半分未満の場合、pane リセットと判断し、旧 `.ans` / `.log` をタイムスタンプ付きの `.protected.ans` / `.protected.log` にコピーしてから上書きします。tmux pane が予期せずクリアされたり agent プロセスが再起動したりしても、リセット前の terminal 出力が保存され、後から確認できます。

#### tmux 健全性の認識

Hub と chat server が発行するすべての tmux コマンドは、タイムアウト付きのラッパーを通します。タイムアウトした tmux コマンドは「missing（存在しない）」ではなく「unhealthy（不調）」として報告されます。この区別により、tmux が単に遅いだけなのに「session が無い」と誤認することを防ぎます。unhealthy 状態が検出されると、自動 revive などの破壊的操作はブロックされ、Hub は 404 ではなく 503 を返して UI が正しい状態を表示できるようにします。

#### Session ライフサイクル: Kill, Revive, Delete

`Kill` は実行中の session の tmux window と chat server を停止しますが、保存済みの log、workspace metadata、`.meta` ファイルはそのまま残します。session は archived 一覧に移動し、あとで `Revive` すると保存された workspace path と agent 構成を使って tmux session を再作成できます。revive 前には tmux の健全性確認、workspace directory の存在確認を行い、最大 12 秒間ポーリングして session が実際に起動したことを検証します。この間に tmux が不調になった場合は、曖昧な状態を放置せずエラーで中止します。

`Delete` は archived session にのみ適用されます。保存されている log directory と関連する thinking time データを削除します。削除対象のパスは許可されたルート一覧と照合され、パストラバーサルは拒否されます。Delete した session は revive できません。

#### Autosave とメタデータ

2 分ごとの autosave、UI からの手動 `Save Log`、session kill のいずれで発生した pane log の保存も、session の `.meta` ファイルに記録されます。この JSON ファイルには session 名、workspace path、作成日時、最終更新日時、agent 一覧、そしてタイムスタンプと理由を持つ上書き履歴の配列が含まれます。上書き履歴により、session がいつ・なぜ保存されたかを後から追跡できます。

#### 層ごとの保存

`.agent-index.jsonl`（構造化メッセージログ）、`.ans` / `.log`（pane capture）、`.meta`（保存履歴）、`brief`（session 固有の指示）、`memory`（agent ごとの要約）を分離しているため、ある層が失われても他の層に影響しません。pane capture が壊れても会話ログは無事であり、JSONL がクリアされても terminal の記録は残ります。この分離は意図的なもので、それぞれの成果物が異なる復旧・レビュー目的を持ち、部分的な障害が部分的なままに留まるよう独立して保存されています。

## Quickstart

```bash
git clone https://github.com/estrada0521/multiagent-chat.git ~/multiagent-chat
cd ~/multiagent-chat
./bin/quickstart
```

`./bin/quickstart` は `python3` と `tmux` を確認し、必要なら依存導入の案内を出し、利用できる agent CLI の導入も対話で確認したうえで、local HTTPS を有効にするかを 1 回だけ尋ねます。必要なら既存の `mkcert` を使うか新規導入して、`~/.local/bin` に `multiagent` / `agent-index` / `agent-send` を配置して Hub を起動します。この段階では agent session はまだ作成されません。New Session を作る段階でも、未導入の agent を選んだ場合は改めて確認が入ります。

この対話的な CLI 導入対象には Kimi も含めました。ただし binary を入れるだけでは完了ではなく、実際に pane 内で応答させるには、この Mac 上で `kimi login` または Kimi CLI 内の `/login` を 1 回済ませる必要があります。

起動後は terminal に `Hub:` と `Hub (LAN / phone):` が表示されます。PC では `Hub:` の URL を開いてブックマークしておくと再訪しやすく、同じ Wi-Fi 上のスマホでは `Hub (LAN / phone):` の URL を開くと同じ session 一覧と chat UI を使えます。スマホ側でも New Session の作成、workspace path の入力、既存 session への復帰ができます。

local HTTPS は任意です。quickstart 中の分岐は次の通りです。
- `no`: HTTP のまま起動します。same-WiFi の Safari / browser 利用だけならこれで十分です。
- `yes`: HTTPS で起動します。iPhone / iPad で Home Screen web app、Hub 中心の browser notification、microphone、その他 secure browser features を使いたいときはこちらです。

`yes` を選んだ場合、Mac 側では local CA が system trust に入り、macOS では quickstart が自動で `rootCA.pem` を Finder で選択表示します。そのまま `rootCA.pem` を AirDrop / Files / Mail などで iPhone / iPad に送り、端末側で証明書プロファイルをインストールしたうえで `Settings > General > About > Certificate Trust Settings` から trust を有効化してください。`rootCA-key.pem` は共有しないでください。

`mkcert` の local CA は Mac ごとに別です。つまり、別の Mac の `https://192.168...` を iPhone / iPad から開きたい場合は、その Mac の `rootCA.pem` も別途インストールして trust する必要があります。

端末側で local HTTPS を trust できたら、Hub Settings で `Install This App` を使って Hub を追加し、その場で browser notification を許可します。現行の通知モデルは Hub 中心で、1 つの Hub install が active session 全体の background reply を受け取ります。

最初の session を作成したら、workspace 側の `docs/AGENT.md` を各 agent に送って、この環境での返信経路と `agent-send` の前提を読ませてから使い始めます。

Auto mode、Awake、Sound notifications、Browser notifications、Read aloud (TTS) は初回起動時は off です。必要なら Hub の Settings から on にします。

## 更新 / 削除

既存の導入を更新するときは、repo を pull して quickstart をもう一度実行します。

```bash
cd ~/multiagent-chat
git pull --ff-only
./bin/quickstart
```

これで repo の内容を更新しつつ、依存 / CLI / local HTTPS の確認をやり直し、必要なら `~/.local/bin` の symlink も張り直します。`logs/` 配下の session、保存済み log、archived history は消えません。

グローバルに使える command だけ外したい場合は、quickstart が置いた symlink だけ消せば十分です。

```bash
rm -f ~/.local/bin/multiagent ~/.local/bin/agent-index ~/.local/bin/agent-send
```

ローカル環境を丸ごと消したい場合は、まず active session を止めます。public access を有効にしていたなら、それも止めてから repo を削除してください。

```bash
cd ~/multiagent-chat
bin/multiagent kill --all
bin/multiagent-cloudflare quick-stop
bin/multiagent-cloudflare named-stop
bin/multiagent-cloudflare daemon-uninstall
rm -f ~/.local/bin/multiagent ~/.local/bin/agent-index ~/.local/bin/agent-send
cd ~
rm -rf ~/multiagent-chat
```

保存済み log や archived session を残したいなら、repo directory は消さずに symlink だけ外してください。

## Public Access (Optional)

<p align="center">
  <img src="cloudflare-color.svg" alt="Cloudflare" width="84">
</p>

`./bin/quickstart` までで、ローカルまたは同一 LAN からの利用は完了です。外部公開はその後に足す追加機能で、公開 URL を作ると LAN の外からでも同じ Hub / chat UI をブラウザで開けるようになります。外部公開の手段は Cloudflare に限りませんが、この repo には Cloudflare ルートをそのまま使える command と docs を用意しています。以下は Cloudflare を使う場合の最短導線です。

公開 URL にするとできること:
- LAN の外から `https://<your-hostname>/` で Hub を開ける
- chat は `/session/<name>/...` のまま外から開ける
- ローカル/LAN で既にできるスマホ操作を、LAN の外からでも同じように行える
- これは local HTTPS / `mkcert` とは別系統で、public URL 自体のために iPhone へ local CA を入れる必要はない

Cloudflare ルートで自分で用意するもの:
- Mac 側の `cloudflared`
- 安定した公開 URL を使うなら、Cloudflare 管理下に置いた独自ドメイン(zone)
- 公開先を制限するための Cloudflare Zero Trust / Access 設定
- 外から使いたい間、Mac を sleep させない運用

Cloudflare を使う場合の実際の流れは次のとおりです。

1. まず一時公開だけ試す
```sh
bin/multiagent-cloudflare quick-start
```
- Quick Tunnel で一時的な `https://...trycloudflare.com` を取ります
- 確認後は `bin/multiagent-cloudflare quick-stop` で戻せます
- これは短時間の確認用です。外から自分の Mac へ継続的につなぐ用途には向きません

2. 自分のドメインで固定 URL にする
```sh
bin/multiagent-cloudflare named-login
bin/multiagent-cloudflare named-setup multiagent <your-hostname>
bin/multiagent-cloudflare named-start
```
- `named-login` は Cloudflare の browser login と origin cert 導入です
- `named-setup` は tunnel 作成または再利用、DNS route、config 書き込みを行います
- `named-start` 後は `https://<your-hostname>/` が Hub になります

3. Cloudflare Access を前段に置くことを推奨
```sh
bin/multiagent-cloudflare access-enable <team-name> <aud-tag>
```
- 公開先を自分や許可した identity だけに制限できます
- Mac に外から入れる以上、変わった事情がない限り Access 付きでの運用を推奨します

4. 常時公開したいなら daemon 化する
```sh
bin/multiagent-cloudflare daemon-install
```
- named tunnel の監視を入れて、login 後も public edge を維持します

5. Mac を sleep させない
- Mac が sleep すると public URL からは到達できません
- 長時間安定して使うなら、給電できる外部モニターや電源接続を使い、Mac 本体は起こしたままにしておく運用を推奨します
- 実運用では、外部モニターをつないだまま画面だけ黒くして、Mac 自体は起こしたままにすると安定しやすいです

実運用イメージ:
- 普段は `./bin/quickstart` でローカル/LAN 利用
- 外からも使いたくなったら Cloudflare を追加
- 一時確認は Quick Tunnel
- 実運用は named tunnel + 独自ドメイン + Cloudflare Access
- 外から使う間は Mac を sleep させない

Cloudflare 以外の reverse proxy / tunnel を使う場合も、考え方は同じです。local/LAN の Hub の前に public hostname を置き、必要なら認証を前段に足します。Cloudflare で進める場合の詳細は [docs/cloudflare-quick-tunnel.md](docs/cloudflare-quick-tunnel.md)、[docs/cloudflare-access.md](docs/cloudflare-access.md)、[docs/cloudflare-daemon.md](docs/cloudflare-daemon.md) を参照してください。

## Requirements

- `python3`
- `tmux`
- macOS または Linux

macOS では Homebrew が入っていると導入しやすいです。

## Main Commands

| コマンド | 内容 |
|------|------|
| `./bin/quickstart` | 依存確認つきで Hub を起動 |
| `./bin/multiagent` | session の作成、再開、一覧表示、agent 追加 / 削除、save |
| `./bin/agent-index` | Hub、chat UI、Stats、Settings、log viewer |
| `./bin/agent-send` | user や他 agent への message 送信 |
| `./bin/agent-help` | この環境内の agent 向け簡易 cheatsheet |
| `./bin/multiagent-cloudflare` | 必要時のみ public access を追加 |

## Docs

- [docs/updates/README.md](docs/updates/README.md): 節目ごとの更新ノートとリリース要約
- [docs/updates/beta-1.0.5.ja.md](docs/updates/beta-1.0.5.ja.md): `beta 1.0.4` 以降の変更点
- [docs/AGENT.md](docs/AGENT.md): この環境で動く agent 向けの運用ガイド
- [docs/chat-commands.md](docs/chat-commands.md): chat UI の command、Pane Trace、quick action 一覧
- [docs/design-philosophy.md](docs/design-philosophy.md): なぜ tmux、chat、mobile、layered logs をこの形で組み合わせているか
- [docs/gemini-direct-api.md](docs/gemini-direct-api.md): Gemini direct bridge、runner、JSONL/runtime note の扱い
- [docs/technical-details.md](docs/technical-details.md): 実装構成、message transport、log / export / state の技術詳細
- [docs/cloudflare-quick-tunnel.md](docs/cloudflare-quick-tunnel.md): Cloudflare Quick Tunnel / named tunnel
- [docs/cloudflare-access.md](docs/cloudflare-access.md): public Hub を Cloudflare Access で保護する方法
- [docs/cloudflare-daemon.md](docs/cloudflare-daemon.md): public tunnel の常駐運用
- [sounds/README.md](sounds/README.md): 通知音ファイルの置き方と命名規則
