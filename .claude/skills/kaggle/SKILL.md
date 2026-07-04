---
name: kaggle
description: Kaggle competition development skills. Use when the user mentions Kaggle, competition, ML modeling, data analysis, feature engineering, model training, or asks about submitting predictions. Also use when working with kaggle CLI commands or Google Colab integration.
user-invocable: true
argument-hint: "[competition-name or topic]"
---

# Kaggle Competition Development

Comprehensive skills for Kaggle competition development, including workflow patterns, API usage, Google Colab integration, and machine learning best practices.

## Quick Start

```bash
# Setup Kaggle API
uv sync --extra kaggle

# Download competition data
uv run kaggle competitions download -c competition-name

# Submit predictions
uv run kaggle competitions submit -c competition-name -f submission.csv -m "Message"
```

## Available Resources

### Setup and Tools
- [kaggle-api-setup.md](kaggle-api-setup.md) - Kaggle API installation and authentication guide
- [kaggle-scraping.md](kaggle-scraping.md) - Playwright スクレイピング + discussion 一括取得スクリプト
- [colab-workflow.md](colab-workflow.md) - Google Colab + Claude Code development workflow（Drive 構成・チェックポイント戦略。実行は colab スキル推奨）
- [../colab/SKILL.md](../colab/SKILL.md) - Colab CLI / MCP による実行（GPU/TPU ヘッドレス実行・ノートブックのライブ操作）
- [claude-friendly-outputs.md](claude-friendly-outputs.md) - Creating outputs Claude can review locally
- [data-analysis-workflow.md](data-analysis-workflow.md) - Complete data analysis workflow with Claude + Colab
- [notebook-development-guide.md](notebook-development-guide.md) - Colab/Kaggle デュアル環境ノートブック開発ガイド

### Competition Workflow
- [experiment-tracking.md](experiment-tracking.md) - 実験トラッキング3層構造パターン
- [solution-strategy.md](solution-strategy.md) - 競技フェーズ別の戦略・リソース配分

### ML Reference
- [data-understanding.md](data-understanding.md) - データセット分析・特徴量ドキュメントテンプレート
- [feature-engineering.md](feature-engineering.md) - 特徴量エンジニアリングパターン集
- [model-zoo.md](model-zoo.md) - モデル別ハイパーパラメータ設定・学習コード例
- [evaluation-metrics.md](evaluation-metrics.md) - 評価指標・バリデーション戦略

## Competition Setup

1. **Assess problem type** (tabular, CV, NLP) and evaluation metric
2. **Set up validation strategy** matching competition timeline and data structure
3. **Establish baseline** using simple models (mean/mode prediction, basic tree model)
4. **Configure experiment tracking** and reproducibility (random seeds, version control)

## Development Workflow Options

### Standard Setup (Local execution)
```bash
cp -r kaggle-template/ my-competition/
cd my-competition/
uv sync --extra kaggle
```

### Google Colab Setup (Cloud execution with GPU)
For competitions requiring large datasets or GPU/TPU resources:
- Develop code locally with Claude Code
- Store data in Google Drive
- Execute training on Google Colab — prefer the Colab CLI (`colab run` / `colab exec`) via the [colab skill](../colab/SKILL.md); it runs scripts on GPU/TPU runtimes headlessly from the terminal
- See [colab-workflow.md](colab-workflow.md) for the Drive structure and checkpointing guide
