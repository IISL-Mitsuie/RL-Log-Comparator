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
    "ep_len_mean", "length", "l"
]

SUCCESS_ALIASES = [
    "success", "is_success", "goalsuccessrate", "success_rate"
]

COLLISION_ALIASES = [
    "collision", "is_collision", "collisionrate", "collision_rate"
]

# エピソード番号・メタデータ列（指標一覧から除外）
# step / epoch 等は、X 軸に使った場合だけ除外する（get_available_numeric_columns を参照）
EXCLUDE_COLUMNS = {
    "episode", "total_episode", "task_episode", "task_id", "sap_plan"
}


# X 軸の候補列 (小文字の列名, 種別)。上から優先する
X_AXIS_CANDIDATES: list[tuple[str, str]] = [
    ("episode", "episode"), ("total_episode", "episode"), ("episodes", "episode"),
    ("global_step", "step"), ("timesteps", "step"), ("step", "step"),
    ("epoch", "epoch"), ("epochs", "epoch"),
    ("iteration", "iteration"), ("iterations", "iteration"),
]

EPISODE_X_LABEL = "Total Episode (通算エピソード)"
ROW_X_LABEL = "Row Index (行番号)"
_X_AXIS_KIND_NAMES = {"step": "Step", "epoch": "Epoch", "iteration": "Iteration"}

# 正規化済み DataFrame の attrs に XAxisInfo を保持するキー
X_AXIS_ATTR = "x_axis"


@dataclass
class XAxisInfo:
    """X 軸に使う列の情報"""
    column: Optional[str]   # 実際の列名（行番号補完時は None）
    kind: str               # 'episode' | 'step' | 'epoch' | 'iteration' | 'row'
    label: str              # 既定の軸ラベル


@dataclass
class MetricSeriesData:
    """プロット用の計算済み系列データ"""
    has_data: bool
    x: Optional[np.ndarray] = None
    y_raw: Optional[np.ndarray] = None
    y_ma: Optional[np.ndarray] = None
    legend_label_ma: str = ""
    y_label: str = ""
    x_label: str = ""                    # 既定の X 軸ラベル
    x_kind: str = ""                     # X 軸の種別 (XAxisInfo.kind)
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


def find_column_by_aliases(
    df: Optional[pd.DataFrame],
    aliases: list[str],
    exclude: Optional[set[str]] = None
) -> Optional[str]:
    """DataFrame の列からエイリアスリストにマッチする列名を大文字小文字無視で探す（exclude の列は除く）"""
    if df is None or df.empty:
        return None
    lower_to_col = {str(col).lower(): str(col) for col in df.columns if not exclude or str(col) not in exclude}
    for alias in aliases:
        if alias.lower() in lower_to_col:
            return lower_to_col[alias.lower()]
    return None


def resolve_x_axis(df: Optional[pd.DataFrame]) -> XAxisInfo:
    """DataFrame から X 軸に使う列を決定する（Episode, Total_Episode, X_AXIS_CANDIDATES の順。なければ行番号）"""
    if df is None:
        return XAxisInfo(column=None, kind="row", label=ROW_X_LABEL)
    if 'Episode' in df.columns:
        return XAxisInfo(column='Episode', kind="episode", label=EPISODE_X_LABEL)
    if 'Total_Episode' in df.columns:
        return XAxisInfo(column='Total_Episode', kind="episode", label=EPISODE_X_LABEL)

    lower_to_col = {str(col).lower(): str(col) for col in df.columns}
    for name, kind in X_AXIS_CANDIDATES:
        col = lower_to_col.get(name)
        if col is not None and pd.api.types.is_numeric_dtype(df[col]):
            label = EPISODE_X_LABEL if kind == "episode" else f"{_X_AXIS_KIND_NAMES[kind]} ({col})"
            return XAxisInfo(column=col, kind=kind, label=label)
    return XAxisInfo(column=None, kind="row", label=ROW_X_LABEL)


