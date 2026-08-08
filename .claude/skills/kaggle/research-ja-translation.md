# 公開情報の日本語訳レイヤ（人間用）

`kaggle_research.py` が取ってきた英語の公開情報に対して、**図つきの日本語全訳**を
生成する層。`research_ja.py` と `.claude/ops/translate.sh` が担当する。

## 鉄則: 原文と訳文の役割は分離する

| ディレクトリ | 言語 | 誰が読むか | 位置づけ |
|---|---|---|---|
| `research/rendered/` | 英語 | **エージェント** | 正典。判断の根拠にしてよいのはこちらだけ |
| `research/assets/` | — | 両方 | 図（バイナリ、言語非依存） |
| `docs/research-ja/` | 日本語 | **人間だけ** | 二次的な派生物。エージェントは読まない |

**なぜ分けるか。** 訳文は損失のある派生物である。エージェントが訳文を引用すると、
著者が書いた内容ではなく訳者の解釈が下流のすべての判断に伝播し、しかも
**それが起きたことは誰にも分からない**。1文字の訳ミスがコンペ戦略の前提になっても、
遡って気づく手段がない。だから「なるべく原文を見る」という運用ルールではなく、
機械的に読めなくしてある:

1. **`.claude/settings.json` の `permissions.deny`** に `Read(./docs/research-ja/**)`。
   `allow` より `deny` が優先されるので、Read ツールでは開けない。
2. 各訳文の冒頭に `<!-- HUMAN-ONLY-TRANSLATION ... -->` マーカーと、
   対応する英語原文へのパス。`research_ja.py index` が毎回入れ直すので、
   翻訳エージェントが書き忘れても必ず付く。
3. `docs/research-ja/README.md`（索引）の冒頭にも同じ注意書き。

人間が訳文を読むのは自由。**エージェントに読ませたい時は英語原文の方を指す**こと。
どうしても訳文を開く必要が出たら deny 行を一時的に外すが、それは「原文を読めば
済む話ではないか」を確認してからにする。

## パイプライン

```bash
COMP=<slug>

# 1) 取得（既存フロー。これが英語原文の供給元）
python3 scripts/kaggle_research.py --comp $COMP --out research

# 2) 翻訳元のレンダリング（決定的、モデルなし）
python3 scripts/research_ja.py prep --comp $COMP --out research --docs docs/research-ja

# 3) 未訳の確認
python3 scripts/research_ja.py pending --out research --docs docs/research-ja

# --- ここで1ファイル1エージェントで翻訳（translate.sh が自動でやる） ---

# 4) 索引の再生成 + HUMAN-ONLY マーカーと図パスの補正
python3 scripts/research_ja.py index --comp $COMP --out research --docs docs/research-ja

# 5) ブラウザで読めるHTML（図込み・ダーク/ライト対応）
python3 scripts/research_ja.py html --out research --docs docs/research-ja \
        --dest ~/Downloads/$COMP-research-ja
```

日次で回すなら `.claude/ops/ops.conf` に `TRANSLATE_ENABLED=1` を書いて
`./install.sh` を実行する（既定は off。1文書1エージェントでトークンを使うため）。

## prep が作るもの — 本文の末尾にコメントが付いた1枚の文書

`prep` は1スレッドを**1ファイル**にまとめる。ここが要点で、

```
# <タイトル>
> 著者 / 投稿日 / votes / コメント数
> 原文URL
---
<本文（表・数式・コードブロック・図をそのまま）>
---
## Comments (n)
### <著者> — <日付> (votes n)
<返信本文>
```

返信スレッドを別ファイルにせず本文の末尾に連結してある。実際に効く情報
——「この投稿のこのハイパラは間違い」「その後こう直した」——は3つ下の返信に
書かれていることが多く、別ファイルにすると読まれないため。

## なぜ本文取得に r.jina.ai が要るのか

- `kaggle competitions topics show --format json` が返すのは
  **`id` / `title` / `authorName` / `commentCount` / `votes` / `postDate` と返信だけ**で、
  **本文（トピック本体）が入っていない**（実測）。
- プレーンテキスト形式にすると本文は出るが、**表の構造が潰れ、図が消える**。
- `https://r.jina.ai/<discussion URL>` は表・画像URL込みの Markdown を返す。認証不要。
  ただし返信は取れない。

したがって **本文 = jina / 返信・メタデータ = 公式 CLI** の二経路。writeup 本文は
`kaggle_research.py` が既に jina で取っているので、`prep` は再取得しない。

## 翻訳対象の選び方

既定は「**タイトルが解法writeupに見えるスレッド**（`3rd place` / `solution` /
`write-up` / `approach` / `lessons learned` …）**または votes 20 以上**」。
締切1時間前に投稿された1位解法は votes 0 なので、票だけで選ぶと取り逃す。

```bash
--min-votes 10        # 閾値を下げる
--topic 733154        # 個別に強制追加（繰り返し可）
--all-topics          # 全スレッド（高い。全部が翻訳候補になる）
--skip-writeups       # writeup を除外
--limit N             # この実行での jina 取得回数の上限
--full                # キャッシュを無視して再レンダリング
```

## 落とし穴（すべて実害があったもの）

- **画像URLに `(` `)` が入る**（`.../image (4).png`）。素朴な `\(([^)]+)\)` は
  途中で切れ、404 の JSON エラーページを `.png` として保存してしまう。開くまで
  成功に見える。`find_images()` は括弧の対応を数え、保存後にマジックナンバーで
  画像であることを検証する。
- **図のファイル名は連番にしない。** URL のハッシュにしてある。連番だと著者が
  図を1枚挿入しただけで以降が全部ずれ、挿入前に書いた訳文の図が黙って別の図を
  指す。ハッシュなら動かない。
- **図のパスは翻訳エージェントに計算させない。** 原文からは `../assets/...`、
  訳文からは `../../research/assets/...` になるが、これは `index` が決定的に
  書き換える。プロンプトは「画像行は1文字も変えずにコピーせよ」と指示している。
  この種の機械的な変換をモデルにやらせると、8割正解という最悪の正答率になる。
- **翻訳は1文書1エージェント。** バッチで渡すと、ターンが減ったところで勝手に
  要約を始める。それはこの仕組みが防ごうとしている唯一の失敗そのもの。
- **再訳の前に出力先ファイルを消す。** `docs/research-ja/**` は Read 禁止だが、
  Write は「既存ファイルは一度 Read してから」を要求する。消してから書かせる。
- 訳出済みかどうかは**原文の sha** で判定する。返信が1件付けば sha が変わり、
  索引に `⚠️ 原文更新 (再訳待ち)` が立つ。

## 著作権

他者の著作物の翻訳。索引と各ファイルに原文URLと著者名を必ず併記している。
引用・再配布時は Kaggle の規約と各投稿のライセンスに従うこと。
