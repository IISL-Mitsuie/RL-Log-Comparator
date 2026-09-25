"""
数値ログ (CSV) 読み込みおよび指標・移動平均計算モジュール（Qt非依存）
単一学習ログ（8列）および継続学習ログ（14列）に完全対応し、
通算/タスク内エピソード、タスク境界線、収束マーカー、および各種メトリックの抽出をサポート。
"""

import os
import glob
from dataclasses import dataclass, field
from typing import Optional, Union
import numpy as np
import pandas as pd


# 従来の標準指標定義 (後方互換用)
METRIC_DEFINITIONS = [
    ("TotalReward (累計報酬)", 0, "TotalReward", "Total Reward"),
    ("Steps (エピソードステップ数)", 1, "Steps", "Steps per Episode"),
    ("UnsafeActions (安全違反回数)", 2, "UnsafeActions", "Unsafe Actions Count"),
    ("GoalSuccessRate (成功率 %)", 3, "GoalSuccessRate", "Goal Success Rate (%)"),
    ("Acquired_Policies (知識獲得数)", 4, "Acquired_Policies", "Acquired Policies"),
    ("GoalDistance (ゴール残距離 m)", 5, "GoalDistance", "Distance to Goal (m)"),
    ("CollisionRate (衝突率 %)", 6, "CollisionRate", "Collision Rate (%)"),
]


# 代表的な指標名のエイリアス（小文字比較用）
REWARD_ALIASES = [
    "totalreward", "reward", "episode_reward", "total_reward",
    "return", "episode_return", "r", "ep_rew_mean", "mean_reward"
]

STEPS_ALIASES = [
    "steps", "episode_steps", "episode_step", "episode_length",
    "ep_len_mean", "length", "step", "l"
]

SUCCESS_ALIASES = [
    "success", "is_success", "goalsuccessrate", "success_rate"
]

COLLISION_ALIASES = [
    "collision", "is_collision", "collisionrate", "collision_rate"
]

# X軸候補列・メタデータ列（指標一覧から除外）
EXCLUDE_COLUMNS = {
    "episode", "total_episode", "task_episode", "task_id",
    "step", "steps", "epoch", "iteration", "sap_plan"
}


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


@dataclass
class MetricItemInfo:
    """UI 表示用および計算用の指標メタデータ"""
    display_name: str
    key: str                    # '__reward__', '__steps__', または生の列名 ('loss' 等)
    category: str               # 'primary' (主要), 'domain' (独自ドメイン), 'generic' (その他数値列)
    metric_idx: Optional[int] = None  # 従来の 0..6 との互換インデックス (任意)


def find_column_by_aliases(df: Optional[pd.DataFrame], aliases: list[str]) -> Optional[str]:
    """DataFrame の列からエイリアスリストにマッチする列名を大文字小文字無視で探す"""
    if df is None or df.empty:
        return None
    lower_to_col = {str(col).lower(): str(col) for col in df.columns}
    for alias in aliases:
        if alias.lower() in lower_to_col:
            return lower_to_col[alias.lower()]
    return None


def get_available_numeric_columns(df: Optional[pd.DataFrame]) -> list[str]:
    """DataFrame に含まれるプロット可能な数値列（X軸・管理列を除く）をリストで返す"""
    if df is None or df.empty:
        return []
    numeric_cols: list[str] = []
    for col in df.columns:
        col_str = str(col)
        if col_str.lower() in EXCLUDE_COLUMNS:
            continue
        # 数値型（int, float）または bool 型かチェック
        if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_bool_dtype(df[col]):
            numeric_cols.append(col_str)
    return numeric_cols


