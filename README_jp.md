# Agent Window

Agent Windowは、複数のAgent CLIが動いている作業場所を外から眺めるための、UNIX哲学に則った**macOS向けのローカルインターフェース**です。

各Agent CLIはtmuxのpane内で通常どおり起動します。APIやSDK等を経由してmodelを呼ぶことはありません。**CLIが既に備えている機能を、そのまま利用します。**

[設計哲学](DESIGN_jp.md) · [English](README.md)

<p align="center">
  <img src="media/agent-window-hero-1.png" width="100%" alt="Agent Window hero 1">
  <img src="media/agent-window-hero-2.png" width="100%" alt="Agent Window hero 2">
</p>

---

# Setup

現在の実装はmacOSを前提としています。

## 必要なもの

* `python3`
* `tmux`
* `cargo`
* `tauri-cli`
* Xcode Command Line Tools

`./setup/preflight` は、不足している依存関係と、その導入コマンドを確認します。このscriptが何かをinstallすることはありません。

使用するAgent CLIは個別にinstallし、通常の方法で認証を済ませてください。

## 起動

repo rootで次を実行します。

```bash
./tauri_app/tauri_start
```

Tauri Appをbuildして起動します。HubはTauri Appから起動され、既定のportは `8788` です。

# 使う

## sessionを始める

Hubの `New Session` からworkspaceを選択します。

一つの統一ログは、session名、workspace、参加Agentが変わっても続きます。`New Session` は別のlogを始める操作であり、いつそうするかは人間が決めます。

sessionのArchive、revive、削除、rename、workspaceの変更はHubから行えます（サイドバーのsessionを右クリック）。renameしてもchat serverは再起動せず、URLも変わりません。

## Agentを足す

右上の `Add / Remove Agent` からAgentを追加・削除できます。同種のCLI Agentを複数起動した場合は `Claude-2` のようなinstance名になります。

* `Terminal` — workspace rootで素のシェルを開きます
* `tmux window` — compactなpane切り替え式のtmux terminalを直接開きます(tmux socket名は `agent-window` で固定です)
* `Finder` — 現在のworkspaceをFinderで開きます

隣のreload buttonはGUI serverをhard reloadします。source codeを変更している場合は、動作中のserverを新しい実装へ置き換えます。

<p align="center">
  <img src="media/agent-window-menu.png" width="500" alt="Menu">
</p>

## 送る

入力欄は通常、chatの表示領域を広く取るために最小化されており、画面下部の `O` button、またはホイール押し込みで展開されます。Agent Iconの選択状態がメッセージの送信先を指定します。

入力された文字列は、選択中のAgent CLIが動作するpaneへ `tmux send-keys` を介して直接入力されます。Agent Window専用のmessage形式へ変換しないため、**各CLIのslash commandやその他のCLIコマンドも同じ入力欄から通ります。**

入力に失敗した場合は `send_error` として検出されますが、成功は通知しません。paneのrestartやmobileからのinterruptなど、CLIの既定コマンドだけでは届かない最小限の制御はAgent Windowが配線します。

Agent Windowは次のshortcut commandも認識します。

| Command | 操作 |
| --- | --- |
| `/up, /down, /left, /right [count]`, `/enter`, `/esc`, `/ctrlc` | 対応するkeyを送ります。 |
| `/restart`, `/resume` | CLIをrestart/resumeします。 |
| `/open-pane` | 選択中のAgentのtmux paneを開きます。desktopのみ。 |
| `/nativelog` | 選択中のAgentのnative logをFinderで表示します。desktopのみ。 |
| `/log` | `.agent-window/.log.jsonl` をmessageへ挿入します。文中でも使用できます。 |

`@` を入力するとworkspace内のfileを検索できます。fileはplus buttonまたはdrag-and-dropでも添付できます。添付されたfileは `<workspace>/.agent-window/uploads/` に保存され、そのpathがAgentへ通常のtextとして渡されます。

## 読む

GUIは統一ログを、人間と各Agentを横断する一つの時系列として表示します。

CLIの切り替え、複数Agentの同時実行、processの再起動を跨いで、メッセージは同じ統一ログへ続きます。session名やworkspaceを変更しても、過去の記録はそのまま残ります。

統一ログの実体はappend-only JSONLです。

```text
~/.agent-window/session/{session_name}/.log.jsonl
```

現在のworkspaceからもsymlinkで参照できます。Agent Window内部に閉じたdatabaseではなく、Agent Windowが停止してもそのまま残り、通常のfileとして読めます。

統一ログは各CLIの詳細な実行履歴そのものではありません。人間とAgentが横断して読める粒度へのprojectionです。

