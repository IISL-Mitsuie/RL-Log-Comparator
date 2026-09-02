"""
仕様書ガイドビューウィジェット (LogSpecWidget) の単体テスト
"""

import unittest
from src.ui.widgets.log_spec_widget import LogSpecWidget
from tests.helpers import get_qapp


class TestUiLogSpecWidget(unittest.TestCase):
    """LogSpecWidget の UI テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def test_markdown_rendering(self):
        widget = LogSpecWidget()
        text = widget.text_browser.toPlainText()
        self.assertTrue(len(text) > 0)

    def test_reload_spec(self):
        widget = LogSpecWidget()
        widget.reload_spec()
        self.assertTrue(len(widget.text_browser.toPlainText()) > 0)


if __name__ == "__main__":
    unittest.main()
