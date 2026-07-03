---
name: colab
description: Google Colab integration for Claude Code. Use when the user mentions Google Colab, wants to run Python on remote GPU/TPU runtimes, train models in the cloud, execute scripts on a Colab VM, or operate a Colab notebook from the terminal. Covers the official Colab CLI (headless execution) and Colab MCP server (live browser notebook control).
user-invocable: true
argument-hint: "[task, e.g. 'run train.py on a T4']"
---

# Google Colab Integration

Google 公式の 2 つのツールで Claude Code から Colab を操作できる。タスクに応じて選ぶ:

| やりたいこと | 手段 | 参照 |
|---|---|---|
| スクリプトを GPU/TPU でヘッドレス実行（学習・バッチ） | **Colab CLI** — Bash で完結、設定不要 | [colab-operator.md](colab-operator.md) |
| ブラウザで開いたノートブックをライブ操作 | **Colab MCP** — opt-in | [colab-mcp.md](colab-mcp.md) |
| 旧来の git push → ブラウザ手動実行フロー | kaggle スキル | [../kaggle/colab-workflow.md](../kaggle/colab-workflow.md) |

## Quick Start (CLI)

```bash
# インストール（macOS / Linux のみ。Windows 非対応）
uv tool install google-colab-cli

# 認証（ADC、初回のみ・要ブラウザ）— 4 スコープ必須
gcloud auth application-default login \
  --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory

# ワンショット実行: VM 確保 → 実行 → 自動破棄
colab run --gpu T4 train.py --epochs 10

# セッション型: カーネル状態が exec 間で持続する
colab new -s exp1 --gpu T4
colab exec -s exp1 -f setup_data.py
colab exec -s exp1 -f train.py
colab download -s exp1 /content/model.pt ./models/model.pt
colab stop -s exp1   # 必ず停止（放置するとコンピュートユニットを消費し続ける）
```

## エージェント必須ルール

詳細・根拠は [colab-operator.md](colab-operator.md)（公式 colab-operator スキルの vendored コピー）を必ず読むこと。特に:

1. **使い終わったら必ず `colab stop -s <name>`**。ワンショットは `colab run`（自動クリーンアップ）を優先
2. **`colab repl` / `console` / `auth` / `drivemount` を対話モードで実行しない** — TTY 待ちでハングする（`repl`/`console` はパイプ入力なら可）
3. **常に `-s <name>` でセッション名を明示する**
4. CLI の 401/403 は ADC スコープ不足が原因 — `colab whoami` で確認。`colab auth` は VM 側の認証であり無関係
5. GPU 指定は `T4 / L4 / G4 / H100 / A100`、TPU は `v5e1 / v6e1`。アカウントの Colab プランによっては割当不可（400）— その場合は `--gpu T4` か CPU にフォールバック
6. CLI がインストール済みなら `colab skill` で最新の公式リファレンスを取得できる

## Available Resources

- [colab-operator.md](colab-operator.md) — Colab CLI 完全リファレンス（公式スキルの vendored コピー: 認証、セッション管理、実行、ファイル転送、復旧手順）
- [colab-mcp.md](colab-mcp.md) — Colab MCP サーバーのセットアップと使い分け（opt-in）

## Kaggle との組み合わせ

Kaggle コンペで GPU 学習を回す場合: データ配置・実験トラッキングは kaggle スキル（[../kaggle/SKILL.md](../kaggle/SKILL.md)）に従い、実行だけを本スキルの CLI に置き換えるのが基本形。`colab drivemount`（ユーザーが対話実行）で Google Drive のデータセットを VM から参照できる。
