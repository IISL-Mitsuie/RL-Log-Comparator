"""
環境初期化モジュール (src.core.env) の単体テスト
"""

import os
import unittest
import matplotlib.pyplot as plt
from src.core.env import (
    setup_app_user_model_id,
    setup_mpl_cache_dir,
    setup_matplotlib_japanese_font,
    initialize_environment
)


class TestEnv(unittest.TestCase):
    """実行環境・フォント設定関数のテスト"""

    def test_setup_app_user_model_id(self):
        # 例外が発生しないことを検証
        setup_app_user_model_id()

    def test_setup_mpl_cache_dir(self):
        setup_mpl_cache_dir()
        self.assertIn('MPLCONFIGDIR', os.environ)
        cache_dir = os.environ['MPLCONFIGDIR']
        self.assertTrue(os.path.isdir(cache_dir))

    def test_setup_matplotlib_japanese_font(self):
        setup_matplotlib_japanese_font()
        self.assertFalse(plt.rcParams['axes.unicode_minus'])
        self.assertEqual(plt.rcParams['text.color'], '#222222')
        self.assertTrue(len(plt.rcParams['font.family']) > 0)

    def test_initialize_environment(self):
        initialize_environment()
        self.assertIn('MPLCONFIGDIR', os.environ)


if __name__ == "__main__":
    unittest.main()
