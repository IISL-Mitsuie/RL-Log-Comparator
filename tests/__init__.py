"""
RL-Log-Comparator Unit and Integration Test Suite
"""

import sys
import os

# プロジェクトルートを確実に sys.path の先頭に追加
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
