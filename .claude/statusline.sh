#!/bin/bash
# Claude Code Statusline - Context Usage Display
# Shows: Model | Input/Output tokens | Context usage % with bar | Cost | Duration
#
# Setup:
#   1. Copy to ~/.claude/statusline.sh
#   2. chmod +x ~/.claude/statusline.sh
#   3. Add to ~/.claude/settings.json:
#      "statusLine": { "type": "command", "command": "~/.claude/statusline.sh" }

input=$(cat)

# Extract fields
MODEL=$(echo "$input" | jq -r '.model.display_name')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
INPUT_TOKENS=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
OUTPUT_TOKENS=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
COST=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
API_DURATION_MS=$(echo "$input" | jq -r '.cost.total_api_duration_ms // 0')

# ANSI colors
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
CYAN='\033[36m'
RESET='\033[0m'

# Color based on context usage threshold
if [ "$PCT" -ge 90 ]; then
    BAR_COLOR="$RED"
elif [ "$PCT" -ge 70 ]; then
    BAR_COLOR="$YELLOW"
else
    BAR_COLOR="$GREEN"
fi

# Build progress bar (10 chars wide)
BAR_WIDTH=10
FILLED=$((PCT * BAR_WIDTH / 100))
EMPTY=$((BAR_WIDTH - FILLED))
BAR=""
[ "$FILLED" -gt 0 ] && printf -v FILL "%${FILLED}s" && BAR="${FILL// /█}"
[ "$EMPTY" -gt 0 ] && printf -v PAD "%${EMPTY}s" && BAR="${BAR}${PAD// /░}"

# Format cost
COST_FMT=$(printf '$%.4f' "$COST")

# Format API duration (ms -> seconds)
API_SEC=$(echo "scale=1; $API_DURATION_MS / 1000" | bc 2>/dev/null || echo "0.0")

# Output
echo -e "${CYAN}${MODEL}${RESET} | ${INPUT_TOKENS}/${OUTPUT_TOKENS} tokens | ${BAR_COLOR}${BAR} ${PCT}%${RESET} | ${YELLOW}${COST_FMT}${RESET} | ${API_SEC}s"
