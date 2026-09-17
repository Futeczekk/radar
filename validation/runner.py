"""Stable validation entrypoint; implementation remains compatible with v0.8.x."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_corpus import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
