"""Refreshing a generated RCP ``.import`` package through the real CLI.

Exports a scene as ``RCP_IMPORT``, then re-exports over the same destination
with ``--replace``. The refresh must succeed, still pass the build-80 contract
inspection, and - because the writer is deterministic - reproduce the previous
package byte for byte rather than churning every record identity.

``TestScenes/`` is gitignored, so the whole module skips when the scene is
absent.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENE = REPO_ROOT / "TestScenes" / "14_rcp_import_multimaterial.blend"
INSPECTOR = REPO_ROOT / "scripts" / "inspect_rcp_import.py"


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _inspect(package: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(INSPECTOR),
            str(package),
            "--profile",
            "static",
            "--rcp-version",
            "3.0",
            "--rcp-build",
            "80.0.1.500.1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def scene() -> Path:
    if not SCENE.exists():
        pytest.skip(f"TestScenes fixture is not present: {SCENE}")
    return SCENE


def test_replace_refreshes_a_generated_package(run_cli, scene, tmp_path):
    destination = tmp_path / "Duo.import"

    first = run_cli(
        "--json",
        "export",
        str(scene),
        "-o",
        str(destination),
        "--format",
        "RCP_IMPORT",
        timeout=600,
    )
    assert first.ok, first.stdout + first.stderr
    assert destination.is_dir()
    baseline = _tree(destination)
    assert (destination / "__tm_directory.tm_dir").is_file()

    inspected = _inspect(destination)
    assert inspected.returncode == 0, inspected.stdout + inspected.stderr

    # Without the opt-in the refusal is unchanged.
    refused = run_cli(
        "--json",
        "export",
        str(scene),
        "-o",
        str(destination),
        "--format",
        "RCP_IMPORT",
        timeout=600,
    )
    assert not refused.ok
    assert refused.json["error"]["code"] == "RCP_IMPORT_EXISTS"
    assert _tree(destination) == baseline

    refreshed = run_cli(
        "--json",
        "export",
        str(scene),
        "-o",
        str(destination),
        "--format",
        "RCP_IMPORT",
        "--replace",
        timeout=600,
    )
    assert refreshed.ok, refreshed.stdout + refreshed.stderr
    assert destination.is_dir()

    # Identity stability: an unchanged scene must reproduce the same package.
    assert _tree(destination) == baseline

    reinspected = _inspect(destination)
    assert reinspected.returncode == 0, reinspected.stdout + reinspected.stderr

    # No staging or move-aside directory survives a successful refresh.
    leftovers = sorted(
        entry.name
        for entry in tmp_path.iterdir()
        if entry.name.startswith(".blendertorcp-import-")
    )
    assert leftovers == []


def test_bake_export_replace_refreshes_a_generated_package(run_cli, scene, tmp_path):
    """The bake lane publishes its .usda inside the same staged transaction.

    Deliberately no byte-identity assertion here. A textured export allocates a
    fresh immutable sidecar generation each run, so its ``.usda`` - and with it
    every identity derived from that ``.usda`` - legitimately differs between
    runs. That predates ``--replace``: deleting the package by hand and
    re-exporting churned the same records.
    """
    destination = tmp_path / "Baked.import"
    invocation = (
        "--json",
        "bake-export",
        str(scene),
        "-o",
        str(destination),
        "--format",
        "RCP_IMPORT",
        "--resolution",
        "128",
    )

    first = run_cli(*invocation, timeout=900)
    assert first.ok, first.stdout + first.stderr
    baseline = _tree(destination)
    assert (destination / "__tm_directory.tm_dir").is_file()

    refused = run_cli(*invocation, timeout=900)
    assert not refused.ok
    assert refused.json["error"]["code"] == "RCP_IMPORT_EXISTS"
    assert _tree(destination) == baseline

    refreshed = run_cli(*invocation, "--replace", timeout=900)
    assert refreshed.ok, refreshed.stdout + refreshed.stderr
    assert (destination / "__tm_directory.tm_dir").is_file()
    assert destination.with_suffix(".usda").is_file()

    inspected = _inspect(destination)
    assert inspected.returncode == 0, inspected.stdout + inspected.stderr

    leftovers = sorted(
        entry.name
        for entry in tmp_path.iterdir()
        if entry.name.startswith(".blendertorcp-import-")
    )
    assert leftovers == []


def test_replace_is_rejected_for_a_non_rcp_format(run_cli, scene, tmp_path):
    result = run_cli(
        "--json",
        "export",
        str(scene),
        "-o",
        str(tmp_path / "scene.usdz"),
        "--format",
        "USDZ",
        "--replace",
        timeout=600,
    )

    assert not result.ok
    assert result.json["error"]["code"] == "RCP_IMPORT_REPLACE_NOT_APPLICABLE"
    assert not (tmp_path / "scene.usdz").exists()


def test_replace_refuses_a_directory_that_is_not_a_generated_package(
    run_cli, scene, tmp_path
):
    destination = tmp_path / "NotOurs.import"
    destination.mkdir()
    (destination / "keep.txt").write_text("keep")

    result = run_cli(
        "--json",
        "export",
        str(scene),
        "-o",
        str(destination),
        "--format",
        "RCP_IMPORT",
        "--replace",
        timeout=600,
    )

    assert not result.ok
    assert result.json["error"]["code"] == "RCP_IMPORT_REPLACE_NOT_A_PACKAGE"
    assert (destination / "keep.txt").read_text() == "keep"
