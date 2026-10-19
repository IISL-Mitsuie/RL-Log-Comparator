"""
CSV 数値ログ解析モジュール (src.core.parsers.csv_metric) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
import numpy as np
import pandas as pd
from src.core.parsers.csv_metric import (
    read_log_csv, compute_metric_series
)
from tests.helpers import create_dummy_experiment_folder


class TestParserCsvMetric(unittest.TestCase):
    """CSV パースおよび移動平均・成功率計算のテスト"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_read_log_csv_with_episode(self):
        folder = create_dummy_experiment_folder(self.test_dir, episodes=5)
        df = read_log_csv(folder)
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 5)
        self.assertIn("Episode", df.columns)

    def test_read_log_csv_auto_episode_completion(self):
        folder = os.path.join(self.test_dir, "no_episode_folder")
        os.makedirs(folder, exist_ok=True)
        df_raw = pd.DataFrame({"TotalReward": [10.0, 20.0, 30.0]})
        df_raw.to_csv(os.path.join(folder, "learning_log_test.csv"), index=False)

        df = read_log_csv(folder)
        self.assertIsNotNone(df)
        self.assertIn("Episode", df.columns)
        self.assertEqual(list(df["Episode"]), [1, 2, 3])

    def test_compute_total_reward_series(self):
        df = pd.DataFrame({
            "Episode": [1, 2, 3, 4],
            "TotalReward": [10.0, 20.0, 30.0, 40.0]
        })
        res = compute_metric_series(df, metric_idx=0, window=2, label_prefix="TestA")
        self.assertTrue(res.has_data)
        self.assertEqual(res.legend_label_ma, "TestA (移動平均: 2ep)")
        self.assertEqual(res.y_ma[0], 10.0)
        self.assertEqual(res.y_ma[1], 15.0)
        self.assertEqual(res.y_ma[2], 25.0)
        self.assertEqual(res.y_ma[3], 35.0)

    def test_compute_goal_success_rate(self):
        df = pd.DataFrame({
            "Episode": [1, 2, 3, 4],
            "Result": ["Failed", "Goal", "Goal", "Goal"]
        })
        res = compute_metric_series(df, metric_idx=3, window=2, label_prefix="TestB")
        self.assertTrue(res.has_data)
        self.assertIn("成功率", res.legend_label_ma)
        self.assertIsNone(res.y_raw)  # 成功率は生データなし
        self.assertEqual(res.y_ma[0], 0.0)    # 1ep: 0%
        self.assertEqual(res.y_ma[1], 50.0)   # 2ep: 50%
        self.assertEqual(res.y_ma[2], 100.0)  # 3ep: 100%

    def test_compute_empty_or_none(self):
        res1 = compute_metric_series(None, 0, 5, "A")
        self.assertFalse(res1.has_data)
        res2 = compute_metric_series(pd.DataFrame(), 0, 5, "A")
        self.assertFalse(res2.has_data)

    def test_continual_learning_task_boundaries_and_filtering(self):
        """継続学習のタスク境界抽出とタスク絞り込みの検証"""
        df = pd.DataFrame({
            "Task_ID": [1, 1, 2, 2, 2],
            "Task_Episode": [1, 2, 1, 2, 3],
            "Total_Episode": [1, 2, 3, 4, 5],
            "TotalReward": [10.0, 20.0, 5.0, 15.0, 25.0],
            "Is_Converged": [False, True, False, False, True]
        })
        # 全タスク統合時
        res_all = compute_metric_series(df, metric_idx=0, window=1, label_prefix="TestCL", task_filter_id=0)
        self.assertTrue(res_all.has_data)
        self.assertEqual(len(res_all.x), 5)
        # タスク境界 (Task 2 開始地点)
        self.assertEqual(len(res_all.task_boundaries), 1)
        self.assertEqual(res_all.task_boundaries[0], (3, "Task 2"))
        # 収束ポイント (ep 2 と ep 5)
        self.assertEqual(res_all.converged_episodes, [2, 5])

        # Task 2 絞り込み時 (案A: タスク内エピソード基準)
        res_t2 = compute_metric_series(df, metric_idx=0, window=1, label_prefix="TestCL", task_filter_id=2)
        self.assertTrue(res_t2.has_data)
        self.assertEqual(list(res_t2.x), [1, 2, 3])
        self.assertEqual(list(res_t2.y_raw), [5.0, 15.0, 25.0])

    def test_new_metrics_computation(self):
        """知識獲得数、ゴール残距離、衝突率の計算検証"""
        df = pd.DataFrame({
            "Episode": [1, 2, 3],
            "Acquired_Policies": [0, 1, 2],
            "Goal_X": [10.0, 10.0, 10.0],
            "Goal_Y": [0.0, 0.0, 0.0],
            "Final_X": [7.0, 10.0, 6.0],
            "Final_Y": [4.0, 0.0, 0.0],
            "Result": ["Collision", "Goal", "Collision"]
        })
        # Acquired_Policies (metric_idx=4)
        res_pol = compute_metric_series(df, metric_idx=4, window=1, label_prefix="P")
        self.assertTrue(res_pol.has_data)
        self.assertEqual(list(res_pol.y_raw), [0, 1, 2])

        # GoalDistance (metric_idx=5): sqrt(3^2 + 4^2) = 5.0, sqrt(0) = 0.0, sqrt(4^2) = 4.0
        res_dist = compute_metric_series(df, metric_idx=5, window=1, label_prefix="D")
        self.assertTrue(res_dist.has_data)
        self.assertAlmostEqual(res_dist.y_raw[0], 5.0)
        self.assertAlmostEqual(res_dist.y_raw[1], 0.0)
        self.assertAlmostEqual(res_dist.y_raw[2], 4.0)

        # CollisionRate (metric_idx=6): 100%, 50%, 66.6%
        res_col = compute_metric_series(df, metric_idx=6, window=2, label_prefix="C")
        self.assertTrue(res_col.has_data)
        self.assertEqual(res_col.y_ma[0], 100.0)
        self.assertEqual(res_col.y_ma[1], 50.0)

    def test_generic_numeric_columns_and_aliases(self):
        """汎用強化学習CSV (Gym / CleanRL / SB3想定) のエイリアスおよび任意数値列の検証"""
        from src.core.parsers.csv_metric import (
            get_available_numeric_columns, find_column_by_aliases,
            get_available_metrics, REWARD_ALIASES, STEPS_ALIASES
        )
        # 代表的なRLライブラリのCSV形式 (小文字カラム)
        df = pd.DataFrame({
            "step": [100, 200, 300],
            "reward": [1.5, 3.0, 4.5],
            "episode_length": [10, 20, 30],
            "loss": [0.5, 0.3, 0.1],
            "critic_loss": [0.2, 0.15, 0.05],
            "entropy": [1.2, 1.1, 0.9]
        })

        # 1. 数値列の抽出 (step 等の管理列は除外される)
        numeric_cols = get_available_numeric_columns(df)
        self.assertIn("reward", numeric_cols)
        self.assertIn("loss", numeric_cols)
        self.assertIn("critic_loss", numeric_cols)
        self.assertIn("entropy", numeric_cols)
        self.assertNotIn("step", numeric_cols)

        # 2. エイリアス解決
        col_rew = find_column_by_aliases(df, REWARD_ALIASES)
        self.assertEqual(col_rew, "reward")
        col_stp = find_column_by_aliases(df, STEPS_ALIASES)
        self.assertEqual(col_stp, "episode_length")

        # 3. 指標一覧生成 (案A: グループ化)
        metrics = get_available_metrics(df, None)
        keys = [m.key for m in metrics]

        # 主要指標として報酬・ステップが含まれる
        self.assertIn("__reward__", keys)
        self.assertIn("__steps__", keys)
        # 一般数値列として loss, critic_loss, entropy が含まれる
        self.assertIn("loss", keys)
        self.assertIn("critic_loss", keys)
        self.assertIn("entropy", keys)

        # 4. 任意数値列のプロット計算
        res_loss = compute_metric_series(df, metric_target="loss", window=2, label_prefix="TestLoss")
        self.assertTrue(res_loss.has_data)
        self.assertEqual(res_loss.y_label, "loss")
        self.assertAlmostEqual(res_loss.y_ma[0], 0.5)
        self.assertAlmostEqual(res_loss.y_ma[1], 0.4)  # (0.5+0.3)/2

        # 5. エイリアスキー指定での計算
        res_rew = compute_metric_series(df, metric_target="__reward__", window=1, label_prefix="TestRew")
        self.assertTrue(res_rew.has_data)
        self.assertEqual(list(res_rew.y_raw), [1.5, 3.0, 4.5])

    def test_find_log_csv(self):
        from src.core.parsers.csv_metric import find_log_csv
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertIsNone(find_log_csv(tmp_dir))

            # 汎用 progress.csv
            prog_csv = os.path.join(tmp_dir, "progress.csv")
            with open(prog_csv, "w") as f:
                f.write("a,b\n1,2")
            self.assertEqual(find_log_csv(tmp_dir), prog_csv)

            # タスク別 learning_log_123_task_1.csv
            task_csv = os.path.join(tmp_dir, "learning_log_123_task_1.csv")
            with open(task_csv, "w") as f:
                f.write("a,b\n1,2")
            self.assertEqual(find_log_csv(tmp_dir), task_csv)

            # 全タスク統合 learning_log_123.csv
            main_csv = os.path.join(tmp_dir, "learning_log_123.csv")
            with open(main_csv, "w") as f:
                f.write("a,b\n1,2")
            self.assertEqual(find_log_csv(tmp_dir), main_csv)

    def test_scan_task_options_and_load_task_dataframe(self):
        """個別タスクCSVファイル群からのタスク検出とDataFrameロードのテスト"""
        from src.core.parsers.csv_metric import scan_task_options, load_task_dataframe
        folder = os.path.join(self.test_dir, "task_csv_folder")
        os.makedirs(folder, exist_ok=True)

        # タスク別CSVファイルを作成
        p1 = os.path.join(folder, "learning_log_20261011_task_1.csv")
        p2 = os.path.join(folder, "learning_log_20261011_task_2_unregistered.csv")
        p_other = os.path.join(folder, "eval_metrics.csv")

        pd.DataFrame({
            "Task_Episode": [1, 2],
            "Goal_X": [10.0, 10.0],
            "Goal_Y": [2.0, 2.0],
            "TotalReward": [15.0, 25.0]
        }).to_csv(p1, index=False)

        pd.DataFrame({
            "Task_Episode": [1, 2],
            "Goal_X": [14.0, 14.0],
            "Goal_Y": [4.0, 4.0],
            "TotalReward": [-10.0, 5.0]
        }).to_csv(p2, index=False)

        pd.DataFrame({
            "step": [1, 2],
            "score": [100, 200]
        }).to_csv(p_other, index=False)

        # 走査実行
        options = scan_task_options(folder)
        self.assertEqual(len(options), 3)

        # Task 1
        opt1 = options[0]
        self.assertEqual(opt1.task_id, 1)
        self.assertIn("Task 1", opt1.display_name)
        self.assertEqual(opt1.csv_path, p1)

        # Task 2 [非登録]
        opt2 = options[1]
        self.assertEqual(opt2.task_id, 2)
        self.assertIn("[非登録]", opt2.display_name)
        self.assertEqual(opt2.csv_path, p2)

        # eval_metrics.csv (その他CSV)
        opt3 = options[2]
        self.assertEqual(opt3.task_id, -1)
        self.assertIn("eval_metrics.csv", opt3.display_name)

        # load_task_dataframe のテスト
        df1 = load_task_dataframe(None, folder, opt1)
        self.assertIsNotNone(df1)
        self.assertEqual(len(df1), 2)
        self.assertEqual(list(df1["TotalReward"]), [15.0, 25.0])

        df2 = load_task_dataframe(None, folder, opt2)
        self.assertIsNotNone(df2)
        self.assertEqual(len(df2), 2)
        self.assertEqual(list(df2["TotalReward"]), [-10.0, 5.0])


