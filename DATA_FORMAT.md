# RL-Log-Comparator ログデータ フォーマット仕様書 (Log Data Format Specification)

本ドキュメントは、**RL-Log-Comparator (`main.py`)** でログデータを正しく比較・可視化するためのデータ出力フォーマット仕様をまとめたものです。

本ツールは **「極小の必須要件（CSV 1枚から即使える汎用モード）」** と、**「高度な分析機能（タスク境界線・収束マーカー・画像ペアリングを活用する推奨モード）」** の2つのレベルをサポートしています。

> [!TIP]
> **実動サンプルデータについて**:  
> リポジトリ内の [`sample_logs/`](./sample_logs/) フォルダに、最小構成および推奨構成（通常RL、SAP-net、継続学習）のサンプル実験ログがすべて同梱されています。本アプリを起動し、フォルダA/Bとして選択することで各機能の動作を即座に確認できます。詳細は [`sample_logs/README.md`](./sample_logs/README.md) をご覧ください。

---

# 第1部: 汎用強化学習ログ 最小仕様 (Minimum Viable Specification)

OpenAI Gym / Gymnasium、Stable-Baselines3、CleanRL、自作強化学習環境など、任意の強化学習アルゴリズムの実験結果を本アプリで比較・分析するための仕様です。

## 1. ディレクトリ構造
- **必須要件**: 1回の実験ごとに生成される**独立したフォルダが1つ**存在すること。
- **フォルダ名**: 任意の名前（例: `ppo_cartpole_run1`, `dqn_seed42`, `experiment_A` 等）。
  - ※タイムスタンプ（`YYYYMMDD_HHMMSS`）が含まれない場合、フォルダの最終更新日時が自動的に一覧画面の日時として表示されます。

```text
experiments/                      <-- 実験保存ルート
├── exp_dqn_01/                   <-- 実験Aのフォルダ（名前自由）
│   ├── progress.csv              <-- 任意の名前のCSV（1列以上数値があればOK）
│   ├── config.json (任意)        <-- ハイパーパラメータ
│   └── plot.jpg (任意)           <-- 任意のグラフやレンダリング画像
└── exp_ppo_02/                   <-- 実験Bのフォルダ
    ├── progress.csv
    ├── config.yaml (任意)
    └── plot.png (任意)
```

## 2. 数値ログ (CSV) の最小仕様
- **ファイル名**: フォルダ内に任意の `*.csv` が1つ以上（`learning_log_*.csv` または最初の `.csv` を自動認識）。
- **ヘッダー行**: 1行目にカラム名を含むカンマ区切り形式。
- **X軸（横軸）**: 
  - `Episode`, `Total_Episode`, `step`, `epoch`, `iteration` 等の列があればそれをX軸として使用。
  - いずれの列も存在しない場合は、**「行番号（1, 2, 3...）」が自動的にエピソード番号**として補完されます。
- **Y軸（指標）の自動検出と自由プロット**:
  - CSVに含まれるすべての数値列（`loss`, `critic_loss`, `actor_loss`, `entropy`, `q_value`, `epsilon` 等）を自動抽出し、ドロップダウンで自由に選択・移動平均重ね合わせ比較できます。
  - 片方の実験CSVにしか存在しない指標列（例: Aのみ `actor_loss` がある等）でも、エラーを起こさず片側のみ安全にプロットされます。

### 主要指標のエイリアス（表記ゆれ自動認識）
以下のカラム名が含まれている場合、アプリ起動時に主要指標として最上部に優先表示されます：

| 指標 | 対応する列名エイリアス（大文字小文字無視） |
| :--- | :--- |
| **報酬 (Reward)** | `TotalReward`, `reward`, `episode_reward`, `total_reward`, `return`, `r`, `ep_rew_mean` |
| **ステップ数 (Steps)** | `Steps`, `steps`, `episode_length`, `episode_steps`, `length`, `step`, `l`, `ep_len_mean` |
| **成功率 (Success Rate)** | `Result` (`'Goal'` 判定), `success`, `is_success`, `success_rate` (0/1 または bool) |

### 最小限の CSV 例 (`progress.csv`)
```csv
step,reward,loss,entropy
100,-150.2,0.45,1.20
200,-120.0,0.38,1.15
300,-35.5,0.12,0.85
```

## 3. 設定ファイル (YAML / JSON)
- **拡張子**: `.yaml`, `.yml`, `.json`
- **ファイル名**: `config_used_*.yaml`, `config*.json`, `params*.json`, またはフォルダ内の最初の設定ファイル。
- 形式は任意で、キー・バリューのツリー構造が「2. ハイパーパラメータ差分」タブで階層比較されます。

## 4. 可視化画像 (PNG / JPG / WebP 等)
- **拡張子**: `.png`, `.jpg`, `.jpeg`, `.bmp`, `.webp`（大文字小文字無視）。
- ファイル名が異なる画像同士でも、「3. 画像目視比較」タブの**「左右自由選択モード」**をONにすることで、左右それぞれ自由に選んで並列比較できます。