def normalize_log_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, XAxisInfo]:
    """
    読み込んだ DataFrame を正規化する（df を直接変更する）。
    - Episode 列がなければ X 軸の列（なければ行番号）から作る
    - Is_Converged 列を bool 型にする
    - X 軸の情報を df.attrs[X_AXIS_ATTR] に保持する
    """
    x_info = resolve_x_axis(df)
    if 'Episode' not in df.columns:
        if x_info.column is not None:
            df['Episode'] = df[x_info.column]
        else:
            df['Episode'] = np.arange(1, len(df) + 1)

    if 'Is_Converged' in df.columns and df['Is_Converged'].dtype != bool:
        df['Is_Converged'] = df['Is_Converged'].astype(str).str.lower().isin(['true', '1'])

    df.attrs[X_AXIS_ATTR] = x_info
    return df, x_info


def get_x_axis_info(df: Optional[pd.DataFrame]) -> XAxisInfo:
    """正規化時に保持した X 軸の情報を返す（未正規化なら推定する）"""
    if df is not None:
        info = df.attrs.get(X_AXIS_ATTR)
        if isinstance(info, XAxisInfo):
            return info
    return resolve_x_axis(df)


def _x_axis_exclude(df: Optional[pd.DataFrame]) -> set[str]:
    """指標の候補から除外する X 軸の列名"""
    if df is None:
        return set()
    column = get_x_axis_info(df).column
    return {column} if column else set()


def _read_csv_robust(path: str, **kwargs) -> pd.DataFrame:
    """CSV を UTF-8 (BOM 付きを含む) で読み込み、失敗したら cp932 で再試行する"""
    try:
        return pd.read_csv(path, encoding="utf-8-sig", **kwargs)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp932", **kwargs)


