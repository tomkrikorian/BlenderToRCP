#!/usr/bin/env python3
"""Inspect, capture, and compare RCP-generated ``.import`` directory structure."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts._lib.rcp_import_contract import (
    ContractError,
    build_report,
    compare_reports,
    inspect_import,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed structural inspector for RCP-private .import directories. "
            "Opaque buffers are hashed, never decoded or generated."
        )
    )
    parser.add_argument("path", type=Path, help="RCP-generated .import directory")
    parser.add_argument("--profile", choices=("static", "transform", "skeletal"))
    parser.add_argument(
        "--rcp-version", help="Exact RCP marketing version used for capture"
    )
    parser.add_argument("--rcp-build", help="Exact CFBundleVersion used for capture")
    parser.add_argument(
        "--output", type=Path, help="Write the JSON report to this path"
    )
    parser.add_argument(
        "--compare",
        type=Path,
        help="Compare normalized structure with a prior JSON report",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        inspection = inspect_import(args.path, expected_profile=args.profile)
        report = build_report(
            inspection,
            expected_profile=args.profile,
            rcp_version=args.rcp_version,
            rcp_build=args.rcp_build,
        )
        payload: dict = report
        if args.compare:
            baseline = json.loads(args.compare.read_text(encoding="utf-8"))
            payload = {
                "report": report,
                "comparison": compare_reports(baseline, report),
            }
        encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        else:
            sys.stdout.write(encoded)
    except (ContractError, OSError, json.JSONDecodeError) as error:
        sys.stderr.write(f"rcp-import inspection failed: {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
