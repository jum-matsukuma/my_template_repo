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

## 記録先（コンペ用スキル）

収集した情報の記録先と更新ルールは
`.claude/skills/kaggle/experiment-tracking.md` に一本化してある。
ここでは繰り返さない — 二重に書くと必ず片方が古くなる。

このコマンドの出力の行き先だけ再掲する:

| 収集したもの | 記録先 |
|---|---|
| リーダーボード動向・公開 notebook の分析 | `existing-solutions.md` |
| 採用候補のテクニック | `EXPERIMENT_LOG.md` の Next Steps |
| 締切・提出制約・データ仕様の変更 | `COMPETITION_TRACKER.md` |

## What This Command Does

このコマンドは以下の情報を収集してレポートします:

### 1. リーダーボード
Kaggle APIで上位チームのスコアと順位を取得:
```bash
uv run kaggle competitions leaderboard <competition-name> --show
```

### 2. 公開ノートブック
人気順と新着順で一覧を取得:
```bash
uv run kaggle kernels list --competition <competition-name> --sort-by voteCount --page-size 5
uv run kaggle kernels list --competition <competition-name> --sort-by dateCreated --page-size 5
```

**ソースの取得は `/kaggle-research` が済ませている** ので、ここでは
`research/notebooks/<ref>/` の .ipynb を Read で読み、手法・アルゴリズム・
技術スタックを日本語で要約する。別の場所へ二重にダウンロードしない。

### 3. 自分の提出履歴
過去の提出結果を取得:
```bash
uv run kaggle competitions submissions <competition-name>
```

### 4. ディスカッション・notebook・コメント・writeup

**`/kaggle-research` に委譲する。** コマンドとフラグの説明はそちらが持つ
（同じ手順を2箇所に書くと必ず片方が古くなる）:

```bash
python3 scripts/kaggle_research.py --comp <competition-name> --out research
```

取得結果は `research/` に入る。このコマンドの仕事は、その中身を読んで
**日本語の要約レポートを作ること**であって、取得そのものではない。

実行後は必ず出力の **warnings 欄**を見る — `fetched X of Y comments` は
取りこぼしのサイン。落とし穴の詳細は
`.claude/skills/kaggle/kaggle-scraping.md`。

### 5. 手動確認リンク
- Overview: https://www.kaggle.com/competitions/<competition-name>/overview

## Notebook Storage

notebook ソースの保管先は `research/notebooks/<ref>/` の一箇所だけ
（`kaggle_research.py` が管理し、`.gitignore` 済み — 他人の著作物なので
コミットしない）。

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
[existing-solutions.md / EXPERIMENT_LOG.md への更新内容があれば記載]

------------------------------------------------------------
手動確認リンク
------------------------------------------------------------
- Discussions: URL
- Announcements: URL
- SKILL.md: .claude/skills/<project-name>/SKILL.md
- EXPERIMENT_LOG: .claude/skills/<project-name>/EXPERIMENT_LOG.md
- existing-solutions: .claude/skills/<project-name>/existing-solutions.md
============================================================
```

## Prerequisites

- Kaggle API認証が必要: `~/.kaggle/kaggle.json`
- セットアップ方法は `.claude/skills/kaggle/kaggle-api-setup.md` を参照

## Error Handling

- API認証エラー: kaggle.jsonのセットアップ方法を案内
- ネットワークエラー: 取得可能な情報のみ表示
- コンペ名エラー: 正しいコンペ名の確認方法を案内
