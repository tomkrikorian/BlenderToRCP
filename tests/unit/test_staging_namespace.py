"""Crash-safe sidecar generation namespace tests."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from Plugin.export import staging_namespace


def test_one_export_reuses_generation_across_asset_and_texture_passes(tmp_path):
    root = tmp_path / "scene.usda"
    root.write_text("#usda 1.0\n")

    first = staging_namespace.output_sidecar_namespace(root)
    second = staging_namespace.output_sidecar_namespace(root)

    assert first == second
    assert first.parts[0] == "scene.usda"
    assert re.fullmatch(r"[0-9a-f]{32}", first.parts[1])


def test_new_export_attempt_gets_an_immutable_new_generation(tmp_path):
    root = tmp_path / "scene.usda"
    root.write_text("#usda 1.0\n")
    first = staging_namespace.output_sidecar_namespace(root)

    shutil.rmtree(tmp_path / staging_namespace.GENERATION_MARKER_DIRECTORY)
    second = staging_namespace.output_sidecar_namespace(root)

    assert second != first


def test_output_filename_is_portable_without_namespace_collisions(tmp_path):
    root = tmp_path / "scene:look.usda"
    root.write_text("#usda 1.0\n")

    namespace = staging_namespace.output_sidecar_namespace(root)

    assert namespace.parts[0].startswith("scene_look.usda-")
    assert len(namespace.parts[0].rsplit("-", 1)[1]) == 8
