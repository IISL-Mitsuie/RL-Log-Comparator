"""
ExperimentExplorerWidget の UI テスト
"""

import os
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from src.ui.widgets.experiment_explorer_widget import ExperimentExplorerWidget
from src.ui.dialogs.experiment_action_dialog import ExperimentActionDialog, ExperimentAction
from tests.helpers import get_qapp, create_dummy_experiment_folder


@pytest.fixture
def explorer_widget(qtbot):
    get_qapp()
    widget = ExperimentExplorerWidget()
    # テスト専用の RecentFolderManager を設定し本番 QSettings を汚染しないようにする
    from src.core.history import RecentFolderManager
    test_mgr = RecentFolderManager(
        org="IISL_Test",
        app="RL_Test_Explorer",
        settings_key="test_root_dirs"
    )
    test_mgr.clear_history()
    widget.history_mgr = test_mgr
    widget._history = []
    widget._update_history_combo()

    qtbot.addWidget(widget)
    yield widget
    # テスト終了後に履歴を抹消
    test_mgr.clear_history()


def test_widget_init(explorer_widget):
    assert explorer_widget.table.columnCount() == 0
    assert explorer_widget.preview_tabs.count() == 1
    assert explorer_widget.preview_tabs.tabText(0) == "画像なし"
    assert explorer_widget.cb_recursive.isChecked() is True


def test_scan_and_populate_table(explorer_widget, tmp_path):
    s_sap_dir = tmp_path / "S-SAP"
    s_sap_dir.mkdir()
    folder1 = create_dummy_experiment_folder(str(s_sap_dir), "output_20260801_100000", mode="S-SAP", learning_rate=0.01)
    folder2 = create_dummy_experiment_folder(str(s_sap_dir), "output_20260802_150000", mode="S-SAP", learning_rate=0.02)

    explorer_widget.set_root_directory(str(tmp_path))

    # テーブルに2行存在すること
    assert explorer_widget.table.rowCount() == 2
    # ヘッダー列: モード, Shield, フォルダ名, タイムスタンプ, ...
    assert explorer_widget.table.horizontalHeaderItem(0).text() == "モード"
    assert explorer_widget.table.horizontalHeaderItem(1).text() == "Shield"
    assert explorer_widget.table.horizontalHeaderItem(2).text() == "フォルダ名"
    assert explorer_widget.table.horizontalHeaderItem(3).text() == "タイムスタンプ"

    # 1行目（新しい順）の確認
    assert explorer_widget.table.item(0, 0).text() == "S-SAP"
    assert explorer_widget.table.item(0, 1).text() == "-"
    assert explorer_widget.table.item(0, 2).text() == "output_20260802_150000"
    assert "2026/08/02" in explorer_widget.table.item(0, 3).text()

    # 動的プレビュータブがアルファベット順に生成されていること
    assert explorer_widget.preview_tabs.count() == 3
    assert explorer_widget.preview_tabs.tabText(0) == "learning_rewards"
    assert explorer_widget.preview_tabs.tabText(1) == "learning_steps"
    assert explorer_widget.preview_tabs.tabText(2) == "trajectory"


def test_tab_index_preservation_on_selection_change(explorer_widget, tmp_path):
    """ログ選択を変えてもプレフィックス名ベースでタブ選択が維持されることの検証"""
    s_sap_dir = tmp_path / "S-SAP"
    s_sap_dir.mkdir()
    create_dummy_experiment_folder(str(s_sap_dir), "output_20260801_100000", mode="S-SAP")
    create_dummy_experiment_folder(str(s_sap_dir), "output_20260802_150000", mode="S-SAP")

    explorer_widget.set_root_directory(str(tmp_path))

    # タブをインデックス1 (learning_steps) に切り替え
    explorer_widget.preview_tabs.setCurrentIndex(1)
    assert explorer_widget.preview_tabs.currentIndex() == 1
    assert explorer_widget.preview_tabs.tabText(1) == "learning_steps"

    # テーブルの選択行を2行目（インデックス1）に変更
    explorer_widget.table.selectRow(1)

    # 行が変わっても learning_steps タブの選択が維持されていること
    assert explorer_widget.preview_tabs.currentIndex() == 1
    assert explorer_widget.preview_tabs.tabText(explorer_widget.preview_tabs.currentIndex()) == "learning_steps"


