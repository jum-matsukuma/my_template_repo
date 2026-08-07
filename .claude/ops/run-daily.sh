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
  for j in research factcheck; do
    launchctl bootout "gui/$UID_N/com.${PREFIX}.${j}" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/com.${PREFIX}.${j}.plist"
  done
  echo "uninstalled."
  exit 0
fi

# --- overlap guard (mkdir is atomic on every filesystem we care about) ------
LOCKDIR="$OPS_DIR/locks/${JOB}.lockdir"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  if [ -n "$(find "$LOCKDIR" -maxdepth 0 -mmin +180 2>/dev/null)" ]; then
    echo "stale lock (>3h) - reclaiming"
    rmdir "$LOCKDIR" 2>/dev/null
    mkdir "$LOCKDIR" 2>/dev/null || { echo "lock race; skip"; exit 0; }
  else
    echo "another $JOB run holds the lock; skip"
    exit 0
  fi
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

cd "$REPO" || { echo "cd $REPO failed"; exit 1; }

# --- sync in: absorb what other sessions and jobs have pushed ---------------
git pull --rebase --autostash 2>&1 | tail -3 || echo "git pull warning (continuing)"

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

echo "$TODAY" > "$STATE"
echo "=== $JOB end rc=$RC $(date '+%F %T') ==="
exit "$RC"
