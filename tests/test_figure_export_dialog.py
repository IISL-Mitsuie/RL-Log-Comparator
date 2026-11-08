"""
論文用図表書き出しダイアログ (FigureExportDialog) および export_figure 関数の単体テスト
"""

import os
import tempfile
import shutil
import unittest
import numpy as np
from PIL import Image
import matplotlib as mpl

from src.core.parsers.csv_metric import MetricSeriesData
from src.ui.dialogs.figure_export_dialog import FigureExportDialog, export_figure, PRESETS
from src.ui.widgets.csv_compare_widget import ChartSpec, _render_chart
from src.ui.theme import DARK, LIGHT
from tests.helpers import get_qapp


class TestFigureExportDialog(unittest.TestCase):
    """論文用図表書き出しの寸法・DPI・フォントタイプ・テーマ固定テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        x = np.array([1, 2, 3, 4, 5])
        y = np.array([10.0, 20.0, 15.0, 25.0, 30.0])
        self.sample_spec = ChartSpec(
            data_a=MetricSeriesData(has_data=True, x=x, y_raw=y, y_ma=y, legend_label_ma="Series A"),
            data_b=MetricSeriesData(has_data=False),
            chart_title="Export Test Title",
            x_label="Total Episode",
            y_label="Total Reward",
            legend_label_a="Series A",
            legend_label_b="",
            show_raw=True,
            show_boundaries=False,
            show_convergence=False,
            is_log_scale=False,
            font_label=11,
            font_ticks=10,
            font_title=12,
            font_legend=10,
            theme=DARK,  # 画面側が DARK テーマであってもエクスポートは LIGHT になること
            show_legend=True,
            show_grid=True,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_presets_and_dimension_switching(self):
        """プリセット選択による寸法更新および cm/inch 単位切り替えの検証"""
        dialog = FigureExportDialog(chart_spec=self.sample_spec, render_func=_render_chart)

        # 初期プリセットは 1 段組 (8.5 × 6 cm)
        self.assertEqual(len(PRESETS), 4)
        self.assertEqual(dialog.combo_preset.currentIndex(), 0)
        self.assertAlmostEqual(dialog.spin_width.value(), 8.5)
        self.assertAlmostEqual(dialog.spin_height.value(), 6.0)

        # 2 段組 (17 × 8 cm)
        dialog.combo_preset.setCurrentIndex(1)
        self.assertAlmostEqual(dialog.spin_width.value(), 17.0)
        self.assertAlmostEqual(dialog.spin_height.value(), 8.0)

        # inch 切り替え
        dialog.btn_unit_inch.setChecked(True)
        self.assertAlmostEqual(dialog.spin_width.value(), 17.0 / 2.54, places=2)
        self.assertAlmostEqual(dialog.spin_height.value(), 8.0 / 2.54, places=2)

        # 手動変更で「カスタム」になること
        dialog.spin_width.setValue(10.0)
        self.assertEqual(dialog.combo_preset.currentText(), "カスタム")

    def test_export_png_dimension_and_dpi(self):
        """1段組 (8.5 × 6 cm), 300 DPI での PNG 出力画像サイズ検証 (約 1004 × 709 ピクセル)"""
        out_png = os.path.join(self.test_dir, "test_paper_1col.png")
        w_inch = 8.5 / 2.54
        h_inch = 6.0 / 2.54
        dpi = 300

        success = export_figure(
            filepath=out_png,
            render_func=_render_chart,
            chart_spec=self.sample_spec,
            width_inch=w_inch,
            height_inch=h_inch,
            dpi=dpi,
            base_font_size=9,
            show_legend=True,
            show_grid=True,
        )
        self.assertTrue(success)
        self.assertTrue(os.path.exists(out_png))

        # 画像を開いてピクセルサイズを検証
        with Image.open(out_png) as img:
            width_px, height_px = img.size
            # 8.5 / 2.54 * 300 = 1003.937 -> 1004
            # 6.0 / 2.54 * 300 = 708.661 -> 709
            self.assertIn(width_px, (1003, 1004, 1005))
            self.assertIn(height_px, (708, 709, 710))

    def test_export_figure_uses_light_theme_and_fonttype_42(self):
        """エクスポート実行時に LIGHT テーマが渡され、pdf.fonttype=42 が有効であること"""
        passed_specs = []

        def mock_render(ax, spec):
            passed_specs.append(spec)
            self.assertEqual(mpl.rcParams["pdf.fonttype"], 42)
            self.assertEqual(mpl.rcParams["ps.fonttype"], 42)
            self.assertEqual(mpl.rcParams["svg.fonttype"], "path")
            return True

        out_pdf = os.path.join(self.test_dir, "test_paper.pdf")
        export_figure(
            filepath=out_pdf,
            render_func=mock_render,
            chart_spec=self.sample_spec,
            width_inch=3.0,
            height_inch=2.0,
            dpi=150,
            base_font_size=8,
        )

        self.assertEqual(len(passed_specs), 1)
        # 元の spec は DARK だったが、export では LIGHT に強制されること
        self.assertEqual(passed_specs[0].theme, LIGHT)


if __name__ == "__main__":
    unittest.main()
