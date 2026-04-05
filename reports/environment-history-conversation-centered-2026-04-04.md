# Multiagent 環境構築史レポート

副題:
- conversation-centered edition

対象:
- `logs/multiagent/.agent-index.jsonl`
- `docs/design-philosophy.md`
- `docs/design-philosophy.en.md`
- 関連スクリプトと docs の git 履歴

## 1. 先に結論

この環境の歴史は、機能が順番に追加された history として読むより、user が agent との会話を通じて environment を押し出していった history として読む方が正確である。

実際の driving force は、抽象的な roadmap ではなく、次のような user の発話パターンにある。

- `コミットして`
- `スマホから使いたい`
- `余白を揃えて`
- `まだ実装せずに、教えて`
- `戻して`
- `Gemini に投げて`
- `Claude にも振ってください`

この環境は、tmux substrate, `agent-send`, chat UI, Hub, mobile, topology, camera mode といった機能を持つ。しかし、それらは feature list として生えたのではない。user が

- 何を見たいか
- どこから戻りたいか
- どの変更を許し、どの変更を却下するか
- どの agent に何を任せるか

を反復的に言い続けた結果として沈殿した。

したがって本稿では、commit chronology より conversation chronology を優先する。

## 2. このログで本当に強い主語は誰か

発話数だけ見ても、主導権ははっきりしている。

- `user`: 9,017
- `codex`: 4,426
- `system`: 2,293
- `claude`: 1,641
- `gemini`: 1,030

さらに user の指示先を見ると、

- `codex`: 3,842
- `claude`: 1,671
- `gemini`: 1,036
- `copilot`: 948
- `cursor`: 646
- `codex-1`: 478

となる。これは user が agent を単なる並列 worker としてではなく、役割の違う相手として使い分けていたことを示す。

会話の実態としてはおおむね次の分担が見える。

- `codex` / `codex-1`
  - 主実装
  - 長い UI 調整
  - ドキュメント化
- `claude`
  - 原因分析
  - commit checkpoint
  - 根本原因説明
- `gemini`
  - 別案
  - mobile / camera 周辺の補助実装
  - 独立レビュー

つまり、この環境の multi-agent 性は Hub や add-agent の存在だけではなく、user 自身が router として振る舞っていたことによって成立している。

## 3. user は何を繰り返し求めていたか

user 発話に多く現れる語は次の通り。

- `コミット`: 780
- `スマホ`: 496
- `もっと`: 211
- `余白`: 209
- `戻して`: 190
- `教えて`: 161
- `原因`: 114

この数字は、そのまま environment の性格を示している。

### 3.1 checkpoint を切ってから進みたい

`コミットして` が非常に多い。user は変更そのものより、「どこを安定点として残すか」を常に意識している。これが結果的に session continuity や revive の文化と噛み合う。

### 3.2 mobile は最初から本番用途

`スマホ` が 496 回出る。これは responsive 対応への要望ではない。後述するように、user は mobile を「離れた場所から session に戻るための主経路」として語っている。

### 3.3 alignment を極端に気にする

`余白` が 209 回出る。user は spacing, padding, alignment, sameness に非常に敏感で、単に「綺麗にして」ではなく、「チャットと同じに」「完全に 0」「同じものを使って良い」と要求する。つまり user が欲していたのは novelty より consistency である。

### 3.4 explanation-first で進めたい

`教えて` と `原因` が多い。user は何度も `まだ実装せずに、教えて`、`編集する前に教えて`、`原因を調査して` と言う。これは保守的というより、guess-and-patch より reason-and-then-edit を好む姿勢である。

### 3.5 rollback を躊躇しない

`戻して` が 190 回出る。user は「失敗したこと」より「scope をはみ出したこと」を嫌う。不要な一般化や横展開が入ると、すぐ戻される。結果としてこの環境は、前進だけでなく rollback の反復でも整えられている。

## 4. 会話の第一幕: 3/8 未明、「見えないものを見えるようにしたい」

最初に visible になる user の不満は、下部 UI の余白である。

- `チャット画面の...下側の余白がやたら大きいです`
- `下側の余白は完全に0にして`

ここだけを見ると単なる CSS 調整に見える。しかし、ここで既に重要な前提が見えている。

