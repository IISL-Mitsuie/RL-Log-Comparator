"""
テスト用ヘルパー関数およびフィクスチャ生成ユーティリティ
"""

import os
import sys
from typing import Optional
import yaml
import pandas as pd
from PySide6.QtWidgets import QApplication
from PIL import Image


def get_qapp() -> QApplication:
    """テスト用の QApplication シングルトンインスタンスを取得（未生成時は生成）"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def create_dummy_experiment_folder(
    base_dir: str,
    folder_name: str = "output_20260801_120000",
    mode: str = "S-SAP",
    learning_rate: float = 0.001,
    batch_size: int = 64,
    episodes: int = 10,
    has_yaml: bool = True,
    has_csv: bool = True,
    images: Optional[list[str]] = None
) -> str:
    """
    一時ディレクトリ内に完全なダミー実験出力フォルダを作成する。
    """
    folder_path = os.path.join(base_dir, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # 1. YAML ファイル
    if has_yaml:
        yaml_data = {
            "mode": mode,
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "network": {
                "hidden_dim": 128,
                "activation": "relu"
            }
        }
        yaml_path = os.path.join(folder_path, "config_used_123.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f)

    # 2. CSV ファイル
    if has_csv:
        ep_list = list(range(1, episodes + 1))
        df = pd.DataFrame({
            "Episode": ep_list,
            "TotalReward": [10.0 + i * 2.5 for i in range(episodes)],
            "Steps": [100 - i * 3 for i in range(episodes)],
            "UnsafeActions": [max(0, 5 - i) for i in range(episodes)],
            "Result": ["Goal" if i >= 3 else "Failed" for i in range(episodes)]
        })
        csv_path = os.path.join(folder_path, "learning_log_001.csv")
        df.to_csv(csv_path, index=False)

    # 3. 画像ファイル群
    if images is None:
        images = [
            "learning_rewards_00010_00100.png",
            "learning_steps_00010_00100.png",
            "trajectory_00010.png"
        ]

    for img_name in images:
        img_path = os.path.join(folder_path, img_name)
        img = Image.new("RGB", (100, 100), color=(73, 109, 137))
        img.save(img_path, format="PNG")

    return os.path.abspath(folder_path)
