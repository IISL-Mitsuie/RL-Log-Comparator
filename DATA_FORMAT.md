# RL-Log-Comparator ログデータ フォーマット仕様書 (Log Data Format Specification)

本ドキュメントは、**RL-Log-Comparator (`main.py`)** でログデータを正しく比較・可視化するためのデータ出力フォーマット仕様（最低必要仕様および推奨仕様）をまとめたものです。

シミュレーションプログラムや強化学習実験で出力ログを実装する際の参考にしてください。

---

## 1. ディレクトリ構造・命名規則

### 最低必須仕様
- **認識単位**: 1回の実験ごとに生成される独立したフォルダ単位（例: `output_20260801_235449`）。
- **フォルダ命名**: フォルダ名内に `YYYYMMDD_HHMMSS`（数字8桁_数字6桁）のタイムスタンプを含むこと。

### 推奨構造
カテゴリ（学習モード・アルゴリズム名など）ごとにサブフォルダを作成し、その中に各回の実験出力フォルダを保存することを推奨します。

```text
output_robotino_rl_control/            <-- アルゴリズムルート (2階層上)
├── S-SAP/                              <-- 学習モード名 (1階層上: 例 S-SAP, Q-SAP, RL)
│   ├── output_20260801_235449/         <-- 実験出力フォルダ
│   │   ├── config_used_20260801_235449.yaml
│   │   ├── learning_log_20260801_235449.csv
│   │   ├── learning_rewards_20260801_235449.png
│   │   ├── learning_steps_20260801_235449.png
│   │   └── trajectory_20260801_235449.png
│   └── output_20260801_235343/
└── Q-SAP/
    └── output_20260801_181036/
```

---

## 2. ハイパーパラメータ設定ファイル (YAML)

アプリの **「2. ハイパーパラメータ差分 (YAML)」** タブでツリー比較されます（「1. 実験ログ一覧・探索」タブでは表形式でパラメータ一覧表示されます）。

| 項目 | 最低仕様 | 推奨仕様 |
| :--- | :--- | :--- |
| **ファイル名** | フォルダ内に任意の `*.yaml` が1つ以上 | **`config_used_{タイムスタンプ}.yaml`** |
| **フォーマット** | 標準 YAML 形式（UTF-8） | 構造化されたネスト辞書形式 |
| **必須/推奨キー** | 任意（空でなければ表示可） | **`mode`** または **`algorithm`**（ヘッダー表示用） |

### サンプル YAML (`config_used_20260801_235449.yaml`)
```yaml
mode: S-SAP
seed: 42
learning_rate: 0.001
gamma: 0.99
max_episodes: 500
reward_settings:
  goal_reward: 100.0
  collision_penalty: -100.0
  step_penalty: -0.1
```

---

## 3. 同種画像ファイル (PNG)

アプリの **「3. 画像目視比較 (Side-by-Side)」** タブで左右並列同期表示されます（「1. 実験ログ一覧・探索」タブではプレビュータブで確認できます）。

| 項目 | 最低仕様 | 推奨仕様 |
| :--- | :--- | :--- |
| **拡張子** | `.png` 画像 | `.png` 画像 |
| **命名規則** | `{種別名}_{タイムスタンプ}.png` | `{種別名}_{タイムスタンプ}.png` |

- 末尾のタイムスタンプ（`_YYYYMMDD_HHMMSS`）が自動除去され、同じ `{種別名}` の画像が自動的に比較対象ペアとなります。

### 推奨画像種別例
- `learning_rewards_{タイムスタンプ}.png`: エピソードごとの報酬推移グラフ
- `learning_steps_{タイムスタンプ}.png`: エピソードごとのステップ数推移グラフ
- `trajectory_{タイムスタンプ}.png`: ロボットの移動軌跡描画画像

---

## 4. 数値ログファイル (CSV)

アプリの **「4. 数値ログ比較グラフ (CSV)」** タブで移動平均付き重ね合わせ折れ線グラフとしてプロットされます。


| 項目 | 最低仕様 | 推奨仕様 |
| :--- | :--- | :--- |
| **ファイル名** | フォルダ内に任意の `*.csv` が1つ以上 | **`learning_log_{タイムスタンプ}.csv`** |
| **フォーマット** | 1行目にヘッダー名を含む標準 CSV | カンマ区切り CSV (UTF-8) |
| **X軸キー** | **`Episode`** カラム (整数) | `Episode` (1, 2, 3, ...) |

### 対応Y軸指標カラム（ヘッダー名）
以下のカラム名が含まれる場合、自動的にグラフ選択リストへ登録されます：

- **`TotalReward`**: エピソードごとの累計報酬（数値型）
- **`Steps`**: エピソードごとの所要ステップ数（数値型）
- **`UnsafeActions`**: エピソードごとの安全違反・作動回数（数値型）
- **`Result`**: エピソード結果文字列（値が `'Goal'` のエピソードの移動平均成功率 `%` を算定）

### サンプル CSV (`learning_log_20260801_235449.csv`)
```csv
Episode,Steps,TotalReward,Result,UnsafeActions
1,46,-80.718,Collision,3
2,162,-210.691,Collision,2
3,387,-488.815,Goal,0
4,425,-524.488,Goal,1
5,500,-555.676,Timeout,0
```

---

## 5. シミュレーション共通モジュールとの連携

シミュレーション共通モジュール（例: `Webots_omni-wheel-RL` の `controllers/common/`）は、本仕様に完全準拠した出力を自動生成します：

1. **`ExperimentManager` (`experiment_manager.py`)**:
   - `output_YYYYMMDD_HHMMSS` フォルダを自動生成し、実行時設定 `config_used_YYYYMMDD_HHMMSS.yaml` をバックアップ保存。
2. **`CSVLogger` (`csv_logger.py`)**:
   - `learning_log_YYYYMMDD_HHMMSS.csv` に各エピソードの `Episode`, `Steps`, `TotalReward`, `Result`, `UnsafeActions` を自動記録。
3. **`TrajectoryPlotter` / `LearningStatsPlotter` (`plotters.py`)**:
   - 終了時に `trajectory_*.png`, `learning_rewards_*.png`, `learning_steps_*.png` を自動生成。

