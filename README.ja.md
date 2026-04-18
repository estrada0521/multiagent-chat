# Multiagent Chat

[English](README.md)

ローカルで完結する HTTPS 専用のチャット基盤です。複数の CLI エージェント
（Claude / Codex / Gemini / Copilot / Cursor / OpenCode / Kimi / Qwen など）を
1 つの会話画面に並べ、同じセッションへ同時にメッセージを送れます。セッション
はこのマシン上に保存され、各エージェントは監視下の `tmux` pane で動きます。
次の 3 つのルートから同じ Hub へアクセスできます。

- **このマシンのブラウザ**
- **macOS ネイティブのデスクトップアプリ**
- **同一 LAN 上の iPhone / iPad の PWA**（必要に応じて Cloudflare Tunnel で
  外部公開）

3 ルートはすべて同じローカル `Hub` プロセス、同じセッション保存先、同じ
mkcert 署名の HTTPS 証明書を共有します。HTTP モードはありません。

## 対応エージェント CLI

次の CLI がローカルにインストール＆ログイン済みなら、Hub から自由に組み合わせ
られます。

- Claude (`claude`)
- Codex (`codex`)
- Gemini (`gemini`)
- Copilot (`copilot`)
- Cursor (`cursor-agent`)
- OpenCode (`opencode`)
- Kimi (`kimi`)
- Qwen (`qwen`)

必要なものだけで構いません。`quickstart` / `desktop-quickstart` は初回実行時
に未導入のものを Homebrew / npm 経由で入れるか確認します。

## 前提条件

`quickstart` 系を実行する前に用意しておくもの。

- `brew` として使える Homebrew が入った macOS
- Xcode Command Line Tools: `xcode-select --install`
- `cargo` が使える Rust（デスクトップアプリを使う場合のみ）: <https://rustup.rs>
- `PATH` に `~/.local/bin` を含めておく（`multiagent` / `agent-index` /
  `agent-send` の symlink がここに作られる）

`quickstart` 系は `python3` / `tmux` / `mkcert` などの軽い runtime 依存を
Homebrew で自動導入しますが、Homebrew 本体・Rust 本体・各エージェント CLI の
ベンダーアカウントまでは面倒を見ません。

## ルート 1 — ブラウザ（Web）

1 コマンドでセットアップと Hub 起動。

```bash
./bin/quickstart
```

セットアップが終わると Hub が次の URL で待ち受けます。

```text
https://127.0.0.1:8788/
```

初回実行時に mkcert のローカル CA をシステム信頼ストアへ入れるため、Safari /
Chrome / Firefox いずれでも警告なしで開けます。

補助オプション:

```bash
./bin/quickstart --setup-only   # セットアップだけ行い Hub は起動しない
./bin/quickstart --no-open      # Hub は起動するがブラウザを開かない
```

## ルート 2 — デスクトップアプリ（macOS）

1 コマンドでセットアップ + ビルド + 起動。

```bash
./bin/desktop-quickstart
```

デスクトップアプリは自身で Hub を抱えて起動するので、別途 `quickstart` を走
らせる必要はありません。初回ビルド時に `tauri-cli` を
`.multiagent/tools/tauri-cli/` 配下にキャッシュします。

補助オプション:

```bash
./bin/desktop-quickstart --dev          # cargo tauri dev
./bin/desktop-quickstart --build-only   # .app をビルドするが開かない
./bin/desktop-quickstart --setup-only   # セットアップだけ行いビルドしない
./bin/tauri-build                       # 再ビルドのみ（対話セットアップを省略）
```

## ルート 3 — モバイル PWA（iPhone / iPad）

PWA も同じ Hub に接続します。接続方法は 2 種類。

### 3a. 同一 LAN（LAN 内だけで使う）

1. Mac 側で `./bin/quickstart` を起動し、Hub をポート `8788` で動かす。
2. Mac 側の `rootCA.pem` の場所を確認する（quickstart の出力に表示されます。
   または `mkcert -CAROOT` で取得）。
3. `rootCA.pem` を AirDrop / Files / Mail などで iPhone / iPad へ転送する。
4. 端末で証明書プロファイルをインストールし、`設定 > 一般 > 情報 > 証明書
   信頼設定` で有効化する。
5. Safari で `https://<Mac-LAN-IP>:8788/` を開き、`共有 > ホーム画面に追加`。

`rootCA-key.pem` は絶対に共有しないでください。

### 3b. Cloudflare Tunnel で外部公開

端末が別ネットワークにいる場合や、固定公開 URL が必要な場合に使います。

```bash
brew install cloudflared
./bin/multiagent-cloudflare quick-start
```

固定ドメインで運用する場合:

```bash
./bin/multiagent-cloudflare named-login
./bin/multiagent-cloudflare named-setup <tunnel-name> <hostname>
./bin/multiagent-cloudflare named-start
```

Cloudflare 側が独自の HTTPS 証明書を発行するため、tunnel 経由のアクセスでは
`3a` の mkcert プロファイルは不要です。

状態確認と停止:

```bash
./bin/multiagent-cloudflare status
./bin/multiagent-cloudflare quick-stop   # または named-stop
```

## トラブルシューティング

- `multiagent: command not found` → `~/.local/bin` を `PATH` に追加するか、
  `quickstart` を再実行して symlink を作り直してください。
- macOS アップデート後にブラウザが証明書警告を出す → `mkcert -install`、
  または `./bin/quickstart --setup-only` を再実行してください。
- ポート `8788` が使用中 → `AGENT_INDEX_HUB_PORT=<port>` を設定してから Hub
  を起動してください。
- デスクトップビルドが `cargo install tauri-cli` で失敗する → Xcode CLT と
  Rust が最新か確認してください（`rustup update`）。
