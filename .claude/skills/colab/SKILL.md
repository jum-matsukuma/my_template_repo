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
| スクリプトを GPU/TPU でヘッドレス実行（学習・バッチ） | **Colab CLI** — Bash で完結（要 CLI インストール + 初回 ADC 認証） | [colab-operator.md](colab-operator.md) |
| ブラウザで開いたノートブックをライブ操作 | **Colab MCP** — opt-in | [colab-mcp.md](colab-mcp.md) |
| 旧来の git push → ブラウザ手動実行フロー | kaggle スキル（残している場合） | [../kaggle/colab-workflow.md](../kaggle/colab-workflow.md) |

## Quick Start (CLI)

```bash
# インストール（macOS / Linux のみ。Windows 非対応）
uv tool install google-colab-cli

# 認証（ADC、初回のみ・要ブラウザ）— 4 スコープ必須
# 注意: ADC はマシン共有の認証情報。既に有効なら再実行不要（`colab sessions` で確認）。
# 最新のスコープ要件は colab-operator.md の Authentication 節が正。
gcloud auth application-default login \
  --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory

# ワンショット実行: VM 確保 → 実行 → 自動破棄
# 注意: リリース版 CLI（0.6.0 で実機確認）のデフォルト認証は oauth2。
# ADC を使うには --auth=adc を「サブコマンドの前に」毎回付けること。
colab --auth=adc run --gpu T4 train.py --epochs 10

# セッション型: カーネル状態が exec 間で持続する
colab --auth=adc new -s exp1 --gpu T4
colab --auth=adc exec -s exp1 -f setup_data.py
colab --auth=adc exec -s exp1 -f train.py
colab --auth=adc download -s exp1 /content/model.pt ./models/model.pt
colab --auth=adc stop -s exp1   # 必ず停止（放置するとコンピュートユニットを消費し続ける）
```

## エージェント必須ルール

作業前に完全リファレンスを一読すること — CLI インストール済みなら `colab skill` の出力、なければ [colab-operator.md](colab-operator.md)（vendored コピー、オフラインフォールバック）。**どちらか一方でよい**（両方読むと同内容を二重にロードする）。特に:

1. **`--auth=adc` を毎回サブコマンドの前に明示する**（リリース版 0.6.0 のデフォルトは oauth2 で、付け忘れると対話式の認可コード入力フローが始まりエージェントはハングする。vendored リファレンスの「デフォルト adc」は upstream main の記述で、リリース版と乖離）
2. **使い終わったら必ず `colab stop -s <name>`**。ワンショットは `colab run`（自動クリーンアップ）を優先
3. **`colab repl` / `console` / `auth` / `drivemount` を対話モードで実行しない** — TTY 待ちでハングする（`repl`/`console` はパイプ入力なら可）
4. **常に `-s <name>` でセッション名を明示する**
5. CLI の 401/403 は ADC スコープ不足が原因 — `colab --auth=adc whoami` で確認。`colab auth` は VM 側の認証であり無関係
6. 利用可能な GPU/TPU の種類はリファレンスの Provision 節を参照（ここには複製しない — vendored 更新時のドリフト防止）。アカウントの Colab プランによっては割当不可（400）— その場合は `--gpu T4` か CPU にフォールバック

## Available Resources

- [colab-operator.md](colab-operator.md) — Colab CLI 完全リファレンス（公式スキルの vendored コピー: 認証、セッション管理、実行、ファイル転送、復旧手順）
- [colab-mcp.md](colab-mcp.md) — Colab MCP サーバーのセットアップと使い分け（opt-in）

## Kaggle との組み合わせ（kaggle スキルを残している場合）

Kaggle コンペで GPU 学習を回す場合: データ配置・実験トラッキングは kaggle スキル（[../kaggle/SKILL.md](../kaggle/SKILL.md)）に従い、実行だけを本スキルの CLI に置き換えるのが基本形。`colab drivemount`（ユーザーが対話実行）で Google Drive のデータセットを VM から参照できる。kaggle スキルを削除したプロジェクトでは本節と上表の「旧来フロー」行は無視してよい。
