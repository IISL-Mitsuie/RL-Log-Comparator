"""
ISSUE-05: 非同期 I/O、自動読み込みのデバウンス、世代番号、キャンセル動作のテスト
"""

import os
import shutil
import tempfile
import time
from unittest.mock import patch
from PySide6.QtGui import QImage, QColor
from src.ui.main_window import ExperimentCompareApp, ComparisonData
from src.ui.widgets.experiment_explorer_widget import (
    ExperimentExplorerWidget,
    _load_and_scale_image,
    MAX_PREVIEW_EDGE
)
from tests.helpers import create_dummy_experiment_folder, get_qapp


class TestAsyncIOAndDebounce:
    """自動読み込みデバウンスおよび世代番号制御のテスト"""

    def setup_method(self):
        get_qapp()
        self.test_dir = tempfile.mkdtemp()
        self.folder_a = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_a", mode="S-SAP"
        )
        self.folder_b = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_b", mode="Q-SAP"
        )

        from src.core.history import RecentFolderManager, SessionStateManager
        self.test_history_mgr = RecentFolderManager(org="IISL_Test", app="RL_Test_AsyncIO")
        self.test_history_mgr.clear_history()
        self.test_session_mgr = SessionStateManager(org="IISL_Test", app="RL_Test_AsyncIO")
        self.test_session_mgr.clear_last_paths()
        self.test_root_mgr = RecentFolderManager(org="IISL_Test", app="RL_Test_AsyncIO", settings_key="test_root_dirs")
        self.test_root_mgr.clear_history()

    def teardown_method(self):
        self.test_history_mgr.clear_history()
        self.test_session_mgr.clear_last_paths()
        self.test_root_mgr.clear_history()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_isolated_window(self) -> ExperimentCompareApp:
        window = ExperimentCompareApp()
        window.history_mgr = self.test_history_mgr
        window.session_mgr = self.test_session_mgr
        window._history = []
        window._update_history_combos()
        window.tab_explorer.history_mgr = self.test_root_mgr
        window.tab_explorer._history = []
        window.tab_explorer._update_history_combo()
        return window

    def test_debounce_continuous_input_triggers_only_once(self, qtbot):
        """フォルダ欄に短時間で連続入力した場合、最後の入力から500ms後に1回だけ読み込みが走ること"""
        window = self._create_isolated_window()
        qtbot.addWidget(window)

        # フォルダBはあらかじめ有効なフォルダに設定
        window.combo_folder_b.setEditText(self.folder_b)

        load_calls = []
        original_load_all = window.load_all

        def mock_load_all(*args, **kwargs):
            load_calls.append(time.time())
            return original_load_all(*args, **kwargs)

        window.load_all = mock_load_all

        # フォルダA欄に100msおきに文字を入力（計5回）
        partial_path = self.folder_a
        for i in range(1, len(partial_path) + 1):
            if i % 3 == 0 or i == len(partial_path):
                sub = partial_path[:i]
                window.combo_folder_a.lineEdit().setText(sub)
                qtbot.wait(60)  # 500ms 未満の間隔

        # 連続入力中はまだ load_all が呼ばれていないこと
        assert len(load_calls) == 0
        assert window._debounce_timer.isActive() is True

        # デバウンスタイマー（500ms）満了を待機
        qtbot.waitUntil(lambda: len(load_calls) == 1, timeout=1500)

        # 満了後も追加で呼ばれず、合計1回のみであることを確認
        qtbot.wait(200)
        assert len(load_calls) == 1

    def test_editing_finished_bypasses_debounce_timer(self, qtbot):
        """Enterキーやフォーカス移動（editingFinished）時はタイマーを待たずに即時読み込みされること"""
        window = self._create_isolated_window()
        qtbot.addWidget(window)

        window.combo_folder_b.setEditText(self.folder_b)

        load_calls = []
        window.load_all = lambda *args, **kwargs: load_calls.append(True)

        window.combo_folder_a.lineEdit().setText(self.folder_a)
        assert window._debounce_timer.isActive() is True

        # 即座に editingFinished を発火
        window.combo_folder_a.lineEdit().editingFinished.emit()

        # タイマーが停止し、即座に load_all が呼ばれたこと
        assert window._debounce_timer.isActive() is False
        assert len(load_calls) == 1

    def test_stale_generation_result_is_discarded(self, qtbot):
        """世代番号が古い非同期結果は破棄され、最新の結果で上書きされないこと"""
        window = self._create_isolated_window()
        qtbot.addWidget(window)

        window._load_generation = 5

        # 世代4の古いデータを作成
        stale_data = ComparisonData(
            folder_a="stale_a",
            folder_b="stale_b",
            info_a="stale_info_a",
            info_b="stale_info_b",
            yaml_a={},
            yaml_failed_a=None,
            yaml_b={},
            yaml_failed_b=None,
            image_pairs=[],
            folder_images_a=[],
            folder_images_b=[],
            df_a=None,
            df_failed_a=None,
            df_b=None,
            df_failed_b=None,
            task_options_a=[],
            task_options_b=[],
        )

        with patch.object(window, "_apply_comparison_data") as mock_apply:
            # 古い世代 (gen=4) のコールバックを呼ぶ
            window._on_load_comparison_finished(4, stale_data)
            mock_apply.assert_not_called()

            # 現在の世代 (gen=5) のコールバックを呼ぶ
            window._on_load_comparison_finished(5, stale_data)
            mock_apply.assert_called_once_with(5, stale_data)


