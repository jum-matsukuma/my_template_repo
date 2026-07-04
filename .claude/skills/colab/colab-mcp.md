# Colab MCP Server (opt-in)

Google 公式の [colab-mcp](https://github.com/googlecolab/colab-mcp)（Apache-2.0）は、**ブラウザで開いている Colab ノートブック**を Claude Code からライブ操作するための MCP サーバー。セルの作成・編集・実行、markdown による説明の挿入、pip での依存インストールなどをノートブック上で直接行える。

CLI（[colab-operator.md](colab-operator.md)）がヘッドレスなスクリプト実行向けなのに対し、MCP は「ブラウザのノートブックそのものを対話的に育てる」用途向け。使い分けの基準は [SKILL.md](SKILL.md) のルーティング表が正とする（CLI で学習を回し、結果の可視化・レポート化だけ MCP で行う併用も可）。

## 有効化（opt-in）

プロジェクトルートの `.mcp.json` に `colab` エントリが定義済みだが、**デフォルト無効**。有効化するには `.claude/settings.local.json` の `enabledMcpjsonServers` に `"colab"` を追加する:

```json
{
  "enabledMcpjsonServers": ["colab"]
}
```

（codex も使っている場合は `["codex", "colab"]` のように併記。）

### 前提条件

- `uv` がインストール済みであること（サーバーは `uvx git+https://github.com/googlecolab/colab-mcp@v1.0.2` で起動される。リリースタグに pin してあり、更新は `.mcp.json` の `@タグ` を意図的に上げる）
- `git` がインストール済みであること
- **注意**: PyPI の `colab-mcp` パッケージは**無関係の別プロジェクト**。必ず `git+https://github.com/googlecolab/colab-mcp@<tag>` 形式を使うこと

非標準のパッケージインデックスを使っている環境では、`--index` を**パッケージ指定より前に**置く（後ろに置くと colab-mcp 側への引数と解釈される）:

```json
"args": ["--index", "https://pypi.org/simple", "git+https://github.com/googlecolab/colab-mcp@v1.0.2"]
```

## 使い方

1. ブラウザで https://colab.research.google.com のノートブックを開き、ランタイムに接続する
2. Claude Code セッションで通常どおり指示する（例: 「この Colab ノートブックにデータ読み込みセルを追加して実行して」）
3. Claude が MCP ツール経由でセルを作成・実行し、結果はブラウザのノートブックにライブ反映される

公開されるツールの一覧はセッション内で確認できる（`/mcp` で接続状態とツールを表示）。

## トラブルシューティング

- **サーバーが起動しない**: `uv --version` で uv の存在を確認。初回は `uvx` が GitHub からパッケージを取得するためネットワークが必要（タグ pin により 2 回目以降はキャッシュされる）
- **初回起動がタイムアウトする**: MCP サーバーの起動タイムアウトは環境変数 `MCP_TIMEOUT`（ms、デフォルト 30 秒）で制御される。初回フェッチが遅い環境では `MCP_TIMEOUT=120000 claude` で起動する。`.mcp.json` の `timeout` フィールドは**ツール実行**のタイムアウトであり起動には効かない（小さい値を設定すると長時間セル実行が打ち切られるため、このテンプレートでは未設定 = デフォルトのまま）
- **ツールが見えない**: ブラウザ側でノートブックが開かれ、ランタイムに接続されているか確認。`/mcp` で colab サーバーの接続状態を確認
