#!/bin/bash
# Daily research diff fetch, then open (or extend) a draft PR with the diff.
#
# Invoked by run-daily.sh, which has already sourced ops.conf, taken the lock,
# and pulled. Runs as a pure script -- no agent. Judgement calls stay out of the
# unattended path; the job's job is to make a change reviewable, not to decide
# what it means.
#
# ORDER MATTERS: the target branch is checked out BEFORE the fetcher runs.
# Fetching first leaves manifest.json modified in the working tree, and git
# then refuses to switch branches ("local changes would be overwritten"), so
# every run after the first would fail to reach its own PR.
set -uo pipefail

# shellcheck source=/dev/null
source "${CONF:?run via run-daily.sh}"

: "${REPO:?ops.conf must set REPO}"
: "${COMP:?ops.conf must set COMP}"
: "${PREFIX:?ops.conf must set PREFIX}"
OUT_DIR="${OUT_DIR:-research}"
FETCH_ARGS="${FETCH_ARGS:-}"
COMMIT_PATHS="${COMMIT_PATHS:-$OUT_DIR/discussions $OUT_DIR/writeups $OUT_DIR/manifest.json}"

# ops.conf is *sourced*, which only creates shell variables. The fetcher reads
# this from the environment, so without an explicit export a key set in
# ops.conf would silently do nothing.
[ -n "${JINA_API_KEY:-}" ] && export JINA_API_KEY

cd "$REPO" || exit 1

FETCHER="scripts/kaggle_research.py"
[ -f "$FETCHER" ] || FETCHER="kaggle-template/scripts/kaggle_research.py"
[ -f "$FETCHER" ] || { echo "[research] no kaggle_research.py found under $REPO"; exit 1; }

SUMMARY="$(mktemp)"

# --- refuse to run on a repo that is not in a clean, known state ------------
if [ -n "$(git status --porcelain -- $COMMIT_PATHS 2>/dev/null)" ]; then
  echo "[research] $COMMIT_PATHS already has uncommitted changes; refusing to run"
  echo "           (commit or discard them, then re-run)"
  rm -f "$SUMMARY"; exit 1
fi

ORIG_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$ORIG_BRANCH" = "HEAD" ]; then
  echo "[research] repo is in detached HEAD (interrupted rebase?); refusing to run"
  rm -f "$SUMMARY"; exit 1
fi

# --- pick a branch: extend an open ops PR, else start today's ---------------
DATE="$(date +%F)"
# PREFIX keeps two competitions sharing one repo from landing on the same
# branch and mixing their diffs into one PR.
BRANCH="ops/research-${PREFIX}-$DATE"
BASE="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
BASE="${BASE:-main}"

EXISTING=""
if command -v gh >/dev/null 2>&1; then
  EXISTING="$(gh pr list --state open --limit 100 --json headRefName \
                --jq "[.[].headRefName | select(startswith(\"ops/research-${PREFIX}-\"))][0] // empty" \
                2>/dev/null || true)"
fi
[ -n "$EXISTING" ] && BRANCH="$EXISTING"

CREATED_BRANCH=0
restore_branch() {
  local rc=$?
  if [ "$(git rev-parse --abbrev-ref HEAD)" != "$ORIG_BRANCH" ]; then
    git checkout -q "$ORIG_BRANCH" 2>/dev/null && echo "[research] restored branch $ORIG_BRANCH"
    # A branch we created but never committed to is pure litter.
    if [ "$CREATED_BRANCH" = "1" ] && \
       [ -z "$(git rev-list "origin/$BASE..$BRANCH" 2>/dev/null)" ]; then
      git branch -q -D "$BRANCH" 2>/dev/null && echo "[research] removed empty $BRANCH"
    fi
  fi
  rm -f "$SUMMARY"
  exit "$rc"
}
trap restore_branch EXIT

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout -q "$BRANCH" || exit 1
elif git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  git checkout -q -b "$BRANCH" "origin/$BRANCH" || exit 1
  CREATED_BRANCH=1
else
  git checkout -q -b "$BRANCH" "origin/$BASE" 2>/dev/null \
    || git checkout -q -b "$BRANCH" || exit 1
  CREATED_BRANCH=1
fi

# --- fetch, now that we are on the branch the results belong on ------------
echo "[research] running $FETCHER for $COMP on $BRANCH"
# shellcheck disable=SC2086
python3 "$FETCHER" --comp "$COMP" --out "$OUT_DIR" $FETCH_ARGS 2>&1 | tee "$SUMMARY" | tail -25
FETCH_RC=${PIPESTATUS[0]}

# --- is there anything to commit? ------------------------------------------
CHANGED=0
# shellcheck disable=SC2086
git diff --quiet HEAD -- $COMMIT_PATHS 2>/dev/null || CHANGED=1
# shellcheck disable=SC2086
[ -n "$(git ls-files --others --exclude-standard -- $COMMIT_PATHS 2>/dev/null)" ] && CHANGED=1

if [ "$CHANGED" = "0" ]; then
  echo "[research] no diff today ($DATE); no PR opened"
  exit "$FETCH_RC"
fi

# shellcheck disable=SC2086
# A bare `git commit` commits the WHOLE INDEX, not the paths staged above. If a
# concurrent interactive session left anything staged, an unattended run adopts
# it -- observed in the wild: a nightly job authored 2 files and committed 1073,
# sweeping in another session's work under a message that described neither.
# The pathspec makes the commit contain exactly what this job produced.
git add $COMMIT_PATHS 2>/dev/null
# shellcheck disable=SC2086
git commit -q -m "chore(research): $COMP daily fetch $DATE [launchd]" \
  -- $COMMIT_PATHS || {
  echo "[research] nothing staged"
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
