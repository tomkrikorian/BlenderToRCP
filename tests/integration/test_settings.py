"""Integration test — blendertorcp settings get/set/list."""

import pytest


pytestmark = pytest.mark.integration


class TestSettingsGet:
    def test_returns_dict(self, run_cli, blend_file):
        result = run_cli("settings", "get", str(blend_file))
        assert result.ok
        assert isinstance(result.json, dict)
        assert len(result.json) > 0, "Settings dict should not be empty"

    def test_has_export_format(self, run_cli, blend_file):
        result = run_cli("settings", "get", str(blend_file))
        assert "export_format" in result.json
        assert isinstance(result.json["export_format"], str)
        assert result.json["export_format"] in ("USDA", "USDC", "USDZ")

    def test_group_filter_bake(self, run_cli, blend_file):
        result = run_cli("settings", "get", str(blend_file), "--group", "bake")
        assert result.ok
        assert "bake_mode" in result.json
        assert isinstance(result.json["bake_mode"], str)
        # Should NOT contain keys from other groups
        assert "export_format" not in result.json
        assert "bake_resolution" not in result.json

    def test_group_filter_texture(self, run_cli, blend_file):
        result = run_cli("settings", "get", str(blend_file), "--group", "texture")
        assert result.ok
        assert "export_texture_settings_enabled" in result.json
        assert "bake_resolution" in result.json
        assert "bake_mode" not in result.json

    def test_group_filter_general(self, run_cli, blend_file):
        result = run_cli("settings", "get", str(blend_file), "--group", "general")
        assert result.ok
        assert "export_format" in result.json
        assert "bake_mode" not in result.json

    def test_group_filter_diagnostics(self, run_cli, blend_file):
        result = run_cli("settings", "get", str(blend_file), "--group", "diagnostics")
        assert result.ok
        assert result.json == {"diagnostics_enabled": False}

    def test_keys_filter(self, run_cli, blend_file):
        result = run_cli("settings", "get", str(blend_file), "--keys", "export_format")
        assert result.ok
        assert "export_format" in result.json
        # Should only return requested keys
        assert len(result.json) == 1


class TestSettingsSet:
    def test_dry_run(self, run_cli, blend_file):
        result = run_cli("settings", "set", str(blend_file), "export_format=USDZ", "--dry-run")
        assert result.ok
        assert result.json is not None

    def test_invalid_format_rejected(self, run_cli, blend_file):
        """Malformed key=value pairs should fail."""
        result = run_cli("settings", "set", str(blend_file), "no_equals_sign")
        assert not result.ok


class TestSettingsList:
    def test_returns_list(self, run_cli):
        result = run_cli("settings", "list")
        assert result.ok
        assert isinstance(result.json, list)
        assert len(result.json) > 0, "Settings list should not be empty"

    def test_entries_have_key(self, run_cli):
        result = run_cli("settings", "list")
        assert len(result.json) > 0
        for entry in result.json:
            assert "key" in entry
            assert isinstance(entry["key"], str)

    def test_entries_have_type(self, run_cli):
        result = run_cli("settings", "list")
        assert len(result.json) > 0
        for entry in result.json:
            assert "type" in entry
            assert isinstance(entry["type"], str)

    def test_contains_export_format(self, run_cli):
        result = run_cli("settings", "list")
        keys = [entry["key"] for entry in result.json]
        assert "export_format" in keys
        assert "diagnostics_enabled" in keys
