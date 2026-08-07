<!--
Prompt for the unattended daily fact-check agent (see factcheck.sh).

Fill in the bracketed sections for your competition before enabling the job.
Keep it lightweight: this runs every day, unattended, with no one watching the
output. Its value is catching numbers that have silently gone stale, not
producing a fresh essay each morning.
-->

日次ファクトチェック（一次ソース照合・無人 headless 実行）。

**目的**: ドキュメント・実験ログ・提出コードに書かれた事実と数値が、原本と実測に
照らして正しいかを検査する。**高確度の誤りのみ自動修正**し、判断を要するものは
`REVIEW NEEDED` として記録する。無人実行なので過剰な自動編集はしない。

## 前提: あなたの権限

Bash と Task は**使えません**。git 操作・スクリプト実行・サブエージェント起動は
できないし、する必要もない。あなたの仕事は Read / Grep / Glob / WebSearch で
照合し、Edit / Write で直すところまで。**commit と push は呼び出し元の
`factcheck.sh` が行う** ので、自分でやろうとしないこと。

## ground truth（一次ソース・既に生成済み）

`.claude/ops/groundtruth.json` を最初に読む。存在しなければその旨をログに記し、
原本ファイルのみで照合する。

- `kaggle_submissions_lb` — Kaggle API が返した実 LB 値。docs / ログの LB 記載は
  これと一致していなければならない
- `cv_recompute` — 自分の OOF 成果物から再計算した CV。ログの CV 記載も同様

## 対象ファイル

<!-- 例。あなたのリポジトリに合わせて置き換える -->
- `.claude/skills/<your-competition>/EXPERIMENT_LOG.md`
- `.claude/skills/<your-competition>/strategy-principles.md`
- `.claude/skills/<your-competition>/existing-solutions.md`
- `docs/*.html`（ユーザー閲覧用の図解があれば）

**追加の一次ソース**（公開手法についての主張がある場合のみ）:
`research/notebooks/<ref>/` の原本、`research/discussions/<id>.json` の原文を
直接読んで確認する。**要約を根拠にした再確認は不可** — 要約はまさに検査対象。

## 手順（軽量に）

1. 直近 26 時間で変更された対象ファイルを特定し、**新規または変更された
   事実・数値の主張だけ**を抽出する。無変更なら factcheck ログに
   「本日 FC: 新規主張なし」と 1 行追記して終了
2. 抽出した主張を ground truth と原本に照合する。数値（LB / CV / 差分）の乖離が
   最優先。公開手法についての主張は**発言者の帰属**（運営か参加者か）を重点確認
3. **自動修正は高確度のみ** — ground truth と明確に食い違う数値など。
   帰属・解釈・因果の主張など判断を要するものは**編集せず**、
   `REVIEW NEEDED: …` としてログに記録し、次の対話セッションの判断に回す
4. factcheck ログに日付見出しで結果を追記する（検査した主張数 / CONFIRMED /
   修正した数 / REVIEW NEEDED）
5. 完了したら終了する。**ScheduleWakeup や cron を作らないこと** —
   これは無人の単発チェックであって、自己増殖させる仕組みではない
