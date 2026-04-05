# bin/agent-index 分割・再編 徹底詳細レビュー報告

対象:
- `bin/agent-index` (Launcher)
- `lib/agent_index/hub_server.py`
- `lib/agent_index/chat_server.py`
- `lib/agent_index/chat_port_cli.py`
- `lib/agent_index/index_viewer.py`

評価者: シニア・ソフトウェアアーキテクト

---

## 1. Import-time side effects (インポート時の副作用)

`if __name__ == "__main__":` ガードの設置により、主要なサーバー起動ロジックはカプセル化されましたが、モジュール設計の観点から以下の細部を確認しました。

### 1.1 グローバルスコープでの初期化
`hub_server.py` および `chat_server.py` では、グローバルスコープにおいて `_initialized = False` や `Path()` インスタンスの生成が行われています。
- **評価**: これらは単なるオブジェクトの生成であり、ネットワークバインドやスレッド起動などの「重い副作用」ではありません。
- **潜在的リスク**: ただし、`hub_server.py` の L115 前後で `_scheme = "http"` が初期化されていたり、`restart_lock` が生成されています。これらは `initialize_from_argv()` の外にありますが、ステートレスな再利用を妨げるほどではありません。

### 1.2 initialize_from_argv() 内でのスレッド起動
`hub_server.py` では、`initialize_from_argv()` 内で `hub_push_monitor` と `cron_scheduler` のスレッドを `daemon=True` で開始しています。
- **評価**: **これは「設計上の副作用」として認識すべき点です。** 
- **影響**: 他の Python スクリプトから `hub_server` の一部（例えば定数やユーティリティ）をインポートしようとして `initialize_from_argv()` を呼んだ場合、意図せずバックグラウンドスレッドが走り始めます。
- **推奨**: スレッドの開始（`.start()`）自体は `main()` 関数内に移動し、`initialize_from_argv` は「設定の確定」のみに専念させるのが、より純粋なモジュール境界となります。

---

## 2. `initialize_from_argv()` 方式の設計評価

Bash から Python への「構成情報の引き渡し」を位置引数（sys.argv）経由で行うこの方式を評価します。

### 2.1 メリット
- **疎結合の維持**: Python モジュール側が環境変数に依存せず、明示的に引数を受け取ることで、テスト容易性（Testability）が向上しています。
- **stdlib-only 制約への合致**: `argparse` すら使わず `sys.argv[1:]` を直接扱うことで、最小限のコード量で動作を担保しています。

### 2.2 設計上の懸念点
- **引数の順序依存**: `chat_server` は現在 12 個もの位置引数を受け取っています。1つでも順序がズレるとシステムが沈黙するため、Launcher 側（`bin/agent-index`）との同期が非常にデリケートです。
- **グローバル変数の多用**: `global runtime` などを通じて初期化を行っています。これは「一度だけ起動されるサーバー」という前提では機能しますが、将来的に単一のプロセス内で複数の ChatRuntime を動かす（マルチテナント化）ような拡張には向きません。

---

## 3. `bin/agent-index` に残る分割方針との矛盾・残骸

Launcher 側を徹底的に精読した結果、以下の「残骸」を特定しました。

### 3.1 `HTTPS_SCHEME` と `HTTPS_MODE` の重複ロジック
`bin/agent-index` の L595-598 で `HTTPS_SCHEME` を決定していますが、同様の判定（`MULTIAGENT_CERT_FILE` の有無）が Python 側（`hub_server.py` の `main` 内）でも再度行われています。
- **矛盾**: 「環境のセットアップは Launcher、ビジネスロジックは Python」という方針ですが、SSL の有効判定という「ポリシー」が両方に散らばっています。

### 3.2 埋め込み AppleScript
L201 からの `osascript`（Safari 操作）は、依然として Bash 内に文字列として埋め込まれています。
- **評価**: これは「OS統合」の Bootstrap 領域であるため Bash に残る妥当性はありますが、コード量が増える場合は Python 側のユーティリティへ移譲する対象となります。

### 3.3 依存関係チェック (`ensure-multiagent-deps`)
冒頭の依存関係チェックは Bash に留まっています。これは正しい設計です（Python が入っていない状態で Python を動かせないため）。

---

## 4. この段階で直すべきクリティカル事項

現時点での実装において、修正を強く推奨する事項は以下の **1点** です。

### 【クリティカル】 `ensure_chat_server` の `script_path` 依存
`lib/agent_index/hub_core.py` の `ensure_chat_server` メソッドにおいて、新しいチャットサーバーを起動する際に依然として `[str(self.script_path), "--session", ...]` を `subprocess.Popen` で呼び出しています。
- **問題点**: `self.script_path` は通常 `bin/agent-index` を指しています。つまり、**「Python ライブラリ（hub_core）が、自分を呼び出した Bash ラッパー（agent-index）を再帰的に呼び出す」** という循環依存のような構造が残っています。
- **最適解**: `hub_core` または `hub_server` からチャットサーバーを起動する際は、Bash を経由せず、直接 `python3 -m agent_index.chat_server` を呼び出すべきです。これにより、Bash への依存を完全に断ち切ることができます。

---

## 5. 結論

本再編は、システムを「一つの巨大なスクリプト」から「管理可能なパッケージ」へと脱皮させることに成功しています。

上述した **「Python からの Bash 再帰呼び出しの除去」** さえ完了すれば、モジュール間の境界線は盤石となり、今回の分割方針は完璧に貫徹されたと評価できます。

以上報告します。
