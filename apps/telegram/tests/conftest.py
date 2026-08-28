import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRS = [
    ROOT / "packages" / "core" / "src",
    ROOT / "packages" / "evaluation" / "src",
    ROOT / "packages" / "top_down" / "src",
    ROOT / "apps" / "telegram" / "src",
]
for source in SOURCE_DIRS:
    sys.path.insert(0, str(source))
