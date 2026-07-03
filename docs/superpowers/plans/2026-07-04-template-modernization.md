# Template Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** テンプレートを Opus 4.7–4.8 基準で近代化する — 一般知識資産の削除、実動作 hooks の導入、permission 構文修正、`/pr` へのローカル完結レビューフロー統合。

**Architecture:** 削除が先、追加が後。hooks は 3 つの独立した bash スクリプト（graceful degradation、常に非ブロック志向）を `.claude/hooks/` に置き、`.claude/settings.json` で配線する。レビューフローは `/pr` コマンド定義（Markdown プロンプト）のワークフロー拡張として実装し、コードは書かない。

**Tech Stack:** bash, jq, Claude Code hooks (Stop / PostToolUse / PreToolUse), Claude Code permission rules, slash command Markdown.

**Spec:** `docs/superpowers/specs/2026-07-04-template-modernization-design.md`

## Global Constraints

- ブランチ: `chore/modernize-template`（作成済み、この上で作業する）
- コミットは conventional commits 形式。各コミット末尾に `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- hooks スクリプトは依存ツールが無い環境で**必ず無音で exit 0**（pr-review-nudge の初回 exit 2 のみ例外）
- hooks スクリプトは全て実行可能ビット付き（`chmod +x`）
- 削除対象以外のファイル・セクションには触れない
- JSON ファイル編集後は必ず `jq . <file>` で構文検証する

---

### Task 1: 死荷重資産の削除

**Files:**
- Delete: `.claude/skills/development/SKILL.md`
- Delete: `.claude/skills/development/architecture-patterns.md`
- Delete: `.claude/skills/development/programming-languages.md`
- Delete: `.claude/skills/development/development-tools.md`
- Delete: `.claude/agents/tech-innovation-advisor.md`
- Delete: `.claude/hooks/pre-commit`
- Delete: `.claude/commands/review.md`
- Modify: `.claude/.mcp.json`（`filesystem` エントリ除去）

**Interfaces:**
- Consumes: なし
- Produces: `.claude/.mcp.json` は `codex` エントリのみを含む。後続タスク（8, 9）はこれら資産が存在しない前提でドキュメントを更新する。

- [ ] **Step 1: ファイル削除**

```bash
git rm -r .claude/skills/development
git rm .claude/agents/tech-innovation-advisor.md .claude/hooks/pre-commit .claude/commands/review.md
```

- [ ] **Step 2: `.mcp.json` から filesystem エントリを除去**

`.claude/.mcp.json` 全体を以下の内容に書き換える:

```json
{
  "mcpServers": {
    "codex": {
      "_comment": "OpenAI Codex CLI as MCP server. Requires `npm i -g @openai/codex` and `codex login`. Disabled by default — to enable, add \"codex\" to enabledMcpjsonServers in settings.local.json. See README.",
      "command": "codex",
      "args": ["mcp-server"],
      "env": {
        "CLAUDE_CODEX_DEPTH": "1"
      }
    }
  }
}
```

- [ ] **Step 3: 検証**

Run: `jq . .claude/.mcp.json && git status --short`
Expected: JSON がエラーなく出力され `filesystem` を含まない。deleted 7 ファイル + modified `.mcp.json`。

- [ ] **Step 4: Commit**

```bash
git add -A .claude
git commit -m "chore: remove generic-knowledge assets and dead config

- skills/development/: general knowledge current models already have
- tech-innovation-advisor: inline capability suffices
- filesystem MCP entry: redundant with built-in file access
- pre-commit template: all checks silently passed (fake guardrail),
  referenced nonexistent PreCommit hook event
- /review command: superseded by built-in /code-review

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: permission 構文修正（スペース形式 → コロン形式）

**Files:**
- Modify: `.claude/settings.json`

**Interfaces:**
- Consumes: なし
- Produces: `permissions.allow` はコロン形式プレフィックスルールのみ。Task 6 がこのファイルに `hooks` キーを追加する。

