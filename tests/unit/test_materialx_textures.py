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


def _normal_connection(stage, manifest, **spec):
    return _create_texture_connection(
        stage,
        "/Material0",
        "normal",
        {
            "path": "textures/normal.avif",
            "output_type": "vector3",
            "type": "normal_texture",
            **spec,
        },
        manifest,
        "Material0",
    )


def test_non_default_strength_stays_on_the_tangent_space_decode():
    """Strength used to force the ND_normalmap fallback, which returns a
    world-space normal into a tangent-space input. It is expressed in tangent
    space now: mix toward (0,0,1), which is Blender's own smooth-shaded path
    (node_normal_map.osl: normalize(N + (Normal - N) * max(Strength, 0)))."""
    stage = Usd.Stage.CreateInMemory()

    assert _normal_connection(stage, load_manifest(), scale=0.5) is not None
    authored = stage.GetRootLayer().ExportToString()
    assert 'uniform token info:id = "ND_normal_map_decode"' in authored
    assert 'uniform token info:id = "ND_normalmap"' not in authored
    assert 'uniform token info:id = "ND_mix_vector3"' in authored
    assert 'uniform token info:id = "ND_normalize_vector3"' in authored
    assert "float inputs:mix = 0.5" in authored


def test_non_tangent_space_is_refused_rather_than_decoded_in_the_wrong_basis():
    """No node RealityKit resolves can carry an object- or world-space normal
    map into the surface's tangent-space input, so there is nothing to author."""
    for space in ("object", "world"):
        stage = Usd.Stage.CreateInMemory()
        with pytest.raises(ValueError, match="cannot be represented"):
            _normal_connection(stage, load_manifest(), scale=0.5, space=space)