tool callは進行状況を示すため実行中にstreamされますが、この時系列には残りません。アイコンをクリックすると対応するtmux paneを開きます。

各CLIの実行記録は外側から監視され、processやlog pathが変われば必要に応じて再解決されます。そのためCLI processの寿命と統一ログの寿命は一致しません。

各entryには、参照元のnative logのpathとその中の位置が記録されています。

## workspaceを見る

gitとworkspaceの状態は監視され、右paneへ投影されます。file検索も観測したworkspaceの情報を利用します。

fileをクリックするとmacOSの既定applicationで開きます。desktop版では、既に存在するfile viewerを再実装しません。mobileではそれらに頼れないため、bottom sheet型の内蔵viewerが開きます。

uncommitted changeをクリックすると、gitに設定されたdiff viewer (`git difftool`) で開きます。

## ウィンドウを合わせる

| キー | 動作 |
|---|---|
| `⌥⌘0` / `⌥⌘9` | 既定 / コンパクトサイズ |
| `⌘B` / `⌘E` | Hubサイドバー / 右paneの表示切替（`⌥` 併用でchat領域を保ったまま外側に広げる） |
| `⌥⌘↑` `←` `→` `↓` | その画面端へ移動。`↓` は中央 |
| `⌥⌘P` | 最前面に固定 |
| `⌥⌘H` | ウィンドウの高さを最新メッセージに合わせ続ける |

Fit Height (`⌥⌘H`) を有効にすると、Hubと右paneがOSのnative menuに置き換えられ、`⌘B` / `⌘E` は無効になります。

<p align="center">
  <img src="media/agent-window-fit.gif" width="100%" alt="Fit Height demo">
</p>

## Agent同士をつなぐ

Agentは `agent-send` で別のAgentへ直接メッセージを送れます。必要な場合は `SKILL.md` を所定の場所に配置してください。これはAgent Windowが契約した唯一のSKILLです。

```bash
agent-send <target> <message>
```

`agent-send` は、人間の入力と同じ `tmux send-keys` を使う薄いwrapperです。宛先を解決し、`[From: Claude]` のようなprefixを付けて入力します。

ここでのsuccessは、入力がruntimeへ渡されたことだけを意味します。送信先のAgentが理解した、あるいは行動したことを意味しません。

## 名前をつける

Agent Windowの唯一の不要な機能です。

```bash
agent-send name <target> <name>
```

Agentに、その場で通じる名前を付けられます。名前が使われるのは `agent-send` の宛先と `[From: ...]` prefixだけで、既存のinstance名やlog上の識別子は変わりません。

## スマートフォンから使う

同一LAN上のmobile端末から、同じ画面へ接続できます。

最初にHTTP modeでTauri AppとHubを起動し、その状態で次を実行します。

```bash
./setup/pwa/enable
```

このscriptは実行中のHubを確認し、mkcertとlocal certificateを準備します。**mkcertはシステムにlocal CAをinstallします。**

以降は起動時に `~/.agent-window/state/pwa/enabled` が検出され、HTTPS modeで起動します。

```bash
./tauri_app/tauri_start
```

mkcertの `rootCA.pem` を接続する端末へ送り、certificate profileをinstallして信頼を有効にします。その後、Safariで次のいずれかを開きます。

```text
https://<MacのLAN IP>:8788/
https://<Mac名>.local:8788/
```

ホーム画面へ追加するとPWAとして使用できます。

LANの外からHubへ到達する方法は [`external-access/README.md`](external-access/README.md) を参照してください。

<p align="center">
  <img src="media/agent-window-mobile-light-1.png" width="48%" alt="Mobile UI, light 1">
  <img src="media/agent-window-mobile-dark-1.png" width="48%" alt="Mobile UI, dark 1">
  <img src="media/agent-window-mobile-light-2.png" width="48%" alt="Mobile UI, light 2">
  <img src="media/agent-window-mobile-dark-2.png" width="48%" alt="Mobile UI, dark 2">
  <img src="media/agent-window-mobile-light-3.png" width="48%" alt="Mobile UI, light 3">
  <img src="media/agent-window-mobile-dark-3.png" width="48%" alt="Mobile UI, dark 3">
  <img src="media/agent-window-mobile-light-4.png" width="48%" alt="Mobile UI, light 4">
  <img src="media/agent-window-mobile-dark-4.png" width="48%" alt="Mobile UI, dark 4">
</p>

## 対応CLI

Claude、Codex、Antigravity、Cursor、Grok。

受信側は各CLIの実行記録の置き場所と形式を知る必要があるため、CLIごとの対応があります。

送信側は共通です。paneへ文字列を入力するだけなので、CLI固有のmessage protocolはありません。

# License

[0BSD](LICENSE)です。好きにしてください。
