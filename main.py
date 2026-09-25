"""
RL-Log-Comparator (PySide6 GUI)
強化学習実験ログ対比・比較分析ツール

2つの実験出力フォルダ（任意の強化学習環境 / 継続学習 / SAP-net 等）を選択し、
1. 設定ファイル (YAML / JSON) の階層差分比較（初期状態は差分項目のみ表示）
2. 多形式画像 (PNG / JPG / WebP 等) の同期パン＆ズーム対応並列目視比較（左右自由選択モード搭載）
3. 数値ログ (CSV) の移動平均付き重ね合わせ比較グラフ描画（任意数値列・片側欠損安全プロット対応）
4. 実験ログエクスプローラーによる一括走査・検索・フィルタリング・ピン留め・左右割当
5. ログデータ仕様ガイド表示および仕様書 Markdown エクスポート
を行うスタンドアロン GUI ツールです。

Usage:
    python main.py [folder_A] [folder_B]
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from src.core.env import initialize_environment
from src.core.paths import get_app_icon_path
from src.ui.main_window import ExperimentCompareApp


def main():
    # 1. 実行環境・Matplotlib・フォントの初期設定
    initialize_environment()

    # 2. Qt アプリケーションの初期化
    app = QApplication(sys.argv)

    # アプリアイコンの設定
    icon_path = get_app_icon_path()
    if icon_path and os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # 3. メインウィンドウの起動
    window = ExperimentCompareApp()

    # 4. コマンドライン引数の処理
    if len(sys.argv) >= 3:
        path_a = sys.argv[1]
        path_b = sys.argv[2]
        window.load_folders(path_a, path_b)
    elif len(sys.argv) == 2:
        path_a = sys.argv[1]
        window.combo_folder_a.setEditText(path_a)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
