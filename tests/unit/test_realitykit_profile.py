"""RealityKit OS 27 export-profile contract tests."""

from __future__ import annotations

from types import SimpleNamespace

from Plugin.api.commands._settings_common import (
    MATERIALX_SURFACE_PROFILE_DEFAULT,
    REALITYKIT_FORWARD_AXIS,
    REALITYKIT_METERS_PER_UNIT,
    REALITYKIT_OS27_DEFAULTS,
    REALITYKIT_OS27_PROFILE_NAME,
    REALITYKIT_SCENE_UNITS,
    REALITYKIT_UP_AXIS,
    realitykit_os27_profile_deviations,
)
from Plugin.export.support_bundle import _collect_export_profile


def _settings(**overrides):
    values = dict(REALITYKIT_OS27_DEFAULTS)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_realitykit_os27_defaults_are_y_up_meters_and_fail_closed():
    assert REALITYKIT_OS27_PROFILE_NAME == "REALITYKIT_OS27"
    assert REALITYKIT_FORWARD_AXIS == "-Z"
    assert REALITYKIT_UP_AXIS == "Y"
    assert REALITYKIT_SCENE_UNITS == "METERS"
    assert REALITYKIT_METERS_PER_UNIT == 1.0
    assert REALITYKIT_OS27_DEFAULTS["materialx_surface_profile"] == (
        MATERIALX_SURFACE_PROFILE_DEFAULT
    )
    assert REALITYKIT_OS27_DEFAULTS["normalize_unsupported_values"] is False


def test_spatial_contract_is_not_a_profile_deviation():
    settings = _settings(up_axis="Z", convert_orientation=False)

    assert realitykit_os27_profile_deviations(settings) == {}
    assert _collect_export_profile(settings)["strict_defaults_active"] is True


def test_profile_reports_strict_defaults_active():
    profile = _collect_export_profile(_settings())

    assert profile["name"] == "REALITYKIT_OS27"
    assert profile["spatial_contract"] == {
        "convert_orientation": True,
        "forward_axis": "-Z",
        "up_axis": "Y",
        "scene_units": "METERS",
        "meters_per_unit": 1.0,
        "relative_paths": True,
        "export_meshes": True,
        "export_uvmaps": True,
        "rename_uvmaps": True,
        "export_normals": True,
    }
    assert profile["strict_defaults_active"] is True
    assert profile["advanced_content_enabled"] == []
    assert profile["deviations"] == {}


def test_a_non_default_material_profile_is_reported_as_a_deviation():
    """PBR Surface 2 is the default now; the portable surface is the deviation.

    This test used to name PBR2 as the "experimental" deviation. The surface
    was verified by import and became the default, so the roles swapped.
    """
    profile = _collect_export_profile(
        _settings(materialx_surface_profile="realitykit_portable")
    )

    assert profile["strict_defaults_active"] is False
    assert profile["deviations"]["materialx_surface_profile"] == {
        "expected": "realitykit_pbr2",
        "actual": "realitykit_portable",
    }


def test_export_normalization_opt_in_is_reported_as_a_deviation():
    profile = _collect_export_profile(
        _settings(normalize_unsupported_values=True)
    )

    assert profile["strict_defaults_active"] is False
    assert profile["deviations"]["normalize_unsupported_values"] == {
        "expected": False,
        "actual": True,
    }
