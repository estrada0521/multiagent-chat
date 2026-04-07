# 開発者ガイド

`multiagent-chat` の内部実装を触る方向けのガイドです。

## 1. リポジトリ構成（概要）

| 領域 | 主なファイル |
|---|---|
| session ライフサイクル CLI | `bin/multiagent`, `bin/lib/multiagent_*_core.sh`, `lib/agent_index/multiagent_*_core.py` |
| agent 間メッセージ配送 | `bin/agent-send`, `lib/agent_index/agent_send_core.py` |
| Hub backend/UI | `lib/agent_index/hub_server.py`, `hub_core.py`, `hub_session_query_core.py`, `hub_stats_core.py`, `hub_chat_supervisor_core.py`, `hub_header_assets.py` |
| Chat backend/UI | `lib/agent_index/chat_server.py`, `chat_core.py`, `chat_*_core.py`, `chat_assets.py`, `chat_template.html` |
| file / preview API | `lib/agent_index/file_core.py`, `file_preview_3d.py` |
| Cron 実行系 | `lib/agent_index/cron_core.py` |
| 共通 state/log helper | `state_core.py`, `jsonl_append.py`, `instance_core.py` |
| テスト | `tests/test_*.py` |

## 2. ローカルセットアップ

1. Python 3 と tmux を用意
2. quickstart 実行
   ```bash
   ./bin/quickstart
   ```
3. 動作確認用 session 起動
   ```bash
   ./bin/multiagent --session demo --workspace "$(pwd)" --agents claude,codex
   ```

## 3. テスト実行

標準テスト（CI と同系列）:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

カバレッジ付き:

```bash
python3 -m pip install coverage
coverage run -m unittest discover -s tests -p 'test_*.py'
coverage report -m
```

CI は `.github/workflows/python-tests.yml` で実行され、coverage XML artifact も保存されます。

## 4. 新しい agent を追加する

1. `lib/agent_index/agent_registry.py` に `AgentDef` を追加
2. `agent_icons/` に対応 SVG を追加
3. 必要なら provider 固有の sync/runtime 解析を追加
   - `chat_core.py` と関連 `chat_*_core.py`
4. `tests/` の関連ケース（registry/sync/routing/UI）を追加・更新

## 5. Hub/Chat HTTP API を触るとき

- Hub ルート: `hub_server.py` の route dispatch table（`_GET_ROUTE_HANDLERS` / `_POST_ROUTE_HANDLERS`）と、それぞれの `_get_*` / `_post_*` handler
- Chat ルート: `chat_server.py` (`do_GET` / `do_POST`)
- API 一覧: `docs/http-api.md` / `docs/http-api.en.md`

ルート追加時の方針:

1. レスポンス形 (`ok`, `error`, key 名) を安定させる
2. 既存 helper を再利用する
3. parsing/dispatch/境界条件のテストを入れる
4. `/session/<name>/...` 経由（Hub プロキシ）でも成立する前提で実装する

## 6. この repo のリファクタ方針

- まとまりのある責務は `*_core.py` へ抽出
- shell は薄く、永続ロジックは Python core へ寄せる
- 既存の挙動・エラー意味を維持する
- routing/sync/state を触る変更は回帰テストを追加する

## 7. リリース運用

更新ノートは `docs/updates/` に置きます。

リリース公開コマンド:

```bash
./bin/multiagent-release --tag vX.Y.Z --notes docs/updates/beta-X.Y.Z.md
```

タグ/手動公開フローは `.github/workflows/publish-release.yml` にあります。