def test_dynamic_tabs_with_different_images_and_no_images(explorer_widget, tmp_path):
    """ログごとに画像構成が異なる場合や、画像が存在しない場合の動的タブ挙動テスト"""
    s_dir = tmp_path / "S-SAP"
    s_dir.mkdir()

    # ログ1: learning_rewards と trajectory のみ
    create_dummy_experiment_folder(
        str(s_dir),
        "output_20260801_100000",
        mode="S-SAP",
        images=["learning_rewards_001.png", "trajectory_001.png"]
    )
    # ログ2: 画像なし (空フォルダ)
    create_dummy_experiment_folder(
        str(s_dir),
        "output_20260802_150000",
        mode="S-SAP",
        images=[]
    )

    explorer_widget.set_root_directory(str(tmp_path))

    # 1行目 (output_20260802_150000: 画像なし) を選択
    explorer_widget.table.selectRow(0)
    assert explorer_widget.preview_tabs.count() == 1
    assert explorer_widget.preview_tabs.tabText(0) == "画像なし"

    # 2行目 (output_20260801_100000: 2画像) を選択
    explorer_widget.table.selectRow(1)
    assert explorer_widget.preview_tabs.count() == 2
    assert explorer_widget.preview_tabs.tabText(0) == "learning_rewards"
    assert explorer_widget.preview_tabs.tabText(1) == "trajectory"

    # trajectory タブ (インデックス1) を選択
    explorer_widget.preview_tabs.setCurrentIndex(1)
    assert explorer_widget.preview_tabs.tabText(explorer_widget.preview_tabs.currentIndex()) == "trajectory"

    # 再度1行目 (画像なし) を選択
    explorer_widget.table.selectRow(0)
    assert explorer_widget.preview_tabs.count() == 1
    assert explorer_widget.preview_tabs.tabText(0) == "画像なし"

    # 再び2行目を選択した際、記憶されていた trajectory タブへ自動復帰すること
    explorer_widget.table.selectRow(1)
    assert explorer_widget.preview_tabs.currentIndex() == 1
    assert explorer_widget.preview_tabs.tabText(explorer_widget.preview_tabs.currentIndex()) == "trajectory"


def test_signals_set_folder_a_and_b(explorer_widget, tmp_path, qtbot):
    s_sap_dir = tmp_path / "S-SAP"
    s_sap_dir.mkdir()
    folder1 = create_dummy_experiment_folder(str(s_sap_dir), "output_20260801_100000", mode="S-SAP")

    explorer_widget.set_root_directory(str(tmp_path))
    explorer_widget.table.selectRow(0)

    # フォルダAセットのシグナル検証
    with qtbot.waitSignal(explorer_widget.request_set_folder_a, timeout=1000) as blocker_a:
        explorer_widget._set_selected_as_a()
    assert blocker_a.args[0] == folder1

    # フォルダBセットのシグナル検証
    with qtbot.waitSignal(explorer_widget.request_set_folder_b, timeout=1000) as blocker_b:
        explorer_widget._set_selected_as_b()
    assert blocker_b.args[0] == folder1


def test_quick_filter(explorer_widget, tmp_path):
    s_sap_dir = tmp_path / "S-SAP"
    q_sap_dir = tmp_path / "Q-SAP"
    s_sap_dir.mkdir()
    q_sap_dir.mkdir()
    create_dummy_experiment_folder(str(s_sap_dir), "output_20260801_100000", mode="S-SAP")
    create_dummy_experiment_folder(str(q_sap_dir), "output_20260802_150000", mode="Q-SAP")

    explorer_widget.set_root_directory(str(tmp_path))
    assert explorer_widget.table.rowCount() == 2

    # "Q-SAP" でフィルタ
    explorer_widget.edit_filter.setText("Q-SAP")
    assert explorer_widget.table.isRowHidden(0) is False  # Q-SAP行
    assert explorer_widget.table.isRowHidden(1) is True   # S-SAP行

    # フィルタ解除
    explorer_widget.edit_filter.setText("")
    assert explorer_widget.table.isRowHidden(0) is False
    assert explorer_widget.table.isRowHidden(1) is False


def test_mode_and_shield_display_with_reference_yaml(explorer_widget, tmp_path):
    """reference/config_used_20260909_145945.yaml 形式のデータでモードとShield表示を検証"""
    import shutil
    ref_yaml = os.path.join(os.path.dirname(__file__), "..", "reference", "config_used_20260909_145945.yaml")
    
    exp_dir = tmp_path / "S-SAP" / "output_20260909_145945"
    exp_dir.mkdir(parents=True)
    shutil.copy(ref_yaml, exp_dir / "config_used_20260909_145945.yaml")

    explorer_widget.set_root_directory(str(tmp_path))
    assert explorer_widget.table.rowCount() == 1

    # モードが S-SAP、Shield が 無効 と表示されること
    assert explorer_widget.table.item(0, 0).text() == "S-SAP"
    assert explorer_widget.table.item(0, 1).text() == "無効"
    assert explorer_widget.table.item(0, 2).text() == "output_20260909_145945"
    assert "2026/09/09" in explorer_widget.table.item(0, 3).text()


