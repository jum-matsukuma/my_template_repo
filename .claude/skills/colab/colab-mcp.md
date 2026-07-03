# Colab MCP Server (opt-in)

Google 公式の [colab-mcp](https://github.com/googlecolab/colab-mcp)（Apache-2.0）は、**ブラウザで開いている Colab ノートブック**を Claude Code からライブ操作するための MCP サーバー。セルの作成・編集・実行、markdown による説明の挿入、pip での依存インストールなどをノートブック上で直接行える。

CLI（[colab-operator.md](colab-operator.md)）がヘッドレスなスクリプト実行向けなのに対し、MCP は「ノートブックそのものを対話的に育てる」用途向け。

## 有効化（opt-in）

`.claude/.mcp.json` に `colab` エントリが定義済みだが、**デフォルト無効**。有効化するには `.claude/settings.local.json` の `enabledMcpjsonServers` に `"colab"` を追加する:

```json
{
  "enabledMcpjsonServers": ["colab"]
}
```

（codex も使っている場合は `["codex", "colab"]` のように併記。）

### 前提条件

- `uv` がインストール済みであること（サーバーは `uvx git+https://github.com/googlecolab/colab-mcp` で起動される）
- `git` がインストール済みであること
- Claude Code は `notifications/tools/list_changed` に対応しているため、クライアント要件は満たしている

非標準のパッケージインデックスを使っている環境では、`.mcp.json` の `args` に `--index https://pypi.org/simple` を追加する。

## 使い方

1. ブラウザで https://colab.research.google.com のノートブックを開き、ランタイムに接続する
2. Claude Code セッションで通常どおり指示する（例: 「この Colab ノートブックにデータ読み込みセルを追加して実行して」）
3. Claude が MCP ツール経由でセルを作成・実行し、結果はブラウザのノートブックにライブ反映される

公開されるツールの一覧はセッション内で確認できる（`/mcp` で接続状態とツールを表示）。

## CLI との使い分け

| やりたいこと | 使うもの |
|---|---|
| 学習スクリプトを GPU でヘッドレス実行し成果物を回収 | CLI（`colab run` / `colab exec`） |
| バッチ処理・CI 的なワンショットジョブ | CLI（`colab run`、自動クリーンアップ） |
| ブラウザのノートブックを見ながら対話的に分析を進める | MCP |
| 共有・提出用ノートブックを整形しながら作る | MCP |
| Kaggle 提出フローの一部として実行 | CLI（kaggle スキルと組み合わせ） |

両者は排他ではない。例: CLI で学習を回し、結果の可視化・レポート化はブラウザのノートブックで MCP により行う。

## トラブルシューティング

- **サーバーが起動しない**: `uv --version` で uv の存在を確認。初回は `uvx` が GitHub からパッケージを取得するためネットワークが必要
- **起動が遅い / タイムアウト**: `.mcp.json` の `timeout: 30000` は初回取得の遅さを見込んだ値。それでも失敗する場合は一度シェルで `uvx git+https://github.com/googlecolab/colab-mcp --help` を実行してキャッシュを温める
- **ツールが見えない**: ブラウザ側でノートブックが開かれ、ランタイムに接続されているか確認。`/mcp` で colab サーバーの接続状態を確認
