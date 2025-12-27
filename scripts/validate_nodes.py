#!/usr/bin/env python3
"""
Systematic Reality Composer Pro node validation.

Wrapper around scripts/_lib/node_validation.py.
"""

from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from scripts._lib.node_validation import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
