"""Unit tests for Blender USD export staging helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules.setdefault("bpy", SimpleNamespace())

from Plugin.export import blender_usd_export  # noqa: E402


def test_reset_export_staging_dir_removes_stale_sidecars(tmp_path):
    final_path = tmp_path / "scene.usda"
    staging_dir = blender_usd_export.get_export_staging_dir(final_path)
    stale_texture = staging_dir / "textures" / "scene-old.png"
    stale_asset = staging_dir / "assets" / "stale.usdc"
    stale_texture.parent.mkdir(parents=True)
    stale_asset.parent.mkdir(parents=True)
    stale_texture.write_bytes(b"stale texture")
    stale_asset.write_bytes(b"stale asset")

    blender_usd_export._reset_export_staging_dir(staging_dir)

    assert staging_dir.exists()
    assert list(staging_dir.iterdir()) == []
