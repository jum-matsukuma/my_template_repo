# /kaggle-research — 公開 notebook・discussion・コメント・writeup の差分取得

公開情報を **公式 Kaggle CLI で差分取得**する。スクレイピングも delay も不要。
writeup 本文だけは CLI に存在しないため外部リーダーを経由するが、
**新規 writeup の検知は CLI だけで完結する**ので、外部サービスが落ちても
「気づかない」ことは起きない。

## Usage

```bash
# 差分取得（既定で全スレッドを列挙する）
python3 scripts/kaggle_research.py --comp <slug> --out research

# 取りこぼしの監査だけ（取得はしない）
python3 scripts/kaggle_research.py --comp <slug> --out research --audit

# 初回・全再取得
python3 scripts/kaggle_research.py --comp <slug> --out research --full

# 事前確認 / 一部をスキップ
python3 scripts/kaggle_research.py --comp <slug> --dry-run
python3 scripts/kaggle_research.py --comp <slug> --skip-comments --skip-writeups
```

`<slug>` は `.claude/skills/<comp>/COMPETITION_TRACKER.md` 冒頭のものを使う。

## 差分の判定

| 対象 | 変化の検出 |
|---|---|
| notebook | `lastRunTime` が変化＝新バージョンが実行された |
| topic | `commentCount` が増加＝新しい返信 |
| kernel comments | 親 notebook の `lastRunTime` が変化 |
| writeup | 本文 SHA が変化＝**その場で改訂された**（新規追加だけでなく編集も拾う） |

状態は `research/manifest.json`。

## 出力を読むときの注意

**warnings 欄を必ず見ること。**

```
! 1 count mismatches (possible silent under-fetch):
    kernel foo/bar: fetched 3 of 4 comments
```

Kaggle の申告件数より取得数が少ないという意味。削除済みコメントによる 1 件差は
正常だが、大きく食い違うなら取得側の問題を疑う。この検査が無かった頃、
1050 notebook から 15 件しか拾えていないのに**何のエラーも出なかった**ことがある。

## 使ってはいけないオプション

`--top-topics N` / `--top-notebooks N` は**既定では使わない**。
上位 N のみを取得して manifest に記録すると、差分取得は以後
「manifest にあるものの更新」しか見ないため、**初回に外れたものは二度と現れない**。
158 スレッド中 43 件しか追跡できておらず、上位陣との差を説明する情報が
見落とし側にあった、という実例がある。急ぐ理由がある時だけ、
盲点を作ると分かった上で使うこと。

## 取得物と保管

```
research/
├── manifest.json               # 差分判定の状態・エラー・警告
├── discussions/<id>.json       # 本文 + コメント全文（切り詰めなし）
├── notebooks/<ref>/            # ソース ← gitignore 推奨（他者の著作物）
├── kernel_comments/<ref>.json
└── writeups/<user>__<slug>.md
```

## 取得後のアクション

1. 新規トピック・**新規/更新 writeup** をサマリで確認する
2. 手法の分類・要点を `.claude/skills/<comp>/existing-solutions.md` に反映する。
   **コードの丸写しはしない** — ライセンスを確認し、要約と分類に留める
3. 採用候補は `EXPERIMENT_LOG.md` の Next Steps へ

## 規約

- 公式 API 認証（`~/.kaggle/kaggle.json`）で取得する
- 他者のソースは `research/notebooks/`（非コミット）に留め、派生した要約のみコミットする
- 手段の詳細と落とし穴: `.claude/skills/kaggle/kaggle-scraping.md`
- 日次自動化: `.claude/ops/README.md`（差分を draft PR で出す）
