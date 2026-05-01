# Codex Reviewer Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three opt-in routes (agent, slash command, MCP) for invoking OpenAI Codex CLI as a second-opinion reviewer from inside a Claude Code session.

**Architecture:** A shared shell wrapper (`.claude/scripts/codex-run.sh`) centralizes the safety logic — install check, depth tracking, opt-in depth ceiling, default 30-minute timeout. The wrapper takes `codex` arguments and forwards them. Two routes use the wrapper:

- **Agent** (`.claude/agents/codex-reviewer.md`) calls `bash .claude/scripts/codex-run.sh exec -s read-only "<prompt>"` for ad-hoc reviews with a custom prompt.
- **Slash command** (`.claude/commands/codex-review.md`) calls `bash .claude/scripts/codex-run.sh exec -s read-only review --base <branch>` to delegate to Codex's built-in `exec review` subcommand (which already has `--base`, `--uncommitted`, `--commit` flags).

The MCP route adds a `codex` server entry to `.claude/.mcp.json` that is **not** in `enabledMcpjsonServers` by default — users opt in via their `settings.local.json`.

**Tech Stack:** Bash, Codex CLI (`@openai/codex` ≥ 0.128.0), Claude Code agent/command/MCP config files.

**Refinement vs spec:** The spec described building a custom diff-piping prompt in the slash command. During plan drafting we discovered `codex exec review` already provides this natively, so the slash command delegates to it. The spec's intent (single-shot, read-only sandbox, native git-range support) is preserved.

---

## File Structure

**New files:**
- `.claude/scripts/codex-run.sh` — shared wrapper (install check + depth + timeout + exec)
- `.claude/agents/codex-reviewer.md` — agent definition
- `.claude/commands/codex-review.md` — slash command definition

**Modified files:**
- `.claude/.mcp.json` — add `codex` server entry (opt-in)
- `.claude/settings.json` — add Bash permissions for codex/timeout/script
- `README.md` — add "Codex CLI Integration (Optional Reviewer)" section
- `CLAUDE.md` — short mention with pointer to README

---

## Task 1: Shared wrapper script

**Files:**
- Create: `.claude/scripts/codex-run.sh`

- [ ] **Step 1: Create scripts directory if needed**

```bash
mkdir -p .claude/scripts
```

- [ ] **Step 2: Write the wrapper script**

Create `.claude/scripts/codex-run.sh`:

```bash
#!/usr/bin/env bash
# Wrapper for invoking the Codex CLI from Claude Code with safety guardrails.
#
# Usage: codex-run.sh <codex-args...>
# Examples:
#   codex-run.sh exec -s read-only "review this snippet: ..."
#   codex-run.sh exec -s read-only review --base main
#
# Environment:
#   CLAUDE_CODEX_DEPTH        Current call depth (incremented on each call). Default: 0.
#   CLAUDE_CODEX_MAX_DEPTH    Opt-in depth ceiling. Default: 0 (unlimited).
#   CLAUDE_CODEX_TIMEOUT      Per-call timeout in seconds. Default: 1800 (30 min). 0 disables.

set -eu

DEPTH="${CLAUDE_CODEX_DEPTH:-0}"
MAX="${CLAUDE_CODEX_MAX_DEPTH:-0}"
TIMEOUT="${CLAUDE_CODEX_TIMEOUT:-1800}"

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found. Install with: npm install -g @openai/codex" >&2
  echo "Then run: codex login" >&2
  exit 127
fi

if [ "$MAX" -gt 0 ] && [ "$DEPTH" -ge "$MAX" ]; then
  echo "Codex depth limit (CLAUDE_CODEX_MAX_DEPTH=$MAX) reached at depth $DEPTH." >&2
  exit 1
fi

export CLAUDE_CODEX_DEPTH=$((DEPTH + 1))

if [ "$TIMEOUT" -gt 0 ]; then
  exec timeout "$TIMEOUT" codex "$@"
else
  exec codex "$@"
fi
```

- [ ] **Step 3: Make it executable**

```bash
chmod +x .claude/scripts/codex-run.sh
```

- [ ] **Step 4: Smoke-test the install-check path**

Run with `codex` temporarily masked (no codex installed scenario):

