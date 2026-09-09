"""
ColumnVisibilityDialog の単体テスト
"""

import pytest
from PySide6.QtCore import Qt
from src.ui.dialogs.column_visibility_dialog import ColumnVisibilityDialog, DEFAULT_BASIC_COLUMNS
from tests.helpers import get_qapp


@pytest.fixture
def sample_columns():
    return ["モード", "Shield", "タイムスタンプ", "フォルダ名", "reward.goal", "qlearning.alpha"]


def test_dialog_init(sample_columns):
    get_qapp()
    hidden = {"reward.goal"}
    dlg = ColumnVisibilityDialog(sample_columns, hidden_columns=hidden)

    assert dlg.list_widget.count() == 6
    # reward.goal は非表示（Unchecked）
    item_goal = dlg.list_widget.item(4)
    assert item_goal.text() == "reward.goal"
    assert item_goal.checkState() == Qt.CheckState.Unchecked

    # モード は表示（Checked）
    item_mode = dlg.list_widget.item(0)
    assert item_mode.text() == "モード"
    assert item_mode.checkState() == Qt.CheckState.Checked


def test_quick_buttons(sample_columns):
    get_qapp()
    dlg = ColumnVisibilityDialog(sample_columns)

    # 1. すべて非表示
    dlg._select_none()
    assert dlg.get_hidden_columns() == set(sample_columns)

    # 2. すべて表示
    dlg._select_all()
    assert dlg.get_hidden_columns() == set()

    # 3. 基本列のみ（モード、Shield、フォルダ名）
    dlg._select_basic_only()
    hidden = dlg.get_hidden_columns()
    assert "reward.goal" in hidden
    assert "qlearning.alpha" in hidden
    assert "タイムスタンプ" in hidden
    assert "モード" not in hidden
    assert "フォルダ名" not in hidden
    assert "Shield" not in hidden


def test_search_filter(sample_columns):
    get_qapp()
    dlg = ColumnVisibilityDialog(sample_columns)

    dlg.edit_search.setText("reward")
    assert dlg.list_widget.item(4).isHidden() is False  # reward.goal
    assert dlg.list_widget.item(0).isHidden() is True   # モード
