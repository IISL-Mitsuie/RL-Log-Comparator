"""
数値ログ (CSV) 読み込みおよび指標・移動平均計算モジュール（Qt非依存）
単一学習ログ（8列）および継続学習ログ（14列）に完全対応し、
通算/タスク内エピソード、タスク境界線、収束マーカー、および各種メトリックの抽出をサポート。
"""

import os
import glob
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd


METRIC_DEFINITIONS = [
    ("TotalReward (累計報酬)", 0, "TotalReward", "Total Reward"),
    ("Steps (エピソードステップ数)", 1, "Steps", "Steps per Episode"),
    ("UnsafeActions (安全違反回数)", 2, "UnsafeActions", "Unsafe Actions Count"),
    ("GoalSuccessRate (成功率 %)", 3, "GoalSuccessRate", "Goal Success Rate (%)"),
    ("Acquired_Policies (知識獲得数)", 4, "Acquired_Policies", "Acquired Policies"),
    ("GoalDistance (ゴール残距離 m)", 5, "GoalDistance", "Distance to Goal (m)"),
    ("CollisionRate (衝突率 %)", 6, "CollisionRate", "Collision Rate (%)"),
]


@dataclass
class MetricSeriesData:
    """プロット用の計算済み系列データ"""
    has_data: bool
    x: Optional[np.ndarray] = None
    y_raw: Optional[np.ndarray] = None
    y_ma: Optional[np.ndarray] = None
    legend_label_ma: str = ""
    y_label: str = ""
    # 継続学習用メタデータ
    task_boundaries: list[tuple[int, str]] = field(default_factory=list)  # [(境界エピソード, "Task 2" 等)]
    converged_episodes: list[int] = field(default_factory=list)          # 収束したエピソード番号リスト
    converged_y_values: list[float] = field(default_factory=list)        # 収束時の指標値（マーカー描画用）


def read_log_csv(folder_path: str) -> Optional[pd.DataFrame]:
    """
    フォルダ内の learning_log_*.csv (または *.csv) を安全に読み込んで DataFrame を返す。
    _task_ を含まない全タスク統合CSVを最優先でロードする。
    """
    if not folder_path or not os.path.isdir(folder_path):
        return None

    csv_candidates = sorted(glob.glob(os.path.join(folder_path, "learning_log_*.csv")))
    main_csvs = [p for p in csv_candidates if "_task_" not in os.path.basename(p)]

    target_csv = None
    if main_csvs:
        target_csv = main_csvs[0]
    elif csv_candidates:
        target_csv = csv_candidates[0]
    else:
        other_csvs = sorted(glob.glob(os.path.join(folder_path, "*.csv")))
        if other_csvs:
            target_csv = other_csvs[0]

    if not target_csv:
        return None

    try:
        df = pd.read_csv(target_csv)
        # エピソード列の正規化
        if 'Episode' not in df.columns:
            if 'Total_Episode' in df.columns:
                df['Episode'] = df['Total_Episode']
            else:
                df['Episode'] = np.arange(1, len(df) + 1)

        # 収束列 (Is_Converged) を bool 型に正規化
        if 'Is_Converged' in df.columns:
            if df['Is_Converged'].dtype != bool:
                df['Is_Converged'] = df['Is_Converged'].astype(str).str.lower().isin(['true', '1'])

        return df
    except Exception as e:
        print(f"[ERROR] Failed to read CSV ({target_csv}): {e}")
        return None


def get_available_tasks(df: Optional[pd.DataFrame]) -> list[tuple[int, str]]:
    """
    DataFrame に含まれるタスク一覧を [(task_id, 表示名), ...] の形式で返す。
    task_id 0 は常に「全タスク統合 (通算エピソード)」を表す。
    """
    default_list = [(0, "全タスク統合 (通算エピソード)")]
    if df is None or len(df) == 0 or 'Task_ID' not in df.columns:
        return default_list

    unique_tasks = sorted(df['Task_ID'].dropna().unique())
    if not unique_tasks:
        return default_list

    tasks = [(0, "全タスク統合 (通算エピソード)")]
    for t_id in unique_tasks:
        try:
            t_int = int(t_id)
        except (ValueError, TypeError):
            continue

        # タスク内のゴール座標を取得（存在する場合）
        sub = df[df['Task_ID'] == t_id]
        goal_desc = ""
        if 'Goal_X' in sub.columns and 'Goal_Y' in sub.columns and not sub.empty:
            gx = sub['Goal_X'].iloc[0]
            gy = sub['Goal_Y'].iloc[0]
            goal_desc = f" (Goal: [{gx:.1f}, {gy:.1f}])"

        # 非登録タスクの識別（Acquired_Policies が増加しない、または設定等）
        is_unregistered = False
        if 'Acquired_Policies' in sub.columns and len(sub) > 0:
            # タスク内最後の Acquired_Policies が直前と変わらないなどの判定
            pass

        tasks.append((t_int, f"Task {t_int}{goal_desc}"))

    return tasks


