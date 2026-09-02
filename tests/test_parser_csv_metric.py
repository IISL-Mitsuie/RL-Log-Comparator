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


if __name__ == "__main__":
    unittest.main()
