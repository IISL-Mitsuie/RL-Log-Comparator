"""
ImageOverlayView の単体テスト
"""

import unittest
from PySide6.QtGui import QPixmap, QColor, QPainter, QImage
from PySide6.QtCore import Qt, QPoint

from src.ui.widgets.image_overlay_view import ImageOverlayView
from tests.helpers import get_qapp


def create_solid_pixmap(w: int, h: int, color: QColor) -> QPixmap:
    pix = QPixmap(w, h)
    pix.fill(color)
    return pix


def render_view_to_image(view: ImageOverlayView, w: int, h: int) -> QImage:
    """ビューのシーン全体を画像にレンダリングして取得"""
    pix = QPixmap(w, h)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    view.scene().render(painter)
    painter.end()
    return pix.toImage().convertToFormat(QImage.Format.Format_RGBA8888)


class TestImageOverlayView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def test_identical_images_diff_mode(self):
        view = ImageOverlayView()
        pix_a = create_solid_pixmap(100, 100, QColor(120, 150, 200))
        pix_b = create_solid_pixmap(100, 100, QColor(120, 150, 200))

        view.set_images(pix_a, pix_b)
        view.set_mode("diff")

        self.assertEqual(view.get_diff_ratio(), 0.0)
        self.assertEqual(view.get_resize_notice(), "")

        # 差分表示 pixmap は黒
        diff_pix = view.item_diff.pixmap()
        self.assertFalse(diff_pix.isNull())
        img = diff_pix.toImage()
        pixel = img.pixelColor(50, 50)
        self.assertEqual(pixel.red(), 0)
        self.assertEqual(pixel.green(), 0)
        self.assertEqual(pixel.blue(), 0)

    def test_partially_different_images_diff_mode(self):
        view = ImageOverlayView()
        pix_a = create_solid_pixmap(100, 100, QColor(0, 0, 0))
        pix_b = create_solid_pixmap(100, 100, QColor(0, 0, 0))

        # pix_b の右半分 (50-99) を白にする
        painter = QPainter(pix_b)
        painter.fillRect(50, 0, 50, 100, QColor(255, 255, 255))
        painter.end()

        view.set_images(pix_a, pix_b)
        view.set_mode("diff")

        # 差分割合はおよそ 50% (0.5)
        self.assertAlmostEqual(view.get_diff_ratio(), 0.5, places=2)

        # 左半分は黒、右半分は白（明るい）
        diff_pix = view.item_diff.pixmap()
        img = diff_pix.toImage()
        self.assertEqual(img.pixelColor(25, 50).red(), 0)
        self.assertEqual(img.pixelColor(75, 50).red(), 255)

    def test_diff_mode_with_pillow_generated_images(self):
        """Pillow で生成した一部だけ異なる画像で差分モードをテスト"""
        from PIL import Image
        import io

        # 100x100 の黒画像
        im_a = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
        im_b = Image.new("RGBA", (100, 100), (0, 0, 0, 255))

        # im_b の中央 (25..75, 25..75) の 2500 画素 (25%) を白にする
        for y in range(25, 75):
            for x in range(25, 75):
                im_b.putpixel((x, y), (255, 255, 255, 255))

        buf_a = io.BytesIO()
        im_a.save(buf_a, format="PNG")
        pix_a = QPixmap()
        pix_a.loadFromData(buf_a.getvalue())

        buf_b = io.BytesIO()
        im_b.save(buf_b, format="PNG")
        pix_b = QPixmap()
        pix_b.loadFromData(buf_b.getvalue())

        view = ImageOverlayView()
        view.set_images(pix_a, pix_b)
        view.set_mode("diff")

        # 差分割合は 25% (0.25)
        self.assertAlmostEqual(view.get_diff_ratio(), 0.25, places=2)

        # 中央部は明るく (255, 255, 255)、周辺部は黒 (0, 0, 0)
        diff_pix = view.item_diff.pixmap()
        diff_img = diff_pix.toImage()
        self.assertEqual(diff_img.pixelColor(50, 50).red(), 255)
        self.assertEqual(diff_img.pixelColor(10, 10).red(), 0)

    def test_overlay_opacity(self):
        view = ImageOverlayView()
        pix_a = create_solid_pixmap(50, 50, QColor(255, 0, 0))  # 赤
        pix_b = create_solid_pixmap(50, 50, QColor(0, 0, 255))  # 青

        view.set_images(pix_a, pix_b)
        view.set_mode("overlay")

        # 不透明度 0% (A だけ)
        view.set_opacity(0.0)
        self.assertEqual(view.item_b.opacity(), 0.0)
        img_0 = render_view_to_image(view, 50, 50)
        col_0 = img_0.pixelColor(25, 25)
        self.assertEqual(col_0.red(), 255)
        self.assertEqual(col_0.blue(), 0)

        # 不透明度 100% (B だけ)
        view.set_opacity(1.0)
        self.assertEqual(view.item_b.opacity(), 1.0)
        img_1 = render_view_to_image(view, 50, 50)
        col_1 = img_1.pixelColor(25, 25)
        self.assertEqual(col_1.red(), 0)
        self.assertEqual(col_1.blue(), 255)

    def test_swipe_mode_rendering(self):
        view = ImageOverlayView()
        pix_a = create_solid_pixmap(100, 50, QColor(255, 0, 0))  # 赤
        pix_b = create_solid_pixmap(100, 50, QColor(0, 0, 255))  # 青

        view.set_images(pix_a, pix_b)
        view.set_mode("swipe")
        view.set_swipe_position(0.5)

        self.assertTrue(view.swipe_line.isVisible())
        self.assertEqual(view.swipe_line.line().x1(), 50.0)

        img = render_view_to_image(view, 100, 50)
        # 左側 (x=20) は A (赤)
        self.assertEqual(img.pixelColor(20, 25).red(), 255)
        self.assertEqual(img.pixelColor(20, 25).blue(), 0)

        # 右側 (x=80) は B (青)
        self.assertEqual(img.pixelColor(80, 25).red(), 0)
        self.assertEqual(img.pixelColor(80, 25).blue(), 255)

    def test_different_sizes_notice(self):
        view = ImageOverlayView()
        pix_a = create_solid_pixmap(800, 600, QColor(255, 255, 255))
        pix_b = create_solid_pixmap(1600, 1200, QColor(100, 100, 100))

        view.set_images(pix_a, pix_b)
        notice = view.get_resize_notice()
        self.assertIn("1600×1200", notice)
        self.assertIn("800×600", notice)
        self.assertIn("縮小", notice)

    def test_swipe_drag_interaction(self):
        view = ImageOverlayView()
        view.resize(200, 200)
        pix_a = create_solid_pixmap(100, 100, QColor(255, 0, 0))
        pix_b = create_solid_pixmap(100, 100, QColor(0, 0, 255))
        view.set_images(pix_a, pix_b)
        view.set_mode("swipe")
        view.set_swipe_position(0.5)

        # マウス近傍判定
        self.assertFalse(view._is_near_swipe_line(QPoint(0, 0)))


if __name__ == "__main__":
    unittest.main()
