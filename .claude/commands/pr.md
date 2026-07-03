# Create Pull Request

変更内容をもとにブランチ作成、コミット、レビュー、修正、プッシュ、PR作成を一括で行う。

## Usage

- `/pr` - 変更内容から自動でブランチ名・コミットメッセージ・PRを生成（レビュー込み）
- `/pr $ARGUMENTS` - 引数をPRの説明として使用
- `/pr --skip-review` - レビュー段階をスキップ

## What This Command Does

以下の手順を順番に実行する:

### 1. 現在の状態を確認
- `git status` で変更ファイルを確認
- `git diff` でstaged/unstaged両方の変更内容を確認
- 変更がない場合はその旨を伝えて終了

### 2. ブランチを作成
- 既にmain/master以外のブランチにいる場合はそのブランチを使用
- main/masterにいる場合は変更内容から適切なブランチ名を生成
  - 命名規則: `feature/description` または `fix/description`（kebab-case）
- `git checkout -b <branch-name>` でブランチを作成

### 3. コミット
- 変更内容を分析してconventional commit形式のメッセージを作成
  - 形式: `type(scope): description`
  - type: feat, fix, improve, docs, refactor, test, chore
- 関連ファイルをステージング（`git add` で個別にファイルを指定）
  - .env, credentials, secrets等のファイルはステージングしない
- コミットを作成

### 4. レビュー（`--skip-review` 指定時はスキップ）
- ビルトインの `/code-review` skill を実行してこのブランチの diff をレビューする
- `codex --version` が成功する環境では、`codex-reviewer` エージェントを並列起動して
  第二意見を取得する（失敗しても続行）
- 指摘の扱い:
  - **confirmed / 明確なバグ**: 修正して追加コミット（`fix:` prefix）
  - **判断が割れる・設計論**: 修正せずユーザーに提示して判断を仰ぐ
  - **false positive**: 却下理由を記録
- 対応結果を次のステップの PR 本文用にまとめる

### 5. プッシュ
- `git push -u origin <branch-name>` でリモートにプッシュ

### 6. PR作成
- `gh pr create` でPRを作成
- タイトル: 70文字以内で変更内容を要約
- 本文: 変更の概要、テストプラン、**レビューサマリ**（実施したレビュー・
  指摘件数・対応結果。スキップした場合は「review skipped」と明記）を含める
- 作成後にPR URLを表示

## Prerequisites

- `gh` CLI がインストール・認証済みであること
- git リモートが設定されていること
- （任意）Codex CLI — あれば第二意見レビューが自動で有効になる
