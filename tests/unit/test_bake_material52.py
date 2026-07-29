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


# ---------------------------------------------------------------------------
# UV binding on baked materials
#
# ShaderNodeTexImage has no uv_map property - only ShaderNodeNormalMap and
# ShaderNodeUVMap do (verified against Blender 5.2) - so every
# `hasattr(node, "uv_map")` guard around an image node was a silent no-op and
# the baked textures were never bound to a UV map at all. An image node with an
# unconnected Vector samples whatever map the renderer defaults to, which need
# not be the one the bake wrote into. On a mesh with two UV maps that is a
# texture sampled through the wrong layout.
# ---------------------------------------------------------------------------


class _UVSocket:
    def __init__(self):
        self.is_linked = False


class _FakeNode:
    """An image node: no uv_map property, one Vector input."""

    def __init__(self, node_type='TEX_IMAGE'):
        self.type = node_type
        self.inputs = {"Vector": _UVSocket()}
        self.outputs = {"UV": object()}


class _FakeUVMapNode(_FakeNode):
    def __init__(self):
        super().__init__(node_type='UVMAP')
        self.uv_map = ""


class _FakeNodes(list):
    def new(self, node_type):
        node = _FakeUVMapNode() if node_type == "ShaderNodeUVMap" else _FakeNode()
        self.append(node)
        return node


class _FakeLinks:
    def __init__(self):
        self.created = []

    def new(self, output, socket):
        socket.is_linked = True
        self.created.append((output, socket))


class _FakeTree:
    def __init__(self):
        self.nodes = _FakeNodes()
        self.links = _FakeLinks()


def test_image_node_gets_a_real_uv_map_source():
    tree = _FakeTree()
    image_node = _FakeNode()

    bake_textures._bind_uv_layer(tree, image_node, "BakeUV")

    uv_nodes = [node for node in tree.nodes if node.type == 'UVMAP']
    assert len(uv_nodes) == 1
    assert uv_nodes[0].uv_map == "BakeUV"
    assert image_node.inputs["Vector"].is_linked


def test_one_uv_source_is_shared_by_every_baked_texture():
    tree = _FakeTree()
    first, second = _FakeNode(), _FakeNode()

    bake_textures._bind_uv_layer(tree, first, "BakeUV")
    bake_textures._bind_uv_layer(tree, second, "BakeUV")

    assert len([node for node in tree.nodes if node.type == 'UVMAP']) == 1
    assert first.inputs["Vector"].is_linked
    assert second.inputs["Vector"].is_linked


def test_node_with_a_real_uv_map_property_is_set_directly():
    """ShaderNodeNormalMap takes the layer without needing a UVMap node."""
    tree = _FakeTree()
    normal_map = _FakeNode(node_type='NORMAL_MAP')
    normal_map.uv_map = ""

    bake_textures._bind_uv_layer(tree, normal_map, "BakeUV")

    assert normal_map.uv_map == "BakeUV"
    assert [node for node in tree.nodes if node.type == 'UVMAP'] == []


def test_no_uv_layer_binds_nothing():
    tree = _FakeTree()
    image_node = _FakeNode()

    bake_textures._bind_uv_layer(tree, image_node, None)

    assert list(tree.nodes) == []
    assert not image_node.inputs["Vector"].is_linked


def test_an_existing_vector_link_is_not_overwritten():
    tree = _FakeTree()
    image_node = _FakeNode()
    image_node.inputs["Vector"].is_linked = True

    bake_textures._bind_uv_layer(tree, image_node, "BakeUV")

    assert list(tree.nodes) == [], "a caller-authored Vector graph must win"


# ---------------------------------------------------------------------------
# Shared mesh datablocks: per-object material slots
#
# Material slots are DATA-linked by default, so assigning a baked material
# writes it onto the shared mesh datablock. With a linked duplicate (Alt+D)
# the last instance to bake overwrote every earlier one - and in LIT_IBL,
# where the reuse cache is deliberately disabled so each instance captures its
# own lighting, every instance ended up bound to the last instance's bake. A
# cube in full sun exported black because its duplicate sat under an occluder.
# ---------------------------------------------------------------------------


class _Slot:
    def __init__(self, material=None, link='DATA'):
        self.material = material
        self.link = link


class _SlotObject:
    def __init__(self, slots):
        self.material_slots = slots


def test_restore_puts_slot_link_back_before_the_material():
    """Restoring the material first would leave the bake on the mesh."""
    original = object()
    slot = _Slot(material=object(), link='OBJECT')
    obj = _SlotObject([slot])

    result = bake_textures.BakeResult()
    result.original_materials[obj] = [original]
    result.original_slot_links[obj] = ['DATA']

    bake_textures.restore_baked_materials(result, keep_baked_materials=False)

    assert slot.link == 'DATA'
    assert slot.material is original


def test_restore_leaves_untouched_slots_on_their_original_link():
    original = object()
    slot = _Slot(material=object(), link='DATA')
    obj = _SlotObject([slot])

    result = bake_textures.BakeResult()
    result.original_materials[obj] = [original]
    result.original_slot_links[obj] = ['DATA']

    bake_textures.restore_baked_materials(result, keep_baked_materials=False)

    assert slot.link == 'DATA'
    assert slot.material is original


def test_restore_without_recorded_links_still_restores_materials():
    """Older results, and objects whose links were never captured."""
    original = object()
    slot = _Slot(material=object(), link='DATA')
    obj = _SlotObject([slot])

    result = bake_textures.BakeResult()
    result.original_materials[obj] = [original]

    bake_textures.restore_baked_materials(result, keep_baked_materials=False)

    assert slot.material is original


