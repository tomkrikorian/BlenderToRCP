"""Background-worker scene snapshot cleanup regression tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


RUNNER_PATH = Path(__file__).resolve().parents[2] / "Plugin" / "bake_export_runner.py"


def _load_runner(monkeypatch, loaded_blend_file: Path):
    fake_bpy = SimpleNamespace(data=SimpleNamespace(filepath=str(loaded_blend_file)))
    monkeypatch.setitem(__import__("sys").modules, "bpy", fake_bpy)
    spec = importlib.util.spec_from_file_location(
        "_blendertorcp_snapshot_cleanup_test_runner",
        RUNNER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_snapshot_lock_defers_cleanup_without_failing_worker(tmp_path, monkeypatch):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    snapshot = job_dir / "scene_snapshot.blend"
    snapshot.write_bytes(b"BLENDER")
    runner = _load_runner(monkeypatch, snapshot)

    original_unlink = Path.unlink

    def locked_unlink(path, *args, **kwargs):
        if path == snapshot:
            raise PermissionError("sharing violation")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_unlink)

    state = runner._consume_loaded_scene_snapshot(
        {"blend_file": str(snapshot), "source_blend_file": "/source/model.blend"},
        job_dir,
    )

    assert state == {
        "loaded": True,
        "removed": False,
        "cleanup_deferred": True,
        "cleanup_error": "PermissionError: sharing violation",
    }
    assert snapshot.is_file()


def test_snapshot_load_mismatch_fails_closed_and_preserves_snapshot(tmp_path, monkeypatch):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    snapshot = job_dir / "scene_snapshot.blend"
    snapshot.write_bytes(b"BLENDER")
    runner = _load_runner(monkeypatch, tmp_path / "different.blend")

    try:
        runner._consume_loaded_scene_snapshot(
            {"blend_file": str(snapshot), "source_blend_file": "/source/model.blend"},
            job_dir,
        )
    except RuntimeError as exc:
        assert "did not load" in str(exc)
    else:
        raise AssertionError("snapshot mismatch did not fail closed")

    assert snapshot.is_file()
