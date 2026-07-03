# Template Modernization Design (Opus 4.7–4.8 baseline)

Date: 2026-07-04
Status: Approved pending user review
Branch: `chore/modernize-template`

## Goal

テンプレートリポジトリを現行モデル性能（Opus 4.7–4.8）基準で見直す。
モデルが既に持っている一般知識を排除し、実際に動く自動化（hooks・レビューフロー）に置き換える。
CI（GitHub Actions / Copilot review）は使わない — クォータを無条件消費するため。
方針: ブロック型ガードレールではなく「観測性 + opt-in + 自律性」。

## 1. 削除（一般知識の死荷重と死んだ設定）

| 対象 | 理由 |
|---|---|
| `.claude/skills/development/`（SKILL.md + 3支援ファイル） | アーキテクチャ/デザインパターン等の一般知識。現行モデルは既知でコンテキストの死荷重 |
| `.claude/agents/tech-innovation-advisor.md` | 汎用技術相談はインラインで十分 |
| `.mcp.json` の `filesystem` エントリ | built-in file access で不要（エントリ自身のコメントも認めている） |
| `.claude/hooks/pre-commit` | 全チェックが `if` 条件内で実行され失敗しても常に exit 0 する偽ガードレール。存在しない `PreCommit` フックイベントへの言及も有害 |
| `.claude/commands/review.md` | ビルトイン `/code-review` の下位互換で冗長 |

温存: `skills/templates/`、`skills/kaggle/`、`skills/sync-template/`、`skills/review-pr-comments/`、
`agents/code-reviewer.md`、`agents/codex-reviewer.md`、`/codex-review`、`/test`、`/docs`、`/turn-main`、`/kaggle-update`、statusline。

## 2. hooks 刷新（非ブロック・graceful degradation）

3つの実動作フックを `.claude/hooks/` に追加し、`.claude/settings.json` にデフォルト有効で配線する。
いずれも依存ツールがなければ無音で exit 0（クローン先の環境を壊さない）。

### 2a. `notify.sh` — Stop フック（観測性）

タスク完了時に OS 通知。macOS: `terminal-notifier` → `osascript` フォールバック。Linux: `notify-send`。どれもなければ無音終了。

### 2b. `format.sh` — PostToolUse フック（Edit|Write）（非ブロック自動化）

stdin の JSON から編集対象ファイルパスを取得し、拡張子に応じて**そのファイルだけ**フォーマット:
- `.py` → `uv run ruff format <file>`（ruff がなければ skip）
- `.js/.jsx/.ts/.tsx/.json/.css/.md` → `npx prettier --write <file>`（prettier 設定がプロジェクトにある場合のみ）

フォーマット失敗してもブロックしない（常に exit 0）。

### 2c. `pr-review-nudge.sh` — PreToolUse フック（Bash）（一度だけのナッジ）

`gh pr create` コマンドを検出したら:
1. ブランチ別マーカー（`.git/.claude-pr-nudge-<branch>`）が**なければ**: マーカーを作成し、exit 2 で「このブランチでレビュー未実施なら `/code-review` を先に実行せよ（ユーザーがスキップ指示済みなら再実行してよい）」と注入
2. マーカーが**あれば**: exit 0 で素通し

→ 1ブランチにつき1回だけ確認が入り、再実行すれば必ず通る。ブロック型ゲートにならない。

## 3. permission 構文修正

`.claude/settings.json` のスペース形式プレフィックスルール（`Bash(git diff *)`）を現行のコロン形式（`Bash(git diff:*)`）に全修正。引数なし完全一致ルール（`Bash(npm test)` 等）はそのまま。

## 4. `/pr` へのレビュー統合（ローカル完結の自動レビューフロー）

`.claude/commands/pr.md` のワークフローを拡張:

```
状態確認 → ブランチ作成 → コミット → ★レビュー → ★修正 → プッシュ → PR作成
```

★レビュー段階:
1. ビルトイン `/code-review` を実行
2. Codex CLI が利用可能（`codex --version` が通る）なら `codex-reviewer` エージェントを並列起動して第二意見
3. confirmed な指摘は修正して追加コミット。判断が割れる指摘はユーザーに提示して判断を仰ぐ
4. PR 本文に「実施レビューと対応結果」サマリを記載
5. `/pr --skip-review` でレビュー段階をスキップ可能

## 5. CLAUDE.md / README 同期・スリム化

- 削除資産への参照除去（エージェント表・File Structure・README の該当箇所・MCP 説明）
- CLAUDE.md「Special Templates」の Kaggle 詳細を kaggle SKILL.md へのポインタに縮約（実体は既に SKILL.md 側にある重複）
- hooks セクションを新 hooks（notify / format / pr-review-nudge、無効化方法）の説明に置換
- `/pr` のレビュー統合と `/review` 廃止（→ ビルトイン `/code-review`）を反映

## 6. 見送り（明示的な非スコープ)

- **GitHub Actions（claude-code-action / Copilot review）**: PR ごとに無条件でクォータを消費する。手動 opt-in のセッション内レビューで代替
- **ブロック型 pre-commit ゲート**: ユーザー方針（自律性 > ハードガードレール）に反する

## テスト計画

- 各フックスクリプトを模擬 JSON 入力で単体実行し、期待動作（通知/フォーマット/ナッジ→素通し）と graceful degradation（ツールなし環境で exit 0）を確認
- `claude` 実セッションで settings.json の hooks 配線が読み込まれることを確認（`/hooks` 表示）
- permission ルールはコロン形式構文のドキュメント準拠を目視確認

## 成果物

PR 1本（`chore/modernize-template` → `main`）。本 spec と実装 plan は過去の慣例（PR #28）に倣い、マージ前に除去する。
