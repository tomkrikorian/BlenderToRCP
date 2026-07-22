"""Tests for CLI argument parsing — no Blender required."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure Plugin package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Plugin.cli.__main__ import CLIUsageError, build_parser  # noqa: E402


@pytest.fixture
def parser():
    return build_parser()


def test_cli_entrypoint_works_when_extension_folder_is_named_blendertorcp(tmp_path: Path):
    installed = tmp_path / "BlenderToRCP"
    shutil.copytree(
        Path(__file__).resolve().parents[2] / "Plugin",
        installed,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    proc = subprocess.run(
        [sys.executable, str(installed), "--json", "version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr

    import tomllib

    manifest = tomllib.loads(
        (Path(__file__).resolve().parents[2] / "Plugin" / "blender_manifest.toml").read_text()
    )
    assert json.loads(proc.stdout)["plugin"] == manifest["version"]


# ---------------------------------------------------------------------------
# Global flags
# ---------------------------------------------------------------------------

class TestGlobalFlags:
    def test_json_flag(self, parser):
        args = parser.parse_args(["--json", "version"])
        assert args.json_only is True

    def test_verbose_flag(self, parser):
        args = parser.parse_args(["--verbose", "version"])
        assert args.verbose is True

    def test_quiet_flag(self, parser):
        args = parser.parse_args(["--quiet", "version"])
        assert args.quiet is True

    def test_blender_flag(self, parser):
        args = parser.parse_args(["--blender", "/usr/bin/blender", "version"])
        assert args.blender == "/usr/bin/blender"

    def test_defaults(self, parser):
        args = parser.parse_args(["version"])
        assert args.json_only is False
        assert args.verbose is False
        assert args.quiet is False
        assert args.blender is None


# ---------------------------------------------------------------------------
# Subcommand parsing
# ---------------------------------------------------------------------------

class TestVersionCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["version"])
        assert args.command == "version"


class TestInfoCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["info", "scene.blend"])
        assert args.command == "info"
        assert args.blend_file == "scene.blend"

    def test_requires_blend_file(self, parser):
        with pytest.raises(CLIUsageError):
            parser.parse_args(["info"])


class TestListObjectsCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["list-objects", "scene.blend"])
        assert args.command == "list-objects"

    def test_type_filter(self, parser):
        args = parser.parse_args(["list-objects", "scene.blend", "--type", "MESH"])
        assert args.type == ["MESH"]

    def test_multiple_types(self, parser):
        args = parser.parse_args(["list-objects", "scene.blend", "--type", "MESH", "--type", "LIGHT"])
        assert args.type == ["MESH", "LIGHT"]

    def test_selected_flag(self, parser):
        args = parser.parse_args(["list-objects", "scene.blend", "--selected"])
        assert args.selected is True


class TestListMaterialsCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["list-materials", "scene.blend"])
        assert args.command == "list-materials"

    def test_unused_flag(self, parser):
        args = parser.parse_args(["list-materials", "scene.blend", "--unused"])
        assert args.unused is True


class TestValidateCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["validate", "scene.blend"])
        assert args.command == "validate"

    def test_material_filter(self, parser):
        args = parser.parse_args(["validate", "scene.blend", "--material", "Wood"])
        assert args.material == "Wood"

    def test_strict(self, parser):
        args = parser.parse_args(["validate", "scene.blend", "--strict"])
        assert args.strict is True

    def test_only_errors(self, parser):
        args = parser.parse_args(["validate", "scene.blend", "--only-errors"])
        assert args.only_errors is True


class TestExportCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["export", "scene.blend", "-o", "out.usdz"])
        assert args.command == "export"
        assert args.output == "out.usdz"
        assert args.blend_file == "scene.blend"

    def test_format(self, parser):
        args = parser.parse_args(["export", "scene.blend", "-o", "out.usdz", "--format", "USDZ"])
        assert args.format == "USDZ"

    def test_selected_only(self, parser):
        args = parser.parse_args(["export", "scene.blend", "-o", "out.usdz", "--selected-only"])
        assert args.selected_only is True

    def test_no_diagnostics(self, parser):
        args = parser.parse_args(["export", "scene.blend", "-o", "out.usdz", "--no-diagnostics"])
        assert args.no_diagnostics is True

    def test_diagnostics(self, parser):
        args = parser.parse_args(["export", "scene.blend", "-o", "out.usdz", "--diagnostics"])
        assert args.diagnostics is True

    def test_missing_output_raises(self, parser):
        with pytest.raises(CLIUsageError):
            parser.parse_args(["export", "scene.blend"])

    def test_overrides_plain(self, parser):
        """Overrides without leading dashes are parsed as positional args."""
        args = parser.parse_args([
            "export", "scene.blend",
            "export-animation=true", "triangulate-meshes=true",
            "-o", "out.usdz",
        ])
        assert "export-animation=true" in args.overrides
        assert "triangulate-meshes=true" in args.overrides


class TestBakeExportCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz"])
        assert args.command == "bake-export"
        assert args.output == "out.usdz"

    def test_bake_mode(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz", "--bake-mode", "LIT_IBL"])
        assert args.bake_mode == "LIT_IBL"

    def test_resolution(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz", "--resolution", "4096"])
        assert args.resolution == "4096"

    def test_image_format(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz", "--image-format", "PNG"])
        assert args.image_format == "PNG"

    def test_original_image_format(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz", "--image-format", "ORIGINAL"])
        assert args.image_format == "ORIGINAL"

    def test_margin_is_int(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz", "--margin", "16"])
        assert args.margin == 16
        assert isinstance(args.margin, int)

    def test_ibl_strength_is_float(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz", "--ibl-strength", "1.5"])
        assert args.ibl_strength == 1.5
        assert isinstance(args.ibl_strength, float)

    def test_ibl_rotation_is_float(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz", "--ibl-rotation", "3.14"])
        assert args.ibl_rotation == pytest.approx(3.14)

    def test_boolean_flags(self, parser):
        args = parser.parse_args([
            "bake-export", "scene.blend", "-o", "out.usdz",
            "--selected-only", "--no-diagnostics", "--isolate-meshes",
            "--no-base-color", "--no-opacity", "--keep-materials",
        ])
        assert args.selected_only is True
        assert args.no_diagnostics is True
        assert args.diagnostics is False
        assert args.isolate_meshes is True
        assert args.no_base_color is True
        assert args.no_opacity is True
        assert args.keep_materials is True

    def test_diagnostics(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz", "--diagnostics"])
        assert args.diagnostics is True

    def test_step_timeout(self, parser):
        args = parser.parse_args(["bake-export", "scene.blend", "-o", "out.usdz", "--step-timeout", "300"])
        assert args.timeout_step == 300

    def test_global_timeout(self, parser):
        args = parser.parse_args(["--timeout", "3600", "bake-export", "scene.blend", "-o", "out.usdz"])
        assert args.timeout == 3600

    def test_global_timeout_default(self, parser):
        args = parser.parse_args(["version"])
        assert args.timeout == 600

    def test_new_bake_flags(self, parser):
        args = parser.parse_args([
            "bake-export", "scene.blend", "-o", "out.usdz",
            "--roughness-mode", "AVERAGE", "--apply-yup",
        ])
        assert args.roughness_mode == "AVERAGE"
        assert args.apply_yup is True

    def test_export_apply_yup(self, parser):
        args = parser.parse_args(["export", "scene.blend", "--apply-yup", "-o", "out.usda"])
        assert args.apply_yup is True


class TestSupportBundleCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["support-bundle", "scene.blend", "-o", "out.usdz"])
        assert args.command == "support-bundle"
        assert args.blend_file == "scene.blend"
        assert args.output == "out.usdz"

    def test_options(self, parser):
        args = parser.parse_args([
            "support-bundle", "scene.blend",
            "--bundle-output", "support.zip",
            "--job-dir", ".blendertorcp_jobs/job",
            "--diagnostics", "out.diagnostics.json",
            "--include-output",
            "--include-blend",
            "--full-log",
            "--no-redact",
        ])
        assert args.bundle_output == "support.zip"
        assert args.job_dir == ".blendertorcp_jobs/job"
        assert args.diagnostics == "out.diagnostics.json"
        assert args.include_output is True
        assert args.include_blend is True
        assert args.full_log is True
        assert args.no_redact is True


class TestSettingsGetCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["settings", "get", "scene.blend"])
        assert args.command == "settings"
        assert args.settings_command == "get"

    def test_keys(self, parser):
        args = parser.parse_args(["settings", "get", "scene.blend", "--keys", "export_format", "bake_resolution"])
        assert args.keys == ["export_format", "bake_resolution"]

    def test_group(self, parser):
        args = parser.parse_args(["settings", "get", "scene.blend", "--group", "texture"])
        assert args.group == "texture"


class TestSettingsSetCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["settings", "set", "scene.blend", "export_format=USDZ"])
        assert args.settings == ["export_format=USDZ"]

    def test_multiple_settings(self, parser):
        args = parser.parse_args(["settings", "set", "scene.blend", "export_format=USDZ", "bake_resolution=4096"])
        assert len(args.settings) == 2

    def test_save_flag(self, parser):
        args = parser.parse_args(["settings", "set", "scene.blend", "export_format=USDZ", "--save"])
        assert args.save is True

    def test_dry_run_flag(self, parser):
        args = parser.parse_args(["settings", "set", "scene.blend", "export_format=USDZ", "--dry-run"])
        assert args.dry_run is True


class TestSettingsListCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["settings", "list"])
        assert args.settings_command == "list"


class TestPreferencesGetCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["preferences", "get"])
        assert args.command == "preferences"
        assert args.prefs_command == "get"


class TestPreferencesSetCommand:
    def test_parses(self, parser):
        args = parser.parse_args(["preferences", "set", "usdzip_path=/opt/usd/bin/usdzip"])
        assert args.settings == ["usdzip_path=/opt/usd/bin/usdzip"]


class TestMissingCommand:
    def test_no_command_raises(self, parser):
        with pytest.raises(CLIUsageError):
            parser.parse_args([])
