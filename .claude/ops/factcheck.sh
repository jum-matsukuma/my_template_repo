#!/bin/bash
# Daily fact-check: catch documentation that has drifted from measured reality.
#
# Two layers, neither of which gets a blanket permission bypass:
#   1. a plain script that produces deterministic ground truth (leaderboard via
#      the Kaggle API, CV recomputed from your own artifacts) -- no model involved
#   2. a bounded headless agent scoped to read/search/edit ONLY, which compares
#      the claims in your docs against that ground truth and fixes the ones that
#      are unambiguously wrong
#
# The agent gets no Bash and no Task. It cannot run your training code, cannot
# submit, cannot spawn subagents, and cannot escalate its own permissions. git
# staging, commit and push happen here in the wrapper, where they are auditable.
#
# Why this job exists: experiment logs accumulate numbers that were true when
# written. Nothing re-checks them, and stale numbers are worse than no numbers
# because they get cited in decisions.
set -uo pipefail

# shellcheck source=/dev/null
source "${CONF:?run via run-daily.sh}"
cd "$REPO" || exit 1

OPS_DIR="${OPS_DIR:-$REPO/.claude/ops}"
PROMPT_FILE="$OPS_DIR/factcheck-prompt.md"
[ -f "$PROMPT_FILE" ] || { echo "[factcheck] missing $PROMPT_FILE"; exit 1; }

if ! command -v claude >/dev/null 2>&1; then
  echo "[factcheck] claude CLI not on PATH; skipping"
  exit 0
fi

# --- layer 1: deterministic ground truth ------------------------------------
if [ -f "scripts/factcheck_groundtruth.py" ]; then
  echo "[factcheck] building ground truth"
  python3 scripts/factcheck_groundtruth.py >/dev/null 2>&1 \
    || echo "[factcheck] groundtruth script warned (the agent will note it)"
else
  echo "[factcheck] no scripts/factcheck_groundtruth.py; running on primary sources only"
fi

# --- layer 2: scoped headless agent -----------------------------------------
echo "[factcheck] running headless agent (read/search/edit only; no Bash, no Task)"
claude -p "$(cat "$PROMPT_FILE")" \
  --permission-mode acceptEdits \
  --allowedTools Read Grep Glob WebSearch Edit Write \
  --disallowedTools Bash Task \
  --max-turns 45 \
  --add-dir "$REPO" 2>&1 | tail -25

# --- wrapper finalizes: the agent has no Bash by design ---------------------
FACTCHECK_PATHS="${FACTCHECK_PATHS:-.claude/skills docs}"
# shellcheck disable=SC2086
if ! git diff --quiet -- $FACTCHECK_PATHS 2>/dev/null \
   || [ -n "$(git ls-files --others --exclude-standard -- $FACTCHECK_PATHS 2>/dev/null)" ]; then
  # shellcheck disable=SC2086
  git add -A $FACTCHECK_PATHS 2>/dev/null
  git commit -q -m "chore(ops): daily fact-check $(date +%F) [launchd]" \
    && git push -q && echo "[factcheck] committed + pushed"
else
  echo "[factcheck] no changes to commit"
fi
