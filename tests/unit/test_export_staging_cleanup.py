"""Unit tests for guaranteed export-staging cleanup.

`remove_export_staging_dir` is the finally-safe counterpart to
`cleanup_export_staging_dir`: it must remove the `.blendertorcp_temp/<stem>`
tree after any export attempt (success or failure) so it never lingers in the
user's export directory, while refusing to touch anything outside that tree.

`blender_usd_export` imports `bpy` (and `animation_export`, which also imports
`bpy`) at module load, so a stub is injected before import; the function under
test is pure pathlib/shutil.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules.setdefault("bpy", types.ModuleType("bpy"))

from Plugin.export.blender_usd_export import (  # noqa: E402
    get_export_staging_dir,
    remove_export_staging_dir,
)


def _make_staging(tmp_path: Path) -> Path:
    """Create a realistic .blendertorcp_temp/<stem>/ tree with content."""
    final = tmp_path / "Chess" / "ChessboardMarbleExport.usda"
    staging = get_export_staging_dir(final)
    (staging / "textures").mkdir(parents=True)
    (staging / "ChessboardMarbleExport.usda").write_text("#usda 1.0\n")
    (staging / "textures" / "marble.png").write_bytes(b"\x89PNG")
    assert staging.exists()
    return final


def test_removes_staging_tree_and_empty_root(tmp_path):
    final = _make_staging(tmp_path)
    staging = get_export_staging_dir(final)
    temp_root = staging.parent
    assert temp_root.name == ".blendertorcp_temp"

    remove_export_staging_dir(final)

    assert not staging.exists()
    # The now-empty .blendertorcp_temp root is dropped too.
    assert not temp_root.exists()


def test_idempotent_when_already_gone(tmp_path):
    final = _make_staging(tmp_path)
    remove_export_staging_dir(final)
    # Second call (e.g. publish already cleaned it) must not raise.
    remove_export_staging_dir(final)
    assert not get_export_staging_dir(final).exists()


def test_keeps_root_when_a_sibling_export_still_staged(tmp_path):
    final_a = _make_staging(tmp_path)
    # A second export staging under the same .blendertorcp_temp root.
    final_b = tmp_path / "Chess" / "OtherExport.usda"
    staging_b = get_export_staging_dir(final_b)
    staging_b.mkdir(parents=True)

    remove_export_staging_dir(final_a)

    assert not get_export_staging_dir(final_a).exists()
    # The shared root survives because sibling B is still staged inside it.
    assert staging_b.exists()
    assert staging_b.parent.exists()


def test_does_not_touch_paths_outside_blendertorcp_temp(tmp_path, monkeypatch):
    # If get_export_staging_dir ever resolved to a non-temp dir, refuse to rmtree.
    victim = tmp_path / "important"
    victim.mkdir()
    (victim / "keep.txt").write_text("do not delete")

    monkeypatch.setattr(
        "Plugin.export.blender_usd_export.get_export_staging_dir",
        lambda _final: victim,
    )
    remove_export_staging_dir(tmp_path / "whatever.usda")

    assert victim.exists()
    assert (victim / "keep.txt").exists()
