# サンプル実験ログデータ (Sample Experiment Logs)

本ディレクトリには、**RL-Log-Comparator** の全機能をすぐに試せるサンプル実験ログデータがまとめられています。  
各カテゴリごとに **2つの実験（Run A / Run B）** が用意されており、アプリ起動後に「フォルダA」「フォルダB」として選択することで、比較グラフ・ハイパーパラメータ差分・画像並列比較を即座に体験できます。

---

## ディレクトリ構成一覧

```text
sample_logs/
├── 1_minimal_generic_rl/            <-- 最小構成（汎用強化学習ログ）
│   ├── exp_cartpole_dqn/            <-- 実験A: DQN (CartPole-v1)
│   │   ├── progress.csv             <-- step, reward, loss, q_value, epsilon
│   │   ├── config.json              <-- JSON形式の設定ファイル
│   │   └── eval_curve.png           <-- 学習曲線画像
│   └── exp_cartpole_ppo/            <-- 実験B: PPO (CartPole-v1)
│       ├── progress.csv             <-- step, reward, actor_loss, critic_loss, entropy
│       ├── params.json              <-- JSON形式の設定ファイル
│       └── eval_curve.png           <-- 学習曲線画像
│
├── 2_recommended_standard_rl/       <-- 推奨構成: 通常の強化学習（単一ゴール学習）
│   ├── output_20260901_100000/      <-- 実験A: Q-Learning ベースライン
│   │   ├── config_used_20260901_100000.yaml
│   │   ├── learning_log_20260901_100000.csv (8列形式)
│   │   ├── learning_rewards_20260901_100000.png
│   │   ├── learning_steps_20260901_100000.png
│   │   └── trajectory_20260901_100000.png
│   └── output_20260901_120000/      <-- 実験B: Q-Learning パラメータ調整版
│       ├── config_used_20260901_120000.yaml
│       ├── learning_log_20260901_120000.csv
│       ├── learning_rewards_20260901_120000.png
│       ├── learning_steps_20260901_120000.png
│       └── trajectory_20260901_120000.png
│
├── 3_recommended_sap_net/           <-- 推奨構成: SAP-net（単一ゴール＋安全性学習）
│   ├── output_20260905_140000/      <-- 実験A: 安全重み λ = 0.5
│   │   ├── config_used_20260905_140000.yaml
│   │   ├── learning_log_20260905_140000.csv (8列形式: UnsafeActions/SAP_Plan含む)
│   │   ├── learning_rewards_20260905_140000.png
│   │   ├── learning_steps_20260905_140000.png
│   │   └── trajectory_20260905_140000.png
│   └── output_20260905_160000/      <-- 実験B: 安全重み λ = 0.8
│       ├── config_used_20260905_160000.yaml
│       ├── learning_log_20260905_160000.csv
│       ├── learning_rewards_20260905_160000.png
│       ├── learning_steps_20260905_160000.png
│       └── trajectory_20260905_160000.png
│
└── 4_recommended_continual_learning/ <-- 推奨構成: 継続学習（S-SAP Continual Learning）
    ├── output_20260920_100000/      <-- 実験A: 3タスク継続学習 ベースライン
    │   ├── config_used_20260920_100000.yaml
    │   ├── learning_log_20260920_100000.csv (14列形式)
    │   ├── continual_learning_curve_20260920_100000.png
    │   ├── learning_rewards_20260920_100000_task_1.png 〜 task_3.png
    │   ├── learning_steps_20260920_100000_task_1.png 〜 task_3.png
    │   └── trajectory_20260920_100000.png
    └── output_20260920_150000/      <-- 実験B: 知識転移ブースト適用版
        ├── config_used_20260920_150000.yaml
        ├── learning_log_20260920_150000.csv
        ├── continual_learning_curve_20260920_150000.png
        ├── learning_rewards_20260920_150000_task_1.png 〜 task_3.png
        ├── learning_steps_20260920_150000_task_1.png 〜 task_3.png
        └── trajectory_20260920_150000.png
```

---

## 各サンプルの特徴と確認ポイント

### 1. 最小構成 (`1_minimal_generic_rl`)
OpenAI Gym / Gymnasium、Stable-Baselines3、CleanRL などで出力される一般的なログの構成です。
- **特徴**:
  - フォルダ名任意（タイムスタンプなしでも更新日時で自動認識）。
  - `progress.csv`（`step` 列をX軸として自動使用、主要指標 `reward` に加え、`loss`, `q_value`, `actor_loss`, `entropy` 等の任意数値を検出）。
  - 設定ファイルは `config.json`, `params.json`（JSON対応）。
- **アプリでの確認ポイント**:
  - **グラフ比較**: `q_value`（Aのみ存在）や `actor_loss`（Bのみ存在）を選択してもエラーにならず、片側のみ安全に折れ線が描画されることを確認できます。
  - **設定差分**: JSONファイル同士の階層差分（`algorithm`, `learning_rate` 等）が表示されます。
  - **画像比較**: 「左右自由選択モード」で `eval_curve.png` を並列目視比較できます。

### 2. 推奨構成: 通常の強化学習 (`2_recommended_standard_rl`)
本研究室のロボット強化学習シミュレータにおける単一ゴール学習の標準出力構成です。
- **特徴**:
  - 8列CSVフォーマット（`Episode`, `Steps`, `TotalReward`, `Result`, `Final_X`, `Final_Y`, `UnsafeActions`, `SAP_Plan`）。
  - `config_used_*.yaml` による詳細なハイパーパラメータ保存。
  - 同種画像（`learning_rewards_*.png`, `learning_steps_*.png`, `trajectory_*.png`）の命名規則準拠。
- **アプリでの確認ポイント**:
  - **主要指標**: 報酬推移、ステップ数、成功率（Goal判定）が自動計算されて滑らかに比較できます。
  - **画像同期**: タイムスタンプが異なっても左右の画像が自動ペアリングされます。

### 3. 推奨構成: SAP-net (`3_recommended_sap_net`)
安全性評価・衝突回避制御を組み込んだ SAP-net アルゴリズムの出力構成です。
- **特徴**:
  - CSV内に不安全行動カウント `UnsafeActions` および介入プラン `SAP_Plan` を記録。
  - 設定ファイルに安全性制御パラメータ（`safety_weight_lambda`, `danger_threshold` 等）を保持。
- **アプリでの確認ポイント**:
  - 安全性の向上に伴い `UnsafeActions` が0に収束していく過程をグラフで比較できます。
  - ハイパーパラメータ差分タブで安全重み λ の違いを一目で比較できます。

### 4. 推奨構成: 継続学習 (`4_recommended_continual_learning`)
環境やゴールが変化するマルチタスク継続学習（S-SAP Continual Learning）の出力構成です。
- **特徴**:
  - 14列CSVフォーマット（`Task_ID`, `Task_Episode`, `Total_Episode`, `Is_Converged`, `Acquired_Policies` 等）。
  - タスク境界（縦破線）および収束地点（星型マーカー ★）のメタデータを保持。
  - 全タスク統合曲線 `continual_learning_curve_*.png` と各タスク別画像を出力。
- **アプリでの確認ポイント**:
  - **タスク境界線**: タスク切り替え地点に縦破線が描画され、タスク間の干渉や転移を確認できます。
  - **収束マーカー**: 収束判定地点に星型マーカーが表示されます。
  - **タスク絞り込み**: コンボボックスで「全タスク統合」や「Task 1 のみ」などを切り替えて詳細分析が可能です。