def get_available_numeric_columns(df: Optional[pd.DataFrame]) -> list[str]:
    """DataFrame に含まれるプロット可能な数値列（X軸に使った列・管理列を除く）をリストで返す"""
    if df is None or df.empty:
        return []
    numeric_cols: list[str] = []
    x_axis_cols = _x_axis_exclude(df)
    for col in df.columns:
        col_str = str(col)
        if col_str.lower() in EXCLUDE_COLUMNS or col_str in x_axis_cols:
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

    # X 軸に使った列は指標の候補から除外する
    ex_a = _x_axis_exclude(df_a)
    ex_b = _x_axis_exclude(df_b)

    # --- 1. 主要強化学習指標 (Primary) ---
    # 報酬
    rew_col_a = find_column_by_aliases(df_a, REWARD_ALIASES, ex_a)
    rew_col_b = find_column_by_aliases(df_b, REWARD_ALIASES, ex_b)
    if rew_col_a or rew_col_b:
        actual_name = rew_col_a or rew_col_b
        items.append(MetricItemInfo(display_name=f"報酬 (Reward: {actual_name})", key="__reward__", category="primary", metric_idx=0))
        if rew_col_a: used_cols.add(rew_col_a)
        if rew_col_b: used_cols.add(rew_col_b)

    # ステップ数
    stp_col_a = find_column_by_aliases(df_a, STEPS_ALIASES, ex_a)
    stp_col_b = find_column_by_aliases(df_b, STEPS_ALIASES, ex_b)
    if stp_col_a or stp_col_b:
        actual_name = stp_col_a or stp_col_b
        items.append(MetricItemInfo(display_name=f"ステップ数 (Steps: {actual_name})", key="__steps__", category="primary", metric_idx=1))
        if stp_col_a: used_cols.add(stp_col_a)
        if stp_col_b: used_cols.add(stp_col_b)

    # 成功率 (Result列 または successエイリアス)
    has_success_a = (df_a is not None and ('Result' in df_a.columns or find_column_by_aliases(df_a, SUCCESS_ALIASES, ex_a) is not None))
    has_success_b = (df_b is not None and ('Result' in df_b.columns or find_column_by_aliases(df_b, SUCCESS_ALIASES, ex_b) is not None))
    if has_success_a or has_success_b:
        items.append(MetricItemInfo(display_name="成功率 (Success Rate %)", key="__success_rate__", category="primary", metric_idx=3))
        succ_col_a = find_column_by_aliases(df_a, SUCCESS_ALIASES, ex_a)
        succ_col_b = find_column_by_aliases(df_b, SUCCESS_ALIASES, ex_b)
        if succ_col_a: used_cols.add(succ_col_a)
        if succ_col_b: used_cols.add(succ_col_b)

    # --- 2. ドメイン固有指標 (Domain Specific) ---
    # 安全違反回数
    unsafe_a = find_column_by_aliases(df_a, ["UnsafeActions", "unsafe_actions", "violations"], ex_a)
    unsafe_b = find_column_by_aliases(df_b, ["UnsafeActions", "unsafe_actions", "violations"], ex_b)
    if unsafe_a or unsafe_b:
        actual_name = unsafe_a or unsafe_b
        items.append(MetricItemInfo(display_name=f"安全違反回数 ({actual_name})", key="__unsafe_actions__", category="domain", metric_idx=2))
        if unsafe_a: used_cols.add(unsafe_a)
        if unsafe_b: used_cols.add(unsafe_b)

    # 知識獲得数
    pol_a = find_column_by_aliases(df_a, ["Acquired_Policies", "acquired_policies"], ex_a)
    pol_b = find_column_by_aliases(df_b, ["Acquired_Policies", "acquired_policies"], ex_b)
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
    has_coll_a = (df_a is not None and ('Result' in df_a.columns or find_column_by_aliases(df_a, COLLISION_ALIASES, ex_a) is not None))
    has_coll_b = (df_b is not None and ('Result' in df_b.columns or find_column_by_aliases(df_b, COLLISION_ALIASES, ex_b) is not None))
    if has_coll_a or has_coll_b:
        items.append(MetricItemInfo(display_name="衝突率 (Collision Rate %)", key="__collision_rate__", category="domain", metric_idx=6))
        coll_col_a = find_column_by_aliases(df_a, COLLISION_ALIASES, ex_a)
        coll_col_b = find_column_by_aliases(df_b, COLLISION_ALIASES, ex_b)
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


def find_log_csv(folder_path: str) -> Optional[str]:
    """
    指定フォルダ配下から学習ログ CSV を探索して最優先のファイルパスを返す。
    _task_ を含まない全タスク統合CSV (learning_log_*.csv) を最優先し、
    次に learning_log_*.csv、無ければ任意の *.csv を探索。
    """
    if not folder_path or not os.path.isdir(folder_path):
        return None

    csv_candidates = sorted(glob.glob(os.path.join(folder_path, "learning_log_*.csv")))
    main_csvs = [p for p in csv_candidates if "_task_" not in os.path.basename(p)]

    if main_csvs:
        return main_csvs[0]
    if csv_candidates:
        return csv_candidates[0]

    other_csvs = sorted(glob.glob(os.path.join(folder_path, "*.csv")))
    if other_csvs:
        return other_csvs[0]
    return None


def read_log_csv(folder_path: str) -> Optional[pd.DataFrame]:
    """
    フォルダ内の learning_log_*.csv (または *.csv) を安全に読み込んで DataFrame を返す。
    _task_ を含まない全タスク統合CSVを最優先でロードする。
    """
    target_csv = find_log_csv(folder_path)
    if not target_csv:
        return None

    try:
        df, _ = normalize_log_dataframe(_read_csv_robust(target_csv))
        return df
    except Exception as e:
        print(f"[ERROR] Failed to read CSV ({target_csv}): {e}")
        return None


