#!/usr/bin/env python3
"""
Validate exported USD/.rkassets for Reality Composer Pro compatibility.

Checks:
- usdchecker (structural)
- manifest lint (nodedef IDs)
- asset path lint (relative paths)
- optional realitytool compile for .rkassets bundles
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional


NODEDEF_RE = re.compile(r'info:id\\s*=\\s*"(?P<nodedef>ND_[^"]+)"')
ASSET_RE = re.compile(r'@(?P<asset>[^@]+)@')


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path

    manifest = _load_manifest(manifest_path)
    nodedefs = set(manifest.get("nodes", {}).keys())

    inputs = _collect_inputs(Path(args.input))
    if not inputs:
        print(f"No USD or rkassets found under {args.input}")
        return 2

    report: Dict[str, object] = {
        "input": str(Path(args.input).resolve()),
        "usdchecker": not args.no_usdchecker,
        "lint": not args.no_lint,
        "compile": not args.no_compile,
        "results": [],
        "errors": [],
    }

    failures = 0

    for entry in inputs:
        if entry.suffix == ".rkassets":
            result = _validate_rkassets(entry, nodedefs, args)
        else:
            result = _validate_usd(entry, nodedefs, args)

        report["results"].append(result)
        if result.get("status") != "ok":
            failures += 1

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2))
        print(f"Report: {args.output}")

    return 0 if failures == 0 else 1


def _validate_usd(path: Path, nodedefs: set, args) -> Dict[str, object]:
    result: Dict[str, object] = {
        "file": str(path),
        "status": "ok",
        "usdchecker": None,
        "lint": None,
        "compile": None,
    }

    if not args.no_usdchecker:
        result["usdchecker"] = _run_usdchecker(path)
        if result["usdchecker"]["ok"] is False:
            result["status"] = "error"

    if not args.no_lint:
        lint = _lint_usd_text(_load_usd_text(path), nodedefs)
        result["lint"] = lint
        if lint["errors"]:
            result["status"] = "error"

    if not args.no_compile and _is_compilable_usd(path):
        compile_result = _compile_from_usd(path, args)
        result["compile"] = compile_result
        if compile_result["ok"] is False:
            result["status"] = "error"

    return result


def _validate_rkassets(path: Path, nodedefs: set, args) -> Dict[str, object]:
    result: Dict[str, object] = {
        "rkassets": str(path),
        "status": "ok",
        "usdchecker": None,
        "lint": None,
        "compile": None,
    }

    scene = path / "scene.usda"
    if scene.exists() and not args.no_usdchecker:
        result["usdchecker"] = _run_usdchecker(scene)
        if result["usdchecker"]["ok"] is False:
            result["status"] = "error"

    if scene.exists() and not args.no_lint:
        lint = _lint_usd_text(_load_usd_text(scene), nodedefs)
        result["lint"] = lint
        if lint["errors"]:
            result["status"] = "error"

    if not args.no_compile:
        compile_result = _compile_rkassets(path, args)
        result["compile"] = compile_result
        if compile_result["ok"] is False:
            result["status"] = "error"

    return result


def _collect_inputs(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    results = []
    for ext in (".usda", ".usdc", ".usd", ".rkassets"):
        results.extend(path.rglob(f"*{ext}"))
    return sorted(set(results))


def _load_manifest(path: Path) -> Dict[str, object]:
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        raise SystemExit(f"Failed to load manifest: {path}: {exc}") from exc


def _run_usdchecker(path: Path) -> Dict[str, object]:
    try:
        proc = subprocess.run(["usdchecker", str(path)], capture_output=True, text=True, check=False)
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "exit_code": proc.returncode,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "usdchecker not found",
            "exit_code": -1,
        }


def _load_usd_text(path: Path) -> str:
    if path.suffix == ".usda":
        return path.read_text(errors="ignore")
    try:
        proc = subprocess.run(["usdcat", str(path)], capture_output=True, text=True, check=False)
        return proc.stdout
    except FileNotFoundError:
        return path.read_text(errors="ignore")


def _lint_usd_text(text: str, nodedefs: set) -> Dict[str, object]:
    errors = []
    warnings = []

    for match in NODEDEF_RE.finditer(text):
        nodedef = match.group("nodedef")
        if nodedef not in nodedefs:
            errors.append(f"Unknown nodedef: {nodedef}")

    assets = [m.group("asset") for m in ASSET_RE.finditer(text)]
    for asset in assets:
        if _is_absolute_asset(asset):
            errors.append(f"Absolute asset path: {asset}")

    if "outputs:mtlx:surface.connect" not in text:
        warnings.append("No MaterialX surface output found.")

    return {"errors": errors, "warnings": warnings, "asset_count": len(assets)}


def _is_absolute_asset(asset: str) -> bool:
    lowered = asset.lower()
    if lowered.startswith(("http:", "https:", "data:", "blob:", "anon:", "mem:", "file:")):
        return True
    if os.path.isabs(asset):
        return True
    if re.match(r"^[a-zA-Z]:\\\\", asset):
        return True
    return False


def _is_compilable_usd(path: Path) -> bool:
    return path.suffix in {".usda", ".usdc", ".usd"}


def _compile_from_usd(path: Path, args) -> Dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="blendertorcp_compile_") as temp_dir:
        bundle = Path(temp_dir) / f"{path.stem}.rkassets"
        bundle.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, bundle / "scene.usda")

        textures_dir = path.parent / "textures"
        if textures_dir.exists() and textures_dir.is_dir():
            shutil.copytree(textures_dir, bundle / "textures", dirs_exist_ok=True)

        return _compile_rkassets(bundle, args)


def _compile_rkassets(bundle: Path, args) -> Dict[str, object]:
    output_reality = bundle.with_suffix(".reality")
    cmd = [
        "xcrun", "realitytool", "compile",
        "--output-reality", str(output_reality),
        "--platform", args.platform,
        "--deployment-target", args.deployment_target,
        str(bundle),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "exit_code": proc.returncode,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "realitytool not found (xcrun)",
            "exit_code": -1,
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate exported USD or rkassets.")
    parser.add_argument("--input", required=True, help="USD file, rkassets bundle, or directory to scan.")
    parser.add_argument("--manifest", default="Plugin/manifest/rk_nodes_manifest.json", help="Manifest JSON path.")
    parser.add_argument("--output", default=None, help="Optional JSON report output.")
    parser.add_argument("--no-usdchecker", action="store_true", help="Skip usdchecker.")
    parser.add_argument("--no-lint", action="store_true", help="Skip manifest/asset lint.")
    parser.add_argument("--no-compile", action="store_true", help="Skip realitytool compile.")
    parser.add_argument("--platform", default="xros", help="realitytool platform.")
    parser.add_argument("--deployment-target", default="1.0", help="realitytool deployment target.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
