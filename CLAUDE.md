# CLAUDE.md

<!-- INITIAL_SETUP_START -->
## Initial Project Setup（テンプレート初期セットアップ）

> **このセクションはテンプレートclone直後の初回セットアップ用です。**
> セットアップ完了後、ユーザーの承認を得てこのセクション（`INITIAL_SETUP_START` 〜 `INITIAL_SETUP_END`）を CLAUDE.md から削除してください。

### トリガー条件

以下のいずれかに該当する場合、ユーザーの最初の指示に応答する**前に**このセットアップを実行する:
- `pyproject.toml` の `name` が `"mytools-python"` のままである
- `src/mytools/` ディレクトリが存在する
- `README.md` の先頭が `# Personal Development Template` である

### セットアップ手順

#### Step 1: プロジェクト情報のヒアリング

ユーザーに以下を確認する（未指定の項目のみ質問）:

1. **プロジェクト名**（例: `my-awesome-app`）
2. **プロジェクト種別**:
   - `web` — フルスタックWebアプリ（フロントエンド + バックエンド）
   - `frontend` — フロントエンドのみ
   - `backend` — バックエンド / API のみ
   - `kaggle` — Kaggleコンペティション / ML実験
   - `python` — 汎用Pythonプロジェクト
   - `node` — Node.js / TypeScript プロジェクト
3. **言語/フレームワーク**（任意、推測可能なら質問不要）

#### Step 2: 不要ファイルの削除

プロジェクト種別に応じて不要なファイルを削除する:

| 種別 | 削除対象 |
|------|---------|
| `web` | `kaggle-template/`, `.claude/agents/experiment-engineer.md`, `.claude/agents/data-analyst.md`, `.claude/agents/notebook-developer.md`, `.claude/skills/kaggle/`, `.claude/commands/kaggle-update.md` |
| `frontend` | 上記 + `.claude/agents/backend-dev.md` |
| `backend` | 上記（`kaggle-template/`等） + `.claude/agents/frontend-dev.md` |
| `kaggle` | `.claude/agents/frontend-dev.md`, `.claude/agents/backend-dev.md` |
| `python` | `kaggle-template/`, `.claude/agents/frontend-dev.md`, `.claude/agents/backend-dev.md`, `.claude/agents/experiment-engineer.md`, `.claude/agents/data-analyst.md`, `.claude/agents/notebook-developer.md`, `.claude/skills/kaggle/`, `.claude/commands/kaggle-update.md` |
| `node` | `kaggle-template/`, `pyproject.toml`, `src/mytools/`, `tests/`, `.claude/agents/experiment-engineer.md`, `.claude/agents/data-analyst.md`, `.claude/agents/notebook-developer.md`, `.claude/skills/kaggle/`, `.claude/commands/kaggle-update.md` |

**注意**: 削除前にファイル一覧をユーザーに提示し、確認を取ること。

#### Step 3: プレースホルダーの置換

以下のプレースホルダーをプロジェクト固有の値に置換する:

| 対象ファイル | 置換内容 |
|-------------|---------|
| `pyproject.toml` | `name = "mytools-python"` → プロジェクト名、`description`、`authors` |
| `src/mytools/` | ディレクトリ名をプロジェクト名に変更（`src/<project>/`） |
| `src/<project>/__init__.py` | docstring をプロジェクト説明に更新 |
| `tests/test_*.py` | import パスを `from mytools.` → `from <project>.` に更新 |
| `README.md` | プロジェクト名・説明に書き換え |
| `CLAUDE.md` | Repository Purpose セクションをプロジェクト説明に更新 |

#### Step 4: CLAUDE.md の整理

削除したファイルに対応する記述を CLAUDE.md から除去する:
- 削除したエージェントを「定義済みエージェント」テーブルから除去
- 削除したスキル/コマンドへの参照を除去
- File Structure セクションを実態に合わせて更新
- Commands セクションでプロジェクト種別に不要なコマンド群を除去（例: Kaggle以外なら Kaggle API Commands を削除）

#### Step 5: ユーザー承認 → セットアップセクション削除

変更内容の概要をユーザーに提示し、承認を得る。承認後:
1. この初期セットアップセクション（`<!-- INITIAL_SETUP_START -->` から `<!-- INITIAL_SETUP_END -->` まで）を CLAUDE.md から削除
2. 変更をコミット: `feat: initialize project from template`

<!-- INITIAL_SETUP_END -->

## Repository Purpose

Personal development template with reusable configurations and best practices. Copy/fork for new projects.

## Commands

### Node.js Projects
```bash
npm install          # Install dependencies
npm run dev         # Start development server
npm run build       # Build for production
npm run test        # Run tests
npm run lint        # Run linting
npm run typecheck   # TypeScript type checking
```

### Python Projects (uv-based)
```bash
uv sync                          # Install dependencies
uv sync --extra dev              # Install with dev dependencies
uv sync --extra kaggle           # Install with Kaggle dependencies
uv run python -m pytest         # Run tests
uv run python -m black .         # Format code
uv run python -m ruff check      # Lint code
uv run python -m mypy .          # Type checking
uv run jupyter notebook          # Start Jupyter
uv run jupyter lab              # Start JupyterLab
```

