"""Unit tests for opacity gating driven by actual transparency.

Regression guard for the Blender 4.2+/5.x ``blend_method`` deprecation: the
exporter must decide whether to author an ``opacity`` input from the real Alpha
value (``is_transparent``), not from ``blend_method`` (which never reports
``OPAQUE`` on modern Blender, so it would wire opacity into every material).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Plugin.export.materials.graph import MaterialXGraphBuilder
from Plugin.manifest.materialx_nodes import load_manifest


def _builder() -> MaterialXGraphBuilder:
    return MaterialXGraphBuilder(load_manifest())


def test_opaque_material_authors_no_opacity():
    builder = _builder()
    material_data = {
        "name": "Opaque",
        "type": "principled",
        "base_color": [0.349, 0.220, 0.125],
        "alpha": 1.0,
        "is_transparent": False,
    }

    pbr = builder._map_pbr_inputs(material_data)
    unlit = builder._map_unlit_inputs(material_data)

    assert "opacity" not in pbr
    assert "opacity" not in unlit


def test_transparent_material_authors_opacity():
    builder = _builder()
    material_data = {
        "name": "Glass",
        "type": "principled",
        "base_color": [0.8, 0.8, 0.8],
        "alpha": 0.4,
        "is_transparent": True,
    }

    pbr = builder._map_pbr_inputs(material_data)
    unlit = builder._map_unlit_inputs(material_data)

    assert pbr["opacity"] == 0.4
    assert unlit["opacity"] == 0.4


def test_missing_flag_defaults_to_opaque():
    """Material data without ``is_transparent`` must not author opacity."""
    builder = _builder()
    material_data = {
        "name": "NoFlag",
        "type": "principled",
        "base_color": [0.5, 0.5, 0.5],
        "alpha": 1.0,
    }

    assert "opacity" not in builder._map_pbr_inputs(material_data)
