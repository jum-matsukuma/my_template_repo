#!/bin/bash
# Generic daily ops runner, started by a macOS LaunchAgent.
#
#   run-daily.sh <job>        # job = research | factcheck | <your own>
#
# Why launchd rather than an in-session scheduler: launchd is one-per-machine,
# so concurrent Claude Code sessions cannot double-run the job, and the schedule
# survives session restarts. Session-scoped schedulers expire (7 days) and
# duplicate across sessions; both failure modes are silent.
#
# The session holds no schedule at all. Jobs publish results through git and
# sessions pick them up with a pull.
set -uo pipefail

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$OPS_DIR/ops.conf"
[ -f "$CONF" ] || { echo "missing $CONF (copy ops.conf.example)"; exit 1; }
# shellcheck source=/dev/null
source "$CONF"
# shellcheck source=/dev/null
source "$OPS_DIR/jobs.def"

# Required, and validated here rather than failing obscurely later under `set -u`.
: "${REPO:?ops.conf must set REPO}"
: "${PREFIX:?ops.conf must set PREFIX}"
STOP_DATE="${STOP_DATE:-2099-12-31}"

export HOME="${HOME:-$(eval echo "~$(id -un)")}"
# launchd hands us a minimal PATH; name the tool locations explicitly.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
UID_N="$(id -u)"

JOB="${1:-}"
[ -n "$JOB" ] || { echo "usage: run-daily.sh <job>"; exit 1; }

mkdir -p "$OPS_DIR/logs" "$OPS_DIR/locks"
LOG="$OPS_DIR/logs/${JOB}-$(date +%Y%m%d-%H%M%S).log"
exec >>"$LOG" 2>&1
echo "=== $JOB start $(date '+%F %T %Z') ==="

# --- auto-stop: uninstall once past STOP_DATE -------------------------------
TODAY="$(date +%Y-%m-%d)"
if [[ "$TODAY" > "$STOP_DATE" ]]; then
  echo "past STOP_DATE ($STOP_DATE) - self-uninstalling LaunchAgents"
  while IFS= read -r j; do
    launchctl bootout "gui/$UID_N/com.${PREFIX}.${j}" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/com.${PREFIX}.${j}.plist"
  done < <(ops_job_names)
  echo "uninstalled."
  exit 0
fi

# --- overlap guard (mkdir is atomic on every filesystem we care about) ------
#
# Liveness is decided by the recorded PID, not by mtime alone. A --full re-pull
# or a Jina rate-limit backoff can legitimately run past any fixed age cutoff,
# and stealing the lock from a job that is still working means two runs do
# checkout/commit/push concurrently in one working tree.
LOCKDIR="$OPS_DIR/locks/${JOB}.lockdir"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  HOLDER="$(cat "$LOCKDIR/pid" 2>/dev/null || echo "")"
  if [ -n "$HOLDER" ] && kill -0 "$HOLDER" 2>/dev/null; then
    echo "another $JOB run (pid $HOLDER) is alive; skip"
    exit 0
  fi
  echo "lock held by dead/unknown pid '${HOLDER:-none}' - reclaiming"
  rm -rf "$LOCKDIR"
  mkdir "$LOCKDIR" 2>/dev/null || { echo "lock race; skip"; exit 0; }
fi
echo "$$" > "$LOCKDIR/pid"
trap 'rm -rf "$LOCKDIR"' EXIT

cd "$REPO" || { echo "cd $REPO failed"; exit 1; }

# --- refuse to operate on a repo left mid-rebase ----------------------------
# Continuing here would run the job on a detached HEAD, which makes the child
# script's "restore the original branch" logic restore to the literal "HEAD".
GITDIR="$(git rev-parse --git-dir 2>/dev/null || echo .git)"
if [ -d "$GITDIR/rebase-merge" ] || [ -d "$GITDIR/rebase-apply" ]; then
  echo "repo has a rebase in progress - refusing to run (resolve it by hand)"
  exit 1
fi

# --- sync in: absorb what other sessions and jobs have pushed ---------------
# A failed pull must stop the run. Carrying on would operate on a conflicted or
# detached tree, and the failure would compound silently every night after.
PULL_LOG="$(mktemp)"
if ! git pull --rebase --autostash >"$PULL_LOG" 2>&1; then
  tail -5 "$PULL_LOG"
  echo "git pull failed - aborting run and leaving the repo untouched"
  git rebase --abort 2>/dev/null || true
  rm -f "$PULL_LOG"
  exit 1
fi
tail -3 "$PULL_LOG"; rm -f "$PULL_LOG"

# --- per-day dedup (machine-local; launchd is one per machine) --------------
STATE="$OPS_DIR/.state-${JOB}"
if [[ "$(cat "$STATE" 2>/dev/null)" == "$TODAY" ]]; then
  echo "$JOB already completed today ($TODAY); skip"
  exit 0
fi

JOB_SCRIPT="$OPS_DIR/${JOB}.sh"
[ -x "$JOB_SCRIPT" ] || [ -f "$JOB_SCRIPT" ] || { echo "unknown job '$JOB' (no $JOB_SCRIPT)"; exit 1; }

OPS_DIR="$OPS_DIR" CONF="$CONF" bash "$JOB_SCRIPT"
RC=$?

# Only a successful run counts as "done today". Stamping unconditionally means
# one bad night (auth expiry, network blip) silently skips that day's fetch for
# good, because every retry short-circuits on the dedup check.
if [ "$RC" -eq 0 ]; then
  echo "$TODAY" > "$STATE"
else
  echo "rc=$RC - not marking $TODAY complete, so a retry today can still run"
fi
echo "=== $JOB end rc=$RC $(date '+%F %T') ==="
exit "$RC"
