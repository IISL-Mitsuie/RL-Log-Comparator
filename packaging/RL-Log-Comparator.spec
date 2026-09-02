# -*- mode: python ; coding: utf-8 -*-
import os

# パス設定（本specファイルのあるディレクトリを基準にルートを特定）
spec_dir = os.path.abspath(SPECPATH)
project_root = os.path.abspath(os.path.join(spec_dir, '..')) if os.path.basename(spec_dir) == 'packaging' else spec_dir
main_script = os.path.join(project_root, 'main.py')
icon_path = os.path.join(project_root, 'packaging', 'app_icon.ico')
version_file = os.path.join(project_root, 'packaging', 'version_info.txt')
data_format_path = os.path.join(project_root, 'DATA_FORMAT.md')

fonts_dir = os.path.join(project_root, 'packaging', 'fonts')

from PyInstaller.utils.hooks import collect_data_files

datas = []
if os.path.exists(data_format_path):
    datas.append((data_format_path, '.'))

# 同梱日本語フォント（IPAexゴシック）を同梱
if os.path.exists(fonts_dir):
    datas.append((fonts_dir, 'fonts'))

# Matplotlib の全データファイル（フォント, mpl-data, 設定ファイル等）を確実に同梱
datas += collect_data_files('matplotlib')

binaries = []
hiddenimports = [
    'yaml',
    'pandas',
    'numpy',
    'matplotlib',
    'matplotlib.font_manager',
    'matplotlib.backends.backend_qtagg',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'src',
    'src.config',
    'src.core',
    'src.core.env',
    'src.core.paths',
    'src.core.history',
    'src.core.parsers',
    'src.core.parsers.experiment',
    'src.core.parsers.yaml_diff',
    'src.core.parsers.image_pair',
    'src.core.parsers.csv_metric',
    'src.core.updater',
    'src.ui',
    'src.ui.main_window',
    'src.ui.dialogs',
    'src.ui.dialogs.update_dialog',
    'src.ui.widgets',
    'src.ui.widgets.sync_graphics_view',
    'src.ui.widgets.yaml_diff_widget',
    'src.ui.widgets.image_compare_widget',
    'src.ui.widgets.csv_compare_widget',
    'src.ui.widgets.log_spec_widget',
]


a = Analysis(
    [main_script],
    pathex=[project_root, os.path.join(project_root, 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchvision',
        'torchaudio',
        'scipy',
        'gymnasium',
        'gym',
        'tensorboard',
        'pygame',
        'pytest',
        # 不要な Qt モジュールを除外してフットプリントを最小化
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQml',
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtPositioning',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtSpatialAudio',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtTest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RL-Log-Comparator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.exists(icon_path) else None,
    version=version_file if os.path.exists(version_file) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RL-Log-Comparator',
)

