# multiagent-dev testing

`bin/multiagent` は保護対象です。機能追加とテストは `bin/multiagent-dev` に対して行います。

## 1. 文法とヘルプ確認

```bash
bash -n bin/multiagent-dev
bin/multiagent-dev --help
```

## 2. 単体確認

```bash
bin/multiagent-dev list
bin/multiagent-dev list --verbose
bin/multiagent-dev status
bin/multiagent-dev status --all
bin/multiagent-dev --session test-dev status
bin/multiagent-dev resume
bin/multiagent-dev resume --latest --detach
```

## 3. 分離した起動テスト

```bash
bin/multiagent-dev --session multiagent-dev-test --agents codex --log-dir "$PWD/logs-dev-test" --detach
tmux has-session -t multiagent-dev-test
bin/multiagent-dev --session multiagent-dev-test status
bin/multiagent-dev --session multiagent-dev-test --detach
bin/multiagent-dev resume --session multiagent-dev-test --detach
bin/multiagent-dev rename --session multiagent-dev-test --to multiagent-dev-test-renamed
bin/multiagent-dev kill --session multiagent-dev-test-renamed
```

## 4. 通信テスト

```bash
bin/agent-send --session multiagent-dev-test codex "疎通確認"
bin/agent-send --session multiagent-dev-test all "broadcast test"
```

## 5. 後始末とログ確認

```bash
bin/multiagent-dev kill --all
find logs-dev-test -maxdepth 3 -type f | sort
```

## 6. Git 差分確認

```bash
git status
git diff -- bin/multiagent-dev
```

## 補足

- `bin/multiagent` は触らない
- 新機能は `bin/multiagent-dev` にだけ入れる
- テスト時は `--session multiagent-dev-test` のように専用セッション名を使う
- ログも `logs-dev-test/` のように分ける
- `resume` は既存セッションがない場合に失敗する
- `list` は現在 workspace に紐づくセッションを要約表示する
- `list --verbose` は workspace、bin dir、window/pane 数、dead pane 数、attached clients、agent ごとの状態まで表示する
- `status --all` は workspace 内の全セッション状態を表示する
- `resume --latest` は workspace 内で最新のセッションを再開対象にする
- `kill --all` は workspace 内の全セッションを削除する
- `rename` は既存セッション名を明示的に変更する
- ログは `<log-dir>/<session>_<yymmdd>_<yymmdd>/` に保存される
- 先頭の日付は作成日、末尾の日付は最終更新日
- 詳細時刻と簡単な上書き記録は `.meta` に保存される
- 各ディレクトリ内には `claude.log`, `claude.ans` のように agent ごとの最新内容だけが残る
- 既存セッション名で新規作成すると失敗する
- セッション削除は `kill` を明示したときだけ行う
