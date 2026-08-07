#!/bin/bash
# Daily research diff fetch, then open (or extend) a draft PR with the diff.
#
# Invoked by run-daily.sh, which has already sourced ops.conf, taken the lock,
# and pulled. Runs as a pure script -- no agent. Judgement calls stay out of the
# unattended path; the job's job is to make a change reviewable, not to decide
# what it means.
set -uo pipefail

# shellcheck source=/dev/null
source "${CONF:?run via run-daily.sh}"
cd "$REPO" || exit 1

SUMMARY="$(mktemp)"
trap 'rm -f "$SUMMARY"' EXIT

FETCHER="scripts/kaggle_research.py"
[ -f "$FETCHER" ] || FETCHER="kaggle-template/scripts/kaggle_research.py"
[ -f "$FETCHER" ] || { echo "[research] no kaggle_research.py found under $REPO"; exit 1; }

echo "[research] running $FETCHER for $COMP"
# shellcheck disable=SC2086
python3 "$FETCHER" --comp "$COMP" --out "$OUT_DIR" $FETCH_ARGS 2>&1 | tee "$SUMMARY" | tail -25
FETCH_RC=${PIPESTATUS[0]}

# --- is there anything to commit? ------------------------------------------
CHANGED=0
# shellcheck disable=SC2086
git diff --quiet -- $COMMIT_PATHS 2>/dev/null || CHANGED=1
# shellcheck disable=SC2086
[ -n "$(git ls-files --others --exclude-standard -- $COMMIT_PATHS 2>/dev/null)" ] && CHANGED=1

if [ "$CHANGED" = "0" ]; then
  echo "[research] no diff today ($(date +%F)); no PR opened"
  exit "$FETCH_RC"
fi

# --- pick a branch: extend today's/an open one, else start a new one --------
DATE="$(date +%F)"
BRANCH="ops/research-$DATE"
BASE="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
BASE="${BASE:-main}"

EXISTING=""
if command -v gh >/dev/null 2>&1; then
  # Reuse an already-open ops PR so a week of runs is one reviewable thread
  # rather than seven abandoned ones.
  EXISTING="$(gh pr list --state open --limit 100 --json headRefName \
                --jq '[.[].headRefName | select(startswith("ops/research-"))][0] // empty' \
                2>/dev/null || true)"
fi
[ -n "$EXISTING" ] && BRANCH="$EXISTING"

ORIG_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
# Whatever happens from here on -- push rejected, gh missing, network gone --
# the repository must end up back on the branch we found it on. Leaving a
# user's checkout parked on an ops branch corrupts the next run's pull and is
# baffling to walk into in the morning.
restore_branch() {
  local rc=$?
  [ "$(git rev-parse --abbrev-ref HEAD)" != "$ORIG_BRANCH" ] \
    && git checkout -q "$ORIG_BRANCH" 2>/dev/null \
    && echo "[research] restored branch $ORIG_BRANCH"
  rm -f "$SUMMARY"
  exit "$rc"
}
trap restore_branch EXIT

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout -q "$BRANCH" || exit 1
elif git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  git checkout -q -b "$BRANCH" "origin/$BRANCH" || exit 1
else
  git checkout -q -b "$BRANCH" "origin/$BASE" 2>/dev/null \
    || git checkout -q -b "$BRANCH" || exit 1
fi

# shellcheck disable=SC2086
git add $COMMIT_PATHS 2>/dev/null
git commit -q -m "chore(research): $COMP daily fetch $DATE [launchd]" || {
  echo "[research] nothing staged after checkout"
  exit "$FETCH_RC"
}
git push -q -u origin "$BRANCH" || { echo "[research] push failed (commit is local)"; exit 1; }
echo "[research] pushed to $BRANCH"

# --- open a draft PR the first time this branch is pushed -------------------
if command -v gh >/dev/null 2>&1; then
  if ! gh pr view "$BRANCH" >/dev/null 2>&1; then
    BODY="$(mktemp)"
    {
      echo "Unattended daily research fetch for \`$COMP\`."
      echo
      echo "Opened by \`.claude/ops/research.sh\` via launchd. Each day's diff is"
      echo "appended to this branch, so review it as a running log rather than a"
      echo "single change. **Read the warnings section**: a count mismatch means"
      echo "the fetcher retrieved fewer comments than Kaggle claims exist, which"
      echo "is how a silent under-fetch announces itself."
      echo
      echo '```'
      tail -30 "$SUMMARY"
      echo '```'
    } > "$BODY"
    gh pr create --draft --base "$BASE" \
      --title "chore(research): $COMP daily fetch" --body-file "$BODY" \
      >/dev/null 2>&1 && echo "[research] draft PR opened" \
      || echo "[research] gh pr create failed (branch is pushed; open it by hand)"
    rm -f "$BODY"
  else
    gh pr comment "$BRANCH" --body "$(printf '%s\n\n```\n%s\n```\n' \
      "Daily fetch $DATE" "$(tail -25 "$SUMMARY")")" >/dev/null 2>&1 \
      && echo "[research] appended run summary to existing PR"
  fi
else
  echo "[research] gh not installed; branch pushed but no PR opened"
fi

# The EXIT trap restores the original branch.
exit "$FETCH_RC"
