# multiagent-chat v1.0.8

English version: [beta-1.0.8.md](beta-1.0.8.md)

Released: 2026-04-08

この release は、新しい workbench shell を前提に組み直した最初の版です。古い Hub 導線を大きく整理し、session 起動も draft-first の流れへ移しました。

## Highlights

### Hub と chat を 1 つの workbench として扱うようにした

- desktop では左の sidebar に session list、右に選択中 chat を埋め込む構成へ変えました。
- mobile は desktop の split view を無理に再現せず、session list を開いたときだけ全画面寄りに切り替えます。
- session 切り替えは同じ shell 内で完結し、kill/delete 時の白画面遷移も止めました。

### New Session は form 入力ではなく workspace 選択から始まる

- `New Session` を押すと、まず workspace picker が開きます。
- workspace を選ぶと、その directory 名を session 名として draft chat がすぐ開きます。
- この時点ではまだ tmux を起動せず、最初の message と選択中の初期 agent が、実際にどの pane を起動するかを決めます。

### 古い Hub 機能を物理的に削除した

- Cron、Stats、旧 Resume Sessions page は削除しました。
- Settings は black-hole baseline、固定 desktop width、残す chat/runtime 制御を中心に絞り込みました。
- 古い standalone Hub error page も廃止し、失敗時は workbench へ戻す flow に変えました。

### chat の見た目と sync の安定性を改善した

- code/file preview の typography を chat 本文に近づけ、HTML preview には text/web 切り替えを追加しました。
- thinking 行を詰め、Codex runtime label を詳しくし、agent 出力内の local file link も正しく描画するようにしました。
- cloud-backed workspace での sync cursor 探索を強化し、Claude/Qwen/Codex の draft launch 周辺も安定化しました。
