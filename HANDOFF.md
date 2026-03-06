# Handoff

このワークスペースでは、`bin/multiagent` は保護対象として扱う。

## 現在の方針

- 本体は `bin/multiagent`
- 実験用ブランチ相当は `bin/multiagent-dev`
- 新機能は `bin/multiagent-dev` にのみ追加する
- テストも `bin/multiagent-dev` に対して行う

## 変更済み内容

- `bin/multiagent` は未変更
- `bin/multiagent-dev` を追加済み
- `bin/multiagent-dev` に以下を追加済み
  - `list` サブコマンド
  - `list` は要約表示
  - `list --verbose` は詳細表示
  - `status` サブコマンド
  - `status --all`
  - `resume` サブコマンド
  - `resume --latest`
  - `kill` サブコマンド
  - `kill --all`
  - `rename` サブコマンド
  - 既定セッション名はカレントディレクトリ名
  - 既定ログディレクトリ `logs-dev/`
  - ログは `<log-dir>/<session>_<yymmdd>_<yymmdd>/` に保存し、詳細時刻と上書き記録は `.meta` に入れる
  - 既存セッションの自動 kill はしない
  - `status` / `resume` / `kill` は、`--session` 未指定時に現在 workspace の既存セッションを 1 件だけ自動解決する

## Git 状態

- このディレクトリは Git 初期化済み
- 初回コミット: `3c26f0a` (`Initialize multiagent scripts`)
- 大きい動画 `d1.mov`, `d2.mov` は未追跡のまま

## テスト手順

- `MULTIAGENT_DEV_TESTING.md` を参照

## 次にやる候補

- `status` の表示改善
- 実験後に問題なければ `bin/multiagent` へ反映するか検討
