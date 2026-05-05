"""Tests for Blender-hosted API runner behavior."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Plugin.api import runner  # noqa: E402


def test_runner_outputs_structured_json_when_addon_load_fails(monkeypatch, capsys):
    request = json.dumps({"command": "export", "args": {"filepath": "/tmp/out.usdz"}})
    monkeypatch.setattr(sys, "argv", ["runner.py", "--", request])

    def fail_load():
        raise RuntimeError("addon load failed")

    monkeypatch.setattr(runner, "_ensure_addon_loaded", fail_load)

    code = runner.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out.split(runner.OUTPUT_MARKER)[1])

    assert code == 1
    assert payload["ok"] is False
    assert payload["command"] == "export"
    assert payload["error"]["message"] == "addon load failed"
