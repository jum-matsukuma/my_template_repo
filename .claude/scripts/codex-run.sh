#!/usr/bin/env bash
# Wrapper for invoking the Codex CLI from Claude Code with safety guardrails.
#
# Usage: codex-run.sh exec [codex-args...]
# Examples:
#   codex-run.sh exec "review this snippet: ..."
#   codex-run.sh exec review --base main
#
# Reviewer-role contract enforced here:
#   - Only `codex exec` is permitted; other subcommands (apply, sandbox,
#     mcp-server, login, …) are rejected. They reach more permissive
#     behavior than the reviewer role allows.
#   - `-s read-only` is forced; any caller-supplied -s/--sandbox is stripped
#     before our flag is inserted (clap rejects duplicates).
#   - `--dangerously-bypass-approvals-and-sandbox` is rejected.
#   - `-c sandbox_permissions=...` style config overrides are not filtered
#     (advanced bypass; out of scope for this wrapper).
#   For codex diagnostics like `codex --version`, call codex directly via
#   the separately allow-listed `Bash(codex --version)` permission.
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

if [ "${1:-}" != "exec" ]; then
  echo "codex-run.sh: only 'codex exec' is permitted via this wrapper (got: '${1:-<empty>}')." >&2
  echo "  This wrapper enforces the reviewer role (read-only sandbox)." >&2
  echo "  For codex diagnostics, run 'codex --version' directly." >&2
  exit 2
fi
shift

# Strip caller-supplied -s/--sandbox; reject the sandbox-bypass flag.
filtered=()
skip=0
for arg in "$@"; do
  if [ "$skip" -eq 1 ]; then
    skip=0
    continue
  fi
  case "$arg" in
    --dangerously-bypass-approvals-and-sandbox)
      echo "codex-run.sh: refusing --dangerously-bypass-approvals-and-sandbox." >&2
      exit 2
      ;;
    -s|--sandbox)
      skip=1
      ;;
    -s=*|--sandbox=*)
      ;;
    *)
      filtered+=("$arg")
      ;;
  esac
done

# Reassemble: codex exec -s read-only <filtered>
set -- exec -s read-only ${filtered[@]+"${filtered[@]}"}

export CLAUDE_CODEX_DEPTH=$((DEPTH + 1))

if [ "$TIMEOUT" -le 0 ]; then
  exec codex "$@"
fi

# Portable timeout: prefer GNU `timeout` (Linux / macOS+coreutils), then `gtimeout`
# (macOS Homebrew default name), then a Perl `alarm` fallback for plain macOS.
# On Perl fallback, SIGALRM kills the child with default disposition; exit code
# is 142 (128+SIGALRM=14) instead of GNU timeout's 124 — both signal "killed".
if command -v timeout >/dev/null 2>&1; then
  exec timeout "$TIMEOUT" codex "$@"
elif command -v gtimeout >/dev/null 2>&1; then
  exec gtimeout "$TIMEOUT" codex "$@"
elif command -v perl >/dev/null 2>&1; then
  exec perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" codex "$@"
else
  echo "warning: no timeout mechanism available (install coreutils for enforcement)." >&2
  exec codex "$@"
fi
