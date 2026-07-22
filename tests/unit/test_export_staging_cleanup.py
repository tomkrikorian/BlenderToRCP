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
    create_export_staging_dir,
    get_export_staging_dir,
    remove_export_staging_dir,
)


def _make_staging(tmp_path: Path) -> tuple[Path, Path]:
    """Create a realistic attempt-scoped staging tree with content."""
    final = tmp_path / "Chess" / "ChessboardMarbleExport.usda"
    staging = create_export_staging_dir(final)
    (staging / "textures").mkdir(parents=True)
    (staging / "ChessboardMarbleExport.usda").write_text("#usda 1.0\n")
    (staging / "textures" / "marble.png").write_bytes(b"\x89PNG")
    assert staging.exists()
    return final, staging


def test_removes_staging_tree_and_empty_root(tmp_path):
    final, staging = _make_staging(tmp_path)
    temp_root = staging.parent
    assert temp_root.name == ".blendertorcp_temp"

    remove_export_staging_dir(final, staging_dir=staging)

    assert not staging.exists()
    # The now-empty .blendertorcp_temp root is dropped too.
    assert not temp_root.exists()


def test_idempotent_when_already_gone(tmp_path):
    final, staging = _make_staging(tmp_path)
    remove_export_staging_dir(final, staging_dir=staging)
    # Second call (e.g. publish already cleaned it) must not raise.
    remove_export_staging_dir(final, staging_dir=staging)
    assert not staging.exists()


def test_keeps_root_when_a_sibling_export_still_staged(tmp_path):
    final_a, staging_a = _make_staging(tmp_path)
    # A second export staging under the same .blendertorcp_temp root.
    final_b = tmp_path / "Chess" / "OtherExport.usda"
    staging_b = create_export_staging_dir(final_b)

    remove_export_staging_dir(final_a, staging_dir=staging_a)

    assert not staging_a.exists()
    # The shared root survives because sibling B is still staged inside it.
    assert staging_b.exists()
    assert staging_b.parent.exists()


def test_does_not_touch_paths_outside_blendertorcp_temp(tmp_path, monkeypatch):
    # If get_export_staging_dir ever resolved to a non-temp dir, refuse to rmtree.
    victim = tmp_path / "important"
    victim.mkdir()
    (victim / "keep.txt").write_text("do not delete")

    monkeypatch.setattr(
        "Plugin.export.blender_usd_export._validate_staging_matches_final",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("unsafe staging path")),
    )
    remove_export_staging_dir(
        tmp_path / "whatever.usda",
        staging_dir=victim,
    )

    assert victim.exists()
    assert (victim / "keep.txt").exists()


def test_attempts_are_unique_for_same_output_and_across_extensions(tmp_path):
    usda = tmp_path / "scene.usda"
    usdc = tmp_path / "scene.usdc"

    first = get_export_staging_dir(usda)
    second = get_export_staging_dir(usda)
    binary = get_export_staging_dir(usdc)

    assert first != second
    assert first.name.startswith("scene.usda.")
    assert binary.name.startswith("scene.usdc.")
    assert len({first, second, binary}) == 3


def test_cleanup_removes_only_the_exact_interleaved_attempt(tmp_path):
    final = tmp_path / "scene.usda"
    first = create_export_staging_dir(final)
    second = create_export_staging_dir(final)
    (first / "owner.txt").write_text("first")
    (second / "owner.txt").write_text("second")

    remove_export_staging_dir(final, staging_dir=first)

    assert not first.exists()
    assert (second / "owner.txt").read_text() == "second"
    remove_export_staging_dir(final, staging_dir=second)


def test_allocator_never_reuses_or_resets_preexisting_attempt(tmp_path, monkeypatch):
    final = tmp_path / "scene.usda"
    occupied_token = "0" * 32
    fresh_token = "1" * 32
    occupied = get_export_staging_dir(final, attempt_id=occupied_token)
    occupied.mkdir(parents=True)
    sentinel = occupied / "keep.txt"
    sentinel.write_text("unowned")
    tokens = iter((occupied_token, fresh_token))
    monkeypatch.setattr(
        "Plugin.export.blender_usd_export.secrets.token_hex",
        lambda _size: next(tokens),
    )

    allocated = create_export_staging_dir(final)

    assert allocated == get_export_staging_dir(final, attempt_id=fresh_token)
    assert sentinel.read_text() == "unowned"
    remove_export_staging_dir(final, staging_dir=allocated)


def test_cleanup_rejects_another_outputs_prefix_matching_attempt(tmp_path):
    shorter_output = tmp_path / "scene"
    longer_output = tmp_path / "scene.usda"
    longer_attempt = create_export_staging_dir(longer_output)
    sentinel = longer_attempt / "keep.txt"
    sentinel.write_text("other export")

    remove_export_staging_dir(
        shorter_output,
        staging_dir=longer_attempt,
    )

    assert sentinel.read_text() == "other export"
    remove_export_staging_dir(longer_output, staging_dir=longer_attempt)
