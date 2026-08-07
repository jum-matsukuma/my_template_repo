# Kaggle カーネル運用の実務（実測ベース）

GPU カーネルとローカル実行のハマりどころ集。すべて実際に踏んで時間を失ったもの。
**同じ穴に落ちないこと。**

## GPU カーネル

### アクセラレータ指定は metadata で行う

**GPU カーネルの既定は P100 だが、現行イメージの torch は sm_70+ しかサポートしない。**
P100 で torch 演算が `no kernel image is available for execution on the device`
で全滅する。

```json
// kernel-metadata.json
{ "enable_gpu": true, "machine_shape": "NvidiaTeslaT4" }
```

CLI の `--accelerator` は値が通っても効かないことがある。**metadata が確実**。
CatBoost の GPU 学習は torch 非依存なので P100 でも動く。

### 実行時間の壁

- **GPU バッチカーネルは 12 時間で `CANCEL_ACKNOWLEDGED`。出力は保存されず全喪失。**
  24 epoch × 5 fold の学習が 12h に収まらず、まるごと消えた事例がある
- 目安は **10 時間以内**（20 epoch × 5 fold 程度）。超えるなら fold 分割
  （2 カーネル × 2〜3 fold）か、epoch 分割のチェックポイント連鎖にする

### クォータ

- **GPU 週間クォータは 30 時間**、リセットは週次
- **T4x2 は wall-clock の 2 倍を消費する**（2 枠占有 = 2 GPU時間/h）。
  12h で CANCEL された T4x2 ジョブが 24h を消し飛ばし、週 30h が 2 日で枯れた実例がある
- **T4x2 実行中は他の GPU カーネルを一切起動できない**
  （"Maximum batch GPU session count of 2 reached"）
- 対策: **キャッシュ生成(CPU)と学習(GPU)を別カーネルに分離**し、
  GPU 時間を学習だけに使う。長時間ジョブの前にクォータ残を必ず計算する

### slug の汚染

**GPU 枠不足で reject された slug は "Notebook not found" 状態に汚染され、
同じ slug への再 push が失敗し続ける。** slug を変えて push し直すしかない
（`foo` → `foo2` → `foo3` の前例）。

### 出力とログ

- 出力は `/kaggle/working` 全体が保存される（上限 ~20GB）。中間キャッシュを
  含めたくなければ最後に `shutil.rmtree` する
- `kaggle kernels output` は**全ファイル一括のみ**（ファイル指定不可）。
  既存ファイルはスキップされるので**中断→再実行でレジューム可能**
- ログ抽出: `kaggle kernels logs <slug>` は JSON ストリーム。
  `grep -oE '"data":"[^"]*"' | sed 's/"data":"//;s/"$//'` で本文が出る

### データのマウントパス

**競技データのマウントパスは環境で変わる。** ハードコードは FileNotFound の前例あり。

```python
glob("/kaggle/input/**/train/*.csv", recursive=True)
```

### 提出

```bash
kaggle competitions submit -k <slug> -v <version> -f submission.csv -m "<message>"
```

`-f` を忘れると 400 Bad Request になる。

## ローカル実行（共有マシン前提）

- **大規模学習はローカルでやらない。** 他プロセス（エディタ、VM、複数の
  Claude セッション）と同居する 16GB 機では、数百万行規模の GBDT 学習は
  スワップスラッシングで死ぬ。重い計算は Kaggle カーネル連鎖へ
- Apple Silicon の MPS は使える（初回コンパイルに ~25 秒かかる）
- **zsh は変数展開後の単語分割をしない**: `cfg="--a 5"; cmd $cfg` は 1 引数になり
  argparse がエラーになる。ループでオプションを回すときは明示的に書く
- macOS の Accelerate BLAS は有限な入力でも matmul で偽の RuntimeWarning
  (divide by zero / overflow) を出す。実害はない

## API・セッション

- **サブエージェントの並列起動はセッション上限を食い切ることがある。**
  大量調査はエージェント、定型実装は自前、と使い分ける
- `kaggle` CLI の実体は `uv run kaggle` ではなく PATH 上のもの
  （`uv tool install kaggle` 版）。Python API を直接使うときは
  そのツールの Python インタプリタを指す必要がある:
  `~/.local/share/uv/tools/kaggle/bin/python`

## 関連

- [kaggle-scraping.md](kaggle-scraping.md) — 公開情報の取得
- [long-running-jobs.md](long-running-jobs.md) — 1 時間超のジョブの回し方
- [colab-workflow.md](colab-workflow.md) — Colab を使う場合
