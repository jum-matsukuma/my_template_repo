#!/bin/bash
# Register the daily jobs as macOS LaunchAgents.
#
#   ./install.sh                 # install every job named in JOBS below
#   ./install.sh research        # install just one
#
# Idempotent: re-running replaces the existing agents.
set -euo pipefail

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$OPS_DIR/ops.conf"
[ -f "$CONF" ] || { echo "missing $CONF -- copy ops.conf.example and fill it in"; exit 1; }
# shellcheck source=/dev/null
source "$CONF"

[ -d "$REPO" ] || { echo "REPO does not exist: $REPO"; exit 1; }
[ "$PREFIX" != "mycomp" ] || echo "warning: PREFIX is still the example value 'mycomp'"

UID_N="$(id -u)"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS" "$OPS_DIR/logs"

# job:hour:minute -- stagger jobs so they never contend for the same lock.
JOBS=("research:3:3" "factcheck:5:5")
WANTED=("$@")

for spec in "${JOBS[@]}"; do
  JOB="${spec%%:*}"; rest="${spec#*:}"; HOUR="${rest%%:*}"; MIN="${rest##*:}"
  if [ ${#WANTED[@]} -gt 0 ] && [[ ! " ${WANTED[*]} " =~ [[:space:]]${JOB}[[:space:]] ]]; then
    continue
  fi
  [ -f "$OPS_DIR/${JOB}.sh" ] || { echo "skip $JOB (no ${JOB}.sh)"; continue; }

  LABEL="com.${PREFIX}.${JOB}"
  PLIST="$AGENTS/${LABEL}.plist"
  sed -e "s|@@LABEL@@|${LABEL}|g" \
      -e "s|@@OPS_DIR@@|${OPS_DIR}|g" \
      -e "s|@@JOB@@|${JOB}|g" \
      -e "s|@@HOUR@@|${HOUR}|g" \
      -e "s|@@MINUTE@@|${MIN}|g" \
      "$OPS_DIR/launchagents/job.plist.template" > "$PLIST"

  launchctl bootout "gui/${UID_N}/${LABEL}" 2>/dev/null || true
  launchctl bootstrap "gui/${UID_N}" "$PLIST"
  echo "installed ${LABEL} (daily ${HOUR}:$(printf '%02d' "$MIN"))"
done

echo
echo "verify with: launchctl list | grep ${PREFIX}"
echo "logs:        $OPS_DIR/logs/"
echo
echo "note: LaunchAgents only fire while the user is logged in -- they need"
echo "      keychain access for the Kaggle and GitHub credentials."