@dataclass
class TaskOption:
    """タスクまたは個別CSVの選択肢情報"""
    task_id: int                     # 0: 全タスク統合, 1..N: 特定タスクID, -1: 個別CSVファイル
    display_name: str                # UIコンボボックスの表示テキスト (例: "Task 1 (Goal: [11.0, 3.0])")
    short_name: str                  # 凡例・タイトル用の簡潔なタスク名 (例: "Task 1")
    csv_path: Optional[str] = None   # 個別ファイルパス (Noneの場合は統合CSVから抽出)
    goal_desc: str = ""              # ゴール説明


def scan_task_options(folder_path: str, df: Optional[pd.DataFrame] = None) -> list[TaskOption]:
    """
    フォルダおよび DataFrame から利用可能な全タスク選択肢（タスクおよびCSVファイル）を検出して返す。
    - 全タスク統合（task_id=0）は含まず、各タスク（Task 1, 2...）および個別CSVファイルを返す。
    """
    options: list[TaskOption] = []
    seen_task_ids: set[int] = set()

    # 1. df があれば Task_ID 列から抽出
    if df is not None and not df.empty and 'Task_ID' in df.columns:
        for t_id in sorted(df['Task_ID'].dropna().unique()):
            try:
                t_int = int(t_id)
            except (ValueError, TypeError):
                continue
            seen_task_ids.add(t_int)
            sub = df[df['Task_ID'] == t_id]
            goal_desc = ""
            if 'Goal_X' in sub.columns and 'Goal_Y' in sub.columns and not sub.empty:
                gx = sub['Goal_X'].iloc[0]
                gy = sub['Goal_Y'].iloc[0]
                goal_desc = f" (Goal: [{gx:.1f}, {gy:.1f}])"
            options.append(TaskOption(
                task_id=t_int,
                display_name=f"Task {t_int}{goal_desc}",
                short_name=f"Task {t_int}",
                goal_desc=goal_desc
            ))

    # 2. フォルダ内のタスク別CSV (learning_log_*_task_*.csv) を走査
    if folder_path and os.path.isdir(folder_path):
        import re
        task_csv_files = sorted(glob.glob(os.path.join(folder_path, "learning_log_*_task_*.csv")))
        for fpath in task_csv_files:
            fname = os.path.basename(fpath)
            m = re.search(r"_task_(\d+)(_unregistered)?\.csv$", fname)
            if m:
                t_int = int(m.group(1))
                is_unreg = bool(m.group(2))
                unreg_label = " [非登録]" if is_unreg else ""

                if t_int in seen_task_ids:
                    # 既に統合CSVから検出済みの場合は csv_path を補完
                    for opt in options:
                        if opt.task_id == t_int:
                            opt.csv_path = fpath
                            if is_unreg and "[非登録]" not in opt.display_name:
                                opt.display_name += " [非登録]"
                                opt.short_name += " [非登録]"
                else:
                    seen_task_ids.add(t_int)
                    goal_desc = ""
                    try:
                        head_df = _read_csv_robust(fpath, nrows=1)
                        if 'Goal_X' in head_df.columns and 'Goal_Y' in head_df.columns:
                            gx = head_df['Goal_X'].iloc[0]
                            gy = head_df['Goal_Y'].iloc[0]
                            goal_desc = f" (Goal: [{gx:.1f}, {gy:.1f}])"
                    except Exception:
                        pass
                    options.append(TaskOption(
                        task_id=t_int,
                        display_name=f"Task {t_int}{unreg_label}{goal_desc}",
                        short_name=f"Task {t_int}{unreg_label}",
                        csv_path=fpath,
                        goal_desc=goal_desc
                    ))

        # 3. 汎用CSVファイル（learning_log_*.csv を除く *.csv 等）の走査
        other_csvs = sorted(glob.glob(os.path.join(folder_path, "*.csv")))
        for fpath in other_csvs:
            fname = os.path.basename(fpath)
            if fname.startswith("learning_log_"):
                continue
            options.append(TaskOption(
                task_id=-1,
                display_name=f"{fname} (CSVファイル)",
                short_name=fname,
                csv_path=fpath
            ))

    # task_id 昇順（-1 は末尾）でソート
    options.sort(key=lambda o: (1 if o.task_id == -1 else 0, o.task_id))
    return options


