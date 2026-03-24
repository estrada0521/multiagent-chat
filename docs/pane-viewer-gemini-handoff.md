# （旧）Pane Trace 引き継ぎメモ — **内容は古いです**

**2026-03 時点:** ヘッダーぶら下げや `__HEADER_TRAILING__` / `__agentIndexClosePaneTrace` などの試行は **リポジトリから撤回済み**です。Gemini へ渡す場合は **このファイルを使わないでください**。

## 現在の実装の要点（更新）

- `#paneViewer` は **`body` 直下**（`hub-page-header` 内には置かない）。
- **見た目**は `.hub-page-menu-panel` と同系（`rgba` + `blur(20px)`、ソフトライトは `0.92` + 弱い blur）。**縦**は `top: var(--header-menu-top)` + `bottom: 0` + 下 safe-area（メニューパネルと同じ考え方）。
- `syncHeaderMenuFocus` は **メニュー開**または **Pane 表示中**で `menu-focus` と `--header-menu-*` を更新。
- **×**（`#paneViewerClose`）で閉じる。プレーンテキスト trace（`stripAnsiForTrace`）。

`chat_core.trace_content` の `capture-pane` 取得行数などは、Pane DOM とは独立した変更のまま残っている場合があります。

---

*以下は歴史的メモ（要件整理用）。コードと一致しません。*

- 下端まで伸ばす・× なしで他ボタンで閉じる・最新行表示 等は **未実装または撤回**。
