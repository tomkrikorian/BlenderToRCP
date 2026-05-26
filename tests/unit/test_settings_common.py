"""Tests for settings common utilities — no Blender required."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Plugin.api.commands._settings_common import (  # noqa: E402
    INTERNAL_KEYS,
    SETTING_GROUPS,
    coerce_value,
)


# ---------------------------------------------------------------------------
# INTERNAL_KEYS
# ---------------------------------------------------------------------------


class TestInternalKeys:
    def test_is_frozenset(self):
        assert isinstance(INTERNAL_KEYS, frozenset)

    def test_contains_expected_keys(self):
        """Verify all expected internal keys are present."""
        expected = {"rna_type", "name", "history_applied"}
        assert expected.issubset(INTERNAL_KEYS)

    def test_not_empty(self):
        assert len(INTERNAL_KEYS) >= 3


# ---------------------------------------------------------------------------
# SETTING_GROUPS
# ---------------------------------------------------------------------------


class TestSettingGroups:
    def test_has_groups(self):
        assert set(SETTING_GROUPS.keys()) == {
            "general",
            "objects",
            "geometry",
            "rigging",
            "texture",
            "bake",
            "diagnostics",
        }

    def test_no_overlap_between_groups(self):
        """No setting key should appear in multiple groups."""
        all_keys: list[str] = []
        for keys in SETTING_GROUPS.values():
            all_keys.extend(keys)
        assert len(all_keys) == len(set(all_keys)), "Duplicate keys found across groups"

    def test_no_internal_keys_in_groups(self):
        for group_name, keys in SETTING_GROUPS.items():
            overlap = keys & INTERNAL_KEYS
            assert not overlap, f"Group '{group_name}' contains internal keys: {overlap}"

    def test_all_groups_non_empty(self):
        for group_name, keys in SETTING_GROUPS.items():
            assert len(keys) > 0, f"Group '{group_name}' is empty"

    def test_general_contains_export_format(self):
        assert "export_format" in SETTING_GROUPS["general"]

    def test_bake_contains_bake_mode(self):
        assert "bake_mode" in SETTING_GROUPS["bake"]

    def test_texture_contains_override_toggle(self):
        assert "export_texture_settings_enabled" in SETTING_GROUPS["texture"]

    def test_geometry_contains_triangulate(self):
        assert "triangulate_meshes" in SETTING_GROUPS["geometry"]

    def test_rigging_contains_armatures(self):
        assert "export_armatures" in SETTING_GROUPS["rigging"]

    def test_objects_contains_meshes(self):
        assert "export_meshes" in SETTING_GROUPS["objects"]

    def test_diagnostics_contains_toggle(self):
        assert "diagnostics_enabled" in SETTING_GROUPS["diagnostics"]

    def test_all_values_are_sets(self):
        for group_name, keys in SETTING_GROUPS.items():
            assert isinstance(keys, (set, frozenset)), f"Group '{group_name}' value is not a set"

    def test_all_keys_are_strings(self):
        for group_name, keys in SETTING_GROUPS.items():
            for key in keys:
                assert isinstance(key, str), f"Non-string key {key!r} in group '{group_name}'"


# ---------------------------------------------------------------------------
# coerce_value — mock Blender property objects
# ---------------------------------------------------------------------------


def _mock_prop(prop_type: str, enum_items=None, identifier="test_prop"):
    """Create a mock Blender property-like object."""
    prop = SimpleNamespace(type=prop_type, identifier=identifier)
    if enum_items:
        prop.enum_items = [SimpleNamespace(identifier=v) for v in enum_items]
    return prop


class TestCoerceValueBoolean:
    def test_true_string(self):
        prop = _mock_prop("BOOLEAN")
        assert coerce_value(prop, "true") is True

    def test_false_string(self):
        prop = _mock_prop("BOOLEAN")
        assert coerce_value(prop, "false") is False

    def test_one_string(self):
        prop = _mock_prop("BOOLEAN")
        assert coerce_value(prop, "1") is True

    def test_yes_string(self):
        prop = _mock_prop("BOOLEAN")
        assert coerce_value(prop, "yes") is True

    def test_zero_string(self):
        prop = _mock_prop("BOOLEAN")
        assert coerce_value(prop, "0") is False

    def test_no_string(self):
        prop = _mock_prop("BOOLEAN")
        assert coerce_value(prop, "no") is False

    def test_off_string(self):
        """'off' is not in truthy set, so coerce_value returns False."""
        prop = _mock_prop("BOOLEAN")
        assert coerce_value(prop, "off") is False

    def test_on_string_is_not_truthy(self):
        """'on' is not in the truthy set (true/1/yes), so it returns False."""
        prop = _mock_prop("BOOLEAN")
        # NOTE: "on" is not recognized as truthy by the implementation
        assert coerce_value(prop, "on") is False

    def test_bool_passthrough(self):
        prop = _mock_prop("BOOLEAN")
        assert coerce_value(prop, True) is True
        assert coerce_value(prop, False) is False

    def test_case_insensitive(self):
        prop = _mock_prop("BOOLEAN")
        assert coerce_value(prop, "TRUE") is True
        assert coerce_value(prop, "False") is False
        assert coerce_value(prop, "YES") is True


class TestCoerceValueInt:
    def test_string_to_int(self):
        prop = _mock_prop("INT")
        assert coerce_value(prop, "42") == 42

    def test_int_passthrough(self):
        prop = _mock_prop("INT")
        assert coerce_value(prop, 42) == 42

    def test_negative_int(self):
        prop = _mock_prop("INT")
        assert coerce_value(prop, "-5") == -5

    def test_zero(self):
        prop = _mock_prop("INT")
        assert coerce_value(prop, "0") == 0

    def test_invalid_raises(self):
        prop = _mock_prop("INT")
        with pytest.raises((ValueError, TypeError)):
            coerce_value(prop, "not_a_number")

    def test_float_string_to_int(self):
        """Float strings should either truncate or raise — verify behavior."""
        prop = _mock_prop("INT")
        # int("1.5") raises ValueError; this is expected behavior
        with pytest.raises((ValueError, TypeError)):
            coerce_value(prop, "1.5")


class TestCoerceValueFloat:
    def test_string_to_float(self):
        prop = _mock_prop("FLOAT")
        assert coerce_value(prop, "1.5") == pytest.approx(1.5)

    def test_int_to_float(self):
        prop = _mock_prop("FLOAT")
        assert coerce_value(prop, 3) == 3.0

    def test_negative_float(self):
        prop = _mock_prop("FLOAT")
        assert coerce_value(prop, "-0.5") == pytest.approx(-0.5)

    def test_zero(self):
        prop = _mock_prop("FLOAT")
        assert coerce_value(prop, "0") == 0.0

    def test_int_string_to_float(self):
        prop = _mock_prop("FLOAT")
        assert coerce_value(prop, "42") == 42.0

    def test_invalid_raises(self):
        prop = _mock_prop("FLOAT")
        with pytest.raises((ValueError, TypeError)):
            coerce_value(prop, "not_a_float")


class TestCoerceValueEnum:
    def test_valid_value(self):
        prop = _mock_prop("ENUM", enum_items=["USDA", "USDC", "USDZ"])
        assert coerce_value(prop, "USDZ") == "USDZ"

    def test_lowercase_auto_uppercased(self):
        prop = _mock_prop("ENUM", enum_items=["USDA", "USDC", "USDZ"])
        assert coerce_value(prop, "usdz") == "USDZ"

    def test_invalid_raises_with_allowed(self):
        prop = _mock_prop("ENUM", enum_items=["USDA", "USDC", "USDZ"], identifier="export_format")
        with pytest.raises(ValueError, match="Invalid value.*Allowed"):
            coerce_value(prop, "FOO")

    def test_mixed_case(self):
        prop = _mock_prop("ENUM", enum_items=["USDA", "USDC", "USDZ"])
        assert coerce_value(prop, "Usdz") == "USDZ"

    def test_empty_string_raises(self):
        prop = _mock_prop("ENUM", enum_items=["USDA", "USDC", "USDZ"], identifier="export_format")
        with pytest.raises(ValueError):
            coerce_value(prop, "")


class TestCoerceValueString:
    def test_string_passthrough(self):
        prop = _mock_prop("STRING")
        assert coerce_value(prop, "hello") == "hello"

    def test_int_to_string(self):
        prop = _mock_prop("STRING")
        assert coerce_value(prop, 42) == "42"

    def test_empty_string(self):
        prop = _mock_prop("STRING")
        assert coerce_value(prop, "") == ""

    def test_path_string(self):
        prop = _mock_prop("STRING")
        assert coerce_value(prop, "/some/path/file.blend") == "/some/path/file.blend"


class TestCoerceValueUnknown:
    def test_unknown_type_passthrough(self):
        prop = _mock_prop("POINTER")
        assert coerce_value(prop, "anything") == "anything"
