# Kaggle ページスクレイピング（Playwright）

KaggleはJavaScript SPAのため、`WebFetch` ではページ内容を取得できない。
`playwright` を使ってブラウザレンダリング後のテキストを取得する。

## 前提

```bash
uv sync --extra kaggle          # playwright が含まれる
uv run playwright install chromium
```

## 基本パターン

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    url = "https://www.kaggle.com/competitions/COMP_NAME/overview"
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(5000)  # JS レンダリング待ち

    content = page.inner_text("body")
    # content は長いので分割して読む
    print(content[:10000])
    # print(content[10000:20000])  # 続き

    browser.close()
```

## 取得対象別 URL

| タブ | URL パス |
|------|---------|
| Overview | `/competitions/COMP_NAME/overview` |
| Rules | `/competitions/COMP_NAME/rules` |
| Data | `/competitions/COMP_NAME/data` |
| Discussion | `/competitions/COMP_NAME/discussion` |
| Leaderboard | `/competitions/COMP_NAME/leaderboard` |
| Notebook | `/code/USER/NOTEBOOK_NAME` |

## 注意事項

- **認証不要**: 公開ページはログインなしで取得可能
- **出力が長い**: `body` のテキストは数万文字になるため、`content[start:end]` でスライスして読む
- **タイムアウト**: `wait_until="networkidle"` + `wait_for_timeout(5000)` でほぼ確実にレンダリング完了
- **Kaggle API で取れるもの**: ファイル一覧、リーダーボード、ノートブックダウンロードは API の方が効率的
- **Playwright が必要な場面**: Overview、Rules、Evaluation の本文テキスト、Discussion の内容

---

## Discussion 一括取得スクリプト

`kaggle-template/scripts/fetch_discussions.py` で competition の全 discussion（トピック一覧 + 各トピックのコメント）を取得できる。

Kaggleコンペ用プロジェクトではテンプレートをコピーした時点でスクリプトも使える:

```bash
cp -r kaggle-template/ my-competition/
cd my-competition/
uv sync --extra kaggle
uv run playwright install chromium
```

### 仕組み

Kaggle は Discussion の公開 API を提供していない。内部 API を以下の方法で利用:

1. **トピック一覧**: Playwright で cookie 取得 → `requests` で内部 API を直接呼び出し（高速）
2. **トピック詳細**: Playwright でページを個別訪問し、`GetForumTopicById` レスポンスをインターセプト

内部 API エンドポイント（`/api/i/discussions.DiscussionsService/`）:

| エンドポイント | 用途 | 認証 |
|---|---|---|
| `GetForum` | フォーラム ID 取得 | 不要 |
| `GetTopicListByForumId` | トピック一覧（ページネーション） | 不要 |
| `GetForumTopicById` | トピック詳細 + コメント | **ブラウザコンテキスト必須** |

`GetForumTopicById` は `requests` からの直接呼び出しでは 404 を返す（Kaggle がブラウザコンテキストを検証）。
そのため Playwright でのページ訪問が必要。

### 使い方

```bash
# 全 discussion 取得（初回）
uv run python scripts/fetch_discussions.py --competition <slug> --delay 10.0

# 差分更新（前回以降の新規・更新トピックのみ取得）
uv run python scripts/fetch_discussions.py --competition <slug> --update --delay 10.0

# コメント未取得分だけ再取得（中断からの復帰）
uv run python scripts/fetch_discussions.py --competition <slug> --resume --delay 10.0

# トピック一覧だけ取得（高速、数十秒）
uv run python scripts/fetch_discussions.py --competition <slug> --topics-only

# 件数制限（テスト用）
uv run python scripts/fetch_discussions.py --competition <slug> --limit 5 --delay 5.0
```

`--competition` を省略したい場合は、スクリプト先頭の `DEFAULT_COMPETITION` を書き換える。

### 出力先

`docs/discussions/` に出力される:

```
docs/discussions/
├── topic_list.json          # 全トピックのメタデータ（タイトル、著者、投票数等）
├── discussions_full.json    # 全トピック詳細 + コメント（JSON）
├── INDEX.md                 # 一覧インデックス
└── markdown/                # 各トピックの個別 Markdown ファイル
    ├── 687017_Nemotron-Cascade-....md
    ├── 680552_Apply here for ....md
    └── ...
```

### Rate Limit 対策

Kaggle は動的 rate limit を適用する。以下の知見に基づいて設計:

| パラメータ | 推奨値 | 説明 |
|---|---|---|
| `--delay` | **10.0** | ページ間の待機秒数。10秒で 298 件取得時に rate limit 回避を確認 |
| API throttle | 0.5秒/リクエスト（固定） | 1 ページロードで ~17 件の内部 API が発火。各リクエストに 0.5 秒の遅延を挿入 |
| トピック一覧 | 1.0秒/ページ（固定） | 20件/ページ × 15ページ程度 |

- **1 ページあたりの負荷**: HTML 1 + JS/CSS ~4 + 内部 API ~17 = **約 22 リクエスト**
- `--delay 10.0` での所要時間: 約 **50-60 分**（~170 件未取得時）
- `--delay 5.0` でも動く可能性はあるが、rate limit リスクが上がる
- rate limit に引っかかった場合: **数十分〜数時間待つ必要がある**（UI でもページが見れなくなる）

### `--update` の動作（差分更新）

`discussions_full.json` の `fetchedAt` タイムスタンプを基準に差分を検出:

- **新規トピック**: `topic_list` にあるが `discussions_full.json` にないもの
- **更新トピック**: `lastCommentPostDate` が `fetchedAt` 以降のもの（新しいコメントが付いた）

変更のあったトピックだけ Playwright で再取得し、既存データにマージする。
新規2件 + 更新3件 なら約1分で完了（フル取得の50分と比較して大幅に高速）。

### `--resume` の動作

- `discussions_full.json` からコメント付きトピックをキャッシュとして読み込む
- コメント 0 件のトピックは再取得対象（前回 rate limit で取得失敗した可能性）
- トピック一覧の取得に失敗した場合、`topic_list.json` からフォールバック

### 外部リクエストのブロック

スクリプトは Playwright の route 機能で外部サービス（Google Analytics, fonts 等）をブロックし、
Kaggle への不要なリクエストを削減している。
**Kaggle 内部 API はブロックしてはいけない**（SPA の初期化に必要で、ブロックすると `GetForumTopicById` が発火しない）。