def load_task_dataframe(
    df_main: Optional[pd.DataFrame],
    folder_path: str,
    task_option: TaskOption
) -> Optional[pd.DataFrame]:
    """
    TaskOption に応じた DataFrame を安全に取得・正規化して返す。
    - 個別 csv_path が指定されていれば優先ロード。
    - なければ df_main から task_id でフィルタリング。
    """
    if task_option.csv_path and os.path.isfile(task_option.csv_path):
        try:
            df, _ = normalize_log_dataframe(_read_csv_robust(task_option.csv_path))
            return df
        except Exception as e:
            print(f"[WARN] Failed to read task csv ({task_option.csv_path}): {e}")

    # 個別ファイルがない場合、df_main から抽出
    if df_main is not None and not df_main.empty:
        if task_option.task_id > 0 and 'Task_ID' in df_main.columns:
            sub = df_main[df_main['Task_ID'] == task_option.task_id].copy()
            if not sub.empty:
                return sub
        elif task_option.task_id == 0:
            return df_main

    # df_main にもなく csv_path もない場合、フォルダから task_{task_id} をフォールバック検索
    if folder_path and task_option.task_id > 0:
        cands = sorted(glob.glob(os.path.join(folder_path, f"*_task_{task_option.task_id}*.csv")))
        if cands and os.path.isfile(cands[0]):
            try:
                df, _ = normalize_log_dataframe(_read_csv_robust(cands[0]))
                return df
            except Exception:
                pass

    return None


def get_available_tasks(
    df: Optional[pd.DataFrame] = None,
    folder_path: Optional[str] = None
) -> list[tuple[int, str]]:
    """
    DataFrame およびフォルダに含まれるタスク一覧を [(task_id, 表示名), ...] の形式で返す。
    task_id 0 は常に「全タスク統合 (通算エピソード)」を表す。
    """
    default_list = [(0, "全タスク統合 (通算エピソード)")]
    if folder_path:
        opts = scan_task_options(folder_path, df)
        if not opts:
            return default_list
        res = [(0, "全タスク統合 (通算エピソード)")]
        for opt in opts:
            res.append((opt.task_id, opt.display_name))
        return res

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

    # 2. X 軸の決定（未正規化の DataFrame はここで正規化する）
    if 'Episode' not in target_df.columns:
        target_df, _ = normalize_log_dataframe(target_df.copy())
    x_info = get_x_axis_info(target_df)
    if is_task_filtered:
        if 'Task_Episode' in target_df.columns:
            x = target_df['Task_Episode'].values
        else:
            x = np.arange(1, len(target_df) + 1)
        x_label = f"Task Episode (Task {task_filter_id} 内エピソード [1..N])"
        x_kind = "episode"
    else:
        x = target_df['Episode'].values
        x_label = x_info.label
        x_kind = x_info.kind

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

    # 4. 指標データ算出（X 軸に使った列は指標の候補から除外する）
    exclude = {x_info.column} if x_info.column else None
    result = _compute_metric(target_df, x, target_key, window, label_prefix, is_task_filtered, exclude)
    result.x_label = x_label
    result.x_kind = x_kind
    return result


def _to_float_array(values: pd.Series) -> np.ndarray:
    """数値に変換できない値・欠損値を NaN とした float 配列に変換する（0 では埋めない）"""
    return pd.to_numeric(values, errors='coerce').astype(float).to_numpy(copy=True)


def _moving_average(y: np.ndarray, window: int) -> np.ndarray:
    """NaN を飛ばした移動平均。生データが NaN の位置は移動平均も NaN にする（記録がない位置に値を描かない）"""
    ma_vals = pd.Series(y, dtype=float).rolling(window=window, min_periods=1).mean().to_numpy(copy=True)
    ma_vals[np.isnan(y)] = np.nan
    return ma_vals


