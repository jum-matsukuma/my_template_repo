#!/bin/bash
# Stop hook: OS notification when Claude Code finishes responding.
# Gracefully degrades: exits 0 silently when no notifier is available.
# Wire-up (already in .claude/settings.json):
#   "Stop": [{ "hooks": [{ "type": "command", "command": "bash .claude/hooks/notify.sh" }] }]

cat > /dev/null  # drain stdin (hook JSON, unused)

TITLE="Claude Code"
MESSAGE="Task complete: $(basename "$PWD")"

if command -v terminal-notifier > /dev/null 2>&1; then
    terminal-notifier -title "$TITLE" -message "$MESSAGE" -sound default -group claude-stop > /dev/null 2>&1
elif command -v osascript > /dev/null 2>&1; then
    osascript -e "display notification \"$MESSAGE\" with title \"$TITLE\"" > /dev/null 2>&1
elif command -v notify-send > /dev/null 2>&1; then
    notify-send "$TITLE" "$MESSAGE" > /dev/null 2>&1
fi

exit 0
