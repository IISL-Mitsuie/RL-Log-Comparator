"""
Widgets package containing individual UI views and specialized components
"""

from src.ui.widgets.yaml_diff_widget import YamlDiffWidget
from src.ui.widgets.image_compare_widget import ImageCompareWidget
from src.ui.widgets.csv_compare_widget import CsvCompareWidget
from src.ui.widgets.log_spec_widget import LogSpecWidget
from src.ui.widgets.experiment_explorer_widget import ExperimentExplorerWidget

__all__ = [
    "YamlDiffWidget",
    "ImageCompareWidget",
    "CsvCompareWidget",
    "LogSpecWidget",
    "ExperimentExplorerWidget"
]