# ---------------------------------------------------------------------------
# Averaged roughness must describe the material, not the bake margin.
#
# _average_image_value used to mean over the whole buffer. Texels no UV island
# covers read 0, and a larger margin dilates real values over more of them, so
# the exported constant moved with the margin setting. Measured end to end on
# Blender 5.2, one material with a uniform 0.5 roughness texture:
#
#   margin  0   8 (default)  32
#   before  0.118  0.212     0.438
#   after   0.502  0.492     0.501
# ---------------------------------------------------------------------------


class _PixelBuffer:
    def __init__(self, values):
        self.values = list(values)

    def __len__(self):
        return len(self.values)

    def foreach_get(self, target):
        target[:] = self.values

    def foreach_set(self, source):
        self.values = [float(v) for v in source]


class _AverageImage:
    def __init__(self, texels):
        """texels: list of (red, alpha) pairs."""
        flat = []
        for red, alpha in texels:
            flat.extend([red, red, red, alpha])
        self.pixels = _PixelBuffer(flat)


def test_average_ignores_texels_no_uv_island_covers():
    # Quarter of the texture carries the real value; the rest is untouched.
    image = _AverageImage([(0.5, 1.0)] * 4 + [(0.0, 0.0)] * 12)

    assert bake_textures._average_image_value(image) == pytest.approx(0.5)


def test_average_is_unchanged_by_how_much_margin_dilated():
    """The same material at two margins must average the same."""
    tight = _AverageImage([(0.5, 1.0)] * 4 + [(0.0, 0.0)] * 12)
    dilated = _AverageImage([(0.5, 1.0)] * 12 + [(0.0, 0.0)] * 4)

    assert bake_textures._average_image_value(tight) == pytest.approx(
        bake_textures._average_image_value(dilated)
    )


def test_a_genuinely_black_material_still_averages_to_zero():
    """Coverage comes from alpha, so 0.0 roughness is not mistaken for empty."""
    image = _AverageImage([(0.0, 1.0)] * 8 + [(0.0, 0.0)] * 8)

    assert bake_textures._average_image_value(image) == pytest.approx(0.0)


def test_average_falls_back_to_the_whole_buffer_without_a_coverage_mask():
    """An unprefilled target must not report every material as fully rough."""
    image = _AverageImage([(0.25, 1.0), (0.75, 1.0)])

    assert bake_textures._average_image_value(image) == pytest.approx(0.5)


def test_mark_pixels_uncovered_zeroes_the_buffer():
    image = _AverageImage([(0.9, 1.0)] * 4)

    bake_textures._mark_pixels_uncovered(image)

    assert set(image.pixels.values) == {0.0}


# ---------------------------------------------------------------------------
# Transparent materials: roughness is carried through, not baked.
#
# Cycles' ROUGHNESS pass returns 0 on an alpha-blended surface. Measured on
# Blender 5.2 with two materials identical but for Alpha, both at roughness
# 0.5: opaque baked R[0.0000, 0.5020], Alpha=0.4 baked R[0.0000, 0.0000]. Any
# glass or foliage material exported a mirror finish. Normal and metallic are
# already carried through for the same reason - the bake cannot represent them.
# ---------------------------------------------------------------------------


class _RoughSocket:
    def __init__(self, default_value=0.5, links=()):
        self.default_value = default_value
        self.links = list(links)
        self.is_linked = bool(links)


def _principled_with_roughness(socket):
    return types.SimpleNamespace(inputs={"Roughness": socket})


def _material_with(principled):
    return types.SimpleNamespace(use_nodes=True, node_tree=object())


def test_constant_roughness_is_carried_through(monkeypatch):
    principled = _principled_with_roughness(_RoughSocket(default_value=0.42))
    monkeypatch.setattr(bake_textures, "_surface_principled_node", lambda m: principled)

    captured = bake_textures._source_roughness_passthrough(_material_with(principled))

    assert captured == {"value": 0.42}


def test_wired_roughness_texture_is_carried_through(monkeypatch):
    image = object()
    from_node = types.SimpleNamespace(type='TEX_IMAGE', image=image, uv_map="RoughUV")
    link = types.SimpleNamespace(
        from_node=from_node, from_socket=types.SimpleNamespace(name="Color")
    )
    principled = _principled_with_roughness(_RoughSocket(links=[link]))
    monkeypatch.setattr(bake_textures, "_surface_principled_node", lambda m: principled)

    captured = bake_textures._source_roughness_passthrough(_material_with(principled))

    assert captured == {"image": image, "uv_layer": "RoughUV"}


def test_unreconstructable_roughness_chain_returns_none(monkeypatch):
    """Falls back to baking rather than guessing at a procedural chain."""
    from_node = types.SimpleNamespace(type='TEX_NOISE', image=None)
    link = types.SimpleNamespace(
        from_node=from_node, from_socket=types.SimpleNamespace(name="Fac")
    )
    principled = _principled_with_roughness(_RoughSocket(links=[link]))
    monkeypatch.setattr(bake_textures, "_surface_principled_node", lambda m: principled)

    assert bake_textures._source_roughness_passthrough(
        _material_with(principled)
    ) is None


def test_non_color_output_socket_is_not_carried_through(monkeypatch):
    from_node = types.SimpleNamespace(type='TEX_IMAGE', image=object(), uv_map=None)
    link = types.SimpleNamespace(
        from_node=from_node, from_socket=types.SimpleNamespace(name="Alpha")
    )
    principled = _principled_with_roughness(_RoughSocket(links=[link]))
    monkeypatch.setattr(bake_textures, "_surface_principled_node", lambda m: principled)

    assert bake_textures._source_roughness_passthrough(
        _material_with(principled)
    ) is None