それは、user が「session 全体を再起動する」のではなく、「`agent-index --chat` のプロセスだけ再起動すればよい」運用をすぐ受け入れていることだ。つまり人間が触る chat surface と、agent が生きる runtime substrate は最初から分離している。

そして user の関心はすぐ次に移る。

- `paneの出力をトレースすることはできますか？`

ここから Pane Trace が生まれる。重要なのは生まれ方である。

最初は status を

- thinking
- approval
- running
- idle

のように細分化する案が出る。しかし user はそれを採らない。

- `thinkingから戻りません`
- `そもそも種類を分けるのではなく、paneの出力をまんまそのままトレースしたい`
- `右上はthinkingとidleだけの元の状態に戻してね`

つまり user は「分類の精密化」ではなく「実体の可視化」を選んだ。この会話が、Pane Trace を taxonomy UI ではなく pane viewer へ押した。

ここに `docs/design-philosophy.md` の最初の 2 原則が既に具現化されている。

- AI を人間用の道具に合わせすぎない
- 人間側の主画面は terminal ではなく chat にする

pane は主画面に昇格しない。あくまで chat から覗く execution layer の viewer に留まる。これは思想文書の先取り実装である。

## 5. 第二幕: 3/8 昼、「同じミスを繰り返したくない」から layered records が生まれる

この日の重要な発話は、機能要望というより運用要望である。

- `次回から同じミスが起こらないようにするため、brief をいい感じに調整できますか？`

ここから chat UI は operator console に変わる。

追加されたもの:

- `Send Brief`
- `Memory`
- `Load Memory`
- `Save Memory`
- `Save Log`

ここで本質的なのは、これらが別々のボタン、別々の操作として現れたことだ。user は「全部を 1 枚のメモに書く」のではなく、

- repo / 環境全体の恒久ルール
- session ごとの追加指示
- agent ごとの要約
- 構造化会話ログ
- pane 側の出力記録

を分けて扱うことになる。

後の `docs/design-philosophy.md` で言えば、

- `transport は薄く、意味づけは後段へ寄せる`
- `文脈は 1 枚の巨大メモにしない`

がここで会話から具体化している。

つまり layered records は architecture 先行の設計ではない。user の「同じミスを繰り返したくない」という実務的な問いの答えとして立ち上がった。

## 6. 第三幕: 3/8 夕方から 3/10、「スマホから使いたい」は生活要求である

この environment を最も特徴づける user 発話の一群がここにある。

- `スマホからこのチャットにアクセスして指示を送りたい`
- `ちなみにこのPCはMac、スマホはiPhoneです`
- `PCを完全に閉じていても、スマホから好きなときにSafariを開いてセッションでやり取りできたりしないかな。何も編集しないでね。できるとしたら方針だけ教えて`
- `一階の部屋で閉じました`
- `私はその後2階でベッドに横になり...`

この言い方から分かるのは、mobile requirement が viewport 要件ではないことだ。user は「iPhone に最適化してほしい」と言う前に、「今 PC の前にいないが session に戻りたい」と言っている。

だからこの時期の改修は単なる responsive CSS ではなく、

- `0.0.0.0` bind
- LAN access
- iPhone CSS
- 16px textarea
- viewport / `visualViewport` 調整
- Safari の自動ズーム対策
- HTTPS-Only による file preview 制約への対応

へ連なっていく。

さらに重要なのは、user が mobile の不満を非常に身体的に語ることだ。

- `入力するときに勝手に拡大されるのがうざい`
- `iPhoneのSafariように`
- `ディスプレイの角が丸っこい`

ここでは browser は抽象層ではなく、手に持っている iPhone の物理的感触に近いものとして現れている。

この conversation から `docs/design-philosophy.md` の次の原則が具現化される。

- `process を守るより session を守る`
- `mobile は付属機能ではなく前提条件`
- `local-first で組み、public は後から足す`

mobile は後付け client ではない。user の lived context そのものが仕様になる。

## 7. 第四幕: 3/12-3/14、user は aesthetic director であり analysis reviewer でもある

3/12-3/14 は機能爆発の時期だが、それを feature list としてだけ読むと外す。会話の質が変わるからだ。

この頃の user は、色、フォント、余白、サイズを極端に細かく指示する。