- [ ] **Step 1: settings.json の permissions を書き換え**

`.claude/settings.json` 全体を以下の内容に書き換える（引数なし完全一致ルールはそのまま、プレフィックスルール `Bash(x *)` → `Bash(x:*)`）:

```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Read",
      "Bash(npm test)",
      "Bash(npm install)",
      "Bash(npm run lint)",
      "Bash(npm run build)",
      "Bash(npm run typecheck)",
      "Bash(npm run dev)",
      "Bash(git status)",
      "Bash(git diff:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git log:*)",
      "Bash(git checkout:*)",
      "Bash(git branch:*)",
      "Bash(git fetch:*)",
      "Bash(git remote:*)",
      "Bash(git show:*)",
      "Bash(git merge-file:*)",
      "Bash(git rev-list:*)",
      "Bash(uv sync:*)",
      "Bash(uv run python -m pytest:*)",
      "Bash(uv run python -m ruff:*)",
      "Bash(uv run python -m black:*)",
      "Bash(uv run python -m mypy:*)",
      "Bash(gh pr:*)",
      "Bash(gh api:*)",
      "Bash(bash .claude/scripts/codex-run.sh:*)",
      "Bash(codex --version)",
      "WebFetch(domain:github.com)"
    ]
  },
  "statusLine": {
    "type": "command",
    "command": ".claude/statusline.sh"
  }
}
```

- [ ] **Step 2: 検証**

Run: `jq -r '.permissions.allow[]' .claude/settings.json | grep ' \*' ; echo "exit: $?"`
Expected: マッチなし（`exit: 1`）— スペース+`*` 形式のルールが残っていないこと。

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.json
git commit -m "fix: use colon-form prefix syntax in permission rules

Space-form rules like Bash(git diff *) do not match under the
current permission syntax; Bash(git diff:*) is the documented form.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: notify.sh（Stop フック: タスク完了通知）

**Files:**
- Create: `.claude/hooks/notify.sh`

**Interfaces:**
- Consumes: なし（stdin の JSON は読み捨てる）
- Produces: `bash .claude/hooks/notify.sh` — 常に exit 0。Task 6 が `Stop` フックとして配線する。

- [ ] **Step 1: スクリプト作成**

`.claude/hooks/notify.sh`:

```bash
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
```

- [ ] **Step 2: 実行可能化**

Run: `chmod +x .claude/hooks/notify.sh`

- [ ] **Step 3: 動作確認**

Run: `echo '{}' | bash .claude/hooks/notify.sh; echo "exit: $?"`
Expected: `exit: 0`。macOS 上では OS 通知が表示される（通知が出ることも目視確認）。

- [ ] **Step 4: Commit**

```bash
git add .claude/hooks/notify.sh
git commit -m "feat: add Stop-hook notification script

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: format.sh（PostToolUse フック: 編集ファイルの自動フォーマット）

**Files:**
- Create: `.claude/hooks/format.sh`

**Interfaces:**
- Consumes: stdin に PostToolUse フック JSON（`.tool_input.file_path` を参照）
- Produces: `bash .claude/hooks/format.sh` — 常に exit 0。Task 6 が `PostToolUse` (matcher `Edit|Write`) として配線する。

- [ ] **Step 1: スクリプト作成**

`.claude/hooks/format.sh`:

```bash
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
```

- [ ] **Step 2: 実行可能化**

Run: `chmod +x .claude/hooks/format.sh`

- [ ] **Step 3: 動作確認（3ケース）**

```bash
# case 1: 汚い .py が整形される
TMP=$(mktemp -d)
printf 'x=1\ny  =  2\n' > "$TMP/sample.py"
echo "{\"tool_input\":{\"file_path\":\"$TMP/sample.py\"}}" | bash .claude/hooks/format.sh
echo "exit: $?"; cat "$TMP/sample.py"