### Kaggle API Commands

Kaggle CLI のセットアップと全コマンドリファレンスは `.claude/skills/kaggle/kaggle-api-setup.md` を参照。

## Code Style

- Use ES modules (import/export) syntax, not CommonJS (require)
- Destructure imports when possible (e.g., import { foo } from 'bar')
- Follow language-specific formatting (Prettier, Black, rustfmt)
- Use strict TypeScript configuration when applicable
- Prefer functional components and hooks in React

## Workflow

- Use `.claude/skills/` directory for project capabilities and domain knowledge
- Copy templates from `.claude/skills/templates/` to create new project-specific skills
- Run typecheck after making code changes
- Write tests for new functionality
- Use conventional commit messages
- Prefer composition over inheritance

### Skills File Management

- **SKILL.md** はスキルのエントリーポイント（インデックス）として100行以内に保つ
- 詳細な内容は個別の支援ファイルに分割し、SKILL.mdから相対パスでリンクする
- 各支援ファイルは1つのトピックに集中させ、100〜300行を目安とする
- 支援ファイルが300行を超えた場合はさらに分割を検討する

```
.claude/skills/my-skill/
├── SKILL.md                  # エントリーポイント（インデックス、~100行以内）
├── topic-a.md                # トピックAの詳細（100-300行）
├── topic-b-workflow.md       # トピックBのワークフロー（100-300行）
└── topic-c.md                # トピックCの詳細（100-300行）
```

SKILL.mdでの参照例:
```markdown
## Available Resources
- [topic-a.md](topic-a.md) - トピックAの説明
- [topic-b-workflow.md](topic-b-workflow.md) - トピックBのワークフロー
```

## Agent Teams (Experimental)

マルチエージェント協調ワークフロー機能。`.claude/settings.json` で `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` を設定済み。

エージェント一覧・チームパターン・ライフサイクル・ファイル所有権ルールは `.claude/skills/teams/SKILL.md` を参照。

## Codex CLI Integration (Optional)

`.claude/agents/codex-reviewer.md`、`.claude/commands/codex-review.md`、および `.claude/.mcp.json` の `codex` エントリで OpenAI Codex CLI をセカンドオピニオン用レビュワーとして呼び出せる。共有ラッパは `.claude/scripts/codex-run.sh`(`-s read-only` 固定、`CLAUDE_CODEX_MAX_DEPTH`/`CLAUDE_CODEX_TIMEOUT` で挙動調整)。

setup・3 経路の使い分け・安全モデル・チューニング項目は `README.md` の "Codex CLI Integration (Optional Reviewer)" セクションを参照。MCP 経路は **opt-in** — `settings.local.json` の `enabledMcpjsonServers` に `"codex"` を追加して有効化。

## File Structure

```
project-root/
├── src/                 # Source code
├── tests/              # Test files
├── CLAUDE.md           # This file
├── .claude/            # Claude Code configurations
│   ├── agents/         # Custom agent definitions
│   │   ├── team-lead.md
│   │   ├── frontend-dev.md
│   │   ├── backend-dev.md
│   │   ├── qa-tester.md
│   │   ├── code-reviewer.md
│   │   ├── tech-innovation-advisor.md
│   │   ├── experiment-engineer.md
│   │   ├── data-analyst.md
│   │   └── notebook-developer.md
│   └── skills/         # Skills directory (Claude Code recommended format)
│       ├── kaggle/     # Kaggle competition skills
│       │   └── SKILL.md
│       ├── development/# Core development skills
│       │   └── SKILL.md
│       ├── teams/      # Agent Teams guide
│       │   └── SKILL.md
│       └── templates/  # Skill templates
│           └── SKILL.md
├── kaggle-template/    # Kaggle competition template
└── README.md           # Project overview
```

## Repository Etiquette

- Branch naming: feature/description, fix/description
- Commit messages: type(scope): description
- Always run lints and tests before committing

## Special Templates

### Kaggle Competition Development

**Standard Setup (Local execution):**
```bash
cp -r kaggle-template/ my-competition/
cd my-competition/
uv sync --extra kaggle
```

**Google Colab Setup (Cloud execution with GPU):**
For competitions requiring large datasets or GPU/TPU resources:
- Develop code locally with Claude Code
- Store data in Google Drive
- Execute training on Google Colab
- See `.claude/skills/kaggle/colab-workflow.md` for complete setup guide
- Use `kaggle-template/colab_template.ipynb` as starting point

The template includes specialized notebooks, directory structure, and Kaggle-specific skills at `.claude/skills/kaggle/`.

**Experiment Tracking (3-tier structure):**
Kaggleコンペでは3層のファイルで知見を管理:
- `SKILL.md` — 現在のベストパラメータ・ワークフロー・Next Steps（置換更新）
- `EXPERIMENT_LOG.md` — 全実験結果の履歴（追記型）
- `COMPETITION_TRACKER.md` — リーダーボード・公開ノートブック分析（置換更新）

詳細: `.claude/skills/kaggle/experiment-tracking.md`