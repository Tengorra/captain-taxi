"""Make `bot/` importable when running `pytest bot/tests/` from the repo root."""
import sys
from pathlib import Path

BOT_ROOT = Path(__file__).resolve().parent.parent
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))