# case 2: 存在しないファイル → 無音 exit 0
echo '{"tool_input":{"file_path":"/nonexistent/x.py"}}' | bash .claude/hooks/format.sh; echo "exit: $?"

# case 3: file_path なし → 無音 exit 0
echo '{}' | bash .claude/hooks/format.sh; echo "exit: $?"
```

Expected: case 1 は `exit: 0` かつ `x = 1` / `y = 2` に整形（ruff がある環境の場合。無ければ未整形のまま exit 0 でも合格）。case 2, 3 は出力なしで `exit: 0`。

- [ ] **Step 4: Commit**

```bash
git add .claude/hooks/format.sh
git commit -m "feat: add PostToolUse auto-format hook for edited files

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: pr-review-nudge.sh（PreToolUse フック: PR 作成前レビューナッジ）

**Files:**
- Create: `.claude/hooks/pr-review-nudge.sh`

**Interfaces:**
- Consumes: stdin に PreToolUse フック JSON（`.tool_input.command` を参照）
- Produces: `bash .claude/hooks/pr-review-nudge.sh` — `gh pr create` 検出時、ブランチ初回のみ exit 2 + stderr メッセージ、以降は exit 0。マーカー: `$GIT_DIR/.claude-pr-nudge-<branch名のスラッシュを-に置換>`。Task 6 が `PreToolUse` (matcher `Bash`) として配線する。

- [ ] **Step 1: スクリプト作成**

`.claude/hooks/pr-review-nudge.sh`:

```bash
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
```

- [ ] **Step 2: 実行可能化**

Run: `chmod +x .claude/hooks/pr-review-nudge.sh`

- [ ] **Step 3: 動作確認（3ケース）**

```bash
# 事前にテスト用マーカーを掃除
BRANCH=$(git rev-parse --abbrev-ref HEAD)
MARKER=".git/.claude-pr-nudge-$(echo "$BRANCH" | tr '/' '-')"
rm -f "$MARKER"

# case 1: 無関係コマンド → exit 0
echo '{"tool_input":{"command":"git status"}}' | bash .claude/hooks/pr-review-nudge.sh; echo "exit: $?"

# case 2: gh pr create 初回 → exit 2 + stderr メッセージ + マーカー作成
echo '{"tool_input":{"command":"gh pr create --title x"}}' | bash .claude/hooks/pr-review-nudge.sh; echo "exit: $?"
ls "$MARKER"

# case 3: 同一ブランチ2回目 → exit 0
echo '{"tool_input":{"command":"gh pr create --title x"}}' | bash .claude/hooks/pr-review-nudge.sh; echo "exit: $?"

# テスト後にマーカーを掃除（本セッションで後で実際に PR を作るため、掃除しないと素通りになる — ここでは掃除して本番でナッジを踏むのが正)
rm -f "$MARKER"
```

Expected: case 1 → `exit: 0`。case 2 → stderr にメッセージ、`exit: 2`、マーカー存在。case 3 → `exit: 0`。

- [ ] **Step 4: Commit**

