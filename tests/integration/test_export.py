"""Integration test — blendertorcp export."""

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


class TestExport:
    def test_export_usdz(self, run_cli, blend_file, tmp_output):
        out = tmp_output / "scene.usdz"
        result = run_cli("export", str(blend_file), "-o", str(out), "--format", "USDZ")
        assert result.ok, f"Export failed: {result.stderr}"
        actual_path = Path(result.json["export_path"])
        assert actual_path.exists(), f"Output USDZ file was not created at {actual_path}"
        assert actual_path.stat().st_size > 0, "Output file is empty"

    def test_export_usda(self, run_cli, blend_file, tmp_output):
        out = tmp_output / "scene.usda"
        result = run_cli("export", str(blend_file), "-o", str(out), "--format", "USDA")
        assert result.ok, f"Export failed: {result.stderr}"
        actual_path = Path(result.json["export_path"])
        assert actual_path.exists(), f"Output USDA file was not created at {actual_path}"
        assert actual_path.stat().st_size > 0, "Output file is empty"

    def test_output_has_export_path(self, run_cli, blend_file, tmp_output):
        out = tmp_output / "scene.usdz"
        result = run_cli("export", str(blend_file), "-o", str(out), "--format", "USDZ")
        assert result.ok
        assert "export_path" in result.json
        assert isinstance(result.json["export_path"], str)
        assert len(result.json["export_path"]) > 0

    def test_output_has_duration(self, run_cli, blend_file, tmp_output):
        out = tmp_output / "scene.usdz"
        result = run_cli("export", str(blend_file), "-o", str(out), "--format", "USDZ")
        assert result.ok
        assert "duration_seconds" in result.json
        assert isinstance(result.json["duration_seconds"], (int, float))
        assert result.json["duration_seconds"] > 0

    def test_invalid_blend_file(self, run_cli, tmp_output):
        out = tmp_output / "scene.usdz"
        result = run_cli("export", "/nonexistent.blend", "-o", str(out))
        assert not result.ok

    def test_no_diagnostics(self, run_cli, blend_file, tmp_output):
        out = tmp_output / "scene.usdz"
        result = run_cli("export", str(blend_file), "-o", str(out), "--format", "USDZ", "--no-diagnostics")
        assert result.ok
        actual_path = Path(result.json["export_path"])
        assert actual_path.exists()
        # diagnostics_path should be None when --no-diagnostics is used
        if "diagnostics_path" in result.json:
            assert result.json["diagnostics_path"] is None
        assert not actual_path.with_suffix(".diagnostics.json").exists()

    def test_diagnostics_disabled_by_default(self, run_cli, blend_file, tmp_output):
        out = tmp_output / "scene.usdz"
        result = run_cli("export", str(blend_file), "-o", str(out), "--format", "USDZ")
        assert result.ok
        actual_path = Path(result.json["export_path"])
        assert actual_path.exists()
        assert result.json.get("diagnostics_path") is None
        assert not actual_path.with_suffix(".diagnostics.json").exists()

    def test_diagnostics_flag_writes_sidecar(self, run_cli, blend_file, tmp_output):
        out = tmp_output / "scene.usdz"
        result = run_cli("export", str(blend_file), "-o", str(out), "--format", "USDZ", "--diagnostics")
        assert result.ok
        diag_path = Path(result.json["diagnostics_path"])
        assert diag_path.exists()
        assert diag_path.name == "scene.diagnostics.json"
