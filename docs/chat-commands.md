# Chat Commands

chat UI で使う command と pane control をまとめた補助メモです。README は概要、ここは現時点の一覧です。

## Pane Trace

- mobile: thinking 行を押すと埋め込み Pane Trace viewer を開きます
- desktop: thinking 行を押すと選択中 agent の Pane Trace を popup window で開きます
- desktop の `Terminal` は terminal 本体を開きます
- mobile の `Terminal` は Pane Trace につながります

## Slash Commands

slash command は composer の先頭で `/` を入力すると候補が出ます。

| command | 内容 |
|------|------|
| `/memo [text]` | `user` 自身へのメモ。本文が空でも Import 添付だけで送れます（target 未選択の通常送信も self 宛） |
| `/load` | 現在の `memory.md` を selected agent に送ります |
| `/memory` | selected agent に `memory.md` の更新を指示します |
| `/model` | 選択中 pane に `model` を送ります |
| `/up [count]` | 選択中 pane に上移動を送ります。`count` 省略時は 1 |
| `/down [count]` | 選択中 pane に下移動を送ります。`count` 省略時は 1 |
| `/restart` | 選択中 agent pane を再起動します |
| `/resume` | 選択中 agent pane を再開します |
| `/ctrlc` | 選択中 agent pane に `Ctrl+C` を送ります |
| `/interrupt` | 選択中 agent pane に `Esc` を送ります |
| `/enter` | 選択中 agent pane に `Enter` を送ります |

`/up` と `/down` の `count` は 1 から 100 の範囲に丸められます。

## Quick Actions

composer 下の quick action や `Cmd` / `Command` メニューから使える操作です。

| UI | 内容 |
|------|------|
| `Import` | ローカル端末のファイルを session uploads に追加 |
| `Load` / `Load Memory` | 現在の `memory.md` を selected agent に送ります |
| `Memory` / `Save Memory` | 現在の会話をもとに `memory.md` を更新させます |
| `Save` / `Save Log` | pane log の snapshot を即時保存します |
| `Restart` | 選択中 agent pane を再起動します |
| `Resume` | 選択中 agent pane を再開します |
| `Ctrl+C` | 選択中 agent pane に `Ctrl+C` を送ります |
| `Enter` | 選択中 agent pane に `Enter` を送ります |
| `Esc` / `Interrupt` | 選択中 agent pane に `Esc` を送ります |

## Header Menu

| UI | 内容 |
|------|------|
| `Finder` | 現在の session workspace を Finder で開きます |
| `Camera` | 直接撮影と音声入力に寄せた mobile-first camera overlay を開きます |
| `Pane Trace` | デスクトップでは専用 Pane Trace window を開き、mobile では埋め込み viewer を使います |

## Notes

- pane control 系の command や quick action は、selected targets が空だと実行できません
- command は今後増える前提なので、README ではなくこのファイルを更新基点にする想定です
