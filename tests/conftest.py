"""
Pytest configuration for Athena's test suite.

Adds src/ to sys.path so tests can import project modules
(tools.*, core.*) the same way the application itself does.
"""

import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent.parent / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))