def test_toggle_sidebar(explorer_widget):
    """サイドバーの開閉およびトグルボタンの挙動テスト"""
    assert explorer_widget.preview_container.isHidden() is False
    assert "プレビュー非表示" in explorer_widget.btn_toggle_sidebar.text()

    # 1. ✕ ボタンで閉じる
    explorer_widget.btn_close_sidebar.click()
    assert explorer_widget.preview_container.isHidden() is True
    assert "プレビュー表示" in explorer_widget.btn_toggle_sidebar.text()

    # 2. トグルボタンで開く
    explorer_widget.btn_toggle_sidebar.click()
    assert explorer_widget.preview_container.isHidden() is False
    assert "プレビュー非表示" in explorer_widget.btn_toggle_sidebar.text()

    # 3. トグルボタンで再度閉じる
    explorer_widget.btn_toggle_sidebar.click()
    assert explorer_widget.preview_container.isHidden() is True
    assert "プレビュー表示" in explorer_widget.btn_toggle_sidebar.text()


def test_column_visibility_integration(explorer_widget, tmp_path):
    """カラム非表示設定とテーブルへの反映テスト"""
    s_sap_dir = tmp_path / "S-SAP"
    s_sap_dir.mkdir()
    create_dummy_experiment_folder(str(s_sap_dir), "output_20260801_100000", mode="S-SAP", learning_rate=0.01)

    explorer_widget.set_root_directory(str(tmp_path))
    assert explorer_widget.table.isColumnHidden(0) is False  # モード列
    assert explorer_widget.table.isColumnHidden(1) is False  # Shield列
    assert explorer_widget.table.isColumnHidden(2) is False  # フォルダ名列
    assert explorer_widget.table.isColumnHidden(3) is True   # タイムスタンプ列 (デフォルト非表示)

    # Shield列を非表示にする
    explorer_widget._hidden_column_names.add("Shield")
    explorer_widget._apply_column_visibility()

    assert explorer_widget.table.isColumnHidden(0) is False
    assert explorer_widget.table.isColumnHidden(1) is True

    # タイムスタンプ列を表示にする
    explorer_widget._hidden_column_names.discard("タイムスタンプ")
    explorer_widget._apply_column_visibility()
    assert explorer_widget.table.isColumnHidden(3) is False


def test_column_filter_apply_and_clear(explorer_widget, tmp_path):
    """列ごとのフィルター適用とヘッダー表示、クリアのテスト"""
    s_sap_dir = tmp_path / "S-SAP"
    s_sap_dir.mkdir()
    create_dummy_experiment_folder(str(s_sap_dir), "output_20260801_100000", mode="S-SAP")

    q_sap_dir = tmp_path / "Q-SAP"
    q_sap_dir.mkdir()
    create_dummy_experiment_folder(str(q_sap_dir), "output_20260801_110000", mode="Q-SAP")

    explorer_widget.set_root_directory(str(tmp_path))
    assert explorer_widget.table.rowCount() == 2
    assert explorer_widget.table.isRowHidden(0) is False
    assert explorer_widget.table.isRowHidden(1) is False

    # 「モード」列に "S-SAP" のみのフィルターを適用
    explorer_widget._column_filters["モード"] = {"S-SAP"}
    explorer_widget._update_header_labels()
    explorer_widget._apply_filter()

    # ヘッダーに 🔍 が付いていることを確認
    header_item = explorer_widget.table.horizontalHeaderItem(0)
    assert header_item.text() == "モード 🔍"

    # 行の表示判定: S-SAP行が表示され、Q-SAP行が隠れる
    visible_modes = []
    for r in range(explorer_widget.table.rowCount()):
        if not explorer_widget.table.isRowHidden(r):
            visible_modes.append(explorer_widget.table.item(r, 0).text())
    assert visible_modes == ["S-SAP"]
    assert explorer_widget.btn_reset_all_filters.isEnabled() is True

    # フィルターを解除
    explorer_widget.clear_column_filter("モード")
    assert header_item.text() == "モード"
    assert explorer_widget.table.isRowHidden(0) is False
    assert explorer_widget.table.isRowHidden(1) is False
    assert explorer_widget.btn_reset_all_filters.isEnabled() is False


