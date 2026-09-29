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


def test_parse_single_experiment_continual_learning_false_with_cl_section(tmp_path):
    """
    continual_learning: false の場合、continual_learning セクションに goal_list が存在していても
    単一学習モード（is_continual = False, display_cl = '単一 (300ep)'）と正しく認識されることの検証
    """
    import yaml
    folder = tmp_path / "output_20260924_120000"
    folder.mkdir()
    yaml_path = folder / "config_used_20260924_120000.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump({
            "mode": {
                "name": "S-SAP",
                "use_shield": False,
                "continual_learning": False
            },
            "single_task": {
                "max_episodes": 300,
                "goal_position": [11.0, 13.0, 0.2]
            },
            "continual_learning": {
                "goal_list": [
                    [11.0, 3.0, 0.0],
                    [15.0, 5.0, 0.0],
                    [16.0, 8.0, 0.0],
                    [15.0, 11.0, 0.0],
                    [11.0, 13.0, 0.0]
                ],
                "unregistered_goal_list": [
                    [11.0, 3.0, 0.0],
                    [16.0, 8.0, 0.0],
                    [11.0, 13.0, 0.0]
                ]
            }
        }, f)

    record = parse_single_experiment(str(folder))
    assert record is not None
    assert record.is_continual is False
    assert record.display_cl == "単一 (300ep)"


def test_parse_single_experiment_continual_learning_true(tmp_path):
    """
    continual_learning: true の場合、継続学習モード（is_continual = True, display_cl = '継続 (5+3タスク)'）
    と正しく認識されることの検証
    """
    import yaml
    folder = tmp_path / "output_20260924_181649"
    folder.mkdir()
    yaml_path = folder / "config_used_20260924_181649.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump({
            "mode": {
                "name": "S-SAP",
                "use_shield": False,
                "continual_learning": True
            },
            "single_task": {
                "max_episodes": 300
            },
            "continual_learning": {
                "goal_list": [
                    [11.0, 3.0, 0.0],
                    [15.0, 5.0, 0.0],
                    [16.0, 8.0, 0.0],
                    [15.0, 11.0, 0.0],
                    [11.0, 13.0, 0.0]
                ],
                "unregistered_goal_list": [
                    [11.0, 3.0, 0.0],
                    [16.0, 8.0, 0.0],
                    [11.0, 13.0, 0.0]
                ]
            }
        }, f)

    record = parse_single_experiment(str(folder))
    assert record is not None
    assert record.is_continual is True
    assert record.display_cl == "継続 (5+3タスク)"


def test_parse_single_experiment_continual_learning_string_bool(tmp_path):
    """文字列の 'false' や 'true' も安全にパースされることの検証"""
    import yaml
    folder = tmp_path / "output_20260924_190000"
    folder.mkdir()
    yaml_path = folder / "config_used_20260924_190000.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump({
            "mode": {
                "name": "S-SAP",
                "continual_learning": "false"
            },
            "continual_learning": {
                "goal_list": [[1.0, 2.0, 0.0]]
            }
        }, f)

    record = parse_single_experiment(str(folder))
    assert record is not None
    assert record.is_continual is False
    assert record.display_cl == "単一"



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


def test_parse_single_experiment_generic_rl(tmp_path):
    """タイムスタンプ無しのフォルダ名、JSON設定、JPG画像、汎用CSVの認識テスト"""
    gen_folder = tmp_path / "ppo_cartpole_run1"
    gen_folder.mkdir()

    # JSON設定ファイル
    with open(gen_folder / "config.json", "w", encoding="utf-8") as f:
        f.write('{"algorithm": "PPO", "learning_rate": 0.0003, "gamma": 0.99}')

    # 汎用CSV
    with open(gen_folder / "progress.csv", "w", encoding="utf-8") as f:
        f.write("step,reward,loss\n1,10.0,0.5\n2,20.0,0.3\n")

    # JPG画像
    with open(gen_folder / "learning_curve.jpg", "w") as f:
        f.write("jpg")

    record = parse_single_experiment(str(gen_folder))
    assert record is not None
    assert record.folder_name == "ppo_cartpole_run1"
    assert record.timestamp_key == "ppo_cartpole_run1"
    # タイムスタンプが無くても更新日時のフォーマット文字列 (YYYY/MM/DD HH:MM:SS) が入る
    assert "/" in record.display_timestamp
    assert record.mode == "PPO"
    assert record.config_flat["learning_rate"] == 0.0003
    assert "learning_curve" in record.images
    assert record.csv_path is not None
    assert record.csv_path.endswith("progress.csv")