---

# 第2部: 本研究室 推奨拡張仕様 (Webots / S-SAP / Continual Learning)

ロボット移動制御や継続学習（Continual Learning）において、**タスク境界線の自動描画・収束マーカー表示・同種画像自動同期**などの高度な機能をフル活用するための推奨仕様です。

## 1. 推奨ディレクトリ構造
```text
output_robotino_rl_control/            <-- アルゴリズムルート
├── S-SAP_continual/                    <-- 学習モード名
│   ├── output_20260924_181649/         <-- 実験出力フォルダ (output_YYYYMMDD_HHMMSS)
│   │   ├── config_used_20260924_181649.yaml
│   │   ├── learning_log_20260924_181649.csv
│   │   ├── continual_learning_curve_20260924_181649.png
│   │   ├── learning_rewards_20260924_181649_task_1.png
│   │   ├── learning_steps_20260924_181649_task_1.png
│   │   └── trajectory_20260924_181649.png
```

## 2. 数値ログ形式 (CSV)

### 2.1 継続学習モード (14列フォーマット)
全タスク統合ログ (`learning_log_{タイムスタンプ}.csv`)：

```csv
Task_ID,Task_Episode,Total_Episode,Goal_X,Goal_Y,Steps,TotalReward,Result,Final_X,Final_Y,Is_Converged,Acquired_Policies,UnsafeActions,SAP_Plan
1,1,1,11.0,3.0,100,66.9,Goal,10.7,2.8,False,0,1,
1,30,30,11.0,3.0,67,100.3,Goal,10.7,2.9,True,0,0,
2,1,31,15.0,5.0,95,-30.2,Collision,12.1,3.4,False,1,2,0
```

- **`Total_Episode`**: 実験開始からの通算エピソード番号（全タスク統合表示時のX軸）。
- **`Task_Episode`**: タスク内エピソード番号（タスク絞り込み時の1始まりX軸）。
- **`Task_ID`**: タスク番号（切り替え地点にタスク境界縦破線を描画）。
- **`Is_Converged`**: 収束判定フラグ（True地点に星型マーカー ★ を重畳描画）。
- **`Acquired_Policies`**: その時点で蓄積された知識ポリシー数。
- **`Goal_X`, `Goal_Y`, `Final_X`, `Final_Y`**: ゴール残距離の算出に使用。

### 2.2 単一学習モード (8列フォーマット)
従来の単一ゴール学習用CSV：

```csv
Episode,Steps,TotalReward,Result,Final_X,Final_Y,UnsafeActions,SAP_Plan
1,46,-80.718,Collision,5.2,1.1,3,None
2,162,-210.691,Collision,8.3,2.4,2,None
3,387,-488.815,Goal,11.0,3.0,0,None
```

## 3. 推奨画像命名規則
`{種別名}_{タイムスタンプ}.png` の形式で出力すると、タイムスタンプが自動除去され、左右の同種画像が自動ペアリングされます。

- **単一学習モード**:
  - `learning_rewards_{タイムスタンプ}.png`: 全エピソードの報酬推移グラフ
  - `learning_steps_{タイムスタンプ}.png`: 全エピソードのステップ数推移グラフ
  - `trajectory_{タイムスタンプ}.png`: ロボットの移動軌跡描画画像
- **継続学習モード**:
  - `continual_learning_curve_{タイムスタンプ}.png`: 全タスク統合学習曲線グラフ（単一学習の `learning_rewards` と自動ペアリング）
  - `learning_rewards_{タイムスタンプ}_task_{id}.png`: タスク別の報酬推移グラフ
  - `learning_steps_{タイムスタンプ}_task_{id}.png`: タスク別のステップ数推移グラフ
  - `trajectory_{タイムスタンプ}.png`: 最終エピソードの走行軌跡画像

---

## 4. シミュレーション共通モジュールとの連携

シミュレーション共通モジュール（例: `Webots_omni-wheel-RL` の `controllers/common/`）は、本仕様に完全準拠した出力を自動生成します：

1. **`ExperimentManager` (`experiment_manager.py`)**:
   - `output_YYYYMMDD_HHMMSS` フォルダを自動生成し、実行時設定 `config_used_YYYYMMDD_HHMMSS.yaml` をバックアップ保存。
2. **`CSVLogger` (`csv_logger.py`)**:
   - 単一モード時は8列、継続学習モード時は14列の `learning_log_*.csv` を自動記録。
3. **`TrajectoryPlotter` / `LearningStatsPlotter` (`plotters.py`)**:
   - 単一モード時は `trajectory_*.png`, `learning_rewards_*.png`, `learning_steps_*.png` を出力。
   - 継続学習モード時は `continual_learning_curve_*.png` およびタスク別 `learning_rewards_*_task_*.png`, `learning_steps_*_task_*.png` を自動生成。
