"""
キーボードショートカット一覧ダイアログ (ShortcutsDialog) の単体テスト
"""

import unittest
from src.ui.dialogs.shortcuts_dialog import ShortcutsDialog, SHORTCUT_DATA
from tests.helpers import get_qapp


class TestShortcutsDialog(unittest.TestCase):
    """ShortcutsDialog の単体テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def test_dialog_init_and_contents(self):
        """ダイアログが正常に初期化され、全ショートカット項目がツリーに格納されていることの検証"""
        dialog = ShortcutsDialog()
        self.assertEqual(dialog.windowTitle(), "キーボードショートカット一覧")

        root = dialog.tree.invisibleRootItem()
        self.assertEqual(root.childCount(), len(SHORTCUT_DATA))

        total_shortcuts = 0
        for i, (cat_title, items) in enumerate(SHORTCUT_DATA):
            cat_item = root.child(i)
            self.assertEqual(cat_item.text(0), cat_title)
            self.assertEqual(cat_item.childCount(), len(items))
            for j, (action_name, shortcut_key) in enumerate(items):
                child = cat_item.child(j)
                self.assertEqual(child.text(0), action_name)
                self.assertEqual(child.text(1), shortcut_key)
                total_shortcuts += 1

        self.assertGreaterEqual(total_shortcuts, 12)

    def test_filter_items(self):
        """検索ボックス入力による動的絞り込みの検証"""
        dialog = ShortcutsDialog()
        root = dialog.tree.invisibleRootItem()

        # 1. "Ctrl+O" で検索
        dialog.edit_search.setText("Ctrl+O")
        # フォルダAを開く (Ctrl+O) は表示され、アプリケーション終了 (Ctrl+Q) は非表示
        file_cat = root.child(0)
        self.assertFalse(file_cat.isHidden())
        self.assertFalse(file_cat.child(0).isHidden())  # フォルダ A を開く… (Ctrl+O)
        self.assertTrue(file_cat.child(3).isHidden())   # アプリケーション終了 (Ctrl+Q)

        # 2. カテゴリ名 "タブ" で検索
        dialog.edit_search.setText("タブ")
        tab_cat = root.child(1)
        self.assertFalse(tab_cat.isHidden())
        # カテゴリ名がマッチするため子項目もすべて表示
        for j in range(tab_cat.childCount()):
            self.assertFalse(tab_cat.child(j).isHidden())

        # 3. 該当なしの文字列
        dialog.edit_search.setText("存在しない操作キーワードXYZ")
        for i in range(root.childCount()):
            self.assertTrue(root.child(i).isHidden())

        # 4. クリアして全表示復帰
        dialog.edit_search.clear()
        for i in range(root.childCount()):
            cat_item = root.child(i)
            self.assertFalse(cat_item.isHidden())
            for j in range(cat_item.childCount()):
                self.assertFalse(cat_item.child(j).isHidden())

    def test_close_button(self):
        """閉じるボタンをクリックしてダイアログが終了することの検証"""
        dialog = ShortcutsDialog()
        self.assertIsNotNone(dialog.btn_close)
        # accept されることを確認
        dialog.btn_close.click()
        self.assertEqual(dialog.result(), ShortcutsDialog.DialogCode.Accepted)


if __name__ == "__main__":
    unittest.main()