def get_available_metrics(
    df_a: Optional[pd.DataFrame] = None,
    df_b: Optional[pd.DataFrame] = None
) -> list[MetricItemInfo]:
    """
    フォルダ A および B の DataFrame から利用可能な指標一覧を生成する（案A: カテゴリ別グループ化）。
    上部: 主要強化学習指標 (報酬, ステップ数, 成功率)
    中部: ドメイン固有指標 (ゴール残距離, 安全違反回数, 知識獲得数, 衝突率) ※存在する場合のみ
    下部: その他の数値列 (loss, critic_loss, entropy 等) ※アルファベット順
    """
    items: list[MetricItemInfo] = []
    used_cols: set[str] = set()

    # どちらかの DataFrame が存在するか判定
    dfs = [df for df in (df_a, df_b) if df is not None and not df.empty]
    if not dfs:
        # データがない場合は従来の標準7指標を返す
        for name, idx, _, _ in METRIC_DEFINITIONS:
            items.append(MetricItemInfo(display_name=name, key=f"__metric_{idx}__", category="primary", metric_idx=idx))
        return items

    # --- 1. 主要強化学習指標 (Primary) ---
    # 報酬
    rew_col_a = find_column_by_aliases(df_a, REWARD_ALIASES)
    rew_col_b = find_column_by_aliases(df_b, REWARD_ALIASES)
    if rew_col_a or rew_col_b:
        actual_name = rew_col_a or rew_col_b
        items.append(MetricItemInfo(display_name=f"報酬 (Reward: {actual_name})", key="__reward__", category="primary", metric_idx=0))
        if rew_col_a: used_cols.add(rew_col_a)
        if rew_col_b: used_cols.add(rew_col_b)

    # ステップ数
    stp_col_a = find_column_by_aliases(df_a, STEPS_ALIASES)
    stp_col_b = find_column_by_aliases(df_b, STEPS_ALIASES)
    if stp_col_a or stp_col_b:
        actual_name = stp_col_a or stp_col_b
        items.append(MetricItemInfo(display_name=f"ステップ数 (Steps: {actual_name})", key="__steps__", category="primary", metric_idx=1))
        if stp_col_a: used_cols.add(stp_col_a)
        if stp_col_b: used_cols.add(stp_col_b)

    # 成功率 (Result列 または successエイリアス)
    has_success_a = (df_a is not None and ('Result' in df_a.columns or find_column_by_aliases(df_a, SUCCESS_ALIASES) is not None))
    has_success_b = (df_b is not None and ('Result' in df_b.columns or find_column_by_aliases(df_b, SUCCESS_ALIASES) is not None))
    if has_success_a or has_success_b:
        items.append(MetricItemInfo(display_name="成功率 (Success Rate %)", key="__success_rate__", category="primary", metric_idx=3))
        succ_col_a = find_column_by_aliases(df_a, SUCCESS_ALIASES)
        succ_col_b = find_column_by_aliases(df_b, SUCCESS_ALIASES)
        if succ_col_a: used_cols.add(succ_col_a)
        if succ_col_b: used_cols.add(succ_col_b)

    # --- 2. ドメイン固有指標 (Domain Specific) ---
    # 安全違反回数
    unsafe_a = find_column_by_aliases(df_a, ["UnsafeActions", "unsafe_actions", "violations"])
    unsafe_b = find_column_by_aliases(df_b, ["UnsafeActions", "unsafe_actions", "violations"])
    if unsafe_a or unsafe_b:
        actual_name = unsafe_a or unsafe_b
        items.append(MetricItemInfo(display_name=f"安全違反回数 ({actual_name})", key="__unsafe_actions__", category="domain", metric_idx=2))
        if unsafe_a: used_cols.add(unsafe_a)
        if unsafe_b: used_cols.add(unsafe_b)

    # 知識獲得数
    pol_a = find_column_by_aliases(df_a, ["Acquired_Policies", "acquired_policies"])
    pol_b = find_column_by_aliases(df_b, ["Acquired_Policies", "acquired_policies"])
    if pol_a or pol_b:
        actual_name = pol_a or pol_b
        items.append(MetricItemInfo(display_name=f"知識獲得数 ({actual_name})", key="__acquired_policies__", category="domain", metric_idx=4))
        if pol_a: used_cols.add(pol_a)
        if pol_b: used_cols.add(pol_b)

    # ゴール残距離
    goal_cols = {'Goal_X', 'Goal_Y', 'Final_X', 'Final_Y'}
    has_dist_a = (df_a is not None and goal_cols.issubset(df_a.columns))
    has_dist_b = (df_b is not None and goal_cols.issubset(df_b.columns))
    if has_dist_a or has_dist_b:
        items.append(MetricItemInfo(display_name="ゴール残距離 (GoalDistance m)", key="__goal_distance__", category="domain", metric_idx=5))
        used_cols.update(goal_cols)

    # 衝突率
    has_coll_a = (df_a is not None and ('Result' in df_a.columns or find_column_by_aliases(df_a, COLLISION_ALIASES) is not None))
    has_coll_b = (df_b is not None and ('Result' in df_b.columns or find_column_by_aliases(df_b, COLLISION_ALIASES) is not None))
    if has_coll_a or has_coll_b:
        items.append(MetricItemInfo(display_name="衝突率 (Collision Rate %)", key="__collision_rate__", category="domain", metric_idx=6))
        coll_col_a = find_column_by_aliases(df_a, COLLISION_ALIASES)
        coll_col_b = find_column_by_aliases(df_b, COLLISION_ALIASES)
        if coll_col_a: used_cols.add(coll_col_a)
        if coll_col_b: used_cols.add(coll_col_b)

    # --- 3. その他の数値列 (Generic) ---
    all_numeric: set[str] = set()
    if df_a is not None:
        all_numeric.update(get_available_numeric_columns(df_a))
    if df_b is not None:
        all_numeric.update(get_available_numeric_columns(df_b))

    generic_cols = sorted([col for col in all_numeric if col not in used_cols and col != 'Result'], key=lambda s: s.lower())
    for col in generic_cols:
        items.append(MetricItemInfo(display_name=f"{col} (数値系列)", key=col, category="generic"))

    return items


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
        # エピソード列の正規化（Episode, Total_Episode, epoch, iteration, step 等のフォールバック）
        if 'Episode' not in df.columns:
            if 'Total_Episode' in df.columns:
                df['Episode'] = df['Total_Episode']
            else:
                ep_alias = find_column_by_aliases(df, ["episode", "total_episode", "episodes", "epoch", "epochs", "iteration", "iterations", "step", "steps"])
                if ep_alias and pd.api.types.is_numeric_dtype(df[ep_alias]):
                    df['Episode'] = df[ep_alias]
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
    metric_target: Optional[Union[int, str]] = None,
    window: int = 10,
    label_prefix: str = "",
    task_filter_id: int = 0,
    metric_idx: Optional[int] = None
) -> MetricSeriesData:
    """
    指定された DataFrame から指標値系列（生データおよび移動平均）を計算する。
    metric_target / metric_idx: 従来の int (0..6) または 指標キー/列名文字列 ('__reward__', 'loss' 等)
    task_filter_id > 0 の場合は特定タスクに絞り込み、Task_Episode を 1 始まりの X 軸とする。
    task_filter_id == 0 の場合は全タスク統合とし、タスク境界線および収束ポイントを抽出する。
    """
    if metric_target is None:
        metric_target = metric_idx if metric_idx is not None else 0

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
                ep_alias = find_column_by_aliases(target_df, ["episode", "total_episode", "episodes", "epoch", "epochs", "iteration", "iterations", "step", "steps"])
                if ep_alias and pd.api.types.is_numeric_dtype(target_df[ep_alias]):
                    target_df = target_df.copy()
                    target_df['Episode'] = target_df[ep_alias]
                else:
                    target_df = target_df.copy()
                    target_df['Episode'] = np.arange(1, len(target_df) + 1)
        x = target_df['Episode'].values

    # 3. 指標キーの正規化
    target_key = str(metric_target)
    if isinstance(metric_target, int):
        int_to_key = {
            0: "__reward__",
            1: "__steps__",
            2: "__unsafe_actions__",
            3: "__success_rate__",
            4: "__acquired_policies__",
            5: "__goal_distance__",
            6: "__collision_rate__"
        }
        target_key = int_to_key.get(metric_target, "__reward__")

    # 4. 指標データ算出
    # (A) 報酬 (Reward)
    if target_key in ("__reward__", "TotalReward", "__metric_0__"):
        col = find_column_by_aliases(target_df, REWARD_ALIASES)
        if col and col in target_df.columns:
            y = pd.to_numeric(target_df[col], errors='coerce').fillna(0.0).values
            ma_vals = pd.Series(y).rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, y, ma_vals, f"{label_prefix} (移動平均: {window}ep)", "Total Reward", is_task_filtered)
        return MetricSeriesData(has_data=False, y_label="Total Reward")

    # (B) ステップ数 (Steps)
    elif target_key in ("__steps__", "Steps", "__metric_1__"):
        col = find_column_by_aliases(target_df, STEPS_ALIASES)
        if col and col in target_df.columns:
            y = pd.to_numeric(target_df[col], errors='coerce').fillna(0.0).values
            ma_vals = pd.Series(y).rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, y, ma_vals, f"{label_prefix} (移動平均: {window}ep)", "Steps per Episode", is_task_filtered)
        return MetricSeriesData(has_data=False, y_label="Steps per Episode")

    # (C) 成功率 (Success Rate)
    elif target_key in ("__success_rate__", "GoalSuccessRate", "__metric_3__"):
        y_label = f"Goal Success Rate (% [{window} ep MA])"
        if 'Result' in target_df.columns:
            is_goal = (target_df['Result'] == 'Goal').astype(float) * 100.0
            ma_vals = is_goal.rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (成功率)", y_label, is_task_filtered)
        succ_col = find_column_by_aliases(target_df, SUCCESS_ALIASES)
        if succ_col and succ_col in target_df.columns:
            vals = pd.to_numeric(target_df[succ_col], errors='coerce').fillna(0.0)
            if vals.max() <= 1.0:
                vals = vals * 100.0
            ma_vals = vals.rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (成功率)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # (D) 衝突率 (Collision Rate)
    elif target_key in ("__collision_rate__", "CollisionRate", "__metric_6__"):
        y_label = f"Collision Rate (% [{window} ep MA])"
        if 'Result' in target_df.columns:
            is_collision = (target_df['Result'] == 'Collision').astype(float) * 100.0
            ma_vals = is_collision.rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (衝突率)", y_label, is_task_filtered)
        coll_col = find_column_by_aliases(target_df, COLLISION_ALIASES)
        if coll_col and coll_col in target_df.columns:
            vals = pd.to_numeric(target_df[coll_col], errors='coerce').fillna(0.0)
            if vals.max() <= 1.0:
                vals = vals * 100.0
            ma_vals = vals.rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (衝突率)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # (E) ゴール残距離 (GoalDistance)
    elif target_key in ("__goal_distance__", "GoalDistance", "__metric_5__"):
        y_label = "Distance to Goal (m)"
        required_cols = {'Goal_X', 'Goal_Y', 'Final_X', 'Final_Y'}
        if required_cols.issubset(target_df.columns):
            dx = target_df['Goal_X'] - target_df['Final_X']
            dy = target_df['Goal_Y'] - target_df['Final_Y']
            dist = np.sqrt(dx**2 + dy**2).values
            ma_vals = pd.Series(dist).rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, dist, ma_vals, f"{label_prefix} (ゴール残距離)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # (F) 安全違反回数 (UnsafeActions)
    elif target_key in ("__unsafe_actions__", "UnsafeActions", "__metric_2__"):
        col = find_column_by_aliases(target_df, ["UnsafeActions", "unsafe_actions", "violations"])
        if col and col in target_df.columns:
            y = pd.to_numeric(target_df[col], errors='coerce').fillna(0.0).values
            ma_vals = pd.Series(y).rolling(window=window, min_periods=1).mean().values
            return _build_metric_result(target_df, x, y, ma_vals, f"{label_prefix} (移動平均: {window}ep)", "Unsafe Actions Count", is_task_filtered)
        return MetricSeriesData(has_data=False, y_label="Unsafe Actions Count")

    # (G) 知識獲得数 (Acquired_Policies)
    elif target_key in ("__acquired_policies__", "Acquired_Policies", "__metric_4__"):
        col = find_column_by_aliases(target_df, ["Acquired_Policies", "acquired_policies"])
        if col and col in target_df.columns:
            y = pd.to_numeric(target_df[col], errors='coerce').fillna(0.0).values
            return _build_metric_result(target_df, x, y, y, f"{label_prefix} ({col})", "Acquired Policies", is_task_filtered)
        return MetricSeriesData(has_data=False, y_label="Acquired Policies")

    # (H) 任意の一般数値列 (Generic)
    elif target_key in target_df.columns:
        y = pd.to_numeric(target_df[target_key], errors='coerce').fillna(0.0).values
        ma_vals = pd.Series(y).rolling(window=window, min_periods=1).mean().values
        return _build_metric_result(target_df, x, y, ma_vals, f"{label_prefix} ({target_key} MA: {window}ep)", target_key, is_task_filtered)

    # 該当列なし
    return MetricSeriesData(has_data=False, y_label=target_key)


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
