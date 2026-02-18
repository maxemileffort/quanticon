"""CLI launcher for the research pair scanner."""

import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from src.research.pair_scanner import main


if __name__ == "__main__":
    main()
