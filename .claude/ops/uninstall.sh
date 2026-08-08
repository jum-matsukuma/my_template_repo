#!/bin/bash
# Remove the daily LaunchAgents and the local runtime state.
#
#   ./uninstall.sh              # remove every job
#   ./uninstall.sh research     # remove one
#
# Run this the moment a competition ends. A scheduled job whose competition is
# over keeps fetching, keeps opening PRs, and keeps looking like it means
# something.
set -uo pipefail

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$OPS_DIR/ops.conf"
[ -f "$CONF" ] || { echo "missing $CONF"; exit 1; }
# shellcheck source=/dev/null
source "$CONF"

UID_N="$(id -u)"
AGENTS="$HOME/Library/LaunchAgents"
# shellcheck source=/dev/null
source "$OPS_DIR/jobs.def"
JOBS=()
while IFS= read -r j; do JOBS+=("$j"); done < <(ops_job_names)
[ $# -gt 0 ] && JOBS=("$@")

for JOB in "${JOBS[@]}"; do
  LABEL="com.${PREFIX}.${JOB}"
  launchctl bootout "gui/${UID_N}/${LABEL}" 2>/dev/null && echo "booted out ${LABEL}" \
    || echo "${LABEL} was not loaded"
  rm -f "$AGENTS/${LABEL}.plist"
  rm -f "$OPS_DIR/.state-${JOB}"
  rm -rf "$OPS_DIR/locks/${JOB}.lockdir"
done

echo
echo "remaining agents for this prefix:"
launchctl list | grep "${PREFIX}" || echo "  (none -- this is the expected end state)"
echo
echo "logs kept at $OPS_DIR/logs/ (delete by hand if you want them gone)"
