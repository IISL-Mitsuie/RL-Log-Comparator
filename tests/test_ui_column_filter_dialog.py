"""
ColumnFilterDialogの単体テスト
"""

import pytest
from PySide6.QtCore import Qt
from src.ui.dialogs.column_filter_dialog import ColumnFilterDialog


def test_column_filter_dialog_init(qtbot):
    """ダイアログの初期化と全選択状態の確認"""
    unique_vals = ["S-SAP", "Q-SAP", "Random"]
    dlg = ColumnFilterDialog("モード", unique_vals)
    qtbot.addWidget(dlg)

    assert dlg.list_widget.count() == 3
    # 初期状態では全選択
    for i in range(3):
        assert dlg.list_widget.item(i).checkState() == Qt.CheckState.Checked

    # 全て選択されている場合は is_filtered が False
    is_filtered, selected = dlg.get_filter_result()
    assert is_filtered is False
    assert selected == {"S-SAP", "Q-SAP", "Random"}


def test_column_filter_dialog_select_partial(qtbot):
    """一部の値を選択した際のフィルター結果"""
    unique_vals = ["0.0001", "0.0003", "0.001"]
    dlg = ColumnFilterDialog("learning_rate", unique_vals, current_selected_values=["0.0003"])
    qtbot.addWidget(dlg)

    assert dlg.list_widget.item(0).checkState() == Qt.CheckState.Unchecked
    assert dlg.list_widget.item(1).checkState() == Qt.CheckState.Checked
    assert dlg.list_widget.item(2).checkState() == Qt.CheckState.Unchecked

    is_filtered, selected = dlg.get_filter_result()
    assert is_filtered is True
    assert selected == {"0.0003"}


def test_column_filter_dialog_quick_buttons_and_search(qtbot):
    """すべて解除・すべて選択・検索フィルタの挙動"""
    unique_vals = ["apple", "banana", "cherry"]
    dlg = ColumnFilterDialog("fruits", unique_vals)
    qtbot.addWidget(dlg)

    # すべて解除
    dlg._select_none()
    is_filtered, selected = dlg.get_filter_result()
    assert is_filtered is True
    assert selected == set()

    # すべて選択
    dlg._select_all()
    is_filtered, selected = dlg.get_filter_result()
    assert is_filtered is False
    assert selected == {"apple", "banana", "cherry"}

    # 検索フィルタ
    dlg._filter_items("ban")
    assert dlg.list_widget.item(0).isHidden() is True
    assert dlg.list_widget.item(1).isHidden() is False
    assert dlg.list_widget.item(2).isHidden() is True


def test_column_filter_dialog_clear_filter(qtbot):
    """「この列のフィルターを解除」ボタンの挙動"""
    unique_vals = ["A", "B"]
    dlg = ColumnFilterDialog("test", unique_vals, current_selected_values=["A"])
    qtbot.addWidget(dlg)

    dlg._on_clear_clicked()
    is_filtered, selected = dlg.get_filter_result()
    assert is_filtered is False
    assert selected == {"A", "B"}
