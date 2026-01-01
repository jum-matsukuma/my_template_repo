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

### Python Projects
```bash
pip install -r requirements.txt  # Install dependencies
python -m pytest                 # Run tests
python -m black .                # Format code
python -m ruff check             # Lint code
python -m mypy .                 # Type checking
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
├── SKILLS/             # Project capabilities (core/, project/, templates/)
├── .claude/            # Claude Code configurations
└── README.md           # Project overview
```

## Repository Etiquette

- Branch naming: feature/description, fix/description
- Commit messages: type(scope): description
- Always run lints and tests before committing