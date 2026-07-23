"""Strict BlenderToRCP 2.0 persisted-settings profile regressions."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_prefs_module(monkeypatch):
    bpy = ModuleType("bpy")
    bpy.__path__ = []
    bpy.context = None
    bpy_props = ModuleType("bpy.props")
    bpy_props.StringProperty = lambda **_kwargs: None
    bpy_props.EnumProperty = lambda **_kwargs: None
    bpy_types = ModuleType("bpy.types")
    bpy_types.AddonPreferences = type("AddonPreferences", (), {})
    bpy.types = bpy_types

    plugin_package = ModuleType("Plugin")
    plugin_package.__path__ = [str(_REPO_ROOT / "Plugin")]
    plugin_package.__package__ = "Plugin"

    monkeypatch.setitem(sys.modules, "Plugin", plugin_package)
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(sys.modules, "bpy.props", bpy_props)
    monkeypatch.setitem(sys.modules, "bpy.types", bpy_types)
    monkeypatch.delitem(sys.modules, "Plugin.prefs", raising=False)
    return importlib.import_module("Plugin.prefs")


class _FakeSettings:
    DEFAULTS = {
        "convert_orientation": True,
        "export_meshes": True,
        "export_format": "USDA",
        "filepath": "",
        "history_applied": False,
        "persist_suspended": False,
    }
    TYPES = {
        "convert_orientation": "BOOLEAN",
        "export_meshes": "BOOLEAN",
        "export_format": "ENUM",
        "filepath": "STRING",
        "history_applied": "BOOLEAN",
        "persist_suspended": "BOOLEAN",
    }

    def __init__(self, raw_values=None):
        object.__setattr__(self, "_raw", dict(raw_values or {}))
        properties = []
        for key, prop_type in self.TYPES.items():
            enum_items = (
                [SimpleNamespace(identifier=value) for value in ("USDA", "USDC", "USDZ")]
                if key == "export_format"
                else []
            )
            properties.append(
                SimpleNamespace(
                    identifier=key,
                    type=prop_type,
                    enum_items=enum_items,
                )
            )
        object.__setattr__(self, "bl_rna", SimpleNamespace(properties=properties))

    def __getattr__(self, key):
        if key in self.DEFAULTS:
            return self._raw.get(key, self.DEFAULTS[key])
        raise AttributeError(key)

    def __setattr__(self, key, value):
        if key in self.DEFAULTS:
            self._raw[key] = value
            return
        object.__setattr__(self, key, value)

    def keys(self):
        return self._raw.keys()

    def get(self, key, default=None):
        return self._raw.get(key, default)

    def __getitem__(self, key):
        return self._raw[key]

    def __setitem__(self, key, value):
        self._raw[key] = value

    def __delitem__(self, key):
        del self._raw[key]

    def property_unset(self, key):
        self._raw.pop(key, None)


def _install_preferences(monkeypatch, prefs_module, serialized=""):
    preferences = SimpleNamespace(last_export_settings_json=serialized)
    monkeypatch.setattr(prefs_module, "get_preferences", lambda _context=None: preferences)
    monkeypatch.setattr(prefs_module, "apply_last_export_path", lambda *_args: False)
    monkeypatch.setattr(prefs_module, "set_last_export_path", lambda *_args: None)
    return preferences


@pytest.mark.parametrize(
    "serialized",
    [
        json.dumps({"convert_orientation": False, "export_meshes": False}),
        json.dumps(
            {
                "schema": "blendertorcp.export-settings",
                "version": 1,
                "profile": "REALITYKIT_OS27",
                "values": {"convert_orientation": False, "export_meshes": False},
            }
        ),
    ],
)
def test_legacy_preferences_and_scene_idproperties_reset_to_strict_defaults(
    monkeypatch,
    serialized,
):
    prefs_module = _load_prefs_module(monkeypatch)
    preferences = _install_preferences(monkeypatch, prefs_module, serialized)
    settings = _FakeSettings(
        {
            "convert_orientation": False,
            "export_meshes": False,
            "history_applied": True,
            "unknown_dev_flag": True,
        }
    )

    result = prefs_module.apply_persisted_export_settings(object(), settings)

    assert result["status"] in {"unversioned", "old_version"}
    assert result["scene_reset"] is True
    assert settings.convert_orientation is True
    assert settings.export_meshes is True
    assert "unknown_dev_flag" not in settings.keys()
    assert prefs_module.export_settings_scene_is_current(settings)

    rewritten = json.loads(preferences.last_export_settings_json)
    assert rewritten == {
        "schema": "blendertorcp.export-settings",
        "version": 2,
        "profile": "REALITYKIT_OS27",
        "values": {
            "convert_orientation": True,
            "export_meshes": True,
            "export_format": "USDA",
        },
    }


def test_current_version_payload_roundtrips_explicit_profile_choices(monkeypatch):
    prefs_module = _load_prefs_module(monkeypatch)
    preferences = _install_preferences(monkeypatch, prefs_module)
    source = _FakeSettings()
    prefs_module.ensure_current_export_settings_scene_profile(source)
    source.convert_orientation = False
    source.export_meshes = False
    source.export_format = "USDC"

    assert prefs_module.persist_export_settings(object(), source) is True
    payload = json.loads(preferences.last_export_settings_json)
    assert payload["version"] == 2
    assert payload["profile"] == "REALITYKIT_OS27"

    target = _FakeSettings()
    result = prefs_module.apply_persisted_export_settings(object(), target)

    assert result == {"status": "current", "scene_reset": False}
    assert target.convert_orientation is False
    assert target.export_meshes is False
    assert target.export_format == "USDC"
    assert target.history_applied is True
    assert prefs_module.export_settings_scene_is_current(target)


def test_incomplete_current_payload_is_rejected_instead_of_partially_applied(
    monkeypatch,
):
    prefs_module = _load_prefs_module(monkeypatch)
    serialized = json.dumps(
        {
            "schema": "blendertorcp.export-settings",
            "version": 2,
            "profile": "REALITYKIT_OS27",
            "values": {"convert_orientation": False},
        }
    )
    preferences = _install_preferences(monkeypatch, prefs_module, serialized)
    settings = _FakeSettings()

    result = prefs_module.apply_persisted_export_settings(object(), settings)

    assert result == {"status": "invalid_values", "scene_reset": True}
    assert settings.convert_orientation is True
    assert settings.export_meshes is True
    assert json.loads(preferences.last_export_settings_json)["values"] == {
        "convert_orientation": True,
        "export_meshes": True,
        "export_format": "USDA",
    }


def test_panel_and_operator_delegate_to_one_shared_settings_loader():
    panel_source = (_REPO_ROOT / "Plugin/ui/panel.py").read_text()
    operator_source = (_REPO_ROOT / "Plugin/ops/export_operator.py").read_text()

    assert "apply_persisted_export_settings" in panel_source
    assert "apply_persisted_export_settings" in operator_source
    assert "last_export_settings_json" not in panel_source
    assert "last_export_settings_json" not in operator_source
