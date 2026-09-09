"""
experiment_scanner モジュールの単体テスト
"""

import os
import pytest
from src.core.parsers.experiment_scanner import (
    flatten_dict, format_timestamp, parse_single_experiment,
    scan_experiments_directory, ExperimentLogRecord
)
from tests.helpers import create_dummy_experiment_folder


def test_flatten_dict():
    nested = {
        "learning_rate": 0.001,
        "reward_settings": {
            "goal": 100.0,
            "penalty": {
                "step": -0.1,
                "collision": -50.0
            }
        },
        "tags": ["rl", "robotino"]
    }
    flat = flatten_dict(nested)
    assert flat["learning_rate"] == 0.001
    assert flat["reward_settings.goal"] == 100.0
    assert flat["reward_settings.penalty.step"] == -0.1
    assert flat["reward_settings.penalty.collision"] == -50.0
    assert flat["tags"] == ["rl", "robotino"]


def test_format_timestamp():
    assert format_timestamp("20260902_113727") == "2026/09/02 11:37:27"
    assert format_timestamp("invalid_format") == "invalid_format"


def test_parse_single_experiment(tmp_path):
    folder = create_dummy_experiment_folder(
        str(tmp_path),
        folder_name="output_20260902_113727",
        mode="S-SAP",
        learning_rate=0.005,
        batch_size=128
    )
    record = parse_single_experiment(folder)
    assert record is not None
    assert record.timestamp_key == "20260902_113727"
    assert record.display_timestamp == "2026/09/02 11:37:27"
    assert record.mode == "S-SAP"
    assert record.config_flat["learning_rate"] == 0.005
    assert record.config_flat["batch_size"] == 128
    assert record.config_flat["network.hidden_dim"] == 128
    assert "learning_rewards" in record.images
    assert "learning_steps" in record.images
    assert "trajectory" in record.images
    assert record.csv_path is not None
    assert os.path.exists(record.csv_path)


def test_parse_single_experiment_multiple_images_latest(tmp_path):
    """同一プレフィックスで複数画像が存在する場合、最新の1枚が選定されること（方針A）の検証"""
    folder = create_dummy_experiment_folder(
        str(tmp_path),
        folder_name="output_20260902_150000",
        mode="S-SAP",
        images=[
            "learning_rewards_00100.png",
            "learning_rewards_00500.png",
            "learning_rewards_00200.png",
            "trajectory_20260902_140000.png",
            "trajectory_20260902_150000.png"
        ]
    )
    record = parse_single_experiment(folder)
    assert record is not None
    assert len(record.images) == 2
    assert "learning_rewards" in record.images
    assert "trajectory" in record.images
    # 最新（00500）が選ばれていること
    assert record.images["learning_rewards"].endswith("learning_rewards_00500.png")
    # 最新（150000）が選ばれていること
    assert record.images["trajectory"].endswith("trajectory_20260902_150000.png")


def test_parse_single_experiment_mode_dict_shield(tmp_path):
    import yaml
    folder = tmp_path / "output_20260909_145945"
    folder.mkdir()
    yaml_path = folder / "config_used_20260909_145945.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump({
            "mode": {
                "name": "S-SAP",
                "use_shield": False
            },
            "reward": {
                "reward_goal": 100.0
            }
        }, f)

    record = parse_single_experiment(str(folder))
    assert record is not None
    assert record.mode == "S-SAP"
    assert record.use_shield is False
    assert record.display_shield == "無効"
    assert record.config_flat["reward.reward_goal"] == 100.0



def test_scan_experiments_directory_recursive(tmp_path):
    # ルート
    # ├── S-SAP/
    # │   ├── output_20260801_100000/
    # │   └── output_20260802_150000/
    # └── Q-SAP/
    #     └── output_20260803_120000/
    s_sap_dir = tmp_path / "S-SAP"
    q_sap_dir = tmp_path / "Q-SAP"
    s_sap_dir.mkdir()
    q_sap_dir.mkdir()

    create_dummy_experiment_folder(str(s_sap_dir), "output_20260801_100000", mode="S-SAP", learning_rate=0.01)
    create_dummy_experiment_folder(str(s_sap_dir), "output_20260802_150000", mode="S-SAP", learning_rate=0.02)
    create_dummy_experiment_folder(str(q_sap_dir), "output_20260803_120000", mode="Q-SAP", learning_rate=0.03)

    # 再帰走査テスト
    records, config_keys = scan_experiments_directory(str(tmp_path), recursive=True)
    assert len(records) == 3

    # 新しい順（降順）にソートされていること
    assert records[0].timestamp_key == "20260803_120000"
    assert records[1].timestamp_key == "20260802_150000"
    assert records[2].timestamp_key == "20260801_100000"

    # カラムキーに learning_rate が含まれていること
    assert "learning_rate" in config_keys
    assert "batch_size" in config_keys

    # 非再帰走査テスト（ルート直下には実験フォルダがないため0件）
    records_non_rec, _ = scan_experiments_directory(str(tmp_path), recursive=False)
    assert len(records_non_rec) == 0

    # サブフォルダ直下を非再帰走査
    records_sub, _ = scan_experiments_directory(str(s_sap_dir), recursive=False)
    assert len(records_sub) == 2