```bash
git add .claude/hooks/pr-review-nudge.sh
git commit -m "feat: add once-per-branch PR review nudge hook

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: settings.json への hooks 配線

**Files:**
- Modify: `.claude/settings.json`（Task 2 の内容に `hooks` キーを追加）

**Interfaces:**
- Consumes: Task 3–5 のスクリプトパス（`bash .claude/hooks/notify.sh` / `format.sh` / `pr-review-nudge.sh`）
- Produces: hooks が新規セッションでデフォルト有効になる settings.json。Task 8, 9 のドキュメントはこの配線を説明する。

- [ ] **Step 1: hooks キーを追加**

`.claude/settings.json` の `"statusLine"` ブロックの後に追加し、ファイル全体を以下にする（permissions は Task 2 と同一）:

```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Read",
      "Bash(npm test)",
      "Bash(npm install)",
      "Bash(npm run lint)",
      "Bash(npm run build)",
      "Bash(npm run typecheck)",
      "Bash(npm run dev)",
      "Bash(git status)",
      "Bash(git diff:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git log:*)",
      "Bash(git checkout:*)",
      "Bash(git branch:*)",
      "Bash(git fetch:*)",
      "Bash(git remote:*)",
      "Bash(git show:*)",
      "Bash(git merge-file:*)",
      "Bash(git rev-list:*)",
      "Bash(uv sync:*)",
      "Bash(uv run python -m pytest:*)",
      "Bash(uv run python -m ruff:*)",
      "Bash(uv run python -m black:*)",
      "Bash(uv run python -m mypy:*)",
      "Bash(gh pr:*)",
      "Bash(gh api:*)",
      "Bash(bash .claude/scripts/codex-run.sh:*)",
      "Bash(codex --version)",
      "WebFetch(domain:github.com)"
    ]
  },
  "statusLine": {
    "type": "command",
    "command": ".claude/statusline.sh"
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/pr-review-nudge.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/format.sh" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/notify.sh" }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: 検証**

Run: `jq '.hooks | keys' .claude/settings.json`
Expected: `["PostToolUse", "PreToolUse", "Stop"]`

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: wire notify/format/pr-review-nudge hooks in settings

All three degrade gracefully (silent exit 0 without their tools),
so default-on is safe for cloned projects.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: /pr コマンドへのレビュー統合

**Files:**
- Modify: `.claude/commands/pr.md`（全体書き換え）

**Interfaces:**
- Consumes: ビルトイン `/code-review`、`codex-reviewer` エージェント（存在チェック: `codex --version`）
- Produces: レビュー段階込みの `/pr` ワークフロー定義。Task 8, 9 のドキュメントはこの `/pr` を参照する。

- [ ] **Step 1: pr.md を書き換え**

`.claude/commands/pr.md` 全体を以下の内容にする:

```markdown
# Create Pull Request

変更内容をもとにブランチ作成、コミット、レビュー、修正、プッシュ、PR作成を一括で行う。

## Usage

- `/pr` - 変更内容から自動でブランチ名・コミットメッセージ・PRを生成（レビュー込み）
- `/pr $ARGUMENTS` - 引数をPRの説明として使用
- `/pr --skip-review` - レビュー段階をスキップ

## What This Command Does

以下の手順を順番に実行する:

### 1. 現在の状態を確認
- `git status` で変更ファイルを確認
- `git diff` でstaged/unstaged両方の変更内容を確認
- 変更がない場合はその旨を伝えて終了

### 2. ブランチを作成
- 既にmain/master以外のブランチにいる場合はそのブランチを使用
- main/masterにいる場合は変更内容から適切なブランチ名を生成
  - 命名規則: `feature/description` または `fix/description`（kebab-case）
- `git checkout -b <branch-name>` でブランチを作成

### 3. コミット
- 変更内容を分析してconventional commit形式のメッセージを作成
  - 形式: `type(scope): description`
  - type: feat, fix, improve, docs, refactor, test, chore
- 関連ファイルをステージング（`git add` で個別にファイルを指定）
  - .env, credentials, secrets等のファイルはステージングしない
- コミットを作成

### 4. レビュー（`--skip-review` 指定時はスキップ）
- ビルトインの `/code-review` skill を実行してこのブランチの diff をレビューする
- `codex --version` が成功する環境では、`codex-reviewer` エージェントを並列起動して
  第二意見を取得する（失敗しても続行）
- 指摘の扱い:
  - **confirmed / 明確なバグ**: 修正して追加コミット（`fix:` prefix）
  - **判断が割れる・設計論**: 修正せずユーザーに提示して判断を仰ぐ
  - **false positive**: 却下理由を記録
- 対応結果を次のステップの PR 本文用にまとめる

### 5. プッシュ
- `git push -u origin <branch-name>` でリモートにプッシュ

### 6. PR作成
- `gh pr create` でPRを作成
- タイトル: 70文字以内で変更内容を要約
- 本文: 変更の概要、テストプラン、**レビューサマリ**（実施したレビュー・
  指摘件数・対応結果。スキップした場合は「review skipped」と明記）を含める
- 作成後にPR URLを表示

## Prerequisites

- `gh` CLI がインストール・認証済みであること
- git リモートが設定されていること
- （任意）Codex CLI — あれば第二意見レビューが自動で有効になる
```

