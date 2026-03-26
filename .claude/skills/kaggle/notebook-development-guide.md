# ノートブック開発ガイド (Colab / Kaggle / Local 3環境対応)

## 鉄則

**すべてのノートブックは Colab と Kaggle と Local の3環境で動くように作ること。**

## 1. 環境判定（最重要）

```python
import os, sys

# Colab判定を先にやること。/kaggle/input がColab上にも存在する場合がある
IS_COLAB  = ('google.colab' in sys.modules
             or 'COLAB_RELEASE_TAG' in os.environ
             or os.path.exists('/root/.config/colab'))
IS_KAGGLE = (not IS_COLAB) and os.path.exists('/kaggle/input')
IS_LOCAL  = not IS_KAGGLE and not IS_COLAB

if IS_KAGGLE:
    ENVIRONMENT = "kaggle"
    DATA_DIR = "/kaggle/input/competition-name"
elif IS_COLAB:
    ENVIRONMENT = "colab"
    DATA_DIR = "/content/drive/MyDrive/Kaggle/competition-name/data"
else:
    ENVIRONMENT = "local"
    DATA_DIR = "./data"
```

**やってはいけない:**
- `IS_KAGGLE = os.path.exists('/kaggle/input')` を先に判定 → Colabで誤判定
- `IS_COLAB = 'google.colab' in sys.modules` だけ → import前はFalseの場合がある

## 2. ノートブック構造テンプレート

### セル構成
1. **セル1**: 環境検出 + 設定パラメータ（実験名、バージョン、DEBUG）
2. **セル2**: パッケージインストール（環境別分岐）
3. **セル3**: データ読み込み（パス分岐）
4. **セル4-N**: 処理ロジック
5. **最終セル**: 出力保存 + 提出CSV生成

### パッケージインストール（環境別）
```python
if IS_KAGGLE:
    # オフライン: wheelファイルからインストール
    !pip install /kaggle/input/your-dataset/*.whl --no-deps --quiet
elif IS_COLAB:
    # オンライン: pipでインストール
    !pip install -q package-name
# Local: uv sync --extra kaggle で事前インストール済み
```

### Pythonバージョン互換性
Kaggle環境のPythonバージョン（cp310等）に合ったwheelを使用すること。

## 3. デバッグモード（必須）

**すべてのノートブックの冒頭に `DEBUG = False` を定義すること。**

```python
DEBUG = False  # True: 少数データで高速デバッグ

if DEBUG:
    data = data.head(100)
    print(f"DEBUG MODE: {len(data)} rows only")
```

### push前のDEBUG確認チェックリスト

**Kaggle pushする前に、必ず `DEBUG = True` で実行し以下を全て確認すること。**

- [ ] 全フェーズがエラーなく通ること
- [ ] 出力ファイルが生成されること
- [ ] 出力のフォーマット（行数・カラム名）が正しいこと
- [ ] 値が妥当な範囲（NaN/Inf がないこと）
- [ ] 新しく追加したロジックが実際に実行されていること

**確認せずにpushしない。** push後のデバッグは1回あたり数時間のロスになる。

## 4. Kaggle提出チェックリスト

- [ ] Internet Off で動作するか
- [ ] 必要なwheelファイルがDatasetとして追加されているか
- [ ] データパスが `/kaggle/input/` を参照しているか
- [ ] 実行時間が8時間以内に収まるか（CPU/GPU）
- [ ] 出力CSVのフォーマットが正しいか
- [ ] 不要な print/display を削除したか
- [ ] `DEBUG = False` になっているか

## 5. エラーハンドリングパターン

### 重い処理の try/except（推奨）
失敗しても後続フェーズに必ず到達させる:
```python
try:
    result = heavy_computation(data)
except Exception as e:
    print(f"Warning: computation failed: {e}")
    print("Continuing with fallback...")
    result = fallback_result
```

### per-item エラーハンドリング
各アイテムの失敗が他に波及しないようにする:
```python
results = {}
for item in items:
    try:
        results[item] = process(item)
    except Exception as e:
        print(f"  {item} FAILED: {e}")
        results[item] = None
    finally:
        gc.collect()
```

## 6. Colab + Google Drive

```python
if IS_COLAB:
    from google.colab import drive
    drive.mount('/content/drive')
    DATA_DIR = "/content/drive/MyDrive/Kaggle/competition-name/data"
```

Google Driveにデータを保存すると:
- セッション切断後もデータが永続化
- Colabの無料枠でも大容量データを扱える
- チェックポイントの保存にも活用可能

## 7. メモリ対策

- 大きなDataFrame読み込み後は `del` + `gc.collect()`
- GPU使用後は `torch.cuda.empty_cache()`（PyTorch使用時）
- Colab無料枠 (12GB RAM) では大ファイル全読み込みに注意
- dtype指定で省メモリ化: `pd.read_csv(..., dtype={'col': 'float32'})`

## 8. Kaggle push後の監視

push後、以下のタイミングで実行状況を確認:
- **2分後**: import/セットアップ段階のエラー検出
- **15分後**: 初期処理完了確認。早期終了やクラッシュの検出

早期完了（想定より大幅に早い場合）はエラー終了の可能性がある。

## 9. ファイル管理

### ディレクトリ構成
```
kaggle-template/
├── notebooks/
│   ├── eda/                    # EDA用
│   ├── experiments/            # 実験用
│   └── submissions/            # 提出用
├── colab_template.ipynb        # Colab用テンプレート
├── colab_minimal.ipynb         # 最小テンプレート
├── setup_download_data.ipynb   # データダウンロード
└── README.md
```

### kernel-metadata.json（Kaggle push用）
```json
{
  "id": "username/notebook-slug",
  "title": "Notebook Title",
  "code_file": "notebook.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": true,
  "enable_internet": false,
  "dataset_sources": ["user/dataset-name"],
  "competition_sources": ["competition-name"]
}
```
