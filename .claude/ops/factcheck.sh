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

: "${REPO:?ops.conf must set REPO}"
: "${PREFIX:?ops.conf must set PREFIX}"
cd "$REPO" || exit 1

OPS_DIR="${OPS_DIR:-$REPO/.claude/ops}"
PROMPT_FILE="$OPS_DIR/factcheck-prompt.md"
[ -f "$PROMPT_FILE" ] || { echo "[factcheck] missing $PROMPT_FILE"; exit 1; }

if ! command -v claude >/dev/null 2>&1; then
  echo "[factcheck] claude CLI not on PATH; skipping"
  exit 0
fi

# --- branch FIRST, then let the agent edit ---------------------------------
#
# Order matters, for two reasons:
#   * `git checkout -b X` with no start point branches from whatever is checked
#     out. Overnight that is often a developer's feature branch, and the
#     resulting PR against $BASE would carry all of their WIP commits.
#   * If the tree is already dirty under FACTCHECK_PATHS, a later `git add -A`
#     cannot tell the agent's edits from the human's and commits both.
# Verifying cleanliness up front and moving to the ops branch before the agent
# runs makes everything staged afterwards unambiguously the agent's work.
FACTCHECK_PATHS="${FACTCHECK_PATHS:-.claude/skills docs}"

# shellcheck disable=SC2086
if [ -n "$(git status --porcelain -- $FACTCHECK_PATHS 2>/dev/null)" ]; then
  echo "[factcheck] $FACTCHECK_PATHS already has uncommitted changes; refusing to run"
  echo "            (an unattended commit here would sweep in your work)"
  exit 1
fi

ORIG_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$ORIG_BRANCH" = "HEAD" ]; then
  echo "[factcheck] detached HEAD (interrupted rebase?); refusing to run"
  exit 1
fi

DATE="$(date +%F)"
BRANCH="ops/factcheck-${PREFIX}-$DATE"
BASE="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
BASE="${BASE:-main}"

restore() {
  local rc=$?
  [ "$(git rev-parse --abbrev-ref HEAD)" != "$ORIG_BRANCH" ] \
    && git checkout -q "$ORIG_BRANCH" 2>/dev/null \
    && echo "[factcheck] restored branch $ORIG_BRANCH"
  exit "$rc"
}
trap restore EXIT

# The PR targets $BASE, so the content being fact-checked must be $BASE -- not
# whatever half-finished state a feature branch happens to be in.
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout -q "$BRANCH" || exit 1
elif git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  git checkout -q -b "$BRANCH" "origin/$BRANCH" || exit 1
else
  git checkout -q -b "$BRANCH" "origin/$BASE" 2>/dev/null \
    || { echo "[factcheck] cannot branch from origin/$BASE"; exit 1; }
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
# We are already on the ops branch and the tree was clean before the agent ran,
# so anything staged now is the agent's doing.
# shellcheck disable=SC2086
if git diff --quiet HEAD -- $FACTCHECK_PATHS 2>/dev/null \
   && [ -z "$(git ls-files --others --exclude-standard -- $FACTCHECK_PATHS 2>/dev/null)" ]; then
  echo "[factcheck] no changes to commit"
  exit 0
fi

# shellcheck disable=SC2086
# A bare `git commit` commits the WHOLE INDEX, not the paths staged above. If a
# concurrent interactive session left anything staged, an unattended run adopts
# it -- observed in the wild: a nightly job authored 2 files and committed 1073,
# sweeping in another session's work under a message that described neither.
# The pathspec makes the commit contain exactly what this job produced.
git add -A $FACTCHECK_PATHS 2>/dev/null
# shellcheck disable=SC2086
if ! git commit -q -m "chore(ops): daily fact-check $DATE [launchd]" \
     -- $FACTCHECK_PATHS; then
  echo "[factcheck] nothing staged"
  exit 0
fi

# A local-only commit is not a delivered result: fail so run-daily.sh does not
# mark the day complete and a retry can still run.
if ! git push -q -u origin "$BRANCH"; then
  echo "[factcheck] push failed (commit is local on $BRANCH)"
  exit 1
fi
echo "[factcheck] pushed to $BRANCH"

if command -v gh >/dev/null 2>&1 && ! gh pr view "$BRANCH" >/dev/null 2>&1; then
  gh pr create --draft --base "$BASE" \
    --title "chore(ops): fact-check $DATE" \
    --body "無人のファクトチェックが記述の誤りを修正した差分。\`REVIEW NEEDED\` と記録された項目は人間の判断待ち。" \
    >/dev/null 2>&1 && echo "[factcheck] draft PR opened"
fi