- `Paneの背景...rgb20,20,19にして`
- `下のフォントに戻して`
- `白い部分を少しグレーに`
- `PC版の大きさをしっかり設定してください`
- `表の左右の余白を...`

しかし同時に、壊れた箇所では編集前説明を強く要求する。

- `Hub機能について確認しておいて、編集しちゃダメだよ`
- `原因を調査して編集する前に教えて。その原因がどれだけ確度の高いものかも書いて`

この 2 つが同時にあるのが重要である。user は aesthetic direction を与えるだけでなく、「いきなり直すな、まず理解を出せ」という規律を環境に課している。

その結果、3/14 の多くの実装は闇雲な UI 追加ではなく、

- Hub
- thinking pane
- attached files panel
- export HTML
- HTTPS via `mkcert`
- voice input
- camera attachment
- core extraction (`hub_core`, `chat_core`, `state_core`, `export_core`)

を reasoned architecture として進める方向に押される。

`docs/design-philosophy.md` との関係で言えば、ここでは

- `人間側の主画面は terminal ではなく chat にする`
- `durable な substrate と一時的な scaffolding を混同しない`

が会話の中で現実になっている。user は「見た目は調整する」が、「原因を説明せずに場当たり patch を積む」ことは許しにくい。これは durable substrate を求める態度そのものである。

## 8. 第五幕: 3/15-3/31、前進より rollback が環境を整える

3 月後半の中心は、追加機能よりも scope discipline である。

代表的な発話は繰り返し現れる。

- `やはり戻して下さい`
- `余計な変更勝手に入れないで`
- `Publicはそのままで良いんです`
- `必要なものまで戻してしまったようです`

これは特に Local / Public / iframe / full-page / Hub overlay を巡る議論で強い。

user が求めているのは「一般解」ではなく、「Local のスマホ操作性を Public に寄せたいが、Public は壊すな」という局所的な修正である。agent 側が scope を広げると、すぐ差し戻される。

この rollback discipline は単なる厳しさではない。結果として environment を次の方向へ押している。

- local-first と public-later を混ぜない
- Hub と chat の役割境界を保つ
- overlay / iframe / direct navigation の差を会話で明示する
- topology や onboarding の追加も、環境全体を壊さない範囲で行う

ここで `docs/design-philosophy.md` の

- `durable な substrate と一時的な scaffolding を混同しない`
- `local-first で組み、public は後から足す`

が会話レベルで実践されている。

さらにこの時期は docs が整う時期でもある。

- `docs/AGENT.md`
- session guide
- `docs/design-philosophy.md`
- `docs/design-philosophy.en.md`

しかし重要なのは順序である。思想文書が先にあり、会話が後から従ったのではない。先に会話があり、その会話が押してきた方向を後から文書が説明している。

## 9. 第六幕: 4/4、camera mode は novelty ではなく sameness の試験場

4/4 は派手に見える日だが、会話の構造自体はそれまでと連続している。

camera mode に対して user が繰り返すのは、新奇さの要求ではなく、chat との整合である。

- `デザインを最小化します`
- `完全にチャットに合わせて下さい`
- `同じものを使って良いです`
- `余白系が揃ってないですね`
- `画像等の位置は変えないように注意しつつ修正してください`

一方で局所的には裁量も渡す。

- `もっとかっこいい感じにできる？ お任せ`

つまり user の設計姿勢は非常に一貫している。

- 大枠の alignment は厳密に固定する
- その上で局所の演出だけ自由にする

camera mode の実装は、その要求に引っ張られて

- chat と同じ message ordering
- chat と同じ meta spacing
- chat と同じ chip spacing
- attachment-only message の例外処理
- waveform
- voice / camera / permissions

へ調整されていく。

この日は `screen の内側だけで完結させない` が最も visible に現れる日でもある。だが、それは「画面外の世界へ開いた」から重要なのではない。user が physical-world input でさえ「chat と同じ秩序に従え」と要求したことが重要である。

つまり camera mode は別 product ではなく、chat-first surface の延長として育てられている。

## 10. 第七幕: 4/4 の revive failure で user は bug reporter ではなく architecture critic になる

4/4 の revive failure は、conversation-centered に見ると「大バグの発生」だけでは終わらない。

まず Claude が原因を説明する。

