# multiagent-chat 思想と設計方針

英語版: [docs/design-philosophy.en.md](design-philosophy.en.md)

この文書は、[README.md](../README.md) の機能説明や [docs/technical-details.md](technical-details.md) の実装説明とは別に、この環境が何を目指しているかをまとめるためのものです。`multiagent-chat` は browser 上に terminal を並べる project ではありません。AI が動く側、人間が触る側、そして現実世界と接続する側を分けたうえで、それぞれに適した形を選ぼうとしています。

ここでいう pure / impure の違いは、機能の数そのものではありません。Hub、構造化ログ、session continuity、mobile access は pure さと矛盾しません。問題になるのは、model の弱さを補うための一時的な protocol、skill、workflow、儀式的 orchestration を system の中心原理として固定してしまうことです。

この環境の前提は、次の非対称性です。

- AI 側は、できるだけ pure な substrate に寄せたい
- 人間側は、できるだけ自然な chat interface で扱いたい
- そのやり取りは、screen の内側だけで閉じず physical world へ開きたい

以下の方針は、その前提から来ています。

## 1. AI を人間用の道具に合わせすぎない

terminal、editor、window system は人間にとって便利な道具ですが、AI にとって本質とは限りません。この環境では、AI が動く側をできるだけ低レベルで味付けの少ない substrate に寄せることを重視しています。

tmux を選んでいる理由も同じです。ここで欲しいのは「気持ちよい terminal UI」より、session、pane、socket、environment、capture が単純に扱えることです。`send-keys` や `capture-pane` のような primitive が直接使えるので、execution layer を必要以上に抽象化せずに済みます。tmux は front-end ではなく、可観測で操作可能な実行基盤として置かれています。

## 2. 人間側の主画面は terminal ではなく chat にする

人間が複数 agent を扱うときに見たいのは、生の pane 群そのものではなく、誰が誰に何を伝え、何が返り、どの成果物が出たかという会話の構造です。そのため、この環境では human-facing な主画面を chat にしています。

chat UI が扱うのは、送信者、宛先、返信関係、添付、brief、memory、Pane Trace、file preview です。これは terminal 出力を並べるより、message 単位で整理した方が読みやすく、スマホにもそのまま落とし込みやすいからです。Pane Trace や terminal popup は残っていますが、それらは execution layer を覗く viewer であって、人間の主画面そのものではありません。

## 3. transport は薄く、意味づけは後段へ寄せる

この環境では、command surface を増やして message bus を重くすることより、transport を薄く保つことを優先しています。`agent-send` はその中心ですが、ここで大事なのは「何でもかんでも option 化しないこと」です。

送信の中心は `agent-send <target>` と text payload で、添付や参照もできるだけ本文側の convention と UI 側の解釈で吸収します。`[Attached: path]` を独立した配送 protocol にしないのはそのためです。実体は text のまま保ち、人間には file card や preview を見せ、agent には path を読ませる。この設計は、便利さより先に transport の純度を守る考え方です。

## 4. durable な substrate と一時的な scaffolding を混同しない

この環境が大事にしているのは、知能の代用品を大量に built-in することではなく、強い model がその場で動ける substrate を保つことです。session 一貫性、state 保持、構造化ログ、可観測性、人間の介入容易性は durable な基盤ですが、固定 skill 群や workflow engine の多くは temporary scaffolding です。

skill や workflow 自体を否定しているわけではありません。必要ならその場で agent に指示すればよく、賢い agent が下位 agent に一時的な役割分担を与えることもできます。ただし、それらを repo の中心原理にしてしまうと、model が強くなったときに system 全体が過去の弱さに縛られます。ここで目指しているのは「今の model の癖に最適化した儀式」を蓄積することではなく、model の進歩に対して残り続ける substrate を作ることです。

## 5. process を守るより session を守る

この環境が守ろうとしている continuity は process continuity ではなく session continuity です。tmux session がそのまま残っていれば Resume できますが、仮に process が止まっても、同じ session 名、workspace、logs、brief、memory が残っていれば、かなり近い状態から再開できます。

Hub で `Kill` と `Delete` を分けているのはこのためです。`Kill` は一旦止める操作であり、後から `Revive` する余地を残します。`Delete` は log directory と関連 state を消し、再開の基盤そのものを消します。ここで重視しているのは「同じ process を延命すること」ではなく、「session を再び扱えること」です。

## 6. 文脈は 1 枚の巨大メモにしない

長期運用では、すべての文脈を 1 つの可変メモへ寄せると、rule、summary、history、terminal reality が混ざりやすくなります。この環境では、それらを最初から分けて持ちます。

- `docs/AGENT.md`: repo / 環境全体の恒久ルール
- brief: session ごとに使い回す半静的な追加指示
- memory: agent ごとに更新される要約
- `.agent-index.jsonl`: 構造化された会話ログ
- `.log` / `.ans` / Pane Trace: pane 側の表示記録

この layered logs の考え方は、「万能な 1 枚」を作らない代わりに、意味の違う層を並べて continuity を保つ方法です。長期一貫性は単一のメモからではなく、複数の記録を役割ごとに保つことから生まれます。

## 7. mobile は付属機能ではなく前提条件

この環境は、PC の前に座っているときだけ使える control panel を目指していません。同じ Hub と chat UI が desktop と mobile の両方で成立し、人が場所に縛られず session に戻れることを前提にしています。

そのため、New Session、Resume、workspace path の入力、message の送受信、file preview、Pane Trace の確認をスマホ側からも行えるようにしています。public access や local HTTPS も、「別 product を足すこと」ではなく、同じ workspace を別の場所や状況から扱えるようにする layer として位置付けられています。

## 8. screen の内側だけで完結させない

この環境は screen world の中だけで閉じた会話を理想としていません。人間は物理世界の中にあり、現実は desk の外にも広がっています。そのため、camera、voice、remote access のような機能は単なる convenience ではなく、physical world から workspace へ情報を持ち込む入口として重要です。

ここで大事なのは、抽象的な「身体らしさ」を足すことではありません。現実の断片を、session に保存でき、message と attachment として参照でき、複数 agent が後から読める形で取り込むことです。写真、音声、外からの接続は、そのための具体的な ingress です。

## 9. local-first で組み、public は後から足す

session の作成、message の配送、logs の保存、Hub / chat UI の基本動作は local/LAN だけで成立するように作られています。public access は core workflow の置き換えではなく、その上に追加する layer です。

Cloudflare 向けの command と docs があるのも、local-first の構造を保ったまま必要な時だけ outside reachability を足すためです。local HTTPS と public HTTPS も別の目的として整理されており、前者は local secure features、後者は external reachability のためのものです。

## 10. まとめ

`multiagent-chat` の設計方針を短く言えば、次の4本です。

- AI 側は、余計な味付けの少ない実行基盤へ寄せる
- 人間側は、message と attachment を中心にした chat interface で扱う
- durable な substrate と temporary scaffolding を分け、後者を system の中心にしない
- そのやり取りを screen の内側に閉じ込めず、mobile と physical world へ開く

tmux、chat UI、layered logs、Hub、mobile access、camera / voice / remote access は、それぞれ別の機能追加ではなく、この前提の上に置かれたものです。
