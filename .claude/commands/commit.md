# Smart Commit

変更内容を分析して、適切なconventional commitメッセージでコミットする。

## Usage

- `/commit` - 全変更を分析してコミット
- `/commit $ARGUMENTS` - 引数をコミットメッセージのヒントとして使用

## What This Command Does

以下の手順を順番に実行する:

### 1. 変更内容の確認
- `git status` で変更ファイルを一覧
- `git diff` でstaged/unstaged両方の変更を確認
- 変更がない場合はその旨を伝えて終了

### 2. コミットメッセージの生成
- 変更内容を分析し、conventional commit形式のメッセージを生成
  - 形式: `type(scope): description`
  - type: feat, fix, improve, docs, refactor, test, chore
  - scope: 変更対象のモジュール・機能
  - description: 変更の「なぜ」を簡潔に
- 複数の論理的な変更がある場合は分割コミットを提案

### 3. ステージングとコミット
- 関連ファイルを `git add` で個別にステージング
  - .env, credentials, secrets等の機密ファイルは除外
  - 不要なファイル（.DS_Store等）は除外
- 生成したメッセージでコミットを作成

### 4. 完了報告
- コミットハッシュとメッセージを表示
- ステージングから除外したファイルがあれば報告
