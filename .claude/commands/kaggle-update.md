# Kaggle Competition Update

コンペティションの最新情報を取得し、日本語でわかりやすくレポートします。

## Usage

- `/kaggle-update` - 全ての情報を取得
- `/kaggle-update leaderboard` - リーダーボードのみ
- `/kaggle-update notebooks` - ノートブック一覧のみ
- `/kaggle-update submissions` - 自分の提出履歴のみ
- `/kaggle-update discussions` - ディスカッション取得（増分更新）
- `/kaggle-update $ARGUMENTS` - カスタム引数で実行

## Competition Target

**重要**: このコマンドを使う前に、プロジェクトの SKILL.md でターゲットコンペを設定してください。

設定ファイル例: `.claude/skills/<project-name>/SKILL.md`

```yaml
competition:
  name: competition-slug-name
  type: kaggle
```

別のコンペを指定: `/kaggle-update --comp other-competition-name`

## Competition Tracker（3層構造）

**重要**: 競技の動向は以下の3つのファイルで追跡管理します:

| ファイル | 内容 | 更新方式 |
|---------|------|---------|
| `.claude/skills/<project>/SKILL.md` | 現在のパラメータ、ワークフロー、Next Steps | 置換 |
| `.claude/skills/<project>/EXPERIMENT_LOG.md` | 実験履歴、結果、教訓 | 追記 |
| `.claude/skills/<project>/COMPETITION_TRACKER.md` | リーダーボード、公開ノートブック分析 | 置換 |

詳細: `.claude/skills/kaggle/experiment-tracking.md` を参照

### Tracker更新ルール

`/kaggle-update` 実行時の更新先:

1. **リーダーボードに大きな変動があった場合** → `COMPETITION_TRACKER.md`
   - 新しいトップスコアが出た
   - 順位に大きな変動があった

2. **新しい重要なノートブックが公開された場合** → `COMPETITION_TRACKER.md`
   - 高投票数の新規ノートブック
   - 新しいアプローチや手法

3. **重要なテクニックを発見した場合**
   - 採用候補 → `SKILL.md` の Next Steps に追加
   - 実験済み → `EXPERIMENT_LOG.md` に結果を記録

更新時は各ファイルの「Last updated」日付も更新すること。

### アーカイブルール

SKILL.mdが肥大化したり、古い情報が不要になった場合は**アーカイブ**する:

**アーカイブ先**:
```
docs/archive/<project-name>/
├── YYYY-MM-DD_archived_content.md
└── ...
```

**アーカイブ対象**:
- 既に実装済みで検証完了したテクニック詳細
- 古いリーダーボード情報
- 採用しなかったアプローチの詳細分析
- 過去のノートブック分析（新しいものに置き換わった場合）

**アーカイブ手順**:
1. 削除する内容を `docs/archive/<project-name>/YYYY-MM-DD_<topic>.md` にコピー
2. SKILL.md から該当セクションを削除
3. 必要なら SKILL.md に「アーカイブ済み」のリンクを残す

**SKILL.mdに残すべき情報**:
- 現在のベストスコアとパラメータ
- 最新のリーダーボード状況
- 未実装の改善アイデア（Next Steps）
- 直近の重要なノートブック分析

## What This Command Does

このコマンドは以下の情報を収集してレポートします:

### 1. リーダーボード
Kaggle APIで上位チームのスコアと順位を取得:
```bash
uv run kaggle competitions leaderboard <competition-name> --show
```

### 2. 公開ノートブック
人気順と新着順でノートブック一覧を取得:
```bash
uv run kaggle kernels list --competition <competition-name> --sort-by voteCount --page-size 5
uv run kaggle kernels list --competition <competition-name> --sort-by dateCreated --page-size 5
```

**重要**: 上位ノートブックについては、Kaggle APIでダウンロードして中身を確認した上でサマリーを作成:
```bash
uv run kaggle kernels pull <kernel-ref> -p data/kaggle_notebooks/<notebook-name>/
```

ダウンロードした.ipynbファイルをReadツールで読み込み、内容を分析して日本語サマリーを作成する。

