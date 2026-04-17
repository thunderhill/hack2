# Makes eda_report importable in tests without `pip install -e .`
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
