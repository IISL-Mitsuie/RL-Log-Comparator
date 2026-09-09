"""
ExperimentActionDialog の単体テスト
"""

import pytest
from src.core.parsers.experiment_scanner import ExperimentLogRecord
from src.ui.dialogs.experiment_action_dialog import ExperimentActionDialog, ExperimentAction
from tests.helpers import get_qapp


@pytest.fixture
def dummy_record():
    return ExperimentLogRecord(
        folder_path="/path/to/output_20260902_113727",
        folder_name="output_20260902_113727",
        timestamp_key="20260902_113727",
        display_timestamp="2026/09/02 11:37:27",
        mode="S-SAP",
        config_flat={"learning_rate": 0.001}
    )


def test_dialog_init(dummy_record):
    get_qapp()
    dlg = ExperimentActionDialog(dummy_record)
    assert dlg.selected_action == ExperimentAction.CANCEL
    assert dlg.record.mode == "S-SAP"


def test_dialog_set_a(dummy_record):
    get_qapp()
    dlg = ExperimentActionDialog(dummy_record)
    dlg._on_set_a()
    assert dlg.selected_action == ExperimentAction.SET_A


def test_dialog_set_b(dummy_record):
    get_qapp()
    dlg = ExperimentActionDialog(dummy_record)
    dlg._on_set_b()
    assert dlg.selected_action == ExperimentAction.SET_B
