"""
パス解決・リソース読み込みモジュール (src.core.paths) の単体テスト
"""

import os
import unittest
from src.core.paths import (
    get_project_root,
    get_bundled_font_path,
    get_app_icon_path,
    get_log_spec_path,
    load_log_spec_markdown
)


class TestPaths(unittest.TestCase):
    """パス解決関数のテスト"""

    def test_get_project_root(self):
        root = get_project_root()
        self.assertTrue(os.path.isdir(root))
        self.assertTrue(os.path.exists(os.path.join(root, "main.py")))

    def test_get_log_spec_path(self):
        spec_path = get_log_spec_path()
        self.assertTrue(os.path.exists(spec_path))
        self.assertTrue(spec_path.endswith(".md"))

    def test_load_log_spec_markdown(self):
        content = load_log_spec_markdown()
        self.assertIsInstance(content, str)
        self.assertIn("#", content)
        self.assertNotIn("仕様書ファイルが見つかりません", content)

    def test_get_bundled_font_path(self):
        # 開発環境またはパッケージ内にフォントが存在する場合の検証
        font_path = get_bundled_font_path()
        if font_path:
            self.assertTrue(os.path.exists(font_path))
            self.assertTrue(font_path.endswith(".ttf"))

    def test_get_app_icon_path(self):
        icon_path = get_app_icon_path()
        if icon_path:
            self.assertTrue(os.path.exists(icon_path))


if __name__ == "__main__":
    unittest.main()
