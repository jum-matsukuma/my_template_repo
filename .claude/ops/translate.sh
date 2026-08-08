#!/bin/bash
# Daily Japanese translation layer for the fetched research corpus.
#
# Two layers, same shape as factcheck.sh:
#   1. a plain script (research_ja.py prep) that renders the selected threads to
#      markdown, downloads their figures, and glues the reply thread onto the end
#      of the body -- no model involved
#   2. a bounded headless agent, invoked ONCE PER DOCUMENT, that translates one
#      English file into one Japanese file and nothing else
#
# One agent per document rather than one agent for the batch: a translation run
# that dies at document 30 of 48 should keep the 29 finished translations, and a
# per-document turn budget is the only bound that actually holds -- a single
# agent asked to translate a batch will silently start summarizing when it runs
# low on turns, which is the one failure this whole job exists to avoid.
#
# WHY THE JAPANESE SIDE IS SEGREGATED: a translation is a lossy derivative. An
# agent that cites it inherits a translator's paraphrase instead of what the
# author wrote, and nothing downstream announces the substitution. So agents
# read research/rendered/ (English), humans read docs/research-ja/ (Japanese),
# and .claude/settings.json denies Read on the latter to make it mechanical
# rather than a convention people remember.
set -uo pipefail

# shellcheck source=/dev/null
source "${CONF:?run via run-daily.sh}"

: "${REPO:?ops.conf must set REPO}"
: "${COMP:?ops.conf must set COMP}"
: "${PREFIX:?ops.conf must set PREFIX}"
cd "$REPO" || exit 1

# Opt-in: this is the only daily job that spends model tokens per document.
if [ "${TRANSLATE_ENABLED:-0}" != "1" ]; then
  echo "[translate] TRANSLATE_ENABLED is not 1 in ops.conf; nothing to do"
  exit 0
fi

OUT_DIR="${OUT_DIR:-research}"
JA_DIR="${JA_DIR:-docs/research-ja}"
TRANSLATE_ARGS="${TRANSLATE_ARGS:-}"
MAX_PER_RUN="${TRANSLATE_MAX_PER_RUN:-5}"
PREP_LIMIT="${TRANSLATE_PREP_LIMIT:-40}"
TRANSLATE_PATHS="${TRANSLATE_PATHS:-$JA_DIR $OUT_DIR/rendered $OUT_DIR/assets $OUT_DIR/translate_manifest.json}"
OPS_DIR="${OPS_DIR:-$REPO/.claude/ops}"
PROMPT_FILE="$OPS_DIR/translate-prompt.md"

[ -f "$PROMPT_FILE" ] || { echo "[translate] missing $PROMPT_FILE"; exit 1; }
[ -n "${JINA_API_KEY:-}" ] && export JINA_API_KEY

TOOL="scripts/research_ja.py"
[ -f "$TOOL" ] || TOOL="kaggle-template/scripts/research_ja.py"
[ -f "$TOOL" ] || { echo "[translate] no research_ja.py found under $REPO"; exit 1; }

if ! command -v claude >/dev/null 2>&1; then
  echo "[translate] claude CLI not on PATH; skipping"
  exit 0
fi

# --- branch FIRST, then render and translate -------------------------------
# Same reasoning as factcheck.sh: `git checkout -b X` with no start point
# branches from whatever is checked out, which overnight is often somebody's
# feature branch, and a dirty tree makes `git add` unable to tell the job's
# output from a human's work in progress.
# shellcheck disable=SC2086
if [ -n "$(git status --porcelain -- $TRANSLATE_PATHS 2>/dev/null)" ]; then
  echo "[translate] $TRANSLATE_PATHS already has uncommitted changes; refusing to run"
  exit 1
fi

ORIG_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$ORIG_BRANCH" = "HEAD" ]; then
  echo "[translate] detached HEAD (interrupted rebase?); refusing to run"
  exit 1
fi

