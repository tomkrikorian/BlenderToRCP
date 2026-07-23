"""Unit tests for Blender USD export staging helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules.setdefault("bpy", SimpleNamespace())

import Plugin as plugin_package  # noqa: E402
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


def test_sidecar_cleanup_uses_exact_output_manifest_not_stem_prefix(tmp_path):
    textures = tmp_path / "textures"
    textures.mkdir()
    chair_texture = textures / "chair-albedo.png"
    chair_v2_texture = textures / "chair-v2-albedo.png"
    chair_texture.write_bytes(b"chair")
    chair_v2_texture.write_bytes(b"chair-v2")

    chair_output = tmp_path / "chair.usda"
    chair_v2_output = tmp_path / "chair-v2.usda"
    blender_usd_export._write_output_sidecar_manifest(
        chair_output,
        [chair_texture],
    )
    blender_usd_export._write_output_sidecar_manifest(
        chair_v2_output,
        [chair_v2_texture],
    )

    blender_usd_export._remove_tracked_output_sidecars(chair_output)

    assert not chair_texture.exists()
    assert chair_v2_texture.exists()
    assert not blender_usd_export._output_sidecar_manifest_path(chair_output).exists()
    assert blender_usd_export._output_sidecar_manifest_path(chair_v2_output).exists()


def test_sidecar_cleanup_preserves_file_owned_by_another_output(tmp_path):
    textures = tmp_path / "textures"
    textures.mkdir()
    shared_texture = textures / "shared-albedo.png"
    shared_texture.write_bytes(b"shared")

    chair_output = tmp_path / "chair.usda"
    chair_v2_output = tmp_path / "chair-v2.usda"
    blender_usd_export._write_output_sidecar_manifest(
        chair_output,
        [shared_texture],
    )
    blender_usd_export._write_output_sidecar_manifest(
        chair_v2_output,
        [shared_texture],
    )

    blender_usd_export._remove_tracked_output_sidecars(chair_output)

    assert shared_texture.exists()


def test_blender_52_external_texture_contract_keeps_preview_without_native_copy():
    kwargs = blender_usd_export._build_export_kwargs(
        SimpleNamespace(),
        output_path="/tmp/scene.usdc",
        root_prim_path="/Scene",
    )

    assert kwargs["export_textures_mode"] == "KEEP"
    assert kwargs["overwrite_textures"] is False
    assert kwargs["generate_preview_surface"] is True
    assert kwargs["generate_materialx_network"] is False
    assert kwargs["root_prim_path"] == "/Scene"
    assert kwargs["incremental_frames"] == 0
    assert kwargs["export_mesh_colors"] is True
    assert kwargs["convert_orientation"] is True
    assert kwargs["export_global_up_selection"] == "Y"
    assert kwargs["convert_scene_units"] == "METERS"
    assert kwargs["export_hair"] is False
    assert kwargs["export_lights"] is False
    assert kwargs["convert_world_material"] is False
    assert kwargs["export_cameras"] is False
    assert kwargs["export_curves"] is False
    assert kwargs["export_points"] is False
    assert kwargs["export_volumes"] is False
    assert not {
        "export_textures",
        "export_texture_dir",
        "default_prim_path",
        "default_usd_format",
    }.intersection(kwargs)


@pytest.mark.parametrize("selected_only", [False, True])
def test_unsupported_raw_content_flags_are_disabled_for_full_and_selected_exports(
    selected_only,
):
    kwargs = blender_usd_export._build_export_kwargs(
        SimpleNamespace(
            selected_objects_only=selected_only,
            export_curves=True,
            export_points=True,
            export_hair=True,
            export_volumes=True,
            export_lights=True,
            convert_world_material=True,
            export_cameras=True,
        ),
        output_path="/tmp/scene.usdc",
        root_prim_path="/Scene",
    )

    assert kwargs["export_curves"] is False
    assert kwargs["export_points"] is False
    assert kwargs["export_hair"] is False
    assert kwargs["export_volumes"] is False
    assert kwargs["export_lights"] is False
    assert kwargs["convert_world_material"] is False
    assert kwargs["export_cameras"] is False
    assert kwargs["selected_objects_only"] is selected_only


def test_packed_image_uses_new_texture_mode_without_mutating_datablock(monkeypatch):
    def forbidden_mutation(*args, **kwargs):
        raise AssertionError("export contract must not unpack or repack images")

    image = SimpleNamespace(
        packed_file=object(),
        source="FILE",
        unpack=forbidden_mutation,
        pack=forbidden_mutation,
    )
    monkeypatch.setattr(
        blender_usd_export,
        "bpy",
        SimpleNamespace(data=SimpleNamespace(images=[image])),
    )

    kwargs = blender_usd_export._build_export_kwargs(
        SimpleNamespace(),
        output_path="/tmp/scene.usdc",
        root_prim_path="/Scene",
    )

    assert kwargs["export_textures_mode"] == "NEW"


def test_generated_image_uses_new_texture_mode(monkeypatch):
    image = SimpleNamespace(packed_file=None, source="GENERATED")
    monkeypatch.setattr(
        blender_usd_export,
        "bpy",
        SimpleNamespace(data=SimpleNamespace(images=[image])),
    )

    assert blender_usd_export._native_texture_export_mode() == "NEW"


def test_external_unpacked_images_use_keep_texture_mode(monkeypatch):
    image = SimpleNamespace(packed_file=None, source="FILE")
    monkeypatch.setattr(
        blender_usd_export,
        "bpy",
        SimpleNamespace(data=SimpleNamespace(images=[image])),
    )

    assert blender_usd_export._native_texture_export_mode() == "KEEP"


class _FakeUSDOperator:
    def __init__(self, properties, result=("FINISHED",)):
        self._properties = tuple(properties)
        self._result = set(result)
        self.called_with = None

    def get_rna_type(self):
        return SimpleNamespace(
            properties=[SimpleNamespace(identifier=name) for name in self._properties]
        )

    def __call__(self, **kwargs):
        self.called_with = kwargs
        return self._result


def test_export_operator_contract_passes_arguments_without_filtering():
    kwargs = blender_usd_export._build_export_kwargs(
        SimpleNamespace(),
        output_path="/tmp/scene.usdc",
        root_prim_path="/Scene",
    )
    operator = _FakeUSDOperator(kwargs)

    result = blender_usd_export._invoke_usd_export(operator, kwargs)

    assert result == {"FINISHED"}
    assert operator.called_with == kwargs


def test_export_operator_contract_fails_instead_of_masking_unknown_argument():
    kwargs = blender_usd_export._build_export_kwargs(
        SimpleNamespace(),
        output_path="/tmp/scene.usdc",
        root_prim_path="/Scene",
    )
    properties = set(kwargs) - {"export_textures_mode"}
    operator = _FakeUSDOperator(properties)

    with pytest.raises(RuntimeError, match="export_textures_mode"):
        blender_usd_export._invoke_usd_export(operator, kwargs)

    assert operator.called_with is None


def test_cancelled_export_operator_is_an_error_and_is_diagnosed():
    kwargs = blender_usd_export._build_export_kwargs(
        SimpleNamespace(),
        output_path="/tmp/scene.usdc",
        root_prim_path="/Scene",
    )
    operator = _FakeUSDOperator(kwargs, result=("CANCELLED",))
    errors = []
    diagnostics = SimpleNamespace(add_error=errors.append)

    with pytest.raises(RuntimeError, match="did not finish.*CANCELLED"):
        blender_usd_export._invoke_usd_export(
            operator,
            kwargs,
            diagnostics=diagnostics,
        )

    assert len(errors) == 1
    assert "CANCELLED" in errors[0]


def test_export_operator_records_new_window_manager_warning(monkeypatch):
    kwargs = blender_usd_export._build_export_kwargs(
        SimpleNamespace(),
        output_path="/tmp/scene.usdc",
        root_prim_path="/Scene",
    )
    reports = []

    class ReportingOperator(_FakeUSDOperator):
        def __call__(self, **call_kwargs):
            reports.append(SimpleNamespace(type={"WARNING"}, message="Material was simplified"))
            return super().__call__(**call_kwargs)

    monkeypatch.setattr(
        blender_usd_export,
        "bpy",
        SimpleNamespace(
            context=SimpleNamespace(window_manager=SimpleNamespace(reports=reports)),
        ),
    )
    warnings = []
    diagnostics = SimpleNamespace(add_warning=warnings.append, add_error=lambda _message: None)

    blender_usd_export._invoke_usd_export(
        ReportingOperator(kwargs),
        kwargs,
        diagnostics=diagnostics,
    )

    assert warnings == ["Blender USD export: Material was simplified"]


@pytest.mark.parametrize("version", [(5, 2, 0), (5, 2, 7), (6, 0, 0)])
def test_runtime_version_gate_accepts_blender_52_and_newer(monkeypatch, version):
    monkeypatch.setattr(plugin_package, "bpy", SimpleNamespace(app=SimpleNamespace(version=version)))

    assert plugin_package.require_supported_blender_version() == version


@pytest.mark.parametrize("version", [(4, 5, 9), (5, 1, 0)])
def test_runtime_version_gate_rejects_older_blender(monkeypatch, version):
    monkeypatch.setattr(plugin_package, "bpy", SimpleNamespace(app=SimpleNamespace(version=version)))

    with pytest.raises(RuntimeError, match=r"requires Blender 5\.2\.0 or newer"):
        plugin_package.require_supported_blender_version()


def test_runtime_version_gate_fails_closed_when_bpy_has_no_app(monkeypatch):
    monkeypatch.setattr(plugin_package, "bpy", SimpleNamespace())

    with pytest.raises(RuntimeError, match=r"detected Blender 0\.0\.0"):
        plugin_package.require_supported_blender_version()
