# CLAUDE.md

This file provides guidance to Claude Code when working in this personal development template repository.

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
uv run python -m pytest         # Run tests
uv run python -m black .         # Format code
uv run python -m ruff check      # Lint code
uv run python -m mypy .          # Type checking
uv run jupyter notebook          # Start Jupyter
uv run jupyter lab              # Start JupyterLab
```

## Code Style

- Use ES modules (import/export) syntax, not CommonJS (require)
- Destructure imports when possible (e.g., import { foo } from 'bar')
- Follow language-specific formatting (Prettier, Black, rustfmt)
- Use strict TypeScript configuration when applicable
- Prefer functional components and hooks in React

## Workflow

- Use SKILLS/ directory for project capabilities and domain knowledge
- Copy templates from SKILLS/templates/ to SKILLS/project/ and customize
- Run typecheck after making code changes
- Write tests for new functionality
- Use conventional commit messages
- Prefer composition over inheritance

## File Structure

```
project-root/
├── src/                 # Source code
├── tests/              # Test files
├── CLAUDE.md           # This file
├── SKILLS/             # Project capabilities
│   ├── core/           # General development skills
│   ├── project/        # Project-specific skills
│   ├── templates/      # Skill templates
│   └── kaggle/         # Kaggle-specific skills (separate)
├── kaggle-template/    # Kaggle competition template
├── .claude/            # Claude Code configurations
└── README.md           # Project overview
```

## Repository Etiquette

- Branch naming: feature/description, fix/description
- Commit messages: type(scope): description
- Always run lints and tests before committing

## Special Templates

### Kaggle Competition Development
For Kaggle competitions, use the dedicated template:
```bash
cp -r kaggle-template/ my-competition/
cd my-competition/
uv sync --extra kaggle
```

The template includes specialized notebooks, directory structure, and access to Kaggle-specific SKILLS at `../SKILLS/kaggle/`.