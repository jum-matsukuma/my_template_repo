# Kaggle 公開情報の取得

**結論から: notebook・discussion・コメントは公式 Kaggle CLI で全部取れる。Playwright は要らない。**

かつては Kaggle が JS SPA であることを理由にブラウザレンダリングが必須だったが、
CLI 2.2 以降は背後の API を正式に叩ける。実測で確認済み（下表）。
唯一の例外は **writeup 本文**で、ここだけレンダラが要る。

## 取得対象 × 手段（実測済み）

| 取得対象 | コマンド | 状態 |
|---|---|---|
| notebook ソース | `kaggle kernels pull <ref> -p <dir>` | ✅ |
| notebook 一覧 | `kaggle kernels list --competition <slug> -p N --page-size 50 --csv` | ✅ 全ページ列挙可 |
| discussion 一覧 | `kaggle competitions topics list <slug> -p N -s new --format json` | ✅ 全ページ列挙可 |
| discussion 本文+コメント | `kaggle competitions topics show <id> --format json` | ✅ 切り詰めなし |
| **kernel コメント** | `kaggle kernels topics list <ref>` → `kaggle kernels topics show <topic_id>` | ✅ |
| **writeup 本文** | ❌ CLI に存在しない | → r.jina.ai |

これらは `kaggle-template/scripts/kaggle_research.py` に実装済み。
個別に叩く前にまずそれを使うこと。

## 落とし穴（すべて実害があったもの）

### 1. `--format json` を必ず付ける

プレーン出力は**コメント本文を切り詰める**。同一スレッドで実測すると
プレーン 2253 バイト / JSON 4522 バイト。JSON なら 1700 字級の本文も完全に返る。

### 2. `kernels topics` の存在を忘れない

kernel のコメントは `kagglesdk` の `list_comments` を直接叩いても取れるが、
**返信ツリーを辿らないので大幅に取りこぼす**。実測: 同一 notebook で
kagglesdk 3 件 / CLI 10 件。コンペ全体では kagglesdk 経由で 1050 notebook から
15 件しか拾えず、実際には 64 件以上あった。

`kernels topics show` は "all its comments in tree form" を返す。こちらを使う。

### 3. 件数を必ず自己検証する

`commentCount`（Kaggle の申告）と実際に取得できた件数を毎回照合すること。
上の取りこぼしは**何のエラーも出さずに起きた**。差分が出たら記録して人間に見せる。
削除済みコメントによる 1 件差は正常。

### 4. 上位 N 件だけ取ると盲点が恒久化する

ソート上位 N のみを取得して manifest に記録する設計だと、**差分取得は
「manifest にあるものの更新」しか見ない**ため、初回に外れたものは二度と現れない。
実例: 158 スレッド中 43 件しか追跡しておらず、上位陣との差を説明する情報が
見落とし側にあった。**全ページ列挙を既定にする。**

### 5. レートリミット

60 件を超える連続取得で 429 が出る。トピック取得の間に 4 秒、
Jina 経由は 6 秒空ける。

## writeup — 唯一レンダラが要る対象

CLI に writeup サブコマンドは無い（`competitions pages` は overview 系のみ）。
生 `curl` は 8.7KB の JS シェルしか返さず本文は入っていない。

**ただし発見（discovery）は CLI だけでできる。** writeup の URL は discussion
本文に貼られるので、取得済み discussion コーパスを正規表現で走査すれば
新規 writeup を検知できる。実測: 1 スレッドから 22 本の URL を抽出。

したがって:

- **検知は CLI 由来**（外部依存ゼロ・無人ジョブでも静かに失敗しない）
- **本文取得のみ** `https://r.jina.ai/<url>` を使う

```bash
curl -s -m 120 -H "x-no-cache: true" "https://r.jina.ai/https://www.kaggle.com/writeups/<user>/<slug>"
```

`x-no-cache: true` を付けないとリーダー側のキャッシュを掴む。
`JINA_API_KEY` があれば `Authorization: Bearer` で渡すとレート制限が緩む。

**404 は本文に埋め込まれて返る。** リーダーは HTTP 200 を返しつつ本文に
`Warning: Target URL returned error 404` と書く。これを見ないと、削除された
writeup の 400 バイトの Cookie バナーを「取得成功」として保存してしまう
（実際にそうなっていた事例あり）。

### 外部サービスを使うことの評価

送るのは URL のみで、対象は公開ページなので内容の機密性は無い。ただし
**「どのコンペの何を調べているか」は第三者のログに残る**。開催中コンペでは
これを踏まえて判断すること。使用面を writeup だけに絞れば曝露は最小化できるし、
無人ジョブのクリティカルパスから外れるので可用性リスクも消える。

## 公式 CLI と Jina が両方使えなくなったら

この節は「二度と Playwright を書かなくて済むように」ではなく、
**本当に必要になった時に一から調べ直さなくて済むように**残してある。

- Kaggle の内部エンドポイントは `https://www.kaggle.com/api/i/<Service>`
  （例: `discussions.DiscussionsService`）。**バージョン無しで予告なく変わる**
- 内部エンドポイントの多くは**ブラウザコンテキストを検証する**ので、`requests`
  だけでは通らずページ遷移が要る。これが当初 Playwright を導入した理由
- 旧実装（Playwright + 内部 API、490 行）は git 履歴にある:

  ```bash
  SHA=$(git log --all --diff-filter=D --format=%h -- '*fetch_discussions.py' | head -1)
  git show "${SHA}^:kaggle-template/scripts/fetch_discussions.py"
  ```

  **`^` を付けて親コミットを指すこと** — 削除コミットそのものには
  もうファイルが無い
- **ただし取りこぼしの前科がある実装なので、復活させるより
  レンダリング済みページを取りに行く方が筋が良い**

## 認証

`kaggle-api-setup.md` を参照。CLI は 2.2 以上が必要
（`kernels topics` は 2.2 で入った）。`kaggle --version` で確認すること。

## 日本語訳レイヤ

取得した英語原文から図つきの日本語全訳を作る手順は
[research-ja-translation.md](research-ja-translation.md) にある。

重要なのは役割分担で、**エージェントが根拠にしてよいのは英語原文
（`research/rendered/*.md`）だけ**、日本語訳（`docs/research-ja/`）は人間専用。
訳文は `.claude/settings.json` の `permissions.deny` で Read が塞いである。
