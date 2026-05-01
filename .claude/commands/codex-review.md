---
description: Get a Codex CLI second-opinion review of the current branch's changes
argument-hint: "[--base BRANCH | --uncommitted | --commit SHA]"
allowed-tools: Bash(bash .claude/scripts/codex-run.sh:*), Bash(git rev-parse:*), Bash(git symbolic-ref:*)
---

# /codex-review

Run a Codex CLI code review of the current branch's changes. Single-shot by design — return Codex's output verbatim and stop.

## Behavior

1. **Resolve the review target.** If `$ARGUMENTS` already contains `--base`, `--uncommitted`, or `--commit`, pass it through unchanged. Otherwise resolve a default base branch:
   - Try `git rev-parse --verify main` — if it exists, use `--base main`
   - Else try `git rev-parse --verify master` — if it exists, use `--base master`
   - Else: print an error: *"No base branch found. Pass `--base <branch>`, `--uncommitted`, or `--commit <sha>`."* and stop.

2. **Invoke Codex via the shared wrapper** with the resolved arguments:

```bash
bash .claude/scripts/codex-run.sh exec -s read-only review <args>
```

The shared wrapper handles install check, depth tracking, and timeout. The `-s read-only` flag fixes the sandbox so Codex never modifies files. The `review` subcommand uses Codex's built-in review prompt against the supplied range.

3. **Display Codex's output verbatim.** Do not follow up with edits, additional reviews, or summaries. The point of a second opinion is the second voice — preserve it.

## Examples

- `/codex-review` → reviews `main..HEAD` (or `master..HEAD`) using Codex's built-in review prompt
- `/codex-review --uncommitted` → reviews staged + unstaged + untracked changes
- `/codex-review --base feature/parent` → reviews against a different base branch
- `/codex-review --commit HEAD~1` → reviews a single commit by SHA

## Errors

- If `codex-run.sh` exits 127, surface its install-hint stderr and stop.
- If neither `main` nor `master` exists and no flag was passed, surface the error from step 1.
- Any other non-zero exit: print Codex's stderr and stop.