class TestExplorerAsyncAndPreview:
    """Explorer走査の中止、プレビュー画像の縮小デコード・LRUキャッシュのテスト"""

    def test_scaled_image_decoding_and_lru_cache(self, tmp_path):
        """画像が1600px上限に縮小デコードされ、LRUキャッシュが正しくヒットすること"""
        # 2000 x 1000 の大きなテスト画像を生成
        large_img_path = str(tmp_path / "large_test.png")
        img = QImage(2000, 1000, QImage.Format.Format_RGB32)
        img.fill(QColor(255, 0, 0))
        img.save(large_img_path)

        mtime = os.path.getmtime(large_img_path)

        _load_and_scale_image.cache_clear()
        initial_info = _load_and_scale_image.cache_info()

        # 1回目の読み込み (表示先 400x300)
        decoded = _load_and_scale_image(large_img_path, mtime, 400, 300)
        assert decoded is not None
        assert not decoded.isNull()
        # アスペクト比2:1、400x300に収まるよう 400x200 にスケール
        assert decoded.width() <= 400
        assert decoded.height() <= 300
        assert max(decoded.width(), decoded.height()) <= MAX_PREVIEW_EDGE

        # 2回目の同一呼び出しでキャッシュヒットを確認
        decoded2 = _load_and_scale_image(large_img_path, mtime, 400, 300)
        assert decoded2 is decoded
        current_info = _load_and_scale_image.cache_info()
        assert current_info.hits == initial_info.hits + 1

    def test_explorer_scan_cancellation(self, qtbot, tmp_path):
        """走査中に中止した場合、キャンセルフラグが立ち結果が部分反映されること"""
        widget = ExperimentExplorerWidget()
        qtbot.addWidget(widget)

        # 3つのダミー実験ログフォルダを作成
        for i in range(3):
            sub = tmp_path / f"output_2026080{i+1}_100000"
            sub.mkdir()
            create_dummy_experiment_folder(str(tmp_path), sub.name, mode="S-SAP")

        widget.combo_root_dir.setEditText(str(tmp_path))

        # 非同期走査を開始
        widget.scan_directory(blocking=False)
        assert widget._is_scanning is True
        assert widget.btn_reload.text() == "中止"

        # 中止をクリック
        widget._on_reload_clicked()
        assert widget.lbl_table_status.text() == "探索を中止中…"

        # 走査完了ハンドラまで待機
        qtbot.waitUntil(lambda: widget._is_scanning is False, timeout=2000)
        assert widget.btn_reload.text() == "再読込"
        assert "探索を中止しました" in widget.lbl_table_status.text() or "探索完了" in widget.lbl_table_status.text()

    def test_explorer_lazy_loading_on_tab_change(self, qtbot, tmp_path):
        """行選択時にアクティブタブのみデコードされ、タブ切り替え時に遅延読み込みされること"""
        widget = ExperimentExplorerWidget()
        qtbot.addWidget(widget)

        # 2種類の画像を持つログを作成
        folder = tmp_path / "output_20260801_100000"
        folder.mkdir()
        img1_path = str(folder / "learning_rewards_001.png")
        img2_path = str(folder / "trajectory_001.png")

        im1 = QImage(100, 100, QImage.Format.Format_RGB32)
        im1.fill(QColor(0, 255, 0))
        im1.save(img1_path)

        im2 = QImage(100, 100, QImage.Format.Format_RGB32)
        im2.fill(QColor(0, 0, 255))
        im2.save(img2_path)

        create_dummy_experiment_folder(
            str(tmp_path),
            folder.name,
            mode="S-SAP",
            images=["learning_rewards_001.png", "trajectory_001.png"]
        )

        widget.set_root_directory(str(tmp_path), blocking=True)
        assert widget.table.rowCount() == 1

        # 行を選択
        widget.table.selectRow(0)

        # 2つのタブが生成されていること
        assert widget.preview_tabs.count() == 2
        active_idx = widget.preview_tabs.currentIndex()
        other_idx = 1 if active_idx == 0 else 0

        active_lbl = widget.preview_tabs.widget(active_idx)
        other_lbl = widget.preview_tabs.widget(other_idx)

        assert active_lbl.text() != "タブを開くと読み込みます"
        # 非アクティブなタブは「タブを開くと読み込みます」プレースホルダー
        assert other_lbl.text() == "タブを開くと読み込みます"

        # タブを切り替え
        widget.preview_tabs.setCurrentIndex(other_idx)

        # 切り替え先のタブの読み込みが開始されること（読み込み中… または デコード完了）
        assert other_lbl.text() in ("読み込み中…", "") or other_lbl._pixmap is not None
