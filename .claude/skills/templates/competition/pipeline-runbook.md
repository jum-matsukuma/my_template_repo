# 運用ランブック

**実際に叩くコマンド列。** 説明ではなく手順を書く。
「思い出さなくても再実行できる」状態を保つのが目的。

## 環境

```bash
uv sync --extra kaggle
kaggle --version        # 2.2 以上（kernels topics が必要）
```

## データ取得

```bash
kaggle competitions download -c <slug> -p data/raw
unzip -q data/raw/<slug>.zip -d data/raw
```

## 公開情報の差分取得

```bash
python3 scripts/kaggle_research.py --comp <slug> --out research

# 取りこぼしが無いかを監査（取得はしない）
python3 scripts/kaggle_research.py --comp <slug> --out research --audit
```

詳細は [kaggle-scraping.md](../kaggle/kaggle-scraping.md)。
日次で自動化する場合は [.claude/ops/README.md](../../ops/README.md)。

## ローカル学習

```bash
# 1 時間を超えるならセッションから切り離す
nohup uv run python scripts/train.py --fold 0 > logs/train_f0.log 2>&1 &
disown
```

判定は終了コードで行う（[long-running-jobs.md](../kaggle/long-running-jobs.md)）。

## Kaggle カーネル連鎖

<!--
重い計算はカーネルに出す。CPU のキャッシュ生成と GPU の学習を分けると
GPU クォータを学習だけに使える。詳細は kaggle-gpu-kernels.md
-->

```bash
# 1. metadata を用意（machine_shape の指定は必須）
cat kernels/<name>/kernel-metadata.json

# 2. push して実行
kaggle kernels push -p kernels/<name>

# 3. 状態確認
kaggle kernels status <user>/<slug>

# 4. ログ本文の抽出
kaggle kernels logs <user>/<slug> \
  | grep -oE '"data":"[^"]*"' | sed 's/"data":"//;s/"$//'

# 5. 出力取得（全ファイル一括・レジューム可）
kaggle kernels output <user>/<slug> -p artifacts/<name>
```

**チェーン構成**:

| カーネル | 役割 | アクセラレータ | 目安時間 |
|---|---|---|---|
| `<name>-cache` | 特徴量生成 | CPU | <時間> |
| `<name>-train` | 学習 | T4 | <時間> |

## 提出

```bash
# Notebook 提出
kaggle competitions submit -c <slug> -k <user>/<slug> -v <version> \
  -f submission.csv -m "<CV値 / 変更点>"

# 提出履歴
kaggle competitions submissions -c <slug>
```

**提出メッセージには CV 値と変更点を必ず入れる。** 後から LB と CV を
突き合わせるときの唯一の手がかりになる。

## CV の再計算

```bash
uv run python scripts/eval_oof.py --oof artifacts/<name>/oof.parquet
```

<!-- 提出前に必ず通す検証があればここに書く -->
