"""Run every backend test with pytest's offline provider isolation."""
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.exit(pytest.main([str(ROOT/"backend"),"-q"]))
