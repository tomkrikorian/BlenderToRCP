from __future__ import annotations

from pathlib import Path

import pytest

from Plugin.export.rcp_import_generator import (
    ImportGenerationError,
    generate_static_import,
)
from scripts._lib.rcp_import_contract import build_report, inspect_import

_CUBE_USDA = """#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "root"
{
    float3 xformOp:rotateXYZ = (-90, 0, 0)
    uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
    def Mesh "Cube"
    {
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 4, 6, 2, 3, 2, 6, 7, 7, 6, 4, 5, 5, 1, 3, 7, 1, 0, 2, 3, 5, 4, 0, 1]
        point3f[] points = [(1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)]
        normal3f[] normals = [(0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1), (0, -1, 0), (0, -1, 0), (0, -1, 0), (0, -1, 0), (-1, 0, 0), (-1, 0, 0), (-1, 0, 0), (-1, 0, 0), (0, 0, -1), (0, 0, -1), (0, 0, -1), (0, 0, -1), (1, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0)] (
            interpolation = "faceVarying"
        )
        texCoord2f[] primvars:st = [(0.625, 0.5), (0.875, 0.5), (0.875, 0.75), (0.625, 0.75), (0.375, 0.75), (0.625, 0.75), (0.625, 1), (0.375, 1), (0.375, 0), (0.625, 0), (0.625, 0.25), (0.375, 0.25), (0.125, 0.5), (0.375, 0.5), (0.375, 0.75), (0.125, 0.75), (0.375, 0.5), (0.625, 0.5), (0.625, 0.75), (0.375, 0.75), (0.375, 0.25), (0.625, 0.25), (0.625, 0.5), (0.375, 0.5)] (
            interpolation = "faceVarying"
        )
        uniform token subdivisionScheme = "none"
    }
}
"""


@pytest.fixture(autouse=True)
def _require_pxr() -> None:
    pytest.importorskip("pxr")


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "Cube.usda"
    source.write_text(_CUBE_USDA, encoding="utf-8")
    return source


def test_generate_static_import_passes_structural_contract(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "Cube.import"

    generate_static_import(source, destination)

    inspection = inspect_import(destination)
    assert inspection.errors == []
    report = build_report(inspection, rcp_build="80.0.1.500.1")
    assert report["counts"]["records"] == 13
    assert report["counts"]["content_hashed_buffers"] == 7
    assert report["counts"]["derived_or_unknown_hashed_buffers"] == 0
    assert report["source"]["exists"] is True
    assert not (destination / "settings.tm_buffers").exists()
    geometry = (destination / "geometry" / "Cube.tm_geometry").read_text()
    assert 'validity_hash: "2cfcf0b4ccf2dcd8"' in geometry


def test_generate_static_import_is_deterministic(tmp_path: Path) -> None:
    source = _source(tmp_path)
    first = generate_static_import(source, tmp_path / "First.import", asset_name="Cube")
    second = generate_static_import(source, tmp_path / "Second.import", asset_name="Cube")

    first_files = {
        path.relative_to(first): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files


def test_generate_static_import_refuses_unknown_geometry_hash(tmp_path: Path) -> None:
    source = tmp_path / "Triangle.usda"
    source.write_text(
        """#usda 1.0
(defaultPrim = "root")
def Xform "root"
{
    def Mesh "Triangle"
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    }
}
""",
        encoding="utf-8",
    )
    destination = tmp_path / "Triangle.import"

    with pytest.raises(ImportGenerationError, match="validity hash"):
        generate_static_import(source, destination)

    assert not destination.exists()


def test_generate_static_import_refuses_overwrite(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "Cube.import"
    destination.mkdir()

    with pytest.raises(ImportGenerationError, match="overwrite"):
        generate_static_import(source, destination)
