# Initialize Project

新しいプロジェクトのセットアップを対話的に行う。

## Usage

- `/init` - 対話形式でプロジェクトを初期化
- `/init $ARGUMENTS` - 引数をプロジェクト種別として使用（例: `/init nextjs`, `/init python-cli`）

## What This Command Does

以下の手順でプロジェクトをセットアップする:

### 1. プロジェクト種別の確認
ユーザーに以下を確認:
- プロジェクトの種類（Webアプリ、CLI、ライブラリ、Kaggle等）
- 使用する言語・フレームワーク
- パッケージマネージャー（npm, pnpm, uv等）

### 2. 基本構成の生成
プロジェクト種別に応じて:
- ディレクトリ構造を作成（src/, tests/ 等）
- パッケージ設定ファイルを生成（package.json, pyproject.toml等）
- 基本的な設定ファイルを配置（tsconfig.json, .prettierrc等）
- .gitignore を生成

### 3. 開発ツールの設定
- リンター設定（ESLint, Ruff等）
- フォーマッター設定（Prettier, Black等）
- テストフレームワーク設定（Vitest, pytest等）
- 型チェック設定（TypeScript, mypy等）

### 4. CLAUDE.md の更新
- プロジェクト固有のコマンドを記載
- ディレクトリ構造を更新
- 開発ワークフローを追記

### 5. 依存関係のインストール
- パッケージマネージャーで依存関係をインストール
- インストール結果を確認
