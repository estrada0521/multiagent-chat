# multiagent-chat beta 1.0.5

English version: [beta-1.0.5.md](beta-1.0.5.md)

公開日: 2026-04-04

このノートは、beta 1.0.4 のリリース準備を行った 2026-04-02 の commit `cbe21cf` 以降の変更をまとめたものです。

## 主な更新

### camera mode を mobile chat の正式な入力面にした

- 画像撮影を通常 composer の横機能として扱うのではなく、mobile 向けの専用 `Camera` action として chat に組み込みました。
- overlay には live camera feed、選択中 target agent、最近の agent reply、即時撮影用 shutter を同居させています。
- 撮影画像は upload 前に縮小し、その後は通常の構造化 message path で送るため、camera 経由の送信も `.agent-index.jsonl`、file menu、export の流れにそのまま乗ります。
- 同じ overlay に voice input も入り、Web Audio が取れる環境では live waveform、取れない環境では loop animation fallback に自動で切り替わる hybrid 表示になりました。
- この release では、spacing、divider、message animation、chip size、overlay hierarchy を main chat renderer に寄せる調整にもかなりの比重を置いています。

### direct provider path を Gemini 以外にも広げた

- composer から `/gemma` を使えるようにし、新しい Ollama direct runner と normalized event plumbing を追加しました。
- ただしこれは pane 駆動の CLI agent と同一ではありません。同じ timeline に結果は返しますが、pane local memory、file mutation tool、CLI session state を自動で持つわけではありません。
- つまりこの release は、local model への入口を足しつつ、direct API path と coding agent pane を安易に同一視しない構成を取っています。

### preview、Pane Trace、runtime hint も継続的に詰めた

- Markdown preview はさらに暗めに揃え、header visibility も修正し、local / public 間の preview chrome を詰めました。
- Pane Trace polling と compact runtime indicator も再調整し、長時間 session の監視時に browser 側の負荷を抑えつつ見やすさを維持しています。
- thinking 行の下に出る runtime hint も provider ごとに抽出範囲を広げ、`Ran`、`Edited`、`ReadFile`、`Grepped`、`Searching` などの pane-side tool summary がより安定して見えるようになりました。

### documentation を現実の UI に合わせ直した

- README、command reference、technical notes を更新し、現在の slash command 群、direct-provider command、mobile camera workflow に合わせました。
- あわせて、すでに消えた raw-send 前提の記述も整理し、公開 docs と実際の UI のズレを減らしています。

## そのほか

- Copilot の auto mode は、boxed な directory-access approval prompt にも最小限の自動承認で対応するようになりました。
- icon の instance badge や message width control も再調整され、mobile / desktop 間の見え方が少しずつ揃っています。
