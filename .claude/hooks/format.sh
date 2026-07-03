#!/bin/bash
# PostToolUse hook (Edit|Write): auto-format only the edited file.
# Never blocks: always exits 0; silently skips when formatter is unavailable.
# Wire-up (already in .claude/settings.json):
#   "PostToolUse": [{ "matcher": "Edit|Write",
#     "hooks": [{ "type": "command", "command": "bash .claude/hooks/format.sh" }] }]

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2> /dev/null)

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
    exit 0
fi

case "$FILE" in
    *.py)
        if command -v ruff > /dev/null 2>&1; then
            ruff format "$FILE" > /dev/null 2>&1
        elif command -v uv > /dev/null 2>&1; then
            uv run --no-sync ruff format "$FILE" > /dev/null 2>&1
        fi
        ;;
    *.js | *.jsx | *.ts | *.tsx | *.json | *.css | *.md)
        # Only when the project opted into prettier (avoid imposing style)
        if ls .prettierrc* prettier.config.* > /dev/null 2>&1; then
            npx --no-install prettier --write "$FILE" > /dev/null 2>&1
        fi
        ;;
esac

exit 0
