# /research-ja — 公開ディスカッション/writeup の日本語全訳（図つき）

`kaggle_research.py` が取得済みの英語原文から、**図込みの日本語全訳**を作る。
日次実行（`.claude/ops/translate.sh`）と同じ処理を、手で1回まわすためのコマンド。
コンペ終了直後に上位解法 writeup をまとめて訳したい、という使い方を想定している。

## 前提

`python3 scripts/kaggle_research.py --comp <slug> --out research` が済んでいること。
このコマンドは取得済みコーパスの上に乗るだけで、自分では discussion を列挙しない。

## 手順

**1. 翻訳元をレンダリングする**（決定的・モデル不使用）

```bash
python3 scripts/research_ja.py prep --comp <slug> --out research --docs docs/research-ja
```

本文を r.jina.ai 経由で Markdown 化し、図を `research/assets/<key>/` に落とし、
返信スレッドを本文末尾に連結して `research/rendered/<key>.md` を書く。
対象は「タイトルが解法writeupに見える or votes 20以上」。広げるなら
`--min-votes 5` / `--all-topics`、個別指定は `--topic <id>`。

**2. 未訳の一覧を出す**

```bash
python3 scripts/research_ja.py pending --out research --docs docs/research-ja
```

**3. 1ファイルずつ訳す。** `pending --porcelain` が `key<TAB>原文<TAB>出力先` を吐く。
各行について、**Task を使わず自分で** 原文を読み、`.claude/ops/translate-prompt.md`
の規約どおりに `docs/research-ja/<key>.ja.md` を書く。要点だけ再掲する:

- **要約しない。全文訳す。** 節を落としたら失敗であって、短い成果物ではない。
- 見出し階層・表・コードブロック・数式は原文のまま。コードは訳さない。
- **画像行は1文字も変えずにコピー**する（パスは手順4が直す）。
- 末尾の `## Comments` は `## コメント欄` として訳す。祝辞だけの返信は
  「n件はすべて祝辞」と明記して省いてよい。技術的な内容は必ず訳す。
- 常体（だ・である）。定着した英語術語は英語のまま。

既に訳文がある場合は**先に `rm` してから** Write すること
（`docs/research-ja/**` は Read 禁止なので、上書き前の Read ができない）。

**4. 索引と図パスを整える**

```bash
python3 scripts/research_ja.py index --comp <slug> --out research --docs docs/research-ja
```

`docs/research-ja/README.md` を再生成し、図パスを訳文基準に直し、
`HUMAN-ONLY` マーカーを入れ直す。

**5. ブラウザで読める形にする**

```bash
python3 scripts/research_ja.py html --out research --docs docs/research-ja \
        --dest ~/Downloads/<slug>-research-ja
```

壊れた内部参照があれば非ゼロで終了する。0 件であることを確認する。

## 忘れてはいけないこと

`docs/research-ja/` は**人間専用**。エージェントが根拠にしてよいのは
`research/rendered/*.md`（英語原文）だけで、訳文は `.claude/settings.json` の
`permissions.deny` で Read が塞いである。訳文を読みたくなったら、まず
「原文を読めば済むのでは」を確認する。理由は
[.claude/skills/kaggle/research-ja-translation.md](../skills/kaggle/research-ja-translation.md) に書いてある。