- [ ] **Step 2: 検証**

Run: `grep -c "skip-review" .claude/commands/pr.md`
Expected: `3`（Usage 1箇所 + 手順4見出し + PR本文の記述で計3。2以上であれば合格）

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/pr.md
git commit -m "feat: integrate local review stage into /pr workflow

Runs built-in /code-review (plus codex-reviewer second opinion when
available) between commit and push; --skip-review escape hatch.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: CLAUDE.md の同期・スリム化

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: Task 1 の削除結果、Task 3–7 の成果物名
- Produces: 実態と一致した CLAUDE.md

- [ ] **Step 1: Custom Agents セクション更新**

現在の内容:

```markdown
## Custom Agents

`.claude/agents/` に補助エージェントを定義済み。いずれも単体での委譲用途で、チーム協調を前提としない。

| エージェント | 用途 |
|---|---|
| `code-reviewer` | 変更コードの独立レビュー |
| `codex-reviewer` | OpenAI Codex CLI によるセカンドオピニオン |
| `tech-innovation-advisor` | 技術戦略・アーキテクチャ助言 |
```

を以下に置換:

```markdown
## Custom Agents

`.claude/agents/` に補助エージェントを定義済み。いずれも単体での委譲用途で、チーム協調を前提としない。

| エージェント | 用途 |
|---|---|
| `code-reviewer` | 変更コードの独立レビュー |
| `codex-reviewer` | OpenAI Codex CLI によるセカンドオピニオン |
```

- [ ] **Step 2: Workflow セクションにレビューフロー追記**

`## Workflow` の箇条書き `- Use conventional commit messages` の直後に以下の2行を追加:

```markdown
- PR作成は `/pr` を使う — コミット後にビルトイン `/code-review`（+ Codex があれば第二意見）を実行し、修正してから PR を作成する。`--skip-review` でスキップ可
- `gh pr create` を直接実行した場合も、ブランチごと初回のみ hooks がレビュー実施を確認する（再実行で通る）
```

- [ ] **Step 3: Hooks セクション追加**

`## Custom Agents` セクションの直前に以下を追加:

```markdown
## Hooks

`.claude/settings.json` で3つのフックがデフォルト有効。いずれも依存ツールが無ければ無音でスキップし、処理をブロックしない:

| フック | イベント | 動作 |
|---|---|---|
| `notify.sh` | Stop | タスク完了をOS通知（terminal-notifier / osascript / notify-send） |
| `format.sh` | PostToolUse (Edit\|Write) | 編集したファイルだけ自動フォーマット（`.py`→ruff、js/ts等→prettier 設定がある場合のみ） |
| `pr-review-nudge.sh` | PreToolUse (Bash) | `gh pr create` 前にブランチごと1回だけレビュー実施を確認（再実行で通る） |

無効化する場合は `settings.json` の `hooks` から該当エントリを削除する。
```

- [ ] **Step 4: File Structure 更新**

File Structure のコードブロックを以下に置換:

```
project-root/
├── CLAUDE.md           # This file
├── .claude/            # Claude Code configurations
│   ├── agents/         # Custom agent definitions
│   │   ├── code-reviewer.md
│   │   └── codex-reviewer.md
│   ├── commands/       # Slash commands (/pr, /codex-review, /docs, /test, ...)
│   ├── hooks/          # notify.sh / format.sh / pr-review-nudge.sh
│   └── skills/         # Skills directory (Claude Code recommended format)
│       ├── kaggle/     # Kaggle competition skills
│       │   └── SKILL.md
│       └── templates/  # Skill templates (technology-stack, custom-tools, project-domain)
├── kaggle-template/    # Kaggle competition template
└── README.md           # Project overview
```

