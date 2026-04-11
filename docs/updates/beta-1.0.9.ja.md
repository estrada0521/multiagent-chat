# multiagent-chat v1.0.9

English version: [beta-1.0.9.md](beta-1.0.9.md)

Released: 2026-04-12

## 修正内容

### macOS デスクトップアプリ: Python 3.9 互換性の修正

システム Python が 3.9（古い macOS の Command Line Tools デフォルト）の Mac でもデスクトップアプリが正常に動作するようになりました。v1.0.8 では Python 3.12 以降でのみ有効な f-string 内のバックスラッシュ構文を使っていたため、Python 3.9 環境でのチャットセッション起動に失敗していました。

### macOS デスクトップアプリ: cryptography パッケージの自動インストール

Hub 起動時に `cryptography` Python パッケージが見つからない場合、サイレントに失敗するのではなく自動でインストールするようになりました。

### ドキュメント: Gatekeeper 回避手順を更新

インターネットからダウンロードした署名なしアプリに macOS が表示する「壊れているため開けません」の警告に対して、正しい回避コマンド（`xattr -cr`）をダウンロードページに追記しました。
