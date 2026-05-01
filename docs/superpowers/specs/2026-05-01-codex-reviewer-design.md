# Codex Reviewer Integration — Design

**Date**: 2026-05-01
**Status**: Approved (brainstorming complete; pending implementation plan)
**Scope**: Template-level integration committed to this repository so derived projects inherit the configuration.

## Goal

Allow a Claude Code session to invoke OpenAI's Codex CLI as a second-opinion reviewer. Provide three call routes — agent, slash command, MCP — so users can pick the right tool for the situation. Ship as opt-in defaults so derived projects without a Codex subscription remain unaffected.

## Three Call Routes

| Route | File | Trigger | Use case |
|-------|------|---------|----------|
| 1. Dedicated agent | `.claude/agents/codex-reviewer.md` | Natural-language invocation by Claude | Flexible "ask Codex to weigh in" |
| 2. Slash command | `.claude/commands/codex-review.md` | `/codex-review [git-range]` | One-shot diff review |
| 3. MCP server | Entry in `.claude/.mcp.json` | Opt-in via `enabledMcpjsonServers` | Codex as a persistent tool, advanced autonomous use |

## Design Philosophy

This integration prefers **autonomous scaling over hard recursion limits**. Two pieces of context drive that:

1. The reviewer is a *role*, not a stylistic restriction — what makes it correct is read-only access to source, not call-frequency limits.
2. Codex Pro plan is flat-rate, so per-invocation cost is not a concern; capping autonomous depth would hurt utilization without a corresponding safety win.

Hard guardrails are kept only where they protect role correctness. Recursion safeguards are observability + an opt-in ceiling, plus a generous per-call timeout to catch truly stuck processes.

## Hard Guardrails (kept)

- **`--sandbox read-only`** is fixed on every `codex exec` invocation. The reviewer never writes files. Code-modifying use cases must use a different tool/agent (out of scope here).
- **codex-reviewer agent has `tools: Bash, Read`** — no `Edit`, `Write`, or `Agent`. Structurally prevents the reviewer from spawning subagents or modifying code.

## Soft Guardrails (observability + opt-in)

- **`CLAUDE_CODEX_DEPTH`** env var is incremented at every wrapper invocation. Visible to the user/agent but not enforced by default.
- **`CLAUDE_CODEX_MAX_DEPTH`** opt-in env (default `0` = unlimited). When set to `N > 0`, the wrapper refuses calls at or beyond depth N.
- **`CLAUDE_CODEX_TIMEOUT`** per-invocation timeout in seconds. Default `1800` (30 min). Set to `0` to disable.
- No prompt-level "do not invoke other AIs" constraints. Codex is trusted to self-regulate within the timeout.

## Common Wrapper

The agent and slash command both invoke Codex through the same shell pattern:

```bash
DEPTH="${CLAUDE_CODEX_DEPTH:-0}"
MAX="${CLAUDE_CODEX_MAX_DEPTH:-0}"   # 0 = unlimited
TIMEOUT="${CLAUDE_CODEX_TIMEOUT:-1800}"  # 0 = disabled

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found. Install with: npm install -g @openai/codex" >&2
  exit 1
fi

if [ "$MAX" -gt 0 ] && [ "$DEPTH" -ge "$MAX" ]; then
  echo "Codex depth limit ($MAX) reached at depth $DEPTH." >&2
  exit 1
fi

NEXT_DEPTH=$((DEPTH + 1))
RUN=(env CLAUDE_CODEX_DEPTH="$NEXT_DEPTH" codex exec --sandbox read-only "$PROMPT")

if [ "$TIMEOUT" -gt 0 ]; then
  timeout "$TIMEOUT" "${RUN[@]}"
else
  "${RUN[@]}"
fi
```

## Route 1 — Agent: `.claude/agents/codex-reviewer.md`

**Frontmatter**:
```yaml
---
name: codex-reviewer
description: Use when you want a second-opinion code review from OpenAI Codex CLI. Complementary to the built-in code-reviewer agent — runs an independent model to surface issues Claude may have missed. Examples: "get a Codex second opinion on this auth refactor", "have Codex review the diff before I push".
tools: Bash, Read
model: sonnet
---
```

