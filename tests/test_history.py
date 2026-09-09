"""
履歴管理モジュール (src.core.history) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
from src.core.history import RecentFolderManager


class TestHistory(unittest.TestCase):
    """RecentFolderManager のテスト"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dirs = [
            os.path.join(self.test_dir, f"dir_{i}")
            for i in range(10)
        ]
        for d in self.dirs:
            os.makedirs(d, exist_ok=True)

        self.mgr = RecentFolderManager(
            org="IISL_TestHistory",
            app="RL_Log_Comparator_TestHistory",
            max_count=5
        )
        self.mgr.clear_history()

    def tearDown(self):
        self.mgr.clear_history()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initial_empty(self):
        history = self.mgr.load_history()
        self.assertEqual(history, [])

    def test_add_folder(self):
        self.mgr.add_folder(self.dirs[0])
        history = self.mgr.load_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0], os.path.abspath(self.dirs[0]))

    def test_mru_order(self):
        self.mgr.add_folder(self.dirs[0])
        self.mgr.add_folder(self.dirs[1])
        self.mgr.add_folder(self.dirs[2])

        # 直近に追加したものが先頭
        history = self.mgr.load_history()
        self.assertEqual(history[0], os.path.abspath(self.dirs[2]))
        self.assertEqual(history[1], os.path.abspath(self.dirs[1]))
        self.assertEqual(history[2], os.path.abspath(self.dirs[0]))

        # 既存の dirs[0] を再追加すると先頭に昇格
        self.mgr.add_folder(self.dirs[0])
        history = self.mgr.load_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0], os.path.abspath(self.dirs[0]))

    def test_max_count_limit(self):
        # 7件追加（上限は5件）
        for i in range(7):
            self.mgr.add_folder(self.dirs[i])

        history = self.mgr.load_history()
        self.assertEqual(len(history), 5)
        # 最も新しい dirs[6] が先頭、古い dirs[0], dirs[1] は押し出されて除外
        self.assertEqual(history[0], os.path.abspath(self.dirs[6]))
        self.assertNotIn(os.path.abspath(self.dirs[0]), history)
        self.assertNotIn(os.path.abspath(self.dirs[1]), history)

    def test_filter_nonexistent_paths(self):
        temp_sub = os.path.join(self.test_dir, "temp_to_delete")
        os.makedirs(temp_sub, exist_ok=True)

        self.mgr.add_folder(self.dirs[0])
        self.mgr.add_folder(temp_sub)

        history = self.mgr.load_history()
        self.assertEqual(len(history), 2)

        # フォルダを削除
        os.rmdir(temp_sub)

        # 読み込み時に実在しないパスが自動除外される
        history_after = self.mgr.load_history()
        self.assertEqual(len(history_after), 1)
        self.assertEqual(history_after[0], os.path.abspath(self.dirs[0]))

    def test_custom_settings_key(self):
        mgr_custom = RecentFolderManager(
            org="IISL_TestHistory",
            app="RL_Log_Comparator_TestHistory",
            settings_key="custom_root_key",
            max_count=3
        )
        mgr_custom.clear_history()
        mgr_custom.add_folder(self.dirs[0])
        mgr_custom.add_folder(self.dirs[1])

        self.assertEqual(len(mgr_custom.load_history()), 2)
        # 通常のマネージャーには影響しないこと
        self.assertEqual(self.mgr.load_history(), [])
        mgr_custom.clear_history()


class TestSessionStateManager(unittest.TestCase):
    """SessionStateManager のテスト"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dir_root = os.path.join(self.test_dir, "root")
        self.dir_a = os.path.join(self.test_dir, "dir_a")
        self.dir_b = os.path.join(self.test_dir, "dir_b")
        os.makedirs(self.dir_root, exist_ok=True)
        os.makedirs(self.dir_a, exist_ok=True)
        os.makedirs(self.dir_b, exist_ok=True)

        from src.core.history import SessionStateManager
        self.session_mgr = SessionStateManager(
            org="IISL_TestSession",
            app="RL_Log_Comparator_TestSession"
        )
        self.session_mgr.clear_last_paths()

    def tearDown(self):
        self.session_mgr.clear_last_paths()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_load_paths(self):
        self.session_mgr.save_last_paths(
            root_dir=self.dir_root,
            folder_a=self.dir_a,
            folder_b=self.dir_b
        )

        paths = self.session_mgr.load_last_paths()
        self.assertEqual(paths.get("root_dir"), os.path.abspath(self.dir_root))
        self.assertEqual(paths.get("folder_a"), os.path.abspath(self.dir_a))
        self.assertEqual(paths.get("folder_b"), os.path.abspath(self.dir_b))

    def test_load_nonexistent_paths_filtered(self):
        fake_path = os.path.join(self.test_dir, "nonexistent")
        self.session_mgr.save_last_paths(
            root_dir=self.dir_root,
            folder_a=fake_path,
            folder_b=self.dir_b
        )

        paths = self.session_mgr.load_last_paths()
        self.assertEqual(paths.get("root_dir"), os.path.abspath(self.dir_root))
        self.assertNotIn("folder_a", paths)
        self.assertEqual(paths.get("folder_b"), os.path.abspath(self.dir_b))

    def test_clear_last_paths(self):
        self.session_mgr.save_last_paths(
            root_dir=self.dir_root,
            folder_a=self.dir_a,
            folder_b=self.dir_b
        )
        self.session_mgr.clear_last_paths()
        self.assertEqual(self.session_mgr.load_last_paths(), {})


if __name__ == "__main__":
    unittest.main()

