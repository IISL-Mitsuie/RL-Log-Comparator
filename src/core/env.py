"""
実行環境・OS・Matplotlib 初期化モジュール
"""

import os
import ctypes
import tempfile
from src.config import APP_USER_MODEL_ID, MATPLOTLIB_CACHE_DIR_NAME
from src.core.paths import get_bundled_font_path


def setup_app_user_model_id():
    """Windows タスクバーでのグループ化およびアプリアイコン分離"""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def setup_mpl_cache_dir():
    """Matplotlib のキャッシュディレクトリ設定（import matplotlib 前に設定して他環境の破損キャッシュ競合を回避）"""
    local_appdata = os.environ.get('LOCALAPPDATA', tempfile.gettempdir())
    mpl_cache_dir = os.path.join(local_appdata, 'RL-Log-Comparator', MATPLOTLIB_CACHE_DIR_NAME)
    try:
        os.makedirs(mpl_cache_dir, exist_ok=True)
        os.environ['MPLCONFIGDIR'] = mpl_cache_dir
    except Exception:
        pass


def setup_matplotlib_japanese_font():
    """
    Matplotlib の日本語および英数字フォント設定を確実に行う
    1. 同梱されたオープンソース日本語フォント (ipaexg.ttf) を最優先で登録
    2. Windows 標準のフォント (MS Gothic, Yu Gothic, Meiryo, BIZ UDGothic) をフォールバック登録
    3. rcParams のフォントファミリー、文字色、負符号を確実に設定
    """
    import matplotlib
    matplotlib.use("QtAgg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    registered_families = []

    def register_font_file(font_path):
        if not font_path or not os.path.exists(font_path):
            return
        try:
            fm.fontManager.addfont(font_path)
            prop = fm.FontProperties(fname=font_path)
            name = prop.get_name()
            if name and name not in registered_families:
                registered_families.append(name)
        except Exception:
            pass

    # 1. 同梱フォント (IPAexゴシック) の登録（最優先）
    bundled_font = get_bundled_font_path()
    register_font_file(bundled_font)

    # 2. Windows 標準フォントの登録（フォールバック）
    windir = os.environ.get('WINDIR', r'C:\Windows')
    fonts_dir = os.path.join(windir, 'Fonts')
    win_font_files = ['msgothic.ttc', 'YuGothM.ttc', 'meiryo.ttc', 'BIZ-UDGothicR.ttc']

    for font_file in win_font_files:
        register_font_file(os.path.join(fonts_dir, font_file))

    # 3. フォールバックリストの構成（確実に存在する名前のみ + DejaVu Sans）
    final_font_list = registered_families if registered_families else ['DejaVu Sans']
    if 'DejaVu Sans' not in final_font_list:
        final_font_list.append('DejaVu Sans')

    plt.rcParams['font.family'] = final_font_list
    plt.rcParams['font.sans-serif'] = final_font_list
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['text.color'] = '#222222'
    plt.rcParams['axes.labelcolor'] = '#222222'
    plt.rcParams['xtick.color'] = '#222222'
    plt.rcParams['ytick.color'] = '#222222'
    plt.rcParams['axes.edgecolor'] = '#888888'


def initialize_environment():
    """アプリケーション起動前の環境初期化を一括実行"""
    setup_app_user_model_id()
    setup_mpl_cache_dir()
    setup_matplotlib_japanese_font()