**Body specifies**:
- The agent is a thin wrapper: it makes **exactly one `codex exec` call per invocation** (no chaining, no retries from the Claude side). What happens *inside* the resulting Codex session is governed by Codex itself and the autonomous-scaling philosophy above — the wrapper does not constrain Codex's internal tool use.
- The agent passes the parent's review request through the common wrapper above.
- The agent returns Codex's output verbatim — no summarization, reinterpretation, or editorial commentary. Preserving the raw second-opinion is the point.
- If `codex` is missing, return the install hint and stop.

**Minimal review prompt**:
```
Review the following code change. Point out correctness issues, security concerns,
and clarity problems. Be concise — bullet points only, no preamble.

<diff or file contents>
```

## Route 2 — Slash command: `.claude/commands/codex-review.md`

**Frontmatter**:
```yaml
---
description: Get a Codex CLI second-opinion review of the current branch's changes
argument-hint: "[git-range]"
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git rev-parse:*), Bash(command -v codex), Bash(codex exec:*), Bash(timeout:*), Bash(env:*)
---
```

**Behavior**:
1. If `$1` is provided, use it as the git range. Otherwise default to `main...HEAD` (fall back to `master...HEAD` if `main` does not exist; error out if neither exists).
2. `command -v codex` — if missing, print install hint and exit.
3. `git diff <range>` — if empty, print "no changes" and exit.
4. If diff exceeds ~200KB, print a notice and proceed anyway (let the user decide).
5. Build the minimal review prompt with the diff embedded.
6. Invoke through the common wrapper.
7. Display Codex's output as-is. Do not follow up with edits or further reviews — single-shot by design.

## Route 3 — MCP server: `.claude/.mcp.json`

```json
{
  "mcpServers": {
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

- `CLAUDE_CODEX_DEPTH=1` initializes depth so Codex sub-invocations through the MCP route increment from 1 (Claude → Codex is already one level).
- Not added to `enabledMcpjsonServers` in the committed `settings.json` — opt-in only.

## Settings Changes

`.claude/settings.json` `permissions.allow` additions:

```json
"Bash(codex exec:*)",
"Bash(command -v codex)",
"Bash(timeout:*)"
```

`enabledMcpjsonServers` is **not** modified. Users who want the MCP route add `"codex"` to their own `settings.local.json`.

## Documentation

**README**: New section "Codex CLI Integration (Optional Reviewer)" covering:
- What it does (three routes summarized).
- Setup:
  1. `npm install -g @openai/codex`
  2. `codex login`
  3. (MCP only) Add `"codex"` to `enabledMcpjsonServers` in `settings.local.json`.
- When to use which route.
- Safety model: read-only sandbox, observability-first depth tracking, 30-minute default timeout.
- Tuning: `CLAUDE_CODEX_MAX_DEPTH`, `CLAUDE_CODEX_TIMEOUT`.

**CLAUDE.md**: Brief mention as an optional integration; pointer to the README section.

## File Changes (final)

**New**:
- `.claude/agents/codex-reviewer.md`
- `.claude/commands/codex-review.md`
- `docs/superpowers/specs/2026-05-01-codex-reviewer-design.md` (this file)

**Modified**:
- `.claude/.mcp.json` — add `codex` server entry
- `.claude/settings.json` — add three Bash permissions
- `README.md` — add integration section
- `CLAUDE.md` — short mention with pointer

## Acceptance Checks

1. `codex-reviewer` agent invoked with a diff returns Codex output verbatim.
2. `/codex-review` with no args reviews `main...HEAD`; with `<range>` arg uses the supplied range.
3. With `codex` uninstalled, both routes print the install hint cleanly.
4. With `CLAUDE_CODEX_MAX_DEPTH=1` and `CLAUDE_CODEX_DEPTH=1`, the wrapper refuses with a clear message.
5. With `CLAUDE_CODEX_TIMEOUT=1`, a long Codex call is killed by `timeout`.
6. MCP route: with `"codex"` not in `enabledMcpjsonServers`, the tool is not exposed; after adding it, the tool appears.
7. `--sandbox read-only` is present in every codex invocation (verified by `set -x` or trace).

## Out of Scope

- A code-modifying Codex agent (only reviewing this round).
- Sharing context/state between consecutive Codex calls.
- Tighter sandbox/PATH restrictions beyond `--sandbox read-only` (revisit if observed misuse).
- A dual-direction setup where Codex registers Claude as MCP — documentable in README but not configured here.
