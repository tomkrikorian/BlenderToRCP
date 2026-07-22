"""RealityKit OS 27 export-profile contract tests."""

from __future__ import annotations

from types import SimpleNamespace

from Plugin.api.commands._settings_common import (
    MATERIALX_SURFACE_PROFILE_DEFAULT,
    REALITYKIT_OS27_ADVANCED_CONTENT_KEYS,
    REALITYKIT_OS27_DEFAULTS,
    REALITYKIT_OS27_PROFILE_NAME,
    realitykit_os27_profile_deviations,
)
from Plugin.export.support_bundle import _collect_export_profile


def _settings(**overrides):
    values = dict(REALITYKIT_OS27_DEFAULTS)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_realitykit_os27_defaults_are_y_up_meters_and_fail_closed():
    assert REALITYKIT_OS27_PROFILE_NAME == "REALITYKIT_OS27"
    assert REALITYKIT_OS27_DEFAULTS["convert_orientation"] is True
    assert REALITYKIT_OS27_DEFAULTS["up_axis"] == "Y"
    assert REALITYKIT_OS27_DEFAULTS["convert_scene_units"] == "METERS"
    assert REALITYKIT_OS27_DEFAULTS["meters_per_unit"] == 1.0
    assert REALITYKIT_OS27_DEFAULTS["export_meshes"] is True
    assert REALITYKIT_OS27_DEFAULTS["materialx_surface_profile"] == (
        MATERIALX_SURFACE_PROFILE_DEFAULT
    )
    assert REALITYKIT_OS27_ADVANCED_CONTENT_KEYS == frozenset()


def test_profile_deviations_report_portable_axis_changes():
    settings = _settings(up_axis="Z")

    deviations = realitykit_os27_profile_deviations(settings)
    profile = _collect_export_profile(settings)

    assert deviations == {
        "up_axis": {"expected": "Y", "actual": "Z"},
    }
    assert profile["strict_defaults_active"] is False
    assert profile["advanced_content_enabled"] == []


def test_profile_reports_strict_defaults_active():
    profile = _collect_export_profile(_settings())

    assert profile["name"] == "REALITYKIT_OS27"
    assert profile["strict_defaults_active"] is True
    assert profile["advanced_content_enabled"] == []
    assert profile["deviations"] == {}


def test_experimental_material_profile_is_reported_as_a_deviation():
    profile = _collect_export_profile(
        _settings(materialx_surface_profile="realitykit_pbr2")
    )

    assert profile["strict_defaults_active"] is False
    assert profile["deviations"]["materialx_surface_profile"] == {
        "expected": "realitykit_portable",
        "actual": "realitykit_pbr2",
    }
