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
        from PySide6.QtCore import QSettings
        from src.config import (
            SETTINGS_ORG, SETTINGS_APP,
            SETTINGS_KEY_CHART_FONT_LABEL, SETTINGS_KEY_CHART_FONT_TICKS,
            SETTINGS_KEY_CHART_FONT_TITLE, SETTINGS_KEY_CHART_FONT_LEGEND
        )
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        s.remove(SETTINGS_KEY_CHART_FONT_LABEL)
        s.remove(SETTINGS_KEY_CHART_FONT_TICKS)
        s.remove(SETTINGS_KEY_CHART_FONT_TITLE)
        s.remove(SETTINGS_KEY_CHART_FONT_LEGEND)


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

        ax = widget.figure.axes[0]
        self.assertEqual(ax.get_title(), "カスタムタイトル (My Curve)")
        self.assertEqual(ax.get_xlabel(), "Custom Episode")
        self.assertEqual(ax.get_ylabel(), "Custom Reward")

        # 3. 空欄（非表示）化の検証（空文字を設定した場合）
        widget.txt_title.setText("")
        widget.txt_xlabel.setText("")
        widget.txt_ylabel.setText("")

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


if __name__ == "__main__":
    unittest.main()


