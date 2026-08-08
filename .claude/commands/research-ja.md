# /research-ja — 公開ディスカッション/writeup の日本語全訳（図つき）

`kaggle_research.py` が取得済みの英語原文から、**図込みの日本語全訳**を作る。
日次実行（`.claude/ops/translate.sh`）と同じ処理を、手で1回まわすためのコマンド。

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

**対象は既定で「取得済みの全部」** — writeup 全件と、discussion スレッド全件。
足切りはしない。`kaggle_research.py` が既に全スレッドを列挙しているので、ここで
絞るのは「取得までしておいて誰にも読ませない」という選択になる。しかも Kaggle CLI
の payload には**本文が入っていない**ので、レンダリングされなかったスレッドは
英語ですら本文がリポジトリに存在しない状態になる。

代わりに**順序**で効かせている: 順位付きの解法 writeup が先頭、その後は votes 降順。
`--limit` で打ち切っても価値の高い方から処理されるので、残りは次回以降に回る。

絞りたいときだけ:

```bash
--writeups-only                 # 解法 writeup だけ
--writeups-only --min-votes 10  # ＋ votes 10 以上の一般スレッド
--skip-writeups                 # discussion のみ
--topic <id>                    # 個別に強制追加（繰り返し可）
```

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

## バックログを一気に消化したいとき

日次ジョブは1晩あたり `TRANSLATE_MAX_PER_RUN` 件しか訳さない。コンペ終了直後など、
溜まった分を今すぐ全部消化したい場合:

```bash
# ops.conf の値を一時的に上げる
TRANSLATE_MAX_PER_RUN=200
TRANSLATE_PREP_LIMIT=500

# 同日中に再実行するには当日の完了記録を消す（1日1回の重複実行ガード）
rm -f .claude/ops/.state-translate
bash .claude/ops/run-daily.sh translate
```

`run-daily.sh` は `ops.conf` を source するので、環境変数で上書きしても効かない。
値そのものを書き換えること。

## 忘れてはいけないこと

`docs/research-ja/` は**人間専用**。エージェントが根拠にしてよいのは
`research/rendered/*.md`（英語原文）だけで、訳文は `.claude/settings.json` の
`permissions.ask` に入っているので、自分の判断で訳文を開こうとすると確認が入る。
ユーザーから明示的に指示されたなら承認して読んでよい。理由は
[.claude/skills/kaggle/research-ja-translation.md](../skills/kaggle/research-ja-translation.md) に書いてある。
