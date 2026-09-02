"""
数値ログ (CSV) 読み込みおよび指標・移動平均計算モジュール（Qt非依存）
"""

import os
import glob
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


METRIC_DEFINITIONS = [
    ("TotalReward (累計報酬)", 0, "TotalReward", "Total Reward"),
    ("Steps (エピソードステップ数)", 1, "Steps", "Steps per Episode"),
    ("UnsafeActions (安全違反回数)", 2, "UnsafeActions", "Unsafe Actions Count"),
    ("GoalSuccessRate (成功率 %)", 3, "GoalSuccessRate", "Goal Success Rate (%)"),
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


def read_log_csv(folder_path: str) -> Optional[pd.DataFrame]:
    """フォルダ内の learning_log_*.csv (または *.csv) を安全に読み込んで DataFrame を返す"""
    if not folder_path or not os.path.isdir(folder_path):
        return None
    csv_files = glob.glob(os.path.join(folder_path, "learning_log_*.csv"))
    if not csv_files:
        csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not csv_files:
        return None
    try:
        df = pd.read_csv(csv_files[0])
        if 'Episode' not in df.columns:
            df['Episode'] = np.arange(1, len(df) + 1)
        return df
    except Exception as e:
        print(f"[ERROR] Failed to read CSV ({csv_files[0]}): {e}")
        return None


def compute_metric_series(
    df: Optional[pd.DataFrame],
    metric_idx: int,
    window: int,
    label_prefix: str
) -> MetricSeriesData:
    """
    指定された DataFrame から指標値系列（生データおよび移動平均）を計算する。
    """
    if df is None or len(df) == 0:
        return MetricSeriesData(has_data=False)

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

    x = df['Episode'].values

    if col_name == "GoalSuccessRate":
        if 'Result' in df.columns:
            is_goal = (df['Result'] == 'Goal').astype(float) * 100.0
            ma_vals = is_goal.rolling(window=window, min_periods=1).mean().values
            return MetricSeriesData(
                has_data=True,
                x=x,
                y_raw=None,  # 成功率は生データなし（移動平均のみ）
                y_ma=ma_vals,
                legend_label_ma=f"{label_prefix} (成功率)",
                y_label=y_label
            )
        return MetricSeriesData(has_data=False, y_label=y_label)

    elif col_name in df.columns:
        y = df[col_name].values
        ma_vals = pd.Series(y).rolling(window=window, min_periods=1).mean().values
        return MetricSeriesData(
            has_data=True,
            x=x,
            y_raw=y,
            y_ma=ma_vals,
            legend_label_ma=f"{label_prefix} (移動平均: {window}ep)",
            y_label=y_label
        )

    return MetricSeriesData(has_data=False, y_label=y_label)
