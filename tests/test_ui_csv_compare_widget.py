"""
CSV 重ね合わせ比較グラフビューウィジェット (CsvCompareWidget) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
from src.ui.widgets.csv_compare_widget import CsvCompareWidget
from tests.helpers import get_qapp, create_dummy_experiment_folder


class TestUiCsvCompareWidget(unittest.TestCase):
    """CsvCompareWidget の UI 操作・チャート描画テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_a = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_a", episodes=20
        )
        self.folder_b = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_b", episodes=20
        )
        self._clean_font_settings()

    def tearDown(self):
        self._clean_font_settings()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _clean_font_settings(self):
        from src.core.settings import create_settings
        from src.config import (
            SETTINGS_KEY_CHART_FONT_LABEL, SETTINGS_KEY_CHART_FONT_TICKS,
            SETTINGS_KEY_CHART_FONT_TITLE, SETTINGS_KEY_CHART_FONT_LEGEND
        )
        s = create_settings()
        s.remove(SETTINGS_KEY_CHART_FONT_LABEL)
        s.remove(SETTINGS_KEY_CHART_FONT_TICKS)
        s.remove(SETTINGS_KEY_CHART_FONT_TITLE)
        s.remove(SETTINGS_KEY_CHART_FONT_LEGEND)


    def _make_csv_folder(self, name: str, data: dict) -> str:
        import pandas as pd
        folder = os.path.join(self.test_dir, name)
        os.makedirs(folder, exist_ok=True)
        pd.DataFrame(data).to_csv(os.path.join(folder, "progress.csv"), index=False)
        return folder

    def test_generic_step_csv_x_label_and_metrics(self):
        """step 列を X 軸とする汎用 CSV で、ステップ数指標が出ず、X 軸ラベルが step を示す (ISSUE-04)"""
        folder = self._make_csv_folder("gen_step", {"step": [10, 20, 30], "reward": [1.0, 2.0, 3.0]})
        widget = CsvCompareWidget()
        widget.load_csvs(folder, folder)

        texts = [widget.list_metrics.item(i).text() for i in range(widget.list_metrics.count())]
        self.assertFalse(any(t.startswith("ステップ数") for t in texts), texts)
        self.assertIn("step", widget.txt_xlabel.text())
        self.assertNotIn("Total Episode", widget.txt_xlabel.text())

    def test_x_axis_kind_mismatch_label(self):
        """A と B で X 軸の種類が違う場合、ラベルに両方を示し注記を出す (ISSUE-04)"""
        folder_a = self._make_csv_folder("ep_axis", {"Episode": [1, 2, 3], "reward": [1.0, 2.0, 3.0]})
        folder_b = self._make_csv_folder("step_axis", {"step": [10, 20, 30], "reward": [1.0, 2.0, 3.0]})
        widget = CsvCompareWidget()
        widget.load_csvs(folder_a, folder_b)

        self.assertTrue(widget.txt_xlabel.text().startswith("A: "))
        self.assertIn(" / B: ", widget.txt_xlabel.text())
        ax = widget.figure.axes[0]
        self.assertTrue(any("X 軸の単位が A/B で異なります" in t.get_text() for t in ax.texts))

    def test_x_label_from_side_with_data(self):
        """指標が片側にしかない場合、データがある側の X 軸ラベルを使う (ISSUE-04)"""
        folder_a = self._make_csv_folder("ep_only", {"Episode": [1, 2], "reward": [1.0, 2.0]})
        folder_b = self._make_csv_folder("step_loss", {"step": [10, 20], "reward": [1.0, 2.0], "loss": [0.5, 0.4]})
        widget = CsvCompareWidget()
        widget.load_csvs(folder_a, folder_b)
        for row in range(widget.list_metrics.count()):
            if widget.list_metrics.item(row).text().startswith("loss"):
                widget.list_metrics.setCurrentRow(row)
                break
        self.assertEqual(widget.txt_xlabel.text(), "Step (step)")

    def _make_broken_csv_folder(self, name: str) -> str:
        folder = os.path.join(self.test_dir, name)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "progress.csv"), "w", encoding="utf-8") as f:
            f.write("step,reward\n1,1.0\n2,2.0,3.0\n")
        return folder

    def test_broken_csv_shows_load_error(self):
        """CSV の読み込みに失敗した場合、「データなし」と区別して表示する (ISSUE-07)"""
        broken = self._make_broken_csv_folder("broken_a")
        widget = CsvCompareWidget()
        widget.load_csvs(broken, broken)
        texts = [t.get_text() for t in widget.figure.axes[0].texts]
        self.assertTrue(any("フォルダ A の CSV の読み込みに失敗しました: progress.csv" in t for t in texts), texts)
        self.assertTrue(any("フォルダ B の CSV の読み込みに失敗しました: progress.csv" in t for t in texts), texts)
        self.assertFalse(any("CSV データが存在しません" in t for t in texts), texts)

        # 片側だけ失敗した場合は、もう片側を描画したうえで、失敗を凡例に表示する
        widget.load_csvs(broken, self.folder_b)
        ax = widget.figure.axes[0]
        self.assertTrue(ax.lines)
        legend_texts = [t.get_text() for t in ax.get_legend().get_texts()]
        self.assertTrue(any("フォルダ A の CSV の読み込みに失敗しました" in t for t in legend_texts), legend_texts)
        self.assertFalse(any("該当列なし" in t for t in legend_texts), legend_texts)
        self.assertFalse(any("フォルダ B" in t for t in legend_texts), legend_texts)

        # 正常なフォルダを読み直すと消える
        widget.load_csvs(self.folder_a, self.folder_b)
        texts = [t.get_text() for t in widget.figure.axes[0].texts]
        self.assertFalse(any("読み込みに失敗しました" in t for t in texts), texts)

    def test_nan_points_are_not_plotted(self):
        """欠損値 (NaN) の点を描画データから除外する (ISSUE-04)"""
        import math
        folder = self._make_csv_folder("nan", {"step": [1, 2, 3, 4], "loss": [None, 0.5, None, 0.3]})
        widget = CsvCompareWidget()
        widget.load_csvs(folder, folder)
        for row in range(widget.list_metrics.count()):
            if widget.list_metrics.item(row).text().startswith("loss"):
                widget.list_metrics.setCurrentRow(row)
                break
        ax = widget.figure.axes[0]
        self.assertTrue(ax.lines)
        for line in ax.lines:
            ys = list(line.get_ydata())
            self.assertFalse(any(math.isnan(v) for v in ys))
            self.assertNotIn(0.0, ys)

    def test_load_csvs_and_change_metrics(self):
        widget = CsvCompareWidget()
        widget.load_csvs(self.folder_a, self.folder_b)

        # 動的に抽出された指標が存在することを確認
        self.assertGreaterEqual(widget.list_metrics.count(), 1)

        # タスクコンボボックスの確認
        self.assertGreaterEqual(widget.combo_task.count(), 1)

        # 各指標を切り替えて例外なく再描画されることを確認
        for i in range(widget.list_metrics.count()):
            widget.list_metrics.setCurrentRow(i)

        # スライダー変更時の更新
        widget.slider_ma.setValue(5)
        self.assertEqual(widget.lbl_ma_val.text(), "5 ep")

        # 生データチェックボックスの切替
        widget.cb_raw_data.setChecked(False)
        widget.cb_raw_data.setChecked(True)

    def test_asymmetric_csv_columns_rendering(self):
        """片方のCSVにしか存在しない指標列（例: Aのみlossあり）の安全な描画テスト"""
        import pandas as pd
        folder_asym_a = os.path.join(self.test_dir, "asym_a")
        folder_asym_b = os.path.join(self.test_dir, "asym_b")
        os.makedirs(folder_asym_a, exist_ok=True)
        os.makedirs(folder_asym_b, exist_ok=True)

        # Aには reward と custom_loss が存在
        pd.DataFrame({
            "step": [1, 2, 3],
            "reward": [10.0, 20.0, 30.0],
            "custom_loss": [0.5, 0.3, 0.1]
        }).to_csv(os.path.join(folder_asym_a, "learning_log_test.csv"), index=False)

        # Bには reward のみ存在 (custom_loss は無し)
        pd.DataFrame({
            "step": [1, 2, 3],
            "reward": [5.0, 15.0, 25.0]
        }).to_csv(os.path.join(folder_asym_b, "learning_log_test.csv"), index=False)

        widget = CsvCompareWidget()
        widget.load_csvs(folder_asym_a, folder_asym_b)

        # custom_loss が指標一覧に含まれていることを確認
        found_loss_row = -1
        for row in range(widget.list_metrics.count()):
            item = widget.list_metrics.item(row)
            if item and item.text().startswith("custom_loss"):
                found_loss_row = row
                break

        self.assertNotEqual(found_loss_row, -1, "custom_loss should be listed in metrics")

        # custom_loss を選択して描画しても例外が発生しないことを確認
        widget.list_metrics.setCurrentRow(found_loss_row)
        widget.update_chart()

    def test_independent_task_mode_same_folder_different_tasks(self):
        """同一実験ログフォルダで異なるタスク（Task 1 vs Task 2）を選択・比較描画するテスト"""
        import pandas as pd
        folder_cl = os.path.join(self.test_dir, "continual_exp")
        os.makedirs(folder_cl, exist_ok=True)

        # 2つのタスクを含む統合CSVを作成
        df_cl = pd.DataFrame({
            "Task_ID": [1, 1, 1, 2, 2, 2],
            "Task_Episode": [1, 2, 3, 1, 2, 3],
            "Total_Episode": [1, 2, 3, 4, 5, 6],
            "Goal_X": [11.0, 11.0, 11.0, 15.0, 15.0, 15.0],
            "Goal_Y": [3.0, 3.0, 3.0, 5.0, 5.0, 5.0],
            "Steps": [100, 80, 60, 120, 90, 70],
            "TotalReward": [50.0, 70.0, 90.0, 20.0, 40.0, 60.0],
            "Is_Converged": [False, False, True, False, False, True]
        })
        df_cl.to_csv(os.path.join(folder_cl, "learning_log_20261011_120000.csv"), index=False)

        widget = CsvCompareWidget()
        # フォルダAとフォルダBに同一の実験ログフォルダを設定
        widget.load_csvs(folder_cl, folder_cl)

        # 個別タスク選択モードを有効化
        self.assertTrue(widget.cb_independent_tasks.isEnabled())
        widget.cb_independent_tasks.setChecked(True)

        # A側・B側のコンボボックスが表示・設定されていることを確認
        self.assertFalse(widget.combo_task_a.isHidden())
        self.assertFalse(widget.combo_task_b.isHidden())
        self.assertTrue(widget.combo_task.isHidden())

        # タスク候補数が 2 (Task 1, Task 2) であることを確認
        self.assertEqual(widget.combo_task_a.count(), 2)
        self.assertEqual(widget.combo_task_b.count(), 2)

        # A側に Task 1 (index 0), B側に Task 2 (index 1) を設定
        widget.combo_task_a.setCurrentIndex(0)
        widget.combo_task_b.setCurrentIndex(1)

        # 再描画
        widget.update_chart()

        # グラフのタイトルに対比タスク名が含まれていることを確認
        ax = widget.figure.axes[0]
        title = ax.get_title()
        self.assertIn("A: Task 1", title)
        self.assertIn("B: Task 2", title)

        # X軸ラベルが Task Episode となっていることを確認
        self.assertEqual(ax.get_xlabel(), "Task Episode (エピソード [1..N])")

        # 境界線オプションが無効化されていることを確認
        self.assertFalse(widget.cb_task_boundaries.isEnabled())

        # モードをOFFに戻した時の連動動作を確認
        widget.cb_independent_tasks.setChecked(False)
        self.assertFalse(widget.combo_task.isHidden())
        self.assertTrue(widget.combo_task_a.isHidden())
        self.assertTrue(widget.combo_task_b.isHidden())

    def test_custom_legend_labels_and_reset(self):
        """凡例のカスタム文字列編集・リアルタイム反映およびリセット動作のテスト"""
        widget = CsvCompareWidget()
        widget.load_csvs(self.folder_a, self.folder_b)

        # プレースホルダーが自動生成凡例で設定されていることを確認
        self.assertTrue(len(widget.txt_legend_a.placeholderText()) > 0)
        self.assertTrue(len(widget.txt_legend_b.placeholderText()) > 0)

        # 凡例A・Bを任意文字列にカスタム設定 (案A: 完全上書き)
        widget.txt_legend_a.setText("提案手法 (Proposed)")
        widget.txt_legend_b.setText("従来手法 (Baseline)")
        widget.update_chart()

        ax = widget.figure.axes[0]
        legend = ax.get_legend()
        self.assertIsNotNone(legend)
        legend_texts = [t.get_text() for t in legend.get_texts()]

        self.assertIn("提案手法 (Proposed)", legend_texts)
        self.assertIn("従来手法 (Baseline)", legend_texts)

        # リセットボタンをクリック
        widget.btn_reset_legend.click()

        # 入力欄がクリアされていることを確認
        self.assertEqual(widget.txt_legend_a.text(), "")
        self.assertEqual(widget.txt_legend_b.text(), "")

        # デフォルトの自動生成凡例に戻っていることを確認
        ax = widget.figure.axes[0]
        legend = ax.get_legend()
        self.assertIsNotNone(legend)
        reset_texts = [t.get_text() for t in legend.get_texts()]
        self.assertNotIn("提案手法 (Proposed)", reset_texts)
        self.assertTrue(any("A:" in t for t in reset_texts))

        # フォルダ再読み込み時に入力欄が自動クリアされることを確認
        widget.txt_legend_a.setText("手動入力ラベル")
        widget.load_csvs(self.folder_a, self.folder_b)
        self.assertEqual(widget.txt_legend_a.text(), "")

    def test_custom_chart_texts_and_reset(self):
        """タイトル・X軸・Y軸ラベルの任意変更（空欄化含む）、リセットおよび指標変更時の動作テスト"""
        widget = CsvCompareWidget()
        widget.load_csvs(self.folder_a, self.folder_b)

        # 1. 初期状態でデフォルト値が入力欄およびグラフに設定されていることを確認
        self.assertTrue(len(widget.txt_title.text()) > 0)
        self.assertEqual(widget.txt_xlabel.text(), "Total Episode (通算エピソード)")
        self.assertTrue(len(widget.txt_ylabel.text()) > 0)

        ax = widget.figure.axes[0]
        self.assertEqual(ax.get_title(), widget.txt_title.text())
        self.assertEqual(ax.get_xlabel(), widget.txt_xlabel.text())
        self.assertEqual(ax.get_ylabel(), widget.txt_ylabel.text())

        # 2. 任意文字列にカスタム変更（リアルタイム反映）
        widget.txt_title.setText("カスタムタイトル (My Curve)")
        widget.txt_xlabel.setText("Custom Episode")
        widget.txt_ylabel.setText("Custom Reward")
        widget.update_chart()

        ax = widget.figure.axes[0]
        self.assertEqual(ax.get_title(), "カスタムタイトル (My Curve)")
        self.assertEqual(ax.get_xlabel(), "Custom Episode")
        self.assertEqual(ax.get_ylabel(), "Custom Reward")

        # 3. 空欄（非表示）化の検証（空文字を設定した場合）
        widget.txt_title.setText("")
        widget.txt_xlabel.setText("")
        widget.txt_ylabel.setText("")
        widget.update_chart()

        ax = widget.figure.axes[0]
        self.assertEqual(ax.get_title(), "")
        self.assertEqual(ax.get_xlabel(), "")
        self.assertEqual(ax.get_ylabel(), "")

        # 4. 「すべてデフォルトに戻す」ボタンの検証
        widget.btn_reset_texts.click()

        self.assertTrue(len(widget.txt_title.text()) > 0)
        self.assertEqual(widget.txt_xlabel.text(), "Total Episode (通算エピソード)")
        self.assertTrue(len(widget.txt_ylabel.text()) > 0)

        ax = widget.figure.axes[0]
        self.assertEqual(ax.get_title(), widget.txt_title.text())
        self.assertEqual(ax.get_xlabel(), widget.txt_xlabel.text())
        self.assertEqual(ax.get_ylabel(), widget.txt_ylabel.text())

        # 5. 指標変更時にデフォルトへ自動リセットされることの検証 (質問2: 案B)
        widget.txt_title.setText("手動で変更したタイトル")
        # 指標を 2 番目の項目に変更
        if widget.list_metrics.count() > 1:
            widget.list_metrics.setCurrentRow(1)
            # 案Bにより、指標変更時に新しい指標のデフォルトにリセットされていることを確認
            self.assertNotEqual(widget.txt_title.text(), "手動で変更したタイトル")
            self.assertTrue(widget.txt_title.text().startswith("学習推移比較:"))

    def test_chart_font_size_customization_and_reset(self):
        """フォントサイズ変更（軸ラベル・軸数値・タイトル・凡例）、リセット、永続化、高DPI設定の検証"""
        import matplotlib.pyplot as plt
        from src.config import (
            DEFAULT_CHART_FONT_LABEL, DEFAULT_CHART_FONT_TICKS,
            DEFAULT_CHART_FONT_TITLE, DEFAULT_CHART_FONT_LEGEND
        )

        widget = CsvCompareWidget()
        widget.load_csvs(self.folder_a, self.folder_b)

        # 1. 初期値の確認
        self.assertEqual(widget.spin_font_label.value(), DEFAULT_CHART_FONT_LABEL)
        self.assertEqual(widget.spin_font_ticks.value(), DEFAULT_CHART_FONT_TICKS)
        self.assertEqual(widget.spin_font_title.value(), DEFAULT_CHART_FONT_TITLE)
        self.assertEqual(widget.spin_font_legend.value(), DEFAULT_CHART_FONT_LEGEND)

        # 2. フォントサイズ変更（リアルタイム反映）
        widget.spin_font_label.setValue(16)
        widget.spin_font_ticks.setValue(14)
        widget.spin_font_title.setValue(18)
        widget.spin_font_legend.setValue(13)

        ax = widget.figure.axes[0]
        self.assertEqual(ax.xaxis.label.get_fontsize(), 16)
        self.assertEqual(ax.yaxis.label.get_fontsize(), 16)
        self.assertEqual(ax.title.get_fontsize(), 18)
        if ax.get_legend():
            for text in ax.get_legend().get_texts():
                self.assertEqual(text.get_fontsize(), 13)

        # 3. 指標を変更してもフォントサイズが維持されることを確認
        if widget.list_metrics.count() > 1:
            widget.list_metrics.setCurrentRow(1)
            self.assertEqual(widget.spin_font_label.value(), 16)
            self.assertEqual(widget.spin_font_ticks.value(), 14)
            self.assertEqual(widget.spin_font_title.value(), 18)
            self.assertEqual(widget.spin_font_legend.value(), 13)

        # 4. 「すべてデフォルトに戻す」ボタンで初期値に復帰
        widget.btn_reset_texts.click()
        self.assertEqual(widget.spin_font_label.value(), DEFAULT_CHART_FONT_LABEL)
        self.assertEqual(widget.spin_font_ticks.value(), DEFAULT_CHART_FONT_TICKS)
        self.assertEqual(widget.spin_font_title.value(), DEFAULT_CHART_FONT_TITLE)
        self.assertEqual(widget.spin_font_legend.value(), DEFAULT_CHART_FONT_LEGEND)

        ax = widget.figure.axes[0]
        self.assertEqual(ax.xaxis.label.get_fontsize(), DEFAULT_CHART_FONT_LABEL)
        self.assertEqual(ax.yaxis.label.get_fontsize(), DEFAULT_CHART_FONT_LABEL)
        self.assertEqual(ax.title.get_fontsize(), DEFAULT_CHART_FONT_TITLE)

        # 5. QSettings 永続化の確認
        widget.spin_font_label.setValue(20)
        widget2 = CsvCompareWidget()
        self.assertEqual(widget2.spin_font_label.value(), 20)
        # テスト後にデフォルトへ戻す
        widget2.btn_reset_texts.click()

        # 6. 保存時解像度 (savefig.dpi) が 300 であることの確認
        self.assertEqual(plt.rcParams['savefig.dpi'], 300)



    def test_task_df_cache_prevents_reloading_on_text_changes(self):
        """個別タスク選択モードでテキスト入力しても load_task_dataframe が重複呼び出しされない (ISSUE-06)"""
        import pandas as pd
        from unittest.mock import patch

        folder_cl = os.path.join(self.test_dir, "cache_exp")
        os.makedirs(folder_cl, exist_ok=True)
        df_cl = pd.DataFrame({
            "Task_ID": [1, 1, 2, 2],
            "Task_Episode": [1, 2, 1, 2],
            "Total_Episode": [1, 2, 3, 4],
            "Steps": [10, 20, 15, 25],
            "TotalReward": [1.0, 2.0, 3.0, 4.0],
            "Is_Converged": [False, True, False, True]
        })
        df_cl.to_csv(os.path.join(folder_cl, "learning_log_test.csv"), index=False)

        widget = CsvCompareWidget()
        widget.load_csvs(folder_cl, folder_cl)
        widget.cb_independent_tasks.setChecked(True)
        widget.combo_task_a.setCurrentIndex(0)
        widget.combo_task_b.setCurrentIndex(1)
        widget.update_chart()

        self.assertGreaterEqual(len(widget._task_df_cache), 2)

        with patch("src.ui.widgets.csv_compare_widget.load_task_dataframe") as mock_load:
            for ch in "HelloWorld":
                widget.txt_title.setText(widget.txt_title.text() + ch)
            widget.update_chart()
            mock_load.assert_not_called()

    def test_task_df_cache_cleared_on_load_csvs(self):
        """フォルダ再読み込み時にタスク別 DataFrame キャッシュが破棄される (ISSUE-06)"""
        import pandas as pd

        folder_cl = os.path.join(self.test_dir, "cache_clear_exp")
        os.makedirs(folder_cl, exist_ok=True)
        df_cl = pd.DataFrame({
            "Task_ID": [1, 1, 2, 2],
            "Task_Episode": [1, 2, 1, 2],
            "Total_Episode": [1, 2, 3, 4],
            "Steps": [10, 20, 15, 25],
            "TotalReward": [1.0, 2.0, 3.0, 4.0],
            "Is_Converged": [False, True, False, True]
        })
        csv_file = os.path.join(folder_cl, "learning_log_test.csv")
        df_cl.to_csv(csv_file, index=False)

        widget = CsvCompareWidget()
        widget.load_csvs(folder_cl, folder_cl)
        widget.cb_independent_tasks.setChecked(True)
        widget.combo_task_a.setCurrentIndex(0)
        widget.combo_task_b.setCurrentIndex(1)
        widget.update_chart()
        self.assertGreaterEqual(len(widget._task_df_cache), 2)

        old_keys = set(widget._task_df_cache.keys())
        self.assertGreater(len(old_keys), 0)

        # 通常モードで再読み込みした場合、キャッシュが空になる
        widget.cb_independent_tasks.setChecked(False)
        widget.load_csvs(self.folder_a, self.folder_b)
        self.assertEqual(len(widget._task_df_cache), 0)
        self.assertFalse(any(k in widget._task_df_cache for k in old_keys))

        # 新しいデータを書き込んで再読み込みした場合、新しいデータが反映される
        df_cl2 = pd.DataFrame({
            "Task_ID": [1, 1, 2, 2],
            "Task_Episode": [1, 2, 1, 2],
            "Total_Episode": [1, 2, 3, 4],
            "Steps": [100, 200, 150, 250],
            "TotalReward": [999.0, 999.0, 888.0, 888.0],
            "Is_Converged": [False, True, False, True]
        })
        df_cl2.to_csv(csv_file, index=False)
        widget.load_csvs(folder_cl, folder_cl)
        widget.cb_independent_tasks.setChecked(True)
        widget.combo_task_a.setCurrentIndex(0)
        widget.update_chart()

        opt_a = widget.combo_task_a.currentData()
        cached_df = widget._get_task_dataframe("A", opt_a)
        self.assertIsNotNone(cached_df)
        self.assertEqual(cached_df["TotalReward"].iloc[0], 999.0)

    def test_debounce_reduces_update_chart_calls_on_slider(self):
        """スライダーを連続で動かしてもデバウンスにより update_chart の呼び出しが抑止される (ISSUE-06)"""
        from unittest.mock import patch

        widget = CsvCompareWidget()
        widget.load_csvs(self.folder_a, self.folder_b)

        with patch.object(widget, "update_chart") as mock_update:
            for val in range(1, 51):
                widget.slider_ma.setValue(val)
            mock_update.assert_not_called()
            self.assertTrue(widget._redraw_timer.isActive())
            widget._redraw_timer.timeout.emit()
            self.assertEqual(mock_update.call_count, 1)

    def test_debounce_reduces_update_chart_calls_on_text_input(self):
        """テキスト入力欄に連続入力してもデバウンスにより update_chart の呼び出しが抑止される (ISSUE-06)"""
        from unittest.mock import patch

        widget = CsvCompareWidget()
        widget.load_csvs(self.folder_a, self.folder_b)

        with patch.object(widget, "update_chart") as mock_update:
            for ch in "1234567890":
                widget.txt_title.setText(widget.txt_title.text() + ch)
            mock_update.assert_not_called()
            self.assertTrue(widget._redraw_timer.isActive())
            widget._redraw_timer.timeout.emit()
            self.assertEqual(mock_update.call_count, 1)


if __name__ == "__main__":
    unittest.main()