def test_column_filter_combined_with_quick_filter(explorer_widget, tmp_path):
    """クイックフィルタと列フィルタの組み合わせおよび一括全解除テスト"""
    s1 = tmp_path / "S1"
    s1.mkdir()
    create_dummy_experiment_folder(str(s1), "output_20260801_100000", mode="S-SAP", learning_rate=0.01)

    s2 = tmp_path / "S2"
    s2.mkdir()
    create_dummy_experiment_folder(str(s2), "output_20260802_100000", mode="S-SAP", learning_rate=0.001)

    q1 = tmp_path / "Q1"
    q1.mkdir()
    create_dummy_experiment_folder(str(q1), "output_20260801_200000", mode="Q-SAP", learning_rate=0.01)

    explorer_widget.set_root_directory(str(tmp_path))
    assert explorer_widget.table.rowCount() == 3

    # 列フィルタ: モード=S-SAP (s1, s2の2件)
    explorer_widget._column_filters["モード"] = {"S-SAP"}
    # クイックフィルタ: "20260802" (s2の1件のみ合致)
    explorer_widget.edit_filter.setText("20260802")

    visible_rows = [r for r in range(3) if not explorer_widget.table.isRowHidden(r)]
    assert len(visible_rows) == 1

    # 一括全解除
    explorer_widget.clear_all_filters()
    assert explorer_widget.edit_filter.text() == ""
    assert len(explorer_widget._column_filters) == 0
    visible_all = [r for r in range(3) if not explorer_widget.table.isRowHidden(r)]
    assert len(visible_all) == 3


def test_table_shift_wheel_horizontal_scroll(explorer_widget, tmp_path):
    """Shift + ホイールスクロールで横スクロールが行われることをテスト"""
    s_dir = tmp_path / "S-SAP"
    s_dir.mkdir()
    create_dummy_experiment_folder(str(s_dir), "output_20260801_100000", mode="S-SAP")
    explorer_widget.set_root_directory(str(tmp_path))

    # 各列の幅を広げてウィンドウを小さくし、横スクロールバーを発生させる
    for c in range(explorer_widget.table.columnCount()):
        explorer_widget.table.setColumnWidth(c, 300)
    explorer_widget.table.resize(200, 200)
    explorer_widget.table.show()

    h_bar = explorer_widget.table.horizontalScrollBar()
    assert h_bar.maximum() > 0

    init_val = h_bar.value()

    # Shift + 下スクロール (delta_y = -120 -> 右へスクロール)
    event_down = QWheelEvent(
        QPointF(50, 50),
        QPointF(50, 50),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ShiftModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False
    )
    explorer_widget.table.wheelEvent(event_down)
    assert h_bar.value() > init_val

    # Shift + 上スクロール (delta_y = 120 -> 左へスクロール)
    cur_val = h_bar.value()
    event_up = QWheelEvent(
        QPointF(50, 50),
        QPointF(50, 50),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ShiftModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False
    )
    explorer_widget.table.wheelEvent(event_up)
    assert h_bar.value() < cur_val


def test_hide_column_by_header_action(explorer_widget, tmp_path):
    """ヘッダーアクション経由での列非表示テスト"""
    s_dir = tmp_path / "S-SAP"
    s_dir.mkdir()
    create_dummy_experiment_folder(str(s_dir), "output_20260801_100000", mode="S-SAP")
    explorer_widget.set_root_directory(str(tmp_path))

    # 初期状態: モード列(0), Shield列(1) ともに表示中
    assert explorer_widget.table.isColumnHidden(0) is False
    assert explorer_widget.table.isColumnHidden(1) is False

    # Shield列を非表示にする
    explorer_widget.hide_column("Shield")
    assert explorer_widget.table.isColumnHidden(1) is True
    assert "Shield" in explorer_widget._hidden_column_names


def test_root_directory_history(explorer_widget, tmp_path):
    """探索ルートフォルダの入力履歴機能テスト"""
    from src.core.history import RecentFolderManager
    test_mgr = RecentFolderManager(
        org="IISL_Test",
        app="RL_Test_Explorer",
        settings_key="test_root_dirs"
    )
    test_mgr.clear_history()
    explorer_widget.history_mgr = test_mgr
    explorer_widget._history = []
    explorer_widget._update_history_combo()

    dir1 = tmp_path / "root1"
    dir1.mkdir()
    dir2 = tmp_path / "root2"
    dir2.mkdir()

    # dir1 をスキャン
    explorer_widget.set_root_directory(str(dir1))
    assert explorer_widget.get_root_directory() == str(dir1.resolve())
    assert len(explorer_widget._history) == 1
    assert explorer_widget._history[0] == str(dir1.resolve())

    # dir2 をスキャン
    explorer_widget.set_root_directory(str(dir2))
    assert explorer_widget.get_root_directory() == str(dir2.resolve())
    assert len(explorer_widget._history) == 2
    assert explorer_widget._history[0] == str(dir2.resolve())
    assert explorer_widget._history[1] == str(dir1.resolve())

    # コンボボックスのアイテム数確認（履歴2件 + セパレータ + クリア = 4件）
    assert explorer_widget.combo_root_dir.count() == 4
    assert explorer_widget.combo_root_dir.itemText(0) == str(dir2.resolve())
    assert explorer_widget.combo_root_dir.itemText(1) == str(dir1.resolve())

    # コンボボックスから dir1 を選択
    explorer_widget._on_root_combo_activated(1)
    assert explorer_widget.get_root_directory() == str(dir1.resolve())

    test_mgr.clear_history()






