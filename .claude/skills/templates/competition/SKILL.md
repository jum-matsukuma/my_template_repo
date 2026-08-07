---
name: <competition-slug>
description: <コンペ名> のコンテキスト。<タスク種別・ドメイン>。概要/評価/データ/公開解法/実験ログ/運用ランブックのインデックス。
---

# <コンペ名> — コンペコンテキスト

<1〜2 文でタスクを説明する。何を入力に何を予測するのか。>
評価は **<指標>**、<提出形式>。締切 **<YYYY-MM-DD>**。
**目標: <メダル圏・順位など>**。

## Available Resources

<!-- 「最初に読むべきもの」が変わったら、この並び順を変える -->

- [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) — 実験ログ（CV/LB・変更点・結論。**再開時はまずここ**）
- [strategy-principles.md](strategy-principles.md) — **戦略原則と失敗録**。
  新しい施策を思いついたら、まず「試して死んだこと」を確認する
- [pipeline-runbook.md](pipeline-runbook.md) — 運用ランブック（定型コマンド・提出手順）
- [COMPETITION_TRACKER.md](COMPETITION_TRACKER.md) — 概要・評価指標・データ仕様・提出制約・締切
- [existing-solutions.md](existing-solutions.md) — 公開解法の要点・**リーダーボード動向**・我々との差の分解

## 要点（30 秒サマリ）

<!-- ここだけ読めば方針が分かる、という密度で書く。長くなったら別ファイルへ -->

- **タスク**: <予測対象と、その構造的な特徴>
- **鍵となる構造**: <この問題の本質は何か。どこで差がつくのか>
- **現在地** (<YYYY-MM-DD>): CV <値> / LB <値> = <順位> / <参加チーム数>
- **⚠️ 注意**: <リーク・分布ずれ・評価の癖など、知らないと事故るもの>

## 運用ルール

- 提出判断・重み調整はすべて **<CV の切り方>** の OOF で行う
- 重い計算は Kaggle カーネル連鎖へ（[kaggle-gpu-kernels.md](../kaggle/kaggle-gpu-kernels.md)）
- 1 時間超のローカルジョブは切り離して実行（[long-running-jobs.md](../kaggle/long-running-jobs.md)）
- **失敗録にある施策は再試行しない**
