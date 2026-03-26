---
name: teams
description: Claude Code Agent Teams の使い方、チームパターン、カスタムエージェント定義のガイド。マルチエージェントワークフローの計画・実行時に参照する。
user-invocable: false
---

# Agent Teams Skills

Claude Code Agent Teams を使ったマルチエージェント協調ワークフローの知識ベース。

## Available Resources

- [team-patterns.md](team-patterns.md) - チームワークフローパターンとベストプラクティス
- [agent-definition-guide.md](agent-definition-guide.md) - カスタムエージェント定義の作成ガイド

## Quick Reference

### セットアップ

Agent Teams は実験的機能。有効化には環境変数が必要:

```json
// .claude/settings.json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### チームのライフサイクル

1. **計画**: タスク分解 → 依存関係の特定 → チームサイズ決定
2. **構築**: `TeamCreate` → `TaskCreate` → `Task`(teammate spawn)
3. **実行**: タスク取得 → 実装 → 完了報告 → 次のタスク
4. **終了**: 全タスク完了 → `shutdown_request` → `TeamDelete`

### 利用可能なエージェント

| エージェント | 用途 | モデル |
|---|---|---|
| `team-lead` | チームオーケストレーター（PDCA対応） | sonnet |
| `frontend-dev` | フロントエンド開発 | sonnet |
| `backend-dev` | バックエンド開発 | sonnet |
| `qa-tester` | テスト・QA | sonnet |
| `code-reviewer` | コードレビュー | sonnet |
| `tech-innovation-advisor` | 技術戦略アドバイス | opus |
| `experiment-engineer` | 実験実行・パラメータ変更・結果検証 | sonnet |
| `data-analyst` | データ分析・仮説生成 | sonnet |
| `notebook-developer` | Kaggle/Colabノートブック開発 | sonnet |

### チームサイズの目安

- **3-5人**: 一般的なワークフロー向け（ソフトウェア開発）
- **2-3人**: Kaggle実験サイクル向け（analyst + engineer + developer）
- **3-5タスク/人**: 最適な生産性バランス

### ファイル所有権ルール

チームメイト間のマージコンフリクトを防ぐため、ファイル所有権を明確に分離:

**ソフトウェア開発:**
```
frontend-dev: src/components/, src/pages/, src/hooks/
backend-dev:  src/api/, src/services/, src/models/
qa-tester:    tests/, __tests__/, *.test.*
```

**Kaggle/ML実験:**
```
experiment-engineer: kaggle-template/submissions/, scripts/
notebook-developer:  kaggle-template/*.ipynb, notebooks/
data-analyst:        .claude/skills/<project>/, docs/
```