DATE="$(date +%F)"
BASE="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
BASE="${BASE:-main}"
BRANCH="ops/translate-${PREFIX}-$DATE"

# A week of daily translations belongs in one reviewable thread, not seven
# abandoned PRs -- so extend an open one if it exists.
EXISTING=""
if command -v gh >/dev/null 2>&1; then
  EXISTING="$(gh pr list --state open --limit 100 --json headRefName \
                --jq "[.[].headRefName | select(startswith(\"ops/translate-${PREFIX}-\"))][0] // empty" \
                2>/dev/null || true)"
fi
[ -n "$EXISTING" ] && BRANCH="$EXISTING"

CREATED_BRANCH=0
restore_branch() {
  local rc=$?
  if [ "$(git rev-parse --abbrev-ref HEAD)" != "$ORIG_BRANCH" ]; then
    git checkout -q "$ORIG_BRANCH" 2>/dev/null && echo "[translate] restored branch $ORIG_BRANCH"
    if [ "$CREATED_BRANCH" = "1" ] && \
       [ -z "$(git rev-list "origin/$BASE..$BRANCH" 2>/dev/null)" ]; then
      git branch -q -D "$BRANCH" 2>/dev/null && echo "[translate] removed empty $BRANCH"
    fi
  fi
  exit "$rc"
}
trap restore_branch EXIT

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout -q "$BRANCH" || exit 1
elif git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  git checkout -q -b "$BRANCH" "origin/$BRANCH" || exit 1
  CREATED_BRANCH=1
else
  git checkout -q -b "$BRANCH" "origin/$BASE" 2>/dev/null || git checkout -q -b "$BRANCH" || exit 1
  CREATED_BRANCH=1
fi

# --- layer 1: deterministic render (body + figures + comment thread) --------
echo "[translate] rendering translatable sources"
# shellcheck disable=SC2086
python3 "$TOOL" prep --comp "$COMP" --out "$OUT_DIR" --docs "$JA_DIR" \
  --limit "$PREP_LIMIT" $TRANSLATE_ARGS 2>&1 | tail -20
# Kept so the run does not report success after a render that partly failed;
# run-daily.sh only stamps the day complete on rc=0, so a retry can still run.
PREP_RC=${PIPESTATUS[0]}

PENDING="$(python3 "$TOOL" pending --out "$OUT_DIR" --docs "$JA_DIR" \
             --porcelain --limit "$MAX_PER_RUN" 2>/dev/null)"

if [ -z "$PENDING" ]; then
  echo "[translate] every rendered document already has a current translation"
else
  # --- layer 2: one bounded agent per document ------------------------------
  # No Bash and no Task: it reads one English file and writes one Japanese file.
  # Read on $JA_DIR is denied repo-wide, so an existing translation is removed
  # first -- Write refuses to overwrite a file the agent has not read, and the
  # agent is not allowed to read this one.
  mkdir -p "$JA_DIR"
  N=0
  while IFS=$'\t' read -r KEY SRC DEST; do
    [ -n "$KEY" ] || continue
    N=$((N + 1))
    echo "[translate] ($N) $KEY"
    rm -f "$DEST"
    PROMPT="$(sed -e "s|@@SRC@@|$SRC|g" -e "s|@@DEST@@|$DEST|g" "$PROMPT_FILE")"
    claude -p "$PROMPT" \
      --permission-mode acceptEdits \
      --allowedTools Read Grep Glob Write \
      --disallowedTools Bash Task WebSearch WebFetch \
      --max-turns 30 \
      --add-dir "$REPO" </dev/null 2>&1 | tail -5
    # </dev/null matters: without it the agent inherits the here-string feeding
    # this while-loop, consumes the remaining pending lines as its own stdin,
    # and the loop silently translates exactly one document per run.
    if [ -s "$DEST" ]; then
      python3 "$TOOL" mark --out "$OUT_DIR" --key "$KEY" >/dev/null
      echo "[translate]     wrote $DEST"
    else
      echo "[translate]     FAILED: $DEST was not written (will retry next run)"
    fi
  done <<< "$PENDING"
fi

# --- index + optional HTML export ------------------------------------------
python3 "$TOOL" index --comp "$COMP" --out "$OUT_DIR" --docs "$JA_DIR" 2>&1 | tail -3

HTML_DIR="${TRANSLATE_HTML_DIR:-$HOME/Downloads/${PREFIX}-research-ja}"
if [ "${TRANSLATE_HTML:-1}" = "1" ]; then
  python3 "$TOOL" html --out "$OUT_DIR" --docs "$JA_DIR" --dest "$HTML_DIR" 2>&1 | tail -2
fi

# --- commit; the agent has no Bash by design -------------------------------
# `git diff` alone compares the worktree to the INDEX, so work this job already
# staged reads as "no changes" and never gets committed. Compare against HEAD.
# shellcheck disable=SC2086
if git diff --quiet HEAD -- $TRANSLATE_PATHS 2>/dev/null \
   && [ -z "$(git ls-files --others --exclude-standard -- $TRANSLATE_PATHS 2>/dev/null)" ]; then
  echo "[translate] no changes to commit"
  exit "$PREP_RC"
fi

# A bare `git commit` commits the WHOLE INDEX, not the paths staged above. If a
# concurrent interactive session left anything staged, an unattended run adopts
# it -- observed in the wild: a nightly job authored 2 files and committed 1073,
# sweeping in another session's work under a message that described neither.
# The pathspec makes the commit contain exactly what this job produced.
# shellcheck disable=SC2086
git add -A $TRANSLATE_PATHS 2>/dev/null
# shellcheck disable=SC2086
if ! git commit -q -m "docs(research-ja): daily translation $DATE [launchd]" \
     -- $TRANSLATE_PATHS; then
  echo "[translate] nothing staged"
  exit "$PREP_RC"
fi

if ! git push -q -u origin "$BRANCH"; then
  echo "[translate] push failed (commit is local on $BRANCH)"
  exit 1
fi
echo "[translate] pushed to $BRANCH"

STATUS="$(python3 "$TOOL" pending --out "$OUT_DIR" --docs "$JA_DIR" 2>&1 | head -12)"
if command -v gh >/dev/null 2>&1; then
  if ! gh pr view "$BRANCH" >/dev/null 2>&1; then
    gh pr create --draft --base "$BASE" \
      --title "docs(research-ja): $COMP 日本語訳" \
      --body "$(printf '%s\n\n```\n%s\n```\n' \
"公開ディスカッション/解法 writeup の**日本語訳（図つき）**。\`.claude/ops/translate.sh\` が日次で追記する。

- 索引: \`$JA_DIR/README.md\`（ブラウザ版は \`$HTML_DIR/index.html\`）
- **この訳文は人間の読者専用**。エージェントが読むのは英語原文 \`$OUT_DIR/rendered/*.md\` の方で、
  \`.claude/settings.json\` の \`permissions.deny\` が Read をブロックしている。
- 図は \`$OUT_DIR/assets/<key>/\` に保存し、原文と訳文の両方から相対パスで参照している。
- 返信スレッドは各本文の末尾に「コメント欄」として連結済み。

翻訳は他者の著作物の派生物。引用時は原文リンクと著者名を必ず併記すること。" "$STATUS")" \
      >/dev/null 2>&1 && echo "[translate] draft PR opened" \
      || echo "[translate] gh pr create failed (branch is pushed; open it by hand)"
  else
    gh pr comment "$BRANCH" --body "$(printf '%s\n\n```\n%s\n```\n' \
      "翻訳 $DATE" "$STATUS")" >/dev/null 2>&1 \
      && echo "[translate] appended status to existing PR"
  fi
fi

# A render that failed part way must not mark the day complete, or the retry
# never runs and the gap is invisible.
exit "$PREP_RC"