- `.meta` の破損
- `.log` / `.ans` ファイル名からの fallback
- base-name 重複による増殖

user はそこで止まらない。

- `この環境は同じエージェントを複数使うことも想定しているよう`
- `もともとcodexが2体いたなら、Reviveも2体成さないといけない`

この一言で fix の方向が変わる。base-name dedupe は捨てられ、mtime-based filtering へ修正される。

ここで user は bug reporter ではなく reviewer であり、さらに言えば environment の前提条件を守る architecture critic として振る舞っている。これは 3 月後半から続いていた rollback / scope discipline の延長でもある。

`docs/design-philosophy.md` との関係で言えば、ここでは

- `durable な substrate`
- `process を守るより session を守る`

が conversation の中で再確認されている。重要なのは bug 自体ではなく、「その fix が environment の前提を壊さないか」を user 自身が見ていることだ。

## 11. agent たちはこの会話の中で何者だったか

この history は user の history であると同時に、agent role differentiation の history でもある。

### 11.1 Codex 系

長い UI 調整、継続的な実装、構造の整理、長文レポート化を担う。特に 4/4 の camera mode のように、細かい alignment を何度も詰める仕事は Codex 系に集中している。

### 11.2 Claude

原因分析、commit checkpoint、根本原因説明が強い。3/8 の trace 崩れ、4/4 の revive failure のように、「何が起きているか」を 먼저整理する役割が目立つ。

### 11.3 Gemini

局所 UI 修正、mobile / camera 周辺の補助、独立レビューが多い。user 自身が `Gemini に投げて` と指示する場面が何度もあり、別解や second opinion の出し手として運用されている。

### 11.4 user

最も重要なのは user である。user は

- 要求する
- 方向転換する
- rollback する
- agent を振り分ける
- invariants を守る

という意味で、この multi-agent environment の実質的な orchestrator である。

したがって、この環境の multi-agent 性は system に built-in された workflow engine の産物ではなく、user の運用作法そのものでもある。

## 12. `docs/design-philosophy.md` はこの会話史の中で何なのか

`docs/design-philosophy.md` は blueprint ではない。少なくともログから見える順序では、

1. 先に user と agents の conversation がある
2. その conversation が pane trace, layered records, mobile access, Hub, camera, topology を形にする
3. その後に design philosophy が、すでに起きていた方向を抽象化する

だからこの文書は「未来の仕様書」というより、「会話によって押し出された environment を後から説明する charter」に近い。

各原則は conversation の中で次のように具体物になる。

- `AI を人間用の道具に合わせすぎない`
  - pane を主画面に戻さず、chat から覗く viewer に留める
- `人間側の主画面は terminal ではなく chat にする`
  - user の余白、meta、spacing、sameness 要求が常に chat surface に集中する
- `transport は薄く、意味づけは後段へ寄せる`
  - `agent-send` と本文 convention を保ったまま UI 側で richness を受ける
- `durable な substrate と一時的な scaffolding を混同しない`
  - analysis-before-edit と rollback discipline が場当たり patch を嫌う
- `process を守るより session を守る`
  - mobile から戻りたい、Kill と Revive を分けたい、topology を保持したい
- `文脈は 1 枚の巨大メモにしない`
  - Brief, Memory, Save Log が別々に制度化される
- `mobile は付属機能ではなく前提条件`
  - user の生活文脈そのものが mobile requirement を押す
- `screen の内側だけで完結させない`
  - camera, voice, uploads が session の一部になる
- `local-first で組み、public は後から足す`
  - Local/Public の差を user 自身が強く管理する

## 13. 結論

この環境の歴史を最も正確に言い表すなら、こうなる。

これは、user が agent との会話を通じて

- 見え方を要求し
- 使い方を要求し
- 生活文脈を持ち込み
- rollback で scope を絞り
- explanation を求め
- agent を振り分け

ながら、chat-first / mobile-first / session-first な environment を押し固めていった history である。

commit や機能追加は重要だが、それ自体が主役ではない。主役は conversation であり、それらは conversation の圧力がコードに沈殿した痕跡である。

それゆえ `multiagent-local` の歴史は、単なる機能追加史でも、単なる設計思想史でもない。user と agents の会話が、設計思想を後から説明可能な形へまで押し出した、conversation-driven architecture の歴史として読むべきである。