- [ ] **Step 5: Special Templates の Kaggle 詳細を縮約**

`### Kaggle Competition Development` から末尾（`詳細: .claude/skills/kaggle/experiment-tracking.md` の行）までを以下に置換:

```markdown
### Kaggle Competition Development

`kaggle-template/` をコピーして開始する:

```bash
cp -r kaggle-template/ my-competition/
cd my-competition/
uv sync --extra kaggle
```

セットアップ・Colab連携（GPU実行）・実験トラッキング（SKILL.md / EXPERIMENT_LOG.md / COMPETITION_TRACKER.md の3層構造）の詳細は `.claude/skills/kaggle/SKILL.md` とその支援ファイルを参照。
```

- [ ] **Step 6: 初期セットアップ表の整合確認**

Initial Project Setup の Step 2 削除対象テーブルと Step 4 に、削除済み資産（`development/` 等）への言及が無いことを確認する。言及があれば除去。

- [ ] **Step 7: 検証**

Run: `grep -n "tech-innovation\|skills/development" CLAUDE.md; echo "exit: $?"`
Expected: マッチなし（`exit: 1`）

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: sync CLAUDE.md with modernized template

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: README の同期

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1 の削除結果、Task 3–7 の成果物名
- Produces: 実態と一致した README

- [ ] **Step 1: What's Included / Files Overview 更新**

- 9行目 `- **Custom Agents**: Reviewer and advisory agent definitions for delegation (\`.claude/agents/\`)` → `- **Custom Agents**: Reviewer agent definitions for delegation (\`.claude/agents/\`)`
- 22行目 `- \`.claude/agents/\` - Custom agent definitions (code-reviewer, codex-reviewer, tech-innovation-advisor)` → `- \`.claude/agents/\` - Custom agent definitions (code-reviewer, codex-reviewer)`
- 24行目 `- \`.claude/hooks/\` - Automation hooks for git and development workflow` → `- \`.claude/hooks/\` - Claude Code hooks (completion notification, auto-format, PR review nudge)`

- [ ] **Step 2: Automated Review Flow セクション追加**

`## Codex CLI Integration (Optional Reviewer)` セクションの直前に追加:

```markdown
## Automated Review Flow (Local, no CI)

PR 前レビューは CI ではなくセッション内で完結する（クォータを消費するのは使うと決めたときだけ）:

1. **`/pr`** — コミット後にビルトイン `/code-review` を実行し、Codex CLI があれば `codex-reviewer` の第二意見も並列取得。confirmed な指摘を修正してから push / PR 作成。`--skip-review` でスキップ可。
2. **レビューナッジ hook** — `/pr` を経由せず `gh pr create` を直接実行した場合も、ブランチごと初回のみレビュー実施を確認する（同じコマンドの再実行で通る。ハードゲートではない）。

## Hooks

`.claude/settings.json` で3つのフックがデフォルト有効。いずれも依存ツールが無ければ無音でスキップする:

| Hook | Event | Behavior |
|------|-------|----------|
| `notify.sh` | Stop | タスク完了のOS通知（terminal-notifier / osascript / notify-send） |
| `format.sh` | PostToolUse (Edit\|Write) | 編集ファイルのみ自動フォーマット（`.py`→ruff、js/ts等→prettier 設定がある場合のみ） |
| `pr-review-nudge.sh` | PreToolUse (Bash) | `gh pr create` 前の一度きりレビューナッジ |

無効化: `settings.json` の `hooks` から該当エントリを削除。
```

- [ ] **Step 3: Codex セクションの MCP 例修正**

`"enabledMcpjsonServers": ["filesystem", "codex"]` → `"enabledMcpjsonServers": ["codex"]`

- [ ] **Step 4: Example Instructions 更新**