def _normalized_result(df: pd.DataFrame) -> pd.Series:
    """Result 列を前後の空白を除いた小文字の文字列にする"""
    return df['Result'].astype(str).str.strip().str.lower()


def _rate_from_result_column(df: pd.DataFrame, value: str, window: int) -> Optional[np.ndarray]:
    """Result 列が value と一致する割合 (%) の移動平均を返す。空欄の行は数えない。すべて空欄なら None"""
    missing = df['Result'].isna().to_numpy()
    if missing.all():
        return None
    vals = (_normalized_result(df) == value).astype(float).to_numpy(copy=True) * 100.0
    vals[missing] = np.nan
    return _moving_average(vals, window)


def _rate_from_numeric_column(vals: np.ndarray, window: int) -> Optional[np.ndarray]:
    """0/1（または %）の数値列から率 (%) の移動平均を返す。すべて NaN なら None"""
    if np.all(np.isnan(vals)):
        return None
    if np.nanmax(vals) <= 1.0:
        vals = vals * 100.0
    return _moving_average(vals, window)


def _compute_metric(
    target_df: pd.DataFrame,
    x: np.ndarray,
    target_key: str,
    window: int,
    label_prefix: str,
    is_task_filtered: bool,
    exclude: Optional[set[str]]
) -> MetricSeriesData:
    """指標キーに応じて生データ・移動平均を算出する"""
    # (A) 報酬 (Reward)
    if target_key in ("__reward__", "TotalReward", "__metric_0__"):
        col = find_column_by_aliases(target_df, REWARD_ALIASES, exclude)
        if col and col in target_df.columns:
            y = _to_float_array(target_df[col])
            ma_vals = _moving_average(y, window)
            return _build_metric_result(target_df, x, y, ma_vals, f"{label_prefix} (移動平均: {window}ep)", "Total Reward", is_task_filtered)
        return MetricSeriesData(has_data=False, y_label="Total Reward")

    # (B) ステップ数 (Steps)
    elif target_key in ("__steps__", "Steps", "__metric_1__"):
        col = find_column_by_aliases(target_df, STEPS_ALIASES, exclude)
        if col and col in target_df.columns:
            y = _to_float_array(target_df[col])
            ma_vals = _moving_average(y, window)
            return _build_metric_result(target_df, x, y, ma_vals, f"{label_prefix} (移動平均: {window}ep)", "Steps per Episode", is_task_filtered)
        return MetricSeriesData(has_data=False, y_label="Steps per Episode")

    # (C) 成功率 (Success Rate)
    elif target_key in ("__success_rate__", "GoalSuccessRate", "__metric_3__"):
        y_label = f"Goal Success Rate (% [{window} ep MA])"
        if 'Result' in target_df.columns:
            ma_vals = _rate_from_result_column(target_df, 'goal', window)
            if ma_vals is not None:
                return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (成功率)", y_label, is_task_filtered)
            return MetricSeriesData(has_data=False, y_label=y_label)
        succ_col = find_column_by_aliases(target_df, SUCCESS_ALIASES, exclude)
        if succ_col and succ_col in target_df.columns:
            ma_vals = _rate_from_numeric_column(_to_float_array(target_df[succ_col]), window)
            if ma_vals is not None:
                return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (成功率)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # (D) 衝突率 (Collision Rate)
    elif target_key in ("__collision_rate__", "CollisionRate", "__metric_6__"):
        y_label = f"Collision Rate (% [{window} ep MA])"
        if 'Result' in target_df.columns:
            ma_vals = _rate_from_result_column(target_df, 'collision', window)
            if ma_vals is not None:
                return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (衝突率)", y_label, is_task_filtered)
            return MetricSeriesData(has_data=False, y_label=y_label)
        coll_col = find_column_by_aliases(target_df, COLLISION_ALIASES, exclude)
        if coll_col and coll_col in target_df.columns:
            ma_vals = _rate_from_numeric_column(_to_float_array(target_df[coll_col]), window)
            if ma_vals is not None:
                return _build_metric_result(target_df, x, None, ma_vals, f"{label_prefix} (衝突率)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # (E) ゴール残距離 (GoalDistance)
    elif target_key in ("__goal_distance__", "GoalDistance", "__metric_5__"):
        y_label = "Distance to Goal (m)"
        required_cols = {'Goal_X', 'Goal_Y', 'Final_X', 'Final_Y'}
        if required_cols.issubset(target_df.columns):
            dx = _to_float_array(target_df['Goal_X']) - _to_float_array(target_df['Final_X'])
            dy = _to_float_array(target_df['Goal_Y']) - _to_float_array(target_df['Final_Y'])
            dist = np.sqrt(dx**2 + dy**2)
            ma_vals = _moving_average(dist, window)
            return _build_metric_result(target_df, x, dist, ma_vals, f"{label_prefix} (ゴール残距離)", y_label, is_task_filtered)
        return MetricSeriesData(has_data=False, y_label=y_label)

    # (F) 安全違反回数 (UnsafeActions)
    elif target_key in ("__unsafe_actions__", "UnsafeActions", "__metric_2__"):
        col = find_column_by_aliases(target_df, ["UnsafeActions", "unsafe_actions", "violations"], exclude)
        if col and col in target_df.columns:
            y = _to_float_array(target_df[col])
            ma_vals = _moving_average(y, window)
            return _build_metric_result(target_df, x, y, ma_vals, f"{label_prefix} (移動平均: {window}ep)", "Unsafe Actions Count", is_task_filtered)
        return MetricSeriesData(has_data=False, y_label="Unsafe Actions Count")

    # (G) 知識獲得数 (Acquired_Policies)
    elif target_key in ("__acquired_policies__", "Acquired_Policies", "__metric_4__"):
        col = find_column_by_aliases(target_df, ["Acquired_Policies", "acquired_policies"], exclude)
        if col and col in target_df.columns:
            y = _to_float_array(target_df[col])
            return _build_metric_result(target_df, x, y, y, f"{label_prefix} ({col})", "Acquired Policies", is_task_filtered)
        return MetricSeriesData(has_data=False, y_label="Acquired Policies")

    # (H) 任意の一般数値列 (Generic)
    elif target_key in target_df.columns:
        y = _to_float_array(target_df[target_key])
        ma_vals = _moving_average(y, window)
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

    # 境界線は統合表示（タスクフィルタなし）の場合のみ抽出
    if not is_task_filtered and 'Task_ID' in df.columns:
        # Task_ID の変化点を抽出
        task_diff = df['Task_ID'].diff()
        boundary_indices = np.where(task_diff != 0)[0]
        for idx in boundary_indices:
            if idx > 0:  # 先頭行以外
                if pd.isna(df['Episode'].iloc[idx]) or pd.isna(df['Task_ID'].iloc[idx]):
                    continue
                ep_val = int(df['Episode'].iloc[idx])
                task_id_val = int(df['Task_ID'].iloc[idx])
                task_boundaries.append((ep_val, f"Task {task_id_val}"))

    # 収束ポイントは統合表示・タスク絞り込み時を問わず抽出
    if 'Is_Converged' in df.columns:
        conv_mask = (df['Is_Converged'] == True).values
        if np.any(conv_mask):
            conv_indices = np.where(conv_mask)[0]
            for idx in conv_indices:
                if idx < len(x):
                    # マーカー用のY値（移動平均または生データ）
                    if y_ma is not None and idx < len(y_ma):
                        y_val = float(y_ma[idx])
                    elif y_raw is not None and idx < len(y_raw):
                        y_val = float(y_raw[idx])
                    else:
                        y_val = 0.0
                    # 値が記録されていない (NaN) 点にはマーカーを描かない
                    if np.isnan(y_val) or pd.isna(x[idx]):
                        continue
                    converged_episodes.append(int(x[idx]))
                    converged_y_values.append(y_val)

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