### 3. 自分の提出履歴
過去の提出結果を取得:
```bash
uv run kaggle competitions submissions <competition-name>
```

### 4. ディスカッション
Playwright ベースのスクレイパーで全ディスカッション + コメントを取得:
```bash
# 増分更新（推奨: 新規・更新トピックのみ取得、~1-2分）
uv run python scripts/fetch_discussions.py --competition <competition-name> --update --delay 10.0

# 初回フル取得（全トピック、~50-60分）
uv run python scripts/fetch_discussions.py --competition <competition-name> --delay 10.0

# トピック一覧のみ（高速）
uv run python scripts/fetch_discussions.py --competition <competition-name> --topics-only

# 中断再開
uv run python scripts/fetch_discussions.py --competition <competition-name> --resume --delay 10.0
```

**出力先**: `docs/discussions/`
```
docs/discussions/
├── topic_list.json          # トピック一覧メタデータ
├── discussions_full.json    # 全トピック詳細 + コメント
├── INDEX.md                 # Markdown インデックス
└── markdown/                # トピック別 .md ファイル
```

**注意事項**:
- 初回は `--delay 10.0` を推奨（Kaggle レートリミット対策）
- `--update` は前回の `discussions_full.json` の `fetchedAt` を基準に差分検出
- Playwright + Chromium が必要: `uv sync --extra kaggle && uv run playwright install chromium`
- スクリプト詳細・内部 API の仕組みは `.claude/skills/kaggle/kaggle-scraping.md` を参照

**取得後のアクション**:
1. `docs/discussions/INDEX.md` を読んで新しいトピックを確認
2. 重要な知見は `COMPETITION_TRACKER.md` に反映
3. 採用候補のテクニックは `SKILL.md` の Next Steps に追加

### 5. 手動確認リンク
- Overview: https://www.kaggle.com/competitions/<competition-name>/overview

## Notebook Storage

ダウンロードしたノートブックは以下に保存:
```
data/kaggle_notebooks/
├── <notebook-name-1>/
│   └── <notebook-name-1>.ipynb
├── <notebook-name-2>/
│   └── <notebook-name-2>.ipynb
└── ...
```

このディレクトリは `.gitignore` に登録し、コミットしないこと。

## Output Format

日本語で出力し、以下の形式でレポート:

```
============================================================
Kaggle コンペ更新情報
============================================================
コンペ: <Competition Name>
取得日時: YYYY-MM-DD HH:MM

------------------------------------------------------------
リーダーボード (上位10)
------------------------------------------------------------
| 順位 | チーム名 | スコア |
|------|----------|--------|

------------------------------------------------------------
人気ノートブック（中身を確認済み）
------------------------------------------------------------
1. [タイトル](URL) - 投票数

   **サマリ**: ノートブックの内容を読んで分析した結果を記載。
   使用している手法、主要なアルゴリズム、技術スタックなどを含める。

------------------------------------------------------------
新着ノートブック
------------------------------------------------------------
1. [タイトル](URL) - 作成日

------------------------------------------------------------
Tracker更新
------------------------------------------------------------
[COMPETITION_TRACKER.md / SKILL.md への更新内容があれば記載]

------------------------------------------------------------
手動確認リンク
------------------------------------------------------------
- Discussions: URL
- Announcements: URL
- SKILL.md: .claude/skills/<project-name>/SKILL.md
- EXPERIMENT_LOG: .claude/skills/<project-name>/EXPERIMENT_LOG.md
- COMPETITION_TRACKER: .claude/skills/<project-name>/COMPETITION_TRACKER.md
============================================================
```

## Prerequisites

- Kaggle API認証が必要: `~/.kaggle/kaggle.json`
- セットアップ方法は `.claude/skills/kaggle/kaggle-api-setup.md` を参照

## Error Handling

- API認証エラー: kaggle.jsonのセットアップ方法を案内
- ネットワークエラー: 取得可能な情報のみ表示
- コンペ名エラー: 正しいコンペ名の確認方法を案内
