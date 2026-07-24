#!/usr/bin/env python3
"""Fail closed unless all build-pinned RCP acceptance gates have evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts._lib.rcp_import_acceptance import AcceptanceError, validate_acceptance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "rcp_import" / "corpus.json",
    )
    args = parser.parse_args(argv)
    try:
        corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        validate_acceptance(corpus, evidence)
    except (OSError, json.JSONDecodeError, AcceptanceError) as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write("RCP .import acceptance evidence is complete and passing.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
