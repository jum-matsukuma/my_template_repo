# 実験トラッキング3層構造

Kaggleコンペティションの知見・実験結果・競合分析を効率的に管理するための3層ファイル構造。

## 3つのファイルの役割

| ファイル | 内容 | 更新方式 | 更新頻度 |
|---------|------|---------|---------|
| `SKILL.md` | 現在のベストパラメータ、ワークフロー、Next Steps | 置換 | 週次 |
| `EXPERIMENT_LOG.md` | 全実験結果の履歴（バージョン、delta、教訓） | 追記 | 実験ごと |
| `COMPETITION_TRACKER.md` | リーダーボード動向、公開ノートブック分析 | 置換 | 週次 |

## ディレクトリ構成

```
.claude/skills/<competition-name>/
├── SKILL.md                  # 現在の知識・ワークフロー（エントリーポイント）
├── EXPERIMENT_LOG.md         # 実験履歴（追記型）
├── COMPETITION_TRACKER.md    # リーダーボード・ノートブック分析
├── notebook-dev-guide.md     # ノートブック開発ガイド（必要時）
└── advanced-strategy.md      # 戦略研究（必要時）
```

## SKILL.md の構成（~100行、テンプレート）

```markdown
---
name: <competition-name>
description: <competition>のナレッジベース
---

# <Competition Name>

## 概要
- 評価指標: [metric]
- 賞金: $XX,XXX
- 締切: YYYY-MM-DD
- 制約: [CPU/GPU時間、Internet制限等]

## 現在のベストモデル
- スコア: X.XXX (Public LB)
- 手法: [概要]
- 主要パラメータ:
  - param_a = value
  - param_b = value

## ワークフロー
[現在の実行手順]

## Next Steps（優先度順）
1. **[改善案A]** — 根拠、期待改善幅
2. **[改善案B]** — 根拠、期待改善幅
3. **[改善案C]** — 根拠、期待改善幅

## Deprecated（採用しなかったアプローチ）
- [approach]: [理由]

Last updated: YYYY-MM-DD
```

## EXPERIMENT_LOG.md の構成（追記型）

```markdown
# Experiment Log

## vX.Y: [実験名] (YYYY-MM-DD)

**変更内容**: [パラメータ変更の詳細]

**結果**:
| 指標 | 前バージョン | 今回 | Delta |
|------|------------|------|-------|
| Val Score | X.XXXX | X.XXXX | +/-X.XXXX |
| Public LB | X.XXX | X.XXX | +/-X.XXX |

**項目別変化**:
- 改善: [item (+delta)]
- 悪化: [item (-delta)]

**教訓**: [何が効いた/効かなかったか]
**次に試すべき**: [次の実験候補]

---
(以降、過去の実験が続く)
```

## COMPETITION_TRACKER.md の構成

```markdown
# Competition Tracker

Last updated: YYYY-MM-DD

## リーダーボード
| 順位 | チーム | スコア | 前回比 |
|------|--------|--------|--------|

## 注目ノートブック
1. **[タイトル]** — 手法概要、スコア

## 手法分類
| 手法 | スコア範囲 | 代表的チーム |
|------|-----------|-------------|

## トレンド
- [最近の動向メモ]
```

## 更新ルール

### いつ何を更新するか

1. **実験を実行した後** → `EXPERIMENT_LOG.md` に追記
2. **リーダーボードに大きな変動** → `COMPETITION_TRACKER.md`
3. **新しい重要なノートブック公開** → `COMPETITION_TRACKER.md`
4. **重要なテクニック採用決定** → `SKILL.md` の Next Steps に追加
5. **ベストスコア更新** → `SKILL.md` の現在のベストモデルを更新

### アーカイブ

SKILL.md が肥大化した場合:

```
docs/archive/<competition-name>/
├── YYYY-MM-DD_archived_content.md
└── ...
```

**SKILL.md に残す**: 現在のベスト、Next Steps、直近の重要情報
**アーカイブ**: 実装済みテクニック詳細、古い分析、不採用アプローチ詳細

## 担当エージェントとの連携

| 操作 | 担当エージェント |
|------|----------------|
| EXPERIMENT_LOG.md への記録 | experiment-engineer |
| COMPETITION_TRACKER.md の更新 | data-analyst |
| SKILL.md の更新 | team-lead（または手動） |
| 全体の分析・仮説生成 | data-analyst |