def compute_metric_series(
    df: Optional[pd.DataFrame],
    metric_idx: int,
    window: int,
    label_prefix: str,
    task_filter_id: int = 0
) -> MetricSeriesData:
    """
    指定された DataFrame から指標値系列（生データおよび移動平均）を計算する。
    task_filter_id > 0 の場合は特定タスクに絞り込み、Task_Episode を 1 始まりの X 軸とする（案A）。
    task_filter_id == 0 の場合は全タスク統合とし、タスク境界線および収束ポイントを抽出する。
    """
    if df is None or len(df) == 0:
        return MetricSeriesData(has_data=False)

    target_df = df
    is_task_filtered = False

    # 1. タスクフィルタリング（案A: タスク内エピソード基準）
    if task_filter_id > 0 and 'Task_ID' in df.columns:
        target_df = df[df['Task_ID'] == task_filter_id].copy()
        if len(target_df) == 0:
            return MetricSeriesData(has_data=False)
        is_task_filtered = True

    # 2. X 軸の決定
    if is_task_filtered:
        if 'Task_Episode' in target_df.columns:
            x = target_df['Task_Episode'].values
        else:
            x = np.arange(1, len(target_df) + 1)
    else:
        if 'Episode' not in target_df.columns:
            if 'Total_Episode' in target_df.columns:
                target_df = target_df.copy()
                target_df['Episode'] = target_df['Total_Episode']
            else:
                target_df = target_df.copy()
                target_df['Episode'] = np.arange(1, len(target_df) + 1)
        x = target_df['Episode'].values

    # 3. 指標の特定とデータ算出
    col_name = "TotalReward"
    y_label = "Total Reward"
    if metric_idx == 1:
        col_name = "Steps"
        y_label = "Steps per Episode"
    elif metric_idx == 2:
        col_name = "UnsafeActions"
        y_label = "Unsafe Actions Count"
    elif metric_idx == 3:
        col_name = "GoalSuccessRate"
        y_label = f"Goal Success Rate (% [{window} ep MA])"
    elif metric_idx == 4:
        col_name = "Acquired_Policies"
        y_label = "Acquired Policies"
    elif metric_idx == 5:
        col_name = "GoalDistance"
        y_label = "Distance to Goal (m)"
    elif metric_idx == 6:
        col_name = "CollisionRate"
        y_label = f"Collision Rate (% [{window} ep MA])"

    # 成功率 (GoalSuccessRate)
    if col_name == "GoalSuccessRate":
        if 'Result' in target_df.columns:
            is_goal = (target_df['Result'] == 'Goal').astype(float) * 100.0
            ma_vals = is_goal.rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (成功率)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # 衝突率 (CollisionRate)
    elif col_name == "CollisionRate":
        if 'Result' in target_df.columns:
            is_collision = (target_df['Result'] == 'Collision').astype(float) * 100.0
            ma_vals = is_collision.rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (衝突率)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # ゴール残距離 (GoalDistance)
    elif col_name == "GoalDistance":
        required_cols = {'Goal_X', 'Goal_Y', 'Final_X', 'Final_Y'}
        if required_cols.issubset(target_df.columns):
            dx = target_df['Goal_X'] - target_df['Final_X']
            dy = target_df['Goal_Y'] - target_df['Final_Y']
            dist = np.sqrt(dx**2 + dy**2).values
            ma_vals = pd.Series(dist).rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, dist, ma_vals, f"{label_prefix} (ゴール残距離)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # 知識獲得数 (Acquired_Policies)
    elif col_name == "Acquired_Policies":
        if 'Acquired_Policies' in target_df.columns:
            y = target_df['Acquired_Policies'].values
            return _build_metric_result(target_df, x, y, y, f"{label_prefix} (知識獲得数)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # 一般指標 (TotalReward, Steps, UnsafeActions 等)
    elif col_name in target_df.columns:
        y = target_df[col_name].values
        ma_vals = pd.Series(y).rolling(window=window, min_periods=1).mean().values
        return _build_metric_result(target_df, x, y, ma_vals, f"{label_prefix} (移動平均: {window}ep)", y_label, is_task_filtered)

    return MetricSeriesData(has_data=False, y_label=y_label)


def _build_metric_result(
    df: pd.DataFrame,
    x: np.ndarray,
    y_raw: Optional[np.ndarray],
    y_ma: Optional[np.ndarray],
    legend_label_ma: str,
    y_label: str,
    is_task_filtered: bool
) -> MetricSeriesData:
    """タスク境界線および収束ポイントを付加した MetricSeriesData を構築"""
    task_boundaries: list[tuple[int, str]] = []
    converged_episodes: list[int] = []
    converged_y_values: list[float] = []

    # 統合表示（タスクフィルタなし）の場合のみ境界線と収束ポイントを抽出
    if not is_task_filtered:
        if 'Task_ID' in df.columns:
            # Task_ID の変化点を抽出
            task_diff = df['Task_ID'].diff()
            boundary_indices = np.where(task_diff != 0)[0]
            for idx in boundary_indices:
                if idx > 0:  # 先頭行以外
                    ep_val = int(df['Episode'].iloc[idx])
                    task_id_val = int(df['Task_ID'].iloc[idx])
                    task_boundaries.append((ep_val, f"Task {task_id_val}"))

        if 'Is_Converged' in df.columns:
            conv_mask = (df['Is_Converged'] == True).values
            if np.any(conv_mask):
                conv_indices = np.where(conv_mask)[0]
                for idx in conv_indices:
                    ep_val = int(df['Episode'].iloc[idx])
                    converged_episodes.append(ep_val)
                    # マーカー用のY値（移動平均または生データ）
                    if y_ma is not None:
                        converged_y_values.append(float(y_ma[idx]))
                    elif y_raw is not None:
                        converged_y_values.append(float(y_raw[idx]))
                    else:
                        converged_y_values.append(0.0)

    return MetricSeriesData(
        has_data=True,
        x=x,
        y_raw=y_raw,
        y_ma=y_ma,
        legend_label_ma=legend_label_ma,
        y_label=y_label,
        task_boundaries=task_boundaries,
        converged_episodes=converged_episodes,
        converged_y_values=converged_y_values
    )
