import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = [
    ROOT / "UI_telegram" / "src",
    ROOT / "Models" / "Evaluation" / "src",
    ROOT / "Models" / "Top-Down" / "src",
]
for source in SOURCE_DIRS:
    sys.path.insert(0, str(source))