class TestCsvMetricCorrectness(unittest.TestCase):
    """X 軸の解決・欠損値・Result 列・文字コードの扱いのテスト (ISSUE-04)"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_folder(self, name: str, text: str, encoding: str = "utf-8") -> str:
        folder = os.path.join(self.test_dir, name)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "progress.csv"), "w", encoding=encoding, newline="") as f:
            f.write(text)
        return folder

    def test_resolve_x_axis(self):
        from src.core.parsers.csv_metric import resolve_x_axis
        cases = [
            ({"Episode": [1, 2], "Total_Episode": [5, 6]}, "Episode", "episode"),
            ({"Total_Episode": [1, 2], "Task_Episode": [1, 1]}, "Total_Episode", "episode"),
            ({"global_step": [10, 20], "step": [1, 2]}, "global_step", "step"),
            ({"step": [10, 20], "reward": [1.0, 2.0]}, "step", "step"),
            ({"epoch": [1, 2], "loss": [0.5, 0.4]}, "epoch", "epoch"),
            ({"iteration": [1, 2], "loss": [0.5, 0.4]}, "iteration", "iteration"),
            ({"reward": [1.0, 2.0]}, None, "row"),
            ({"step": ["a", "b"], "reward": [1.0, 2.0]}, None, "row"),
        ]
        for data, column, kind in cases:
            with self.subTest(columns=list(data)):
                info = resolve_x_axis(pd.DataFrame(data))
                self.assertEqual(info.column, column)
                self.assertEqual(info.kind, kind)
                self.assertTrue(info.label)
        self.assertIn("step", resolve_x_axis(pd.DataFrame({"step": [1]})).label)

    def test_normalize_log_dataframe(self):
        from src.core.parsers.csv_metric import normalize_log_dataframe
        df, info = normalize_log_dataframe(pd.DataFrame({
            "Total_Episode": [3, 4], "Is_Converged": ["False", "True"]
        }))
        self.assertEqual(list(df["Episode"]), [3, 4])
        self.assertEqual(list(df["Is_Converged"]), [False, True])
        self.assertEqual(info.kind, "episode")

        df, info = normalize_log_dataframe(pd.DataFrame({"reward": [1.0, 2.0, 3.0]}))
        self.assertEqual(list(df["Episode"]), [1, 2, 3])
        self.assertEqual(info.kind, "row")

    def test_steps_metric_not_listed_for_step_axis(self):
        from src.core.parsers.csv_metric import get_available_metrics
        df = read_log_csv(self._write_folder("gen", "step,reward,global_step\n10,1.0,100\n20,2.0,200\n"))
        keys = [m.key for m in get_available_metrics(df, None)]
        self.assertNotIn("__steps__", keys)
        self.assertIn("__reward__", keys)
        # X 軸に使った列は指標に出さない
        df2 = pd.DataFrame({"global_step": [1, 2], "reward": [1.0, 2.0]})
        keys2 = [m.key for m in get_available_metrics(df2, None)]
        self.assertNotIn("global_step", keys2)

    def test_non_axis_step_column_is_listed(self):
        from src.core.parsers.csv_metric import get_available_metrics
        df = pd.DataFrame({"Episode": [1, 2], "TotalReward": [1.0, 2.0], "step": [100, 200]})
        keys = [m.key for m in get_available_metrics(df, None)]
        self.assertIn("step", keys)

    def test_result_column_blank_rows_not_counted(self):
        df = pd.DataFrame({"Episode": [1, 2, 3, 4], "Result": ["Goal", None, None, "Goal"]})
        res = compute_metric_series(df, "__success_rate__", window=4)
        self.assertAlmostEqual(res.y_ma[-1], 100.0)
        self.assertTrue(np.isnan(res.y_ma[1]))

    def test_nan_x_values_do_not_crash(self):
        df = pd.DataFrame({
            "global_step": [10.0, np.nan, 30.0],
            "reward": [1.0, 2.0, 3.0],
            "Task_ID": [1, 2, 2],
            "Is_Converged": [False, True, True],
        })
        res = compute_metric_series(df, "__reward__", window=1)
        self.assertTrue(res.has_data)
        self.assertEqual(res.task_boundaries, [])
        self.assertEqual(res.converged_episodes, [30])

    def test_steps_metric_listed_with_episode_axis(self):
        from src.core.parsers.csv_metric import get_available_metrics
        df = pd.DataFrame({"Steps": [10, 20], "TotalReward": [1.0, 2.0], "Episode": [1, 2]})
        keys = [m.key for m in get_available_metrics(df, None)]
        self.assertIn("__steps__", keys)

    def test_x_label_reflects_step_column(self):
        df = read_log_csv(self._write_folder("gen", "step,reward\n10,1.0\n20,2.0\n"))
        res = compute_metric_series(df, "__reward__", window=2)
        self.assertTrue(res.has_data)
        self.assertEqual(list(res.x), [10, 20])
        self.assertIn("step", res.x_label)
        self.assertNotIn("Total Episode", res.x_label)
        self.assertEqual(res.x_kind, "step")

        res_ep = compute_metric_series(pd.DataFrame({"Episode": [1, 2], "TotalReward": [1.0, 2.0]}), 0)
        self.assertEqual(res_ep.x_label, "Total Episode (通算エピソード)")

    def test_nan_values_are_kept(self):
        df = read_log_csv(self._write_folder("nan", "step,reward,loss\n1,1.0,\n2,2.0,0.5\n3,3.0,\n4,4.0,0.3\n"))
        res = compute_metric_series(df, "loss", window=10)
        self.assertTrue(res.has_data)
        self.assertNotIn(0.0, list(res.y_raw))
        self.assertTrue(np.isnan(res.y_raw[0]))
        self.assertAlmostEqual(res.y_raw[1], 0.5)
        # 記録がない位置は移動平均も NaN、記録がある位置は記録値だけの平均
        self.assertTrue(np.isnan(res.y_ma[0]))
        self.assertTrue(np.isnan(res.y_ma[2]))
        self.assertAlmostEqual(res.y_ma[1], 0.5)
        self.assertAlmostEqual(res.y_ma[3], 0.4)

    def test_nan_in_numeric_success_column(self):
        df = pd.DataFrame({"Episode": [1, 2, 3], "success": [1.0, np.nan, 0.0]})
        res = compute_metric_series(df, "__success_rate__", window=10)
        self.assertTrue(res.has_data)
        self.assertAlmostEqual(res.y_ma[0], 100.0)
        self.assertTrue(np.isnan(res.y_ma[1]))
        self.assertAlmostEqual(res.y_ma[2], 50.0)

        df_all_nan = pd.DataFrame({"Episode": [1, 2], "success": [np.nan, np.nan]})
        self.assertFalse(compute_metric_series(df_all_nan, "__success_rate__").has_data)
        df_all_nan2 = pd.DataFrame({"Episode": [1, 2], "collision": [np.nan, np.nan]})
        self.assertFalse(compute_metric_series(df_all_nan2, "__collision_rate__").has_data)

    def test_converged_marker_skipped_on_nan(self):
        df = pd.DataFrame({
            "Episode": [1, 2, 3],
            "TotalReward": [1.0, np.nan, 3.0],
            "Is_Converged": [False, True, True],
        })
        res = compute_metric_series(df, "__reward__", window=1)
        self.assertEqual(res.converged_episodes, [3])
        self.assertEqual(res.converged_y_values, [3.0])

    def test_result_column_case_and_whitespace(self):
        df = pd.DataFrame({
            "Episode": [1, 2, 3, 4],
            "Result": ["goal", " Goal", "Collision ", "failed"],
        })
        res = compute_metric_series(df, "__success_rate__", window=4)
        self.assertAlmostEqual(res.y_ma[-1], 50.0)
        res = compute_metric_series(df, "__collision_rate__", window=4)
        self.assertAlmostEqual(res.y_ma[-1], 25.0)

    def test_read_csv_robust_encodings(self):
        from src.core.parsers.csv_metric import _read_csv_robust
        text = "step,報酬\n1,1.0\n2,2.0\n"
        for name, encoding in (("bom", "utf-8-sig"), ("sjis", "cp932")):
            with self.subTest(encoding=encoding):
                folder = self._write_folder(name, text, encoding=encoding)
                df = _read_csv_robust(os.path.join(folder, "progress.csv"))
                self.assertEqual(list(df.columns), ["step", "報酬"])
                df2 = read_log_csv(folder)
                self.assertIn("報酬", df2.columns)

    def test_load_task_dataframe_fallback_uses_total_episode(self):
        from src.core.parsers.csv_metric import load_task_dataframe, TaskOption
        folder = os.path.join(self.test_dir, "fallback")
        os.makedirs(folder, exist_ok=True)
        pd.DataFrame({"Total_Episode": [11, 12], "TotalReward": [1.0, 2.0]}).to_csv(
            os.path.join(folder, "log_task_3.csv"), index=False)
        df = load_task_dataframe(None, folder, TaskOption(task_id=3, display_name="Task 3", short_name="Task 3"))
        self.assertEqual(list(df["Episode"]), [11, 12])


if __name__ == "__main__":
    unittest.main()