```bash
PATH=/usr/bin:/bin .claude/scripts/codex-run.sh exec --version
```

Expected stderr:
```
codex CLI not found. Install with: npm install -g @openai/codex
Then run: codex login
```
Exit code: `127`.

- [ ] **Step 5: Smoke-test the depth-limit path**

```bash
CLAUDE_CODEX_DEPTH=2 CLAUDE_CODEX_MAX_DEPTH=2 .claude/scripts/codex-run.sh exec --version
```

Expected stderr: `Codex depth limit (CLAUDE_CODEX_MAX_DEPTH=2) reached at depth 2.`
Exit code: `1`.

- [ ] **Step 6: Smoke-test the happy path (no actual codex call)**

```bash
CLAUDE_CODEX_TIMEOUT=0 .claude/scripts/codex-run.sh --version
```

Expected: prints `codex-cli 0.128.0` (or current version). Exit code 0.

- [ ] **Step 7: Smoke-test the timeout path**

```bash
CLAUDE_CODEX_TIMEOUT=1 .claude/scripts/codex-run.sh exec -s read-only "wait quietly for a long time and say nothing"
```

Expected: process is killed by `timeout` after ~1 second. Exit code: `124` (the timeout exit code).
(If you don't have an OpenAI key configured, this may fail earlier — that is acceptable for the smoke test; the goal is verifying `timeout` wraps the call.)

- [ ] **Step 8: Commit**

```bash
git add .claude/scripts/codex-run.sh
git commit -m "feat: add Codex CLI wrapper with depth + timeout guardrails"
```

---

## Task 2: codex-reviewer agent

**Files:**
- Create: `.claude/agents/codex-reviewer.md`

- [ ] **Step 1: Write the agent definition**

Create `.claude/agents/codex-reviewer.md`:

````markdown
---
name: codex-reviewer
description: Use when you want a second-opinion code review from OpenAI Codex CLI. Complementary to the built-in code-reviewer agent — runs an independent model to surface issues Claude may have missed. Examples - "get a Codex second opinion on this auth refactor", "have Codex review the diff before I push", "show this function to Codex and ask if there's a bug".
tools: Bash, Read
model: sonnet
---

You are a thin wrapper that hands off review work to the Codex CLI and returns its output verbatim. You are NOT a reviewer yourself — you do not analyze, summarize, or reinterpret what Codex says.

# Operating contract

You make **exactly one `codex exec` call per invocation**. No retries. No chaining. If the call fails, return the error to the parent and stop. What happens *inside* the resulting Codex session is governed by Codex itself; you do not constrain its tool use.

# Invocation

Use the shared wrapper, which handles the install check, depth tracking, and timeout:

```bash
bash .claude/scripts/codex-run.sh exec -s read-only "$PROMPT"
```

`$PROMPT` is the review instruction you build from what the parent asked you to look at. Keep it minimal:

```
Review the following code. Point out correctness issues, security concerns,
and clarity problems. Be concise — bullet points only, no preamble.

<paste the code or diff or file contents here>
```

If the parent asked for a focus area (e.g., "look at thread safety"), add one sentence to the instruction. Do not pad with extra formatting requests.

# Reading source

You may use `Read` to load files referenced in the parent's request before constructing the prompt — for example, when the parent says "review the auth module", read the relevant files and embed them in the prompt. Do not modify any files.

# Output

Return Codex's stdout exactly as received. Do not add commentary, do not summarize, do not say "Codex found that...". The point of a second opinion is the second voice — preserve it.

If `codex-run.sh` exits with code 127 (codex not installed), return its stderr verbatim and stop. If it exits with another non-zero code, return both stdout and stderr and stop.
````

- [ ] **Step 2: Verify file syntax**

```bash
head -10 .claude/agents/codex-reviewer.md
```

Expected: Valid YAML frontmatter with `name`, `description`, `tools`, `model`.

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/codex-reviewer.md
git commit -m "feat: add codex-reviewer agent for second-opinion reviews"
```

---

## Task 3: /codex-review slash command

**Files:**
- Create: `.claude/commands/codex-review.md`

- [ ] **Step 1: Write the command definition**

Create `.claude/commands/codex-review.md`:

````markdown
---
description: Get a Codex CLI second-opinion review of the current branch's changes
argument-hint: "[--base BRANCH | --uncommitted | --commit SHA]"
allowed-tools: Bash(bash .claude/scripts/codex-run.sh:*), Bash(git rev-parse:*), Bash(git symbolic-ref:*)
---

Run a Codex code review of the current branch's changes.

# Behavior

1. **Resolve the base branch** if the user did not pass `--base`, `--uncommitted`, or `--commit`:
   - Try `git rev-parse --verify main` → use `--base main`
   - Else try `git rev-parse --verify master` → use `--base master`
   - Else: print an error: "No base branch found. Pass `--base <branch>`, `--uncommitted`, or `--commit <sha>`." and stop.
2. **Pass `$ARGUMENTS` through** if any argument is provided — the user's flags take precedence over the default.
3. **Invoke** the wrapper with `codex exec -s read-only review` and the resolved arguments:

```bash
bash .claude/scripts/codex-run.sh exec -s read-only review <args>
```

4. **Display Codex's output verbatim**. Do not follow up with edits, additional reviews, or summaries — this command is single-shot by design.

# Examples

- `/codex-review` → reviews `main..HEAD` (or `master..HEAD`) using Codex's built-in review prompt.
- `/codex-review --uncommitted` → reviews staged + unstaged + untracked changes.
- `/codex-review --base feature/parent` → reviews against a different base.
- `/codex-review --commit HEAD~1` → reviews a single commit.

# Errors

- If `codex-run.sh` exits 127, surface its install-hint stderr and stop.
- If neither `main` nor `master` exists and no flag was passed, surface the error from step 1.
- Any other non-zero exit: print Codex's stderr and stop.
````

- [ ] **Step 2: Verify file syntax**

```bash
head -6 .claude/commands/codex-review.md
```

Expected: Valid YAML frontmatter with `description`, `argument-hint`, `allowed-tools`.

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/codex-review.md
git commit -m "feat: add /codex-review slash command"
```

---

## Task 4: MCP server entry

**Files:**
- Modify: `.claude/.mcp.json`

- [ ] **Step 1: Read the current file**

```bash
cat .claude/.mcp.json
```

Confirm it contains the `filesystem` entry under `mcpServers`.

- [ ] **Step 2: Add the codex entry**

Replace the file contents with:

```json
{
  "mcpServers": {
    "filesystem": {
      "_comment": "Replace <YOUR_PROJECT_PATH> with your actual project directory. Claude Code has built-in file access, so this MCP server is optional.",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "<YOUR_PROJECT_PATH>"],
      "env": {
        "NODE_ENV": "development"
      }
    },
    "codex": {
      "_comment": "OpenAI Codex CLI as MCP server. Requires `npm i -g @openai/codex` and `codex login`. Disabled by default — to enable, add \"codex\" to enabledMcpjsonServers in settings.local.json. See README.",
      "command": "codex",
      "args": ["mcp"],
      "env": {
        "CLAUDE_CODEX_DEPTH": "1"
      }
    }
  }
}
```

- [ ] **Step 3: Verify JSON validity**

```bash
python3 -m json.tool .claude/.mcp.json > /dev/null && echo OK
```

Expected: `OK`.

- [ ] **Step 4: Verify codex is NOT auto-enabled**

```bash
grep -A 3 enabledMcpjsonServers .claude/settings.local.json
```

Expected: only `"filesystem"` (or whatever was already there) — no `"codex"`. Codex remains opt-in.

- [ ] **Step 5: Commit**

```bash
git add .claude/.mcp.json
git commit -m "feat: register codex MCP server entry (opt-in)"
```

---

## Task 5: Settings permissions

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: Read the current file**

```bash
cat .claude/settings.json
```

Note the existing `permissions.allow` array.

- [ ] **Step 2: Add Bash permissions for codex tooling**

Add the following entries to `permissions.allow` (alphabetical-ish, near other Bash entries):

```json
"Bash(bash .claude/scripts/codex-run.sh:*)",
"Bash(codex exec:*)",
"Bash(codex --version)",
"Bash(timeout:*)"
```

After editing, the `permissions.allow` array should include those four lines. Do not remove any existing entries.

- [ ] **Step 3: Verify JSON validity**

```bash
python3 -m json.tool .claude/settings.json > /dev/null && echo OK
```

Expected: `OK`.

- [ ] **Step 4: Verify the entries are present**

```bash
grep -E 'codex-run.sh|codex exec|codex --version|Bash\(timeout' .claude/settings.json
```

Expected: four matching lines.

- [ ] **Step 5: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: allow codex/timeout Bash invocations in settings"
```

---

## Task 6: README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current README**

```bash
cat README.md
```

Identify a sensible insertion point — after the existing "feature list" or "tools" section, before any project-specific tail content.

- [ ] **Step 2: Append the integration section**

Add the following section to `README.md` at the chosen insertion point:

```markdown
## Codex CLI Integration (Optional Reviewer)

This template ships an opt-in integration that lets you call OpenAI's Codex CLI from inside Claude Code as a second-opinion reviewer. Three call routes are provided:

| Route | How to invoke | When to use |
|-------|---------------|-------------|
| Agent (`codex-reviewer`) | Ask Claude in natural language: "have Codex review this" | Flexible / ad-hoc reviews |
| Slash command (`/codex-review`) | `/codex-review [--base BRANCH \| --uncommitted \| --commit SHA]` | One-shot branch-diff review |
| MCP server (`codex`) | Opt-in (see below); Claude calls Codex tools autonomously | Persistent / autonomous use |

### Setup

1. Install Codex CLI: `npm install -g @openai/codex`
2. Authenticate: `codex login`
3. (MCP route only) Add `"codex"` to `enabledMcpjsonServers` in your `.claude/settings.local.json`:

```json
{
  "enabledMcpjsonServers": ["filesystem", "codex"]
}
```

### Safety model

- **Read-only sandbox** is fixed on every `codex exec` invocation from the agent and slash command (`-s read-only`). Codex cannot modify files through these routes.
- **Autonomous-friendly recursion**: there is no hard depth limit by default. Set `CLAUDE_CODEX_MAX_DEPTH=N` to opt into a ceiling for a session.
- **Per-call timeout** defaults to 30 minutes. Set `CLAUDE_CODEX_TIMEOUT=<seconds>` to override, or `0` to disable.

Pro plan users running deep autonomous workflows often want `CLAUDE_CODEX_TIMEOUT=0` (or a high value like `7200`).

### Tuning

| Env var | Default | Purpose |
|---------|---------|---------|
| `CLAUDE_CODEX_DEPTH` | `0` | Auto-incremented; observability only |
| `CLAUDE_CODEX_MAX_DEPTH` | `0` (unlimited) | Opt-in recursion ceiling |
| `CLAUDE_CODEX_TIMEOUT` | `1800` (30 min) | Per-call timeout in seconds; `0` disables |

### Removing the integration

If you don't want this in your derived project, delete:
- `.claude/agents/codex-reviewer.md`
- `.claude/commands/codex-review.md`
- `.claude/scripts/codex-run.sh`
- The `codex` entry in `.claude/.mcp.json`
- The four `codex`/`timeout` lines from `.claude/settings.json` `permissions.allow`
- This README section
```

- [ ] **Step 3: Verify the section renders**

```bash
grep -n "Codex CLI Integration" README.md
```

Expected: one matching line with the section heading.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document Codex CLI reviewer integration"
```

---

## Task 7: CLAUDE.md mention

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read CLAUDE.md and find the right section**

```bash
grep -n "^##" CLAUDE.md
```

Pick a sensible spot — after the "Workflow" section seems natural, or alongside "Agent Teams (Experimental)".

- [ ] **Step 2: Add a short pointer**

Insert (near the "Agent Teams" section or in a new "Optional Integrations" section):

```markdown
## Codex CLI Integration (Optional)

`.claude/agents/codex-reviewer.md`, `.claude/commands/codex-review.md`, and the `codex` MCP entry provide a Codex CLI second-opinion reviewer. Setup, safety model, and tuning are documented in `README.md` under "Codex CLI Integration (Optional Reviewer)". The MCP route is **opt-in** — add `"codex"` to `enabledMcpjsonServers` in `settings.local.json` to use it.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: mention Codex CLI integration in CLAUDE.md"
```

---

## Task 8: End-to-end acceptance verification

This task runs the spec's seven acceptance checks against the implemented system. Each check is a manual test — record the outcome.

**Files:** none modified (verification only)

- [ ] **Step 1: AC #1 — agent invocation returns Codex output verbatim**

In a Claude Code session, ask: *"Use the codex-reviewer agent to review this snippet: `def add(a, b): return a - b`"*.

Expected: Claude spawns the codex-reviewer agent; the agent runs `bash .claude/scripts/codex-run.sh exec -s read-only "..."`; Codex's bullet-point output is returned without Claude paraphrasing it.

- [ ] **Step 2: AC #2 — `/codex-review` default range works**

Run `/codex-review` on a branch with at least one commit ahead of `main`.

Expected: Codex runs `exec review --base main` and prints its review of the diff.

- [ ] **Step 3: AC #2 (continued) — `/codex-review` with explicit args**

Run `/codex-review --uncommitted` on a worktree with uncommitted changes.

Expected: Codex reviews the uncommitted changes.

- [ ] **Step 4: AC #3 — clean error when codex is uninstalled**

Temporarily mask codex:

```bash
PATH=/usr/bin:/bin bash .claude/scripts/codex-run.sh exec --version
```

Expected: stderr `codex CLI not found. Install with: npm install -g @openai/codex`, exit code 127.

- [ ] **Step 5: AC #4 — depth limit refusal**

```bash
CLAUDE_CODEX_DEPTH=1 CLAUDE_CODEX_MAX_DEPTH=1 bash .claude/scripts/codex-run.sh exec --version
```

Expected: stderr `Codex depth limit (CLAUDE_CODEX_MAX_DEPTH=1) reached at depth 1.`, exit code 1.

- [ ] **Step 6: AC #5 — timeout kills long calls**

```bash
CLAUDE_CODEX_TIMEOUT=1 bash .claude/scripts/codex-run.sh exec -s read-only "sleep for a while please"
```

Expected: killed after ~1 second, exit code 124 (or non-zero from `timeout`). The exact behavior depends on Codex internals; the key is that `timeout` is wrapping the call (verifiable with `set -x` or `bash -x .claude/scripts/codex-run.sh ...`).

- [ ] **Step 7: AC #6 — MCP route is opt-in**

```bash
claude mcp list 2>&1 | grep -i codex
```

Expected: no `codex` server listed when `enabledMcpjsonServers` does not include it.

Then add `"codex"` to `settings.local.json`'s `enabledMcpjsonServers` (manually, not committed), restart the Claude session, and verify `claude mcp list` shows codex.

Revert `settings.local.json` after testing.

- [ ] **Step 8: AC #7 — `--sandbox read-only` is on every call**

```bash
bash -x .claude/scripts/codex-run.sh exec -s read-only "say hi" 2>&1 | head -5
```

Expected: the trace shows `codex exec -s read-only "say hi"` (or with `timeout` prefix). Confirms the flag is forwarded.

Read the agent and slash command files and confirm both pass `-s read-only` to the wrapper:

```bash
grep -n "read-only" .claude/agents/codex-reviewer.md .claude/commands/codex-review.md
```

Expected: at least one match per file.

- [ ] **Step 9: Final commit (if any docs need touch-ups discovered during AC)**

If any AC step uncovered a documentation gap, fix it now and commit.

```bash
git add -A
git commit -m "docs: address acceptance-check findings"
```

If everything passed cleanly, no commit needed.

---

## Self-review notes (post-write)

- Spec coverage: ✓ all three routes, common wrapper, hard guardrail (read-only), soft guardrails (depth/timeout/observability), settings, README, CLAUDE.md, acceptance checks.
- The plan refines the spec by using `codex exec review` (native subcommand) instead of building a diff-piping prompt. This is called out at the top of the plan.
- The `--sandbox read-only` flag for the MCP route cannot be enforced by the wrapper since `codex mcp` is a long-running server, not an `exec` call. This is acceptable: MCP route is "advanced autonomous use" per the spec, and the user opts in. README does not promise read-only sandbox for the MCP route.
- Type/path consistency: wrapper script path is `.claude/scripts/codex-run.sh` everywhere it appears.
- Permissions cover what the agent and slash command actually shell out to.
