"""Unit tests for MaterialX texture authoring."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Plugin.export.materials.textures import _create_texture_connection
from Plugin.export.usd_utils import PXR_AVAILABLE, Usd
from Plugin.manifest.materialx_nodes import load_manifest


pytestmark = pytest.mark.skipif(
    not PXR_AVAILABLE,
    reason="OpenUSD Python bindings are required for MaterialX USD authoring tests.",
)


def test_normal_texture_uses_realitykit_normal_map_decode():
    stage = Usd.Stage.CreateInMemory()
    manifest = load_manifest()

    output = _create_texture_connection(
        stage,
        "/Material0",
        "normal",
        {
            "path": "textures/normal.avif",
            "output_type": "vector3",
            "type": "normal_texture",
        },
        manifest,
        "Material0",
    )

    assert output is not None
    authored = stage.GetRootLayer().ExportToString()
    assert 'uniform token info:id = "ND_normal_map_decode"' in authored
    assert 'uniform token info:id = "ND_normalmap"' not in authored
    assert "inputs:space" not in authored
    assert "inputs:scale" not in authored


def test_normal_texture_with_non_default_strength_uses_stdlib_normalmap():
    stage = Usd.Stage.CreateInMemory()
    manifest = load_manifest()

    output = _create_texture_connection(
        stage,
        "/Material0",
        "normal",
        {
            "path": "textures/normal.avif",
            "output_type": "vector3",
            "type": "normal_texture",
            "scale": 0.5,
            "space": "object",
        },
        manifest,
        "Material0",
    )

    assert output is not None
    authored = stage.GetRootLayer().ExportToString()
    assert 'uniform token info:id = "ND_normalmap"' in authored
    assert 'uniform token info:id = "ND_normal_map_decode"' not in authored
    assert "float inputs:scale = 0.5" in authored
    assert 'string inputs:space = "object"' in authored
