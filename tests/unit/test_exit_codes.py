"""Tests for CLI exit code mapping — no Blender required."""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Plugin.cli.__main__ import main  # noqa: E402
from Plugin.cli.bridge import BridgeError  # noqa: E402


def _run_main(*args: str) -> tuple[int, str, str]:
    """Run main() with given args, capturing stdout/stderr and return (exit_code, stdout, stderr)."""
    captured_out = StringIO()
    captured_err = StringIO()
    with patch("sys.argv", ["blendertorcp"] + list(args)), \
         patch("sys.stdout", captured_out), \
         patch("sys.stderr", captured_err):
        exit_code = main()
    return exit_code, captured_out.getvalue(), captured_err.getvalue()


# ---------------------------------------------------------------------------
# Exit code mapping
# ---------------------------------------------------------------------------


class TestExitCodeMapping:
    def test_blender_not_found_returns_2(self):
        """When bridge raises 'Blender not found', exit code should be 2."""
        with patch("Plugin.cli.__main__.bridge.run", side_effect=RuntimeError("Blender not found at '/bad/path'.")):
            code, _, stderr = _run_main("version")
            assert code == 2
            assert "Blender not found" in stderr

    def test_plugin_not_loaded_returns_3(self):
        with patch("Plugin.cli.__main__.bridge.run", side_effect=RuntimeError("Plugin not loaded in Blender.")):
            code, _, stderr = _run_main("version")
            assert code == 3
            assert "Plugin not loaded" in stderr

    def test_failed_to_import_returns_3(self):
        with patch("Plugin.cli.__main__.bridge.run", side_effect=RuntimeError("Failed to import command registry")):
            code, _, stderr = _run_main("version")
            assert code == 3
            assert "Failed to import" in stderr

    def test_generic_error_returns_1(self):
        with patch("Plugin.cli.__main__.bridge.run", side_effect=RuntimeError("Something unexpected")):
            code, _, stderr = _run_main("version")
            assert code == 1
            assert "Something unexpected" in stderr

    def test_keyboard_interrupt_returns_130(self):
        with patch("Plugin.cli.__main__.bridge.run", side_effect=KeyboardInterrupt):
            code, _, stderr = _run_main("version")
            assert code == 130
            assert "Aborted" in stderr

    def test_happy_path_returns_0(self):
        with patch("Plugin.cli.__main__.bridge.run", return_value={"version": "1.0"}):
            code, stdout, stderr = _run_main("version")
            assert code == 0
            parsed = json.loads(stdout)
            assert parsed["version"] == "1.0"


class TestJsonErrorOutput:
    def test_json_mode_wraps_error(self):
        """With --json flag, errors should be output as JSON on stdout."""
        with patch("Plugin.cli.__main__.bridge.run", side_effect=RuntimeError("Test error")):
            code, stdout, stderr = _run_main("--json", "version")
            assert code == 1
            parsed = json.loads(stdout)
            assert parsed["ok"] is False
            assert "Test error" in parsed["error"]
            # stderr should be suppressed in json mode
            assert stderr == ""

    def test_json_mode_blender_not_found(self):
        with patch("Plugin.cli.__main__.bridge.run", side_effect=RuntimeError("Blender not found at '/x'.")):
            code, stdout, stderr = _run_main("--json", "version")
            assert code == 2
            parsed = json.loads(stdout)
            assert parsed["ok"] is False
            assert "Blender not found" in parsed["error"]
            assert stderr == ""

    def test_json_mode_happy_path(self):
        with patch("Plugin.cli.__main__.bridge.run", return_value={"key": "val"}):
            code, stdout, stderr = _run_main("--json", "version")
            assert code == 0
            parsed = json.loads(stdout)
            assert parsed["key"] == "val"

    def test_json_mode_preserves_bridge_error_envelope(self):
        error = BridgeError(
            "Postprocess failed",
            response={
                "ok": False,
                "schema_version": "1.0",
                "command": "export",
                "error": {"code": "POSTPROCESS_FAILED", "message": "Postprocess failed"},
                "artifacts": {"diagnostics_path": "/tmp/out.diagnostics.json"},
            },
            returncode=1,
            command="export",
        )
        with patch("Plugin.cli.__main__.bridge.run", side_effect=error):
            code, stdout, stderr = _run_main("--json", "export", "scene.blend", "-o", "out.usdz")
            assert code == 1
            parsed = json.loads(stdout)
            assert parsed["error"]["code"] == "POSTPROCESS_FAILED"
            assert parsed["artifacts"]["diagnostics_path"] == "/tmp/out.diagnostics.json"
            assert stderr == ""