- **Code review** の例を置換:

  変更前:
  ```
  /review

  src/models.pyをレビューしてください。
  データリーク、メモリ効率、再現性の観点でチェックしてください。
  ```
  変更後:
  ```
  /code-review

  データリーク、メモリ効率、再現性の観点を重点的にチェックしてください。
  ```

- **Strategic advice** の例（`tech-innovation-advisorエージェントを使って、...` のブロックと見出し）を削除

- [ ] **Step 5: Key Features 更新**

`- **Custom Agents**: code-reviewer and tech-innovation-advisor for specialized tasks` → `- **Custom Agents**: code-reviewer and codex-reviewer for independent review passes`

- [ ] **Step 6: 検証**

Run: `grep -n "tech-innovation\|filesystem\|/review$" README.md; echo "exit: $?"`
Expected: マッチなし（`exit: 1`）

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: sync README with modernized template

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: 最終検証・spec/plan 除去・PR 作成

**Files:**
- Delete: `docs/superpowers/specs/2026-07-04-template-modernization-design.md`
- Delete: `docs/superpowers/plans/2026-07-04-template-modernization.md`

**Interfaces:**
- Consumes: Task 1–9 の全成果物
- Produces: `chore/modernize-template` → `main` の PR

- [ ] **Step 1: 全体検証**

```bash
jq . .claude/settings.json > /dev/null && jq . .claude/.mcp.json > /dev/null && echo "JSON OK"
ls -l .claude/hooks/   # notify.sh / format.sh / pr-review-nudge.sh のみ、全て実行可能
grep -rn "tech-innovation\|skills/development" CLAUDE.md README.md .claude/ ; echo "refs: $?"
```

Expected: `JSON OK`、hooks 3ファイル（`-rwxr-xr-x`）、参照グレップは `refs: 1`（マッチなし）。

- [ ] **Step 2: spec / plan を除去（リポジトリ慣例: PR #28 と同様）**

```bash
git rm -r docs/superpowers
git commit -m "chore: remove modernization spec/plan scaffolding

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 3: プッシュ**

Run: `git push -u origin chore/modernize-template`

- [ ] **Step 4: PR 作成**

`gh pr create` を実行（レビューナッジ hook は本セッション起動時の設定に無いため作動しない。レビューは subagent-driven-development の各タスクレビューで実施済みである旨を PR 本文に記載する）:

```bash
gh pr create --title "chore: modernize template for current model capabilities" --body "$(cat <<'EOF'
## Summary

Opus 4.7–4.8 世代のモデル性能を基準にテンプレートを近代化する。

### Removed (dead weight)
- `.claude/skills/development/` — モデル既知の一般知識（アーキテクチャ/デザインパターン等）
- `tech-innovation-advisor` agent — インライン能力で十分
- `filesystem` MCP entry — built-in file access で不要
- `pre-commit` template — 全チェックが失敗しても exit 0 する偽ガードレール + 存在しない PreCommit イベント言及
- `/review` command — ビルトイン `/code-review` の下位互換

### Added (working automation, non-blocking)
- **Hooks（デフォルト有効・graceful degradation）**: Stop 通知 / 編集ファイルのみ自動フォーマット / ブランチごと一度きりの PR レビューナッジ
- **`/pr` レビュー統合**: commit → built-in `/code-review`（+ Codex 第二意見）→ 修正 → push → PR。`--skip-review` あり。CI・GitHub Actions は不使用（クォータの無条件消費を回避）

### Fixed
- permission ルールをスペース形式（`Bash(git diff *)`）→ コロン形式（`Bash(git diff:*)`）に修正

## Test plan
- [x] 各 hook スクリプトを模擬 JSON 入力で単体実行（正常系 / ツール欠如 / 非対象入力で exit code 検証）
- [x] settings.json / .mcp.json の JSON 構文検証（jq）
- [x] 削除資産への残存参照が無いことを grep で確認

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL が出力される。
