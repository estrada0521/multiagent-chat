# Multiagent（ローカル）

複数の AI エージェントを **tmux** 上で動き、**Hub** と **チャット UI** からまとめて操作するためのツール群です。

---

## 最短で始める（受け取った人向け）

### 前提

- **macOS または Linux**
- **macOS の場合: Homebrew が入っていること**（`brew --version` が通る）。このリポジトリから Homebrew 本体のインストールは行いません。初回だけ次の **1 行**をターミナルで実行（管理者パスワードの入力が求められます）。終了後、表示に従い `brew shellenv` を `~/.zprofile` へ追記し、ターミナルを開き直してください。

  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```

- **tmux** — バインドルは含みません。macOS では `brew install tmux`（無い場合 `ensure-multiagent-deps` が確認）。Linux は各パッケージ（例: `sudo apt install tmux`）。
- **Python 3** — macOS では `brew install python3` で可（同様に `ensure-multiagent-deps` が確認）。
- **各エージェントの CLI**（Claude Code、Codex CLI、Gemini CLI など、使いたいもの）は別途インストール済みであること

`./bin/quickstart` や `multiagent` を叩いた時点で **Python 3 や tmux が無い**場合、macOS（**Homebrew が PATH にあること**）や主要な Linux では **`bin/ensure-multiagent-deps`** が自動実行され、足りないパッケージのインストールを試みます（Linux では `sudo` が必要なことがあります）。自動チェックを止めたいときは環境変数 `MULTIAGENT_SKIP_DEPS_CHECK=1`。Windows ネイティブや未対応のディストリビューションでは手動インストールが必要です。

通知音を使う場合は、好きな **OGG ファイルを `sounds/` に置いてください**（clone 直後は無音で動きます）。ファイル名と意味は [sounds/README.md](sounds/README.md) を参照。

### 1 コマンドで「インストール → Hub 起動」

```bash
git clone <GitHub の Code からコピーした HTTPS/SSH URL> multiagent
cd multiagent
./bin/quickstart
```

`quickstart` は次を順に実行します。

1. 不足していれば **`bin/ensure-multiagent-deps`** — macOS では **Homebrew 前提**で `tmux` / `python3` を確認
2. **`bin/ensure-multiagent-agent-clis --interactive`** — 未導入のエージェント CLI を [y/N] で確認。**macOS + Homebrew では Cursor も `brew install --cask cursor` と `cursor-cli` で入れられます**（スキップ可）
3. `multiagent --install` — `~/.local/bin` に `multiagent` / `agent-index` / `agent-send` などへのシンボリックリンクを作成（既にあればスキップ表示）
4. `agent-index --hub` — **ローカル Hub** を起動し、可能ならブラウザで開く

ターミナルに **Hub の URL** が出ます（例: `Hub:` と `Hub (LAN / phone):`）。**スマホでは LAN IP 側の Hub URL** を Safari で開いてください。Hub に入れば **New Session** や **Resume** は画面から進められます。

**補足（tmux）:** Hub の起動自体は **tmux が無くても**進みますが、**セッションを作って各エージェントのペインを起動する処理は tmux 必須**です。画面にセッションが出ず実行に失敗する場合は、`tmux` が PATH にあるか確認してください。

### HTTPS と iPhone（証明書）

Mac 側に **mkcert** があると、Hub は `certs/cert.pem` を自動生成し **`https://`** で待ち受けることがあります。ブラウザは Mac では問題なくても、**iPhone は同じルート CA を信頼していない**ため、接続時に証明書警告が出ることがあります。

次のような対応が一般的です。

1. Mac で mkcert の CA フォルダを確認: `mkcert -CAROOT`（例: `rootCA.pem`）
2. その **ルート証明書** を AirDrop・ファイル共有などで iPhone に送る
3. iPhone でインストールし、**設定 → 一般 → 情報 → 証明書信頼設定** でその CA を **フル信頼** にする
4. 再度、ターミナルに表示された **Hub の `https://<LAN-IP>:ポート/`** を開く

**HTTP のまま**（mkcert が無い、または `certs/` に鍵がない）運用なら、多くの場合 **平文の `http://`** で LAN から Hub を開けます（上記の手間は不要）。

Let's Encrypt など **ブラウザが既に信頼する CA** で Public 向けに終端 TLS する構成は、別途リバースプロキシ／トンネル側の話です（下記ドキュメント参照）。

---

## インターネット越し（Public / 独自ドメイン）

**同じ Wi‑Fi 以外**から Hub を開きたい場合は、自分で **リバースプロキシ・トンネル・DNS** を用意する必要があります。リポジトリには特定の個人ドメインは含めません（例: ご自身の `example.com` や Cloudflare のホスト名など）。

参考ドキュメント（内容は環境に合わせて読み替えてください）:

- [docs/cloudflare-quick-tunnel.md](docs/cloudflare-quick-tunnel.md) — クイックトンネル例
- [docs/cloudflare-access.md](docs/cloudflare-access.md) — Access 前に置く例
- [docs/cloudflare-daemon.md](docs/cloudflare-daemon.md) — 常時系のメモ

Hub 側では `MULTIAGENT_PUBLIC_HOST` などで「外から見えるホスト名」を伝える構成になっています（各ドキュメント・`bin/agent-index` 内のコメント参照）。

---

## その他

- 全体像・コマンド一覧: [OVERVIEW.md](OVERVIEW.md)
- エージェント定義・拡張: `lib/agent_index/agent_registry.py`

---

## ライセンス

（公開時に LICENSE を置き、ここに名前を追記してください。）
