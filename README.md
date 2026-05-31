# Agent Window

Claude, Codex, Gemini, Cursor, Copilot の CLI を制御する Agent Window です
必要であれば辞書的に任意のCLIを追加登録することができます
通常のサブスクリプションだけで動作します

![Agent Window hero 1](media/agent-window-hero-1.png)

![Agent Window hero 2](media/agent-window-hero-2.png)

# バックエンド
このrepoにおけるセッションには1つのtmuxプロセスとチャットサーバーが紐づけられます
各プロセス内のpaneに任意のエージェントを追加・削除することができます。つまり、1つのセッションを複数のエージェントで運用します。CLIの restart や削除→追加を繰り返しても同セッションである限り同じlocal jsonlにログが追記されます

## 送信
送信のバックエンドにはtmux send-keyを使用しています
エージェント→エージェントへの送信もセッション内外問わず可能です

## 受信
受信はPID Tree等からCLIのnative log pathを解決し、kqueueで直接監視する方式を採用しています
チャットサーバーのリロードやCLIのrestartなど、特定のタイミングでpathの再解決が走ります
イベントはメッセージとツールコールを中心に振り分けられ、前者だけがセッションのjsonlに記録され、後者は一時的にストリームされます

## アプリ
Mac版はRust製Tauriビルドのアプリを用意しています
見た目を整えるだけの薄いラッパーで、実態はただのwebアプリです
スマホ用にはPWAを用意しています

# フロントエンド

## Hub(左サイドバー)
Hubサーバーではセッション一覧を管理します
新しいセッションの開始や、セッションのアーカイブ・削除はここから行います
また、外観の設定や機能周りのグローバルな設定もここにから変更します

### 外観
ダーク、ライトの2種類のテーマを用意しています

### 自動承認
Auto Approval をON にすると、CLI側の設定に依らず全てのエージェントのツールコールが自動承認されます
Running中のエージェントのみ tmux capture pane が Poling され、承認用文字列を見つけたらEnterを送るだけの無骨な方法です

### Caffeinate -i
ONにするとmacのスリープが防止されます

## チャット画面(中央・右)
基本画面です。よくあるAgent winodwと基本的に同じです

### 入力欄
入力欄は普段は最小化され、チャット本文の表示領域を最大化しています。下部のOボタンで展開されます
入力されたメッセージは、選択したエージェントのCLI Paneに直接貼り付けられます
つまり、各CLIのコマンドをそのまま利用可能です
@を入力するとrepo内のファイル検索できます、後述するFSEventsの結果をキャッシュしています
プラスボタン、またはドラッグ&ドロップでファイルを添付できます
添付されたファイルは logs/{セッション名}/uploads/ に保存されます

### Workspace管理
右PaneはWorkspaceの状態を一般的なFSEvents方式で同期しています
未コミット差分だけを小さく表示する機能があります
埋め込みのファイルビューアーは最小実装ですが、HTMLの表示とmarkdownレンダリングには対応しています
設定から「External Editer」をONにした場合は、指定した外部エディタにファイルが展開されます

### メニューボタン
右上のハンバーガーボタンから以下の操作を行うことができます

**reload** : チャットサーバーのハードリロードです。ソースコードを編集していた場合、入れ替わります。何か問題があれば取り柄えずreload

**Terminal** : tmux terminal 本体を開くだけです。コンパクトにしています

**Finder**: セッションワークスペースをFinderで開きます

**Add / Remove Agent** : セッションにエージェントを追加・削除できます。同一エージェントの複数追加も可能です。
Claude-3のようにインスタンス名で処理されます

# Setup

## Tauri App + HTTP

webでも動きますが、UI・UXを確認していないので、基本的にTauri App前提です。

事前に `python3`, `tmux`, `cargo`, Xcode Command Line Tools をインストールしてください。
`tauri-cli` は初回実行時に `.multiagent/tools/tauri-cli` へ自動で入ります。
Claude, Codex, Gemini, Cursor, Copilot などのAgent CLIは自動インストールされません。使うCLIを事前にインストールし、認証まで済ませてください。

```bash
./tauri_app/tauri_start
```

このコマンドで、Tauri Appをbuildし、HubはTauri Appから `http://127.0.0.1:8788/` で起動されます。
起動後はHubの `New Session` からセッションを開始してください。

再buildだけ行う場合:

```bash
./tauri_app/tauri-build
```

## PWA / HTTPS for Mobile

先にHTTPのTauri Appが動いている必要があります。

```bash
./tauri_app/tauri_start
./setup/pwa/enable
./tauri_app/tauri_start --local-https
```

`./setup/pwa/enable` は実行中のHubを確認して、mkcertとローカル証明書を準備します。
iPhone/iPadで使う場合は、表示されるmkcert root CAの信頼手順も行ってください。

PWA有効化後は `--local-https` で起動します。
このときHubとChatはHTTPSで揃います。
