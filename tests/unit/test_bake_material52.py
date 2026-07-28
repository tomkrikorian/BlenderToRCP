"""Blender 5.2 material-bake contract regressions."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules.setdefault("bpy", types.ModuleType("bpy"))

from Plugin.export import bake_textures  # noqa: E402


class Socket:
    def __init__(self, default_value=None, *, node=None):
        self.default_value = default_value
        self.node = node
        self.links = []
        self.is_linked = False


class Node:
    def __init__(self, node_type, *, inputs=None, active=False):
        self.type = node_type
        self.inputs = inputs or {}
        self.outputs = {}
        self.is_active_output = active


def _link(from_node, to_socket):
    link = types.SimpleNamespace(from_node=from_node, to_socket=to_socket)
    to_socket.links.append(link)
    to_socket.is_linked = True
    return link


def test_hdri_blender_relative_path_uses_loaded_source_blend(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    hdri = source_dir / "studio.hdr"
    hdri.write_bytes(b"HDR")
    fake_bpy = types.SimpleNamespace(
        data=types.SimpleNamespace(filepath=str(source_dir / "scene.blend"))
    )
    monkeypatch.setattr(bake_textures, "bpy", fake_bpy)

    resolved = bake_textures._resolve_hdri_filepath(
        types.SimpleNamespace(bake_ibl_filepath="//studio.hdr")
    )

    assert resolved == hdri.resolve()


def test_background_hdri_resolution_can_pin_original_blend(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    hdri = source_dir / "studio.hdr"
    hdri.write_bytes(b"HDR")
    job_dir = tmp_path / "jobs" / "job"
    job_dir.mkdir(parents=True)
    fake_bpy = types.SimpleNamespace(
        data=types.SimpleNamespace(filepath=str(job_dir / "scene_snapshot.blend"))
    )
    monkeypatch.setattr(bake_textures, "bpy", fake_bpy)

    resolved = bake_textures._resolve_hdri_filepath(
        types.SimpleNamespace(bake_ibl_filepath="//studio.hdr"),
        blend_file=source_dir / "scene.blend",
    )

    assert resolved == hdri.resolve()


def test_hdri_blender_relative_path_requires_saved_scene(monkeypatch):
    fake_bpy = types.SimpleNamespace(data=types.SimpleNamespace(filepath=""))
    monkeypatch.setattr(bake_textures, "bpy", fake_bpy)

    with pytest.raises(RuntimeError, match="scene has never been saved"):
        bake_textures._resolve_hdri_filepath(
            types.SimpleNamespace(bake_ibl_filepath="//studio.hdr")
        )


def test_hdri_missing_file_reports_raw_and_resolved_path(tmp_path, monkeypatch):
    source = tmp_path / "scene.blend"
    fake_bpy = types.SimpleNamespace(
        data=types.SimpleNamespace(filepath=str(source))
    )
    monkeypatch.setattr(bake_textures, "bpy", fake_bpy)

    with pytest.raises(RuntimeError, match=r"studio\.hdr.*resolved to"):
        bake_textures._resolve_hdri_filepath(
            types.SimpleNamespace(bake_ibl_filepath="//studio.hdr")
        )


class _NodeCollection(list):
    def new(self, node_type):
        if node_type == "ShaderNodeEmission":
            node = Node('EMISSION')
            node.inputs = {'Color': Socket((0.0, 0.0, 0.0, 1.0), node=node)}
            node.outputs = {'Emission': Socket(node=node)}
        elif node_type == "ShaderNodeOutputMaterial":
            node = Node('OUTPUT_MATERIAL', inputs={'Surface': Socket()})
            node.inputs['Surface'].node = node
        else:  # pragma: no cover - keeps unexpected API changes obvious
            raise AssertionError(f"Unexpected node type: {node_type}")
        self.append(node)
        return node


class _Links:
    def new(self, from_socket, to_socket):
        link = types.SimpleNamespace(
            from_node=from_socket.node,
            from_socket=from_socket,
            to_socket=to_socket,
        )
        to_socket.links.append(link)
        to_socket.is_linked = True
        return link

    def remove(self, link):
        link.to_socket.links.remove(link)
        link.to_socket.is_linked = bool(link.to_socket.links)


def test_surface_principled_follows_active_output_not_collection_order():
    disconnected = Node('BSDF_PRINCIPLED')
    rendered = Node('BSDF_PRINCIPLED')
    inactive_surface = Socket()
    active_surface = Socket()
    _link(disconnected, inactive_surface)
    _link(rendered, active_surface)
    inactive_output = Node(
        'OUTPUT_MATERIAL', inputs={'Surface': inactive_surface}, active=False
    )
    active_output = Node(
        'OUTPUT_MATERIAL', inputs={'Surface': active_surface}, active=True
    )
    material = types.SimpleNamespace(
        use_nodes=True,
        node_tree=types.SimpleNamespace(
            nodes=[disconnected, inactive_output, rendered, active_output]
        ),
    )

    assert bake_textures._surface_principled_node(material) is rendered


def test_connected_non_principled_surface_does_not_use_disconnected_shader():
    disconnected = Node('BSDF_PRINCIPLED')
    emission = Node('EMISSION')
    surface = Socket()
    _link(emission, surface)
    output = Node('OUTPUT_MATERIAL', inputs={'Surface': surface}, active=True)
    material = types.SimpleNamespace(
        use_nodes=True,
        node_tree=types.SimpleNamespace(nodes=[disconnected, emission, output]),
    )

    assert bake_textures._surface_principled_node(material) is None


def test_unlinked_active_output_does_not_use_disconnected_shader():
    disconnected = Node('BSDF_PRINCIPLED')
    output = Node(
        'OUTPUT_MATERIAL', inputs={'Surface': Socket()}, active=True
    )
    material = types.SimpleNamespace(
        use_nodes=True,
        node_tree=types.SimpleNamespace(nodes=[disconnected, output]),
    )

    assert bake_textures._surface_principled_node(material) is None


def test_alpha_emission_uses_principled_connected_to_active_output():
    disconnected = Node(
        'BSDF_PRINCIPLED', inputs={'Alpha': Socket(0.9)}
    )
    rendered = Node('BSDF_PRINCIPLED', inputs={'Alpha': Socket(0.25)})
    disconnected.outputs = {'BSDF': Socket(node=disconnected)}
    rendered.outputs = {'BSDF': Socket(node=rendered)}
    inactive_surface = Socket()
    active_surface = Socket()
    inactive_output = Node(
        'OUTPUT_MATERIAL', inputs={'Surface': inactive_surface}, active=False
    )
    active_output = Node(
        'OUTPUT_MATERIAL', inputs={'Surface': active_surface}, active=True
    )
    nodes = _NodeCollection(
        [disconnected, inactive_output, rendered, active_output]
    )
    links = _Links()
    links.new(disconnected.outputs['BSDF'], inactive_surface)
    links.new(rendered.outputs['BSDF'], active_surface)
    material = types.SimpleNamespace(
        name="TwoPrincipled",
        use_nodes=True,
        node_tree=types.SimpleNamespace(nodes=nodes, links=links),
    )

    bake_textures._configure_emission_for_alpha(material)

    assert inactive_surface.links[0].from_node is disconnected
    emission = active_surface.links[0].from_node
    assert emission.type == 'EMISSION'
    assert emission.inputs['Color'].default_value == (0.25, 0.25, 0.25, 1.0)


def test_alpha_emission_rejects_mixed_surface_without_mutating_output():
    principled = Node('BSDF_PRINCIPLED', inputs={'Alpha': Socket(0.25)})
    transparent = Node('BSDF_TRANSPARENT')
    mix = Node('MIX_SHADER')
    mix.outputs = {'Shader': Socket(node=mix)}
    active_surface = Socket()
    active_output = Node(
        'OUTPUT_MATERIAL', inputs={'Surface': active_surface}, active=True
    )
    nodes = _NodeCollection([principled, transparent, mix, active_output])
    links = _Links()
    links.new(mix.outputs['Shader'], active_surface)
    material = types.SimpleNamespace(
        name="MixedTransparency",
        use_nodes=True,
        node_tree=types.SimpleNamespace(nodes=nodes, links=links),
    )

    with pytest.raises(RuntimeError, match="active Material Output"):
        bake_textures._configure_emission_for_alpha(material)

    assert active_surface.links[0].from_node is mix
    assert not any(node.type == 'EMISSION' for node in nodes)


@pytest.mark.parametrize(
    ("source_method", "transparent", "expected"),
    [
        ("DITHERED", False, "DITHERED"),
        ("BLENDED", False, "DITHERED"),
        ("DITHERED", True, "DITHERED"),
        ("BLENDED", True, "BLENDED"),
    ],
)
def test_surface_render_method_uses_blender_52_values(
    source_method, transparent, expected
):
    material = types.SimpleNamespace(surface_render_method=source_method)
    assert (
        bake_textures._surface_render_method(material, transparent=transparent)
        == expected
    )


def test_surface_render_method_rejects_unknown_value():
    material = types.SimpleNamespace(surface_render_method="OPAQUE")
    with pytest.raises(ValueError, match="Unsupported Blender 5.2"):
        bake_textures._surface_render_method(material, transparent=True)


class _Pixels:
    def __init__(self, values):
        self.values = list(values)

    def __len__(self):
        return len(self.values)

    def foreach_get(self, target):
        target[:] = self.values

    def foreach_set(self, source):
        self.values = [float(value) for value in source]


class _Image:
    def __init__(self, values):
        self.size = (2, 1)
        self.pixels = _Pixels(values)
        self.filepath_raw = ""
        self.alpha_mode = "PREMUL"
        self.saved = False

    def save(self):
        self.saved = True


def test_opacity_merge_exports_straight_alpha_without_changing_rgb():
    base = _Image([0.8, 0.4, 0.2, 1.0, 0.1, 0.2, 0.3, 1.0])
    opacity = _Image([0.25, 0.25, 0.25, 1.0, 0.75, 0.75, 0.75, 1.0])

    assert bake_textures._merge_opacity_into_base_image(base, opacity)
    assert base.alpha_mode == "STRAIGHT"
    assert base.saved
    assert base.pixels.values == pytest.approx(
        [0.8, 0.4, 0.2, 0.25, 0.1, 0.2, 0.3, 0.75]
    )


def test_bake_failure_restores_slots_and_removes_partial_datablocks(
    monkeypatch, tmp_path
):
    original = types.SimpleNamespace(name="Original")
    baked = types.SimpleNamespace(name="Partial", users=0)
    transient = types.SimpleNamespace(name="Throwaway")
    slot = types.SimpleNamespace(material=original)
    class _Object:
        type = 'MESH'
        material_slots = [slot]

    obj = _Object()
    removed_materials = []
    removed_images = []

    fake_bpy = types.SimpleNamespace(
        data=types.SimpleNamespace(
            materials=types.SimpleNamespace(
                remove=lambda material: removed_materials.append(material)
            ),
            images=types.SimpleNamespace(
                remove=lambda image, **_kwargs: removed_images.append(image)
            ),
        )
    )
    monkeypatch.setattr(bake_textures, "bpy", fake_bpy)

    def fail_mid_bake(*_args, result, **_kwargs):
        slot.material = baked
        result.baked_materials.append(baked)
        result.temporary_images.append(transient)
        raise RuntimeError("bake failed")

    monkeypatch.setattr(
        bake_textures, "_bake_materials_for_objects_impl", fail_mid_bake
    )

    with pytest.raises(RuntimeError, match="bake failed"):
        bake_textures.bake_materials_for_objects(
            context=None,
            settings=None,
            objects=[obj],
            output_dir=tmp_path,
        )

    assert slot.material is original
    assert removed_materials == [baked]
    assert removed_images == [transient]


# ---------------------------------------------------------------------------
# bpy.ops.object.bake argument contract
#
# Blender fills any bake property left unset from scene.render.bake, so an
# omitted argument silently inherits whatever the .blend was last saved with.
# Verified in Blender 5.2.0 LTS: with scene.render.bake.target='VERTEX_COLORS'
# and a mesh that has a color attribute, a DIFFUSE/COLOR bake returns
# {'FINISHED'} and leaves the target image fully black; with
# use_pass_direct/use_pass_indirect off, a COMBINED bake goes from mean red
# 1.0 to 0.0. Both produce a saved, packaged, all-black texture and no error.
# ---------------------------------------------------------------------------


def _capture_bake_kwargs(monkeypatch, bake_type, pass_filter, **extra):
    captured = {}

    def fake_bake(**kwargs):
        captured.update(kwargs)
        return {'FINISHED'}

    obj = types.SimpleNamespace(mode='OBJECT')
    context = types.SimpleNamespace(
        view_layer=types.SimpleNamespace(objects=types.SimpleNamespace(active=obj))
    )
    fake_bpy = types.SimpleNamespace(
        ops=types.SimpleNamespace(object=types.SimpleNamespace(bake=fake_bake))
    )
    monkeypatch.setattr(bake_textures, "bpy", fake_bpy)
    bake_textures._bake_object_pass(
        context, obj, bake_type=bake_type, pass_filter=pass_filter, margin=8, **extra
    )
    return captured


def test_bake_pass_pins_image_texture_target(monkeypatch):
    """An inherited target='VERTEX_COLORS' bakes black into the target image."""
    kwargs = _capture_bake_kwargs(monkeypatch, 'DIFFUSE', {'COLOR'})
    assert kwargs["target"] == 'IMAGE_TEXTURES'


def test_bake_pass_pins_internal_save_mode(monkeypatch):
    """An inherited save_mode='EXTERNAL' redirects the bake to disk."""
    kwargs = _capture_bake_kwargs(monkeypatch, 'DIFFUSE', {'COLOR'})
    assert kwargs["save_mode"] == 'INTERNAL'
    assert kwargs["use_split_materials"] is False


def test_combined_bake_always_sends_explicit_pass_filter(monkeypatch):
    """LIT_IBL passes pass_filter=None; unset means 'inherit', not 'no filter'."""
    kwargs = _capture_bake_kwargs(monkeypatch, 'COMBINED', None)
    assert "pass_filter" in kwargs, "COMBINED must never inherit scene use_pass_* toggles"
    assert kwargs["pass_filter"] == set(bake_textures.COMBINED_PASS_FILTER)
    assert {'DIRECT', 'INDIRECT'} <= kwargs["pass_filter"]


def test_non_combined_bake_omits_pass_filter_when_not_applicable(monkeypatch):
    """ROUGHNESS/EMIT have no pass_filter concept; don't invent one."""
    kwargs = _capture_bake_kwargs(monkeypatch, 'ROUGHNESS', None)
    assert "pass_filter" not in kwargs


def test_explicit_pass_filter_is_preserved(monkeypatch):
    kwargs = _capture_bake_kwargs(monkeypatch, 'DIFFUSE', {'COLOR'})
    assert kwargs["pass_filter"] == {'COLOR'}


def test_caller_can_override_pinned_properties(monkeypatch):
    kwargs = _capture_bake_kwargs(
        monkeypatch, 'DIFFUSE', {'COLOR'}, use_selected_to_active=True
    )
    assert kwargs["use_selected_to_active"] is True


def test_forget_image_drops_datablock_before_it_is_freed():
    """A freed datablock left in baked_images raises ReferenceError on read."""
    result = bake_textures.BakeResult()
    keep = object()
    doomed = object()
    result.baked_images.extend([keep, doomed])
    result.temporary_images.append(doomed)

    bake_textures._forget_image(result, doomed)

    assert result.baked_images == [keep]
    assert result.temporary_images == []
