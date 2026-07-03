#!/bin/bash
# PreToolUse hook (Bash): one-shot review nudge before `gh pr create`.
# First attempt on a branch: blocks once (exit 2) with a reminder fed to Claude.
# Any retry on the same branch passes through (exit 0). Not a hard gate.
# Wire-up (already in .claude/settings.json):
#   "PreToolUse": [{ "matcher": "Bash",
#     "hooks": [{ "type": "command", "command": "bash .claude/hooks/pr-review-nudge.sh" }] }]

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2> /dev/null)

case "$CMD" in
    *"gh pr create"*) ;;
    *) exit 0 ;;
esac

GIT_DIR=$(git rev-parse --git-dir 2> /dev/null) || exit 0
BRANCH=$(git rev-parse --abbrev-ref HEAD 2> /dev/null) || exit 0
MARKER="$GIT_DIR/.claude-pr-nudge-$(echo "$BRANCH" | tr '/' '-')"

if [ -f "$MARKER" ]; then
    exit 0
fi

touch "$MARKER" 2> /dev/null

echo "Review nudge (once per branch): このブランチではまだレビュー実施を確認していません。/code-review を実行し（Codex CLI が使えるなら codex-reviewer の第二意見も検討）、confirmed な指摘を修正してから PR を作成してください。既にレビュー済み、またはユーザーがレビュー省略を指示している場合は、同じ gh pr create コマンドを再実行すればそのまま通ります。" >&2
exit 2
