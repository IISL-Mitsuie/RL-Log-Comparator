"""
CSV 数値ログ解析モジュール (src.core.parsers.csv_metric) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
import pandas as pd
from src.core.parsers.csv_metric import (
    read_log_csv, compute_metric_series, METRIC_DEFINITIONS, MetricSeriesData
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


if __name__ == "__main__":
    unittest.main()
