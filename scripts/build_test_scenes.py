"""Generate the small per-feature evaluation scenes in References/Blender.

Run with Blender, not python:

    /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
        --python scripts/build_test_scenes.py

Each scene proves ONE behaviour, and is built so a *wrong* result looks
obviously wrong. That is harder than it sounds, and this kit has shipped probes
that tested nothing: two textures that were byte-identical, a roughness map of
0.502 against a 0.5 default, an identity normal map. The rules below exist to
stop that recurring. See References/Blender/TEST_SCENES.md for what each scene
should look like in Reality Composer Pro.

Design rules:

- **Ship a control in frame.** A verdict about a continuous value needs a
  known-good twin differing in exactly one input, so the pass condition is a
  visible difference rather than an absolute nobody can eyeball.
- **Never say "compare against the Blender render."** Lights are dropped
  silently, so the Blender render is lit by a sun that never reaches the export
  while Reality Composer Pro relights under its own environment. A mismatch is
  guaranteed and proves nothing.
- **Roughness probes are metallic.** On a dielectric, roughness modulates a weak
  specular lobe. On metal it is sharp-versus-blurred reflection - a difference
  of kind, not degree.
- **No value within 0.1 of a Blender default**, and no flat-fill data texture.
  A probe that lands on the default passes when the feature is dropped.
- **Asymmetric, chiral geometry** wherever orientation or handedness is the
  verdict. A symmetric object cannot show a flip.
- **Few large texels for filtering probes.** Closest-versus-Linear needs a 16 px
  image, not a big one: at 256 px the texels are ~9 mm and you would have to put
  your nose on the surface to judge it.
"""

from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path

import bpy

OUT = Path(__file__).resolve().parents[1] / "References" / "Blender"

#: Every image the kit writes, by SHA-256, so two probes meant to be told apart
#: cannot silently be the same picture. Staging deduplicates by digest.
_IMAGE_DIGESTS: dict[str, str] = {}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def fresh(cycles: bool = False, samples: int = 16) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    if cycles:
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = samples


def save(name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    print(f"BUILT {name}.blend {path.stat().st_size}")


def _register(image) -> None:
    digest = hashlib.sha256(bytes(int(c * 255) for c in image.pixels)).hexdigest()
    clash = next((n for n, d in _IMAGE_DIGESTS.items() if d == digest), None)
    if clash:
        raise SystemExit(
            f"image {image.name!r} is byte-identical to {clash!r}; two probes "
            "that must be told apart cannot be the same picture"
        )
    _IMAGE_DIGESTS[image.name] = digest


def grid_image(name: str, size: int = 128):
    """Four distinct quadrants plus a per-name corner stamp.

    The stamp encodes the image's name, so two grids built with the same
    parameters are still distinguishable - both to the eye and to the staging
    layer, which deduplicates by digest.
    """
    image = bpy.data.images.new(name, size, size)
    half = size // 2
    tag = int(hashlib.sha256(name.encode()).hexdigest()[:6], 16)
    stamp = ((tag & 0xFF) / 255.0, ((tag >> 8) & 0xFF) / 255.0,
             ((tag >> 16) & 0xFF) / 255.0)
    pixels = []
    for y in range(size):
        for x in range(size):
            r = 0.90 if x < half else 0.10
            g = 0.85 if y < half else 0.12
            b = 0.15 if (x < half) == (y < half) else 0.75
            # A corner stamp marks (0,0) and makes this image unique.
            if x < max(2, size // 16) and y < max(2, size // 16):
                r, g, b = stamp
            pixels += [r, g, b, 1.0]
    image.pixels = pixels
    _register(image)
    return image


def ramp_image(name: str, size: int = 64, *, axis: str = "x", data: bool = True):
    """A gradient. Flat fills cannot show a dropped link; a ramp can."""
    image = bpy.data.images.new(name, size, size, is_data=data)
    # A per-name offset on the flat channels, so two ramps built with the same
    # parameters are not the same picture. Small enough not to change the read.
    tag = int(hashlib.sha256(name.encode()).hexdigest()[:4], 16) / 65535.0
    pixels = []
    for y in range(size):
        for x in range(size):
            t = (x if axis == "x" else y) / (size - 1)
            # Distinct per channel: reading the wrong channel is then visible.
            pixels += [t, 0.15 + tag * 0.02, 0.85 - tag * 0.02, 1.0]
    image.pixels = pixels
    _register(image)
    return image


def normal_image(name: str, size: int = 64):
    """A strong tangent-space normal map - NOT the identity normal.

    An identity map (0.5, 0.5, 1.0) is indistinguishable from no normal map at
    all, which is how this kit previously shipped a normal probe that proved
    nothing.
    """
    image = bpy.data.images.new(name, size, size, is_data=True)
    pixels = []
    for y in range(size):
        for x in range(size):
            # Diagonal ridges: a strong, directional perturbation.
            angle = math.sin((x / size) * math.pi * 6.0) * 0.7
            nx, ny = angle, math.sin((y / size) * math.pi * 6.0) * 0.7
            nz = math.sqrt(max(0.05, 1.0 - nx * nx - ny * ny))
            pixels += [nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz, 1.0]
    image.pixels = pixels
    _register(image)
    return image


def cube(name: str, *, location=(0, 0, 0), size: float = 1.0):
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = f"{name}Mesh"
    return obj


def sphere(name: str, *, location=(0, 0, 0), radius: float = 0.5):
    """A 16x8 sphere: 114 verts, enough for a reflection, a fifth the cost of
    Blender's 482-vertex default."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=16, ring_count=8, radius=radius, location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = f"{name}Mesh"
    bpy.ops.object.shade_smooth()
    return obj


def unwrap(obj) -> None:
    """cube_project, never smart_project: smart_project repacks when geometry
    changes, so any UV-space claim can drift with no exporter change."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.cube_project(cube_size=1.0)
    bpy.ops.object.mode_set(mode='OBJECT')


def material(obj, name: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    obj.data.materials.append(mat)
    tree = mat.node_tree
    return tree, tree.nodes["Principled BSDF"], mat


def texture_node(tree, image, *, interpolation: str = 'Linear',
                 extension: str = 'REPEAT'):
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    node.interpolation = interpolation
    node.extension = extension
    return node


def sun(energy: float = 5.0) -> None:
    bpy.ops.object.light_add(type='SUN', location=(2, -2, 4))
    bpy.context.active_object.data.energy = energy


# --------------------------------------------------------------------------
# scenes
# --------------------------------------------------------------------------

def scene_orientation() -> None:
    """Y-up conversion and meter scale, on a shape that cannot hide a flip."""
    fresh()
    # An L: tall arm on +X, short foot on +Y. Chiral, so a mirrored or rotated
    # result is unmistakable; 1 m tall with its base on the floor.
    body = cube("Upright", location=(0, 0, 0.5), size=1.0)
    body.scale = (0.18, 0.18, 1.0)
    foot = cube("Foot", location=(0.34, 0, 0.09), size=1.0)
    foot.scale = (0.5, 0.16, 0.18)
    nub = cube("SideNub", location=(0, 0.3, 0.85), size=1.0)
    nub.scale = (0.14, 0.4, 0.14)
    for obj, colour in ((body, (0.8, 0.1, 0.1, 1)), (foot, (0.1, 0.7, 0.2, 1)),
                        (nub, (0.1, 0.3, 0.9, 1))):
        _tree, bsdf, _mat = material(obj, f"{obj.name}Surface")
        bsdf.inputs["Base Color"].default_value = colour
    sun()
    save("t01_orientation_scale")


def scene_uv_layout() -> None:
    """UVs reach the export and address the image the way Blender did."""
    fresh()
    obj = cube("UVCube", size=1.0)
    unwrap(obj)
    tree, bsdf, _mat = material(obj, "UVGrid")
    node = texture_node(tree, grid_image("uv_grid", 128))
    tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    sun()
    save("t02_uv_layout")


def scene_vertex_color() -> None:
    """Vertex colour reaches RealityKit through displayColor."""
    fresh()
    obj = cube("PaintedCube", size=1.0)
    mesh = obj.data
    layer = mesh.color_attributes.new(name="Paint", type='FLOAT_COLOR',
                                      domain='CORNER')
    # A per-corner ramp along z, so a flat fill or a dropped read is visible.
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]
            t = vertex.co.z + 0.5
            layer.data[loop_index].color = (t, 0.15, 1.0 - t, 1.0)
    tree, bsdf, _mat = material(obj, "VertexPaint")
    attr = tree.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Paint"
    tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    sun()
    save("t03_vertex_color")


def scene_multi_material() -> None:
    """Two materials on one mesh stay on their own faces."""
    fresh()
    obj = cube("DuoCube", size=1.0)
    tree_a, bsdf_a, _a = material(obj, "SlotRed")
    bsdf_a.inputs["Base Color"].default_value = (0.85, 0.08, 0.08, 1)
    mat_b = bpy.data.materials.new("SlotBlue")
    mat_b.use_nodes = True
    mat_b.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        0.08, 0.20, 0.90, 1
    )
    obj.data.materials.append(mat_b)
    # Alternating faces, so a swap or a collapse to one material is obvious.
    for index, poly in enumerate(obj.data.polygons):
        poly.material_index = index % 2
    sun()
    save("t04_multi_material")


def scene_metal_roughness() -> None:
    """Roughness reaches the surface. Metallic, so it reads as sharp vs blurred."""
    fresh()
    probe = sphere("RoughRamp", location=(-0.7, 0, 0.5))
    unwrap(probe)
    tree, bsdf, _mat = material(probe, "MetalRamp")
    bsdf.inputs["Metallic"].default_value = 1.0
    node = texture_node(tree, ramp_image("rough_ramp", 64))
    tree.links.new(node.outputs["Color"], bsdf.inputs["Roughness"])

    # The control: same metal, one fixed low roughness. Nothing else differs.
    control = sphere("MirrorControl", location=(0.7, 0, 0.5))
    _t, control_bsdf, _m = material(control, "MetalControl")
    control_bsdf.inputs["Metallic"].default_value = 1.0
    control_bsdf.inputs["Roughness"].default_value = 0.05
    sun()
    save("t05_metal_roughness")


def scene_normal_map() -> None:
    """A normal map perturbs shading. Strong ridges, never the identity normal."""
    fresh()
    probe = cube("BumpyPanel", location=(-0.7, 0, 0.5), size=1.0)
    probe.scale = (1.0, 0.08, 1.0)
    unwrap(probe)
    tree, bsdf, _mat = material(probe, "Ridged")
    bsdf.inputs["Roughness"].default_value = 0.25
    node = texture_node(tree, normal_image("ridges", 64))
    node.image.colorspace_settings.name = 'Non-Color'
    normal_map = tree.nodes.new("ShaderNodeNormalMap")
    normal_map.inputs["Strength"].default_value = 1.0
    tree.links.new(node.outputs["Color"], normal_map.inputs["Color"])
    tree.links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

    control = cube("FlatPanel", location=(0.7, 0, 0.5), size=1.0)
    control.scale = (1.0, 0.08, 1.0)
    _t, control_bsdf, _m = material(control, "Smooth")
    control_bsdf.inputs["Roughness"].default_value = 0.25
    sun()
    save("t06_normal_map")


def scene_emission() -> None:
    """Emissive colour reaches the surface, against a non-emissive twin."""
    fresh()
    glow = sphere("Glowing", location=(-0.7, 0, 0.5))
    _t, bsdf, _m = material(glow, "Emissive")
    bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)
    bsdf.inputs["Emission Color"].default_value = (0.1, 1.0, 0.35, 1)
    bsdf.inputs["Emission Strength"].default_value = 3.0

    dark = sphere("Unlit", location=(0.7, 0, 0.5))
    _t2, dark_bsdf, _m2 = material(dark, "NotEmissive")
    dark_bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)
    sun(energy=1.0)
    save("t07_emission")


def scene_opacity() -> None:
    """Opacity reaches the surface, against an opaque twin."""
    fresh()
    glass = sphere("SeeThrough", location=(-0.7, 0, 0.5))
    _t, bsdf, mat = material(glass, "Translucent")
    bsdf.inputs["Base Color"].default_value = (0.9, 0.35, 0.1, 1)
    bsdf.inputs["Alpha"].default_value = 0.35
    bsdf.inputs["Roughness"].default_value = 0.3
    mat.blend_method = 'BLEND'

    solid = sphere("Opaque", location=(0.7, 0, 0.5))
    _t2, solid_bsdf, _m2 = material(solid, "Solid")
    solid_bsdf.inputs["Base Color"].default_value = (0.9, 0.35, 0.1, 1)
    solid_bsdf.inputs["Roughness"].default_value = 0.3
    # A backdrop, so "transparent" means "you can see the bar through it".
    bar = cube("Backdrop", location=(0, 0.6, 0.5), size=1.0)
    bar.scale = (2.0, 0.05, 0.35)
    _t3, bar_bsdf, _m3 = material(bar, "BackdropStripe")
    bar_bsdf.inputs["Base Color"].default_value = (0.05, 0.85, 0.9, 1)
    sun()
    save("t08_opacity")


def scene_wrap_filter() -> None:
    """Extension and interpolation modes reach the image reader.

    16 px, so one texel is roughly 60 mm on this cube: Closest reads as hard
    squares at normal framing. At 256 px the texels are millimetres and the
    difference is invisible without putting your nose on the surface.
    """
    fresh()
    tiny = grid_image("filter_probe", 16)

    repeat_linear = cube("RepeatLinear", location=(-0.7, 0, 0.5), size=1.0)
    unwrap(repeat_linear)
    tree, bsdf, _m = material(repeat_linear, "RepeatLinear")
    node = texture_node(tree, tiny, interpolation='Linear', extension='REPEAT')
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (3.0, 3.0, 1.0)
    texcoord = tree.nodes.new("ShaderNodeTexCoord")
    tree.links.new(texcoord.outputs["UV"], mapping.inputs["Vector"])
    tree.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
    tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])

    clip_closest = cube("ClipClosest", location=(0.7, 0, 0.5), size=1.0)
    unwrap(clip_closest)
    tree2, bsdf2, _m2 = material(clip_closest, "ClipClosest")
    node2 = texture_node(tree2, tiny, interpolation='Closest', extension='CLIP')
    mapping2 = tree2.nodes.new("ShaderNodeMapping")
    mapping2.inputs["Scale"].default_value = (3.0, 3.0, 1.0)
    texcoord2 = tree2.nodes.new("ShaderNodeTexCoord")
    tree2.links.new(texcoord2.outputs["UV"], mapping2.inputs["Vector"])
    tree2.links.new(mapping2.outputs["Vector"], node2.inputs["Vector"])
    tree2.links.new(node2.outputs["Color"], bsdf2.inputs["Base Color"])
    sun()
    save("t09_wrap_filter")


def scene_texture_transform() -> None:
    """A Mapping node's scale and rotation reach the UV transform."""
    fresh()
    obj = cube("MappedCube", size=1.0)
    unwrap(obj)
    tree, bsdf, _m = material(obj, "Mapped")
    node = texture_node(tree, grid_image("transform_grid", 128))
    mapping = tree.nodes.new("ShaderNodeMapping")
    # 3x tiling plus a 30 degree rotation: dropped, inverted and un-rotated
    # results all land somewhere visibly different.
    mapping.inputs["Scale"].default_value = (3.0, 3.0, 1.0)
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(30.0))
    texcoord = tree.nodes.new("ShaderNodeTexCoord")
    tree.links.new(texcoord.outputs["UV"], mapping.inputs["Vector"])
    tree.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
    tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    sun()
    save("t10_texture_transform")


def scene_transform_animation() -> None:
    """Object animation survives as takes."""
    fresh()
    obj = cube("Mover", location=(0, 0, 0.5), size=0.6)
    _t, bsdf, _m = material(obj, "MoverSurface")
    bsdf.inputs["Base Color"].default_value = (0.9, 0.5, 0.1, 1)
    obj.animation_data_create()

    slide = bpy.data.actions.new("SlideRight")
    obj.animation_data.action = slide
    for frame, x in ((1, -1.2), (24, 1.2)):
        obj.location.x = x
        obj.keyframe_insert("location", index=0, frame=frame)

    lift = bpy.data.actions.new("LiftUp")
    obj.animation_data.action = lift
    for frame, z in ((1, 0.5), (24, 1.8)):
        obj.location.z = z
        obj.keyframe_insert("location", index=2, frame=frame)

    obj.animation_data.action = None
    for action in (slide, lift):
        track = obj.animation_data.nla_tracks.new()
        track.name = action.name
        track.strips.new(action.name, 1, action)

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 24
    sun()
    save("t11_transform_animation")


def scene_skinned() -> None:
    """Armature skinning survives, and the bend is unmistakable."""
    fresh()
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.18, depth=2.0,
                                        location=(0, 0, 1.0))
    mesh_obj = bpy.context.active_object
    mesh_obj.name = "Limb"; mesh_obj.data.name = "LimbMesh"
    # Loop cuts so the bend deforms rather than pivoting rigidly.
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.subdivide(number_cuts=6)
    bpy.ops.object.mode_set(mode='OBJECT')
    _t, bsdf, _m = material(mesh_obj, "LimbSurface")
    bsdf.inputs["Base Color"].default_value = (0.8, 0.75, 0.2, 1)

    bpy.ops.object.armature_add(location=(0, 0, 0))
    rig = bpy.context.active_object
    rig.name = "Rig"
    bpy.ops.object.mode_set(mode='EDIT')
    root = rig.data.edit_bones[0]
    root.name = "lower"; root.head = (0, 0, 0); root.tail = (0, 0, 1.0)
    upper = rig.data.edit_bones.new("upper")
    upper.head = (0, 0, 1.0); upper.tail = (0, 0, 2.0); upper.parent = root
    bpy.ops.object.mode_set(mode='OBJECT')

    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')

    rig.animation_data_create()
    action = bpy.data.actions.new("Bend")
    rig.animation_data.action = action
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    bone = rig.pose.bones["upper"]
    bone.rotation_mode = 'XYZ'
    for frame, angle in ((1, 0.0), (24, math.radians(75.0))):
        bone.rotation_euler = (angle, 0, 0)
        bone.keyframe_insert("rotation_euler", frame=frame)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 24
    sun()
    save("t12_skinned_limb")


def scene_shape_keys() -> None:
    """Shape keys reach USD and can be driven in the editor."""
    fresh()
    obj = sphere("KeyedBall", location=(0, 0, 0.6), radius=0.5)
    _t, bsdf, _m = material(obj, "KeyedSurface")
    bsdf.inputs["Base Color"].default_value = (0.2, 0.55, 0.9, 1)
    obj.shape_key_add(name="Basis", from_mix=False)

    squash = obj.shape_key_add(name="Squash", from_mix=False)
    for vertex in squash.data:
        vertex.co.z *= 0.35
    lean = obj.shape_key_add(name="Lean", from_mix=False)
    for vertex in lean.data:
        vertex.co.x += 0.9 * (vertex.co.z + 0.5)
    sun()
    save("t13_shape_keys")


def scene_dropped_lights_cameras() -> None:
    """Lights and cameras vanish with no warning. The mesh proves the export ran."""
    fresh()
    obj = cube("SurvivingCube", location=(0, 0, 0.5), size=1.0)
    _t, bsdf, _m = material(obj, "Survivor")
    bsdf.inputs["Base Color"].default_value = (0.85, 0.75, 0.2, 1)
    bpy.ops.object.light_add(type='POINT', location=(1.5, -1.5, 2.0))
    bpy.context.active_object.name = "ShouldVanish_Point"
    bpy.ops.object.light_add(type='AREA', location=(-1.5, 1.5, 2.0))
    bpy.context.active_object.name = "ShouldVanish_Area"
    bpy.ops.object.camera_add(location=(0, -4, 1.5), rotation=(1.3, 0, 0))
    bpy.context.active_object.name = "ShouldVanish_Camera"
    save("t14_dropped_lights_cameras")


def scene_dropped_curves() -> None:
    """Curve, text and point-cloud objects vanish with no warning."""
    fresh()
    obj = cube("SurvivingCube", location=(0, 0, 0.5), size=0.8)
    _t, bsdf, _m = material(obj, "Survivor")
    bsdf.inputs["Base Color"].default_value = (0.2, 0.8, 0.5, 1)
    # Curve objects drop. Text is NOT in this scene: Blender converts a Text
    # object to a mesh, so it survives the export and would muddy the verdict.
    bpy.ops.curve.primitive_bezier_circle_add(radius=0.9, location=(1.6, 0, 0.5))
    bpy.context.active_object.name = "ShouldVanish_Curve"
    bpy.ops.curve.primitive_nurbs_path_add(location=(-1.6, 0, 0.5))
    bpy.context.active_object.name = "ShouldVanish_Path"
    sun()
    save("t15_dropped_curves")


def scene_dropped_world() -> None:
    """The world material vanishes with no warning."""
    fresh()
    obj = sphere("MirrorBall", location=(0, 0, 0.6), radius=0.5)
    _t, bsdf, _m = material(obj, "Chrome")
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.05
    world = bpy.data.worlds.new("LoudWorld")
    world.use_nodes = True
    background = world.node_tree.nodes["Background"]
    # Saturated magenta at high strength: if the world reached the export, a
    # chrome ball could not possibly look neutral.
    background.inputs["Color"].default_value = (1.0, 0.0, 0.7, 1.0)
    background.inputs["Strength"].default_value = 4.0
    bpy.context.scene.world = world
    save("t16_dropped_world")


def scene_procedural_noise() -> None:
    """Noise exports as a MaterialX procedural - approximated, not refused.

    Checker, Brick and Wave refuse; Noise and Voronoi are translated and
    warned about. The control makes the approximation legible: if the noise
    were dropped, both spheres would have the same uniform finish.
    """
    fresh()
    probe = sphere("NoisyMetal", location=(-0.7, 0, 0.5))
    tree, bsdf, _m = material(probe, "ProceduralRough")
    bsdf.inputs["Metallic"].default_value = 1.0
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.name = "ObjectSpaceNoise"
    noise.inputs["Scale"].default_value = 12.0
    tree.links.new(noise.outputs["Fac"], bsdf.inputs["Roughness"])

    control = sphere("EvenMetal", location=(0.7, 0, 0.5))
    _t, control_bsdf, _cm = material(control, "EvenRough")
    control_bsdf.inputs["Metallic"].default_value = 1.0
    control_bsdf.inputs["Roughness"].default_value = 0.35
    sun()
    save("t17_procedural_noise")


def scene_refused_mix_shader() -> None:
    """A Mix Shader refuses the export and points at the bake."""
    fresh()
    obj = cube("MixedCube", location=(0, 0, 0.5), size=1.0)
    tree, bsdf, mat = material(obj, "Mixed")
    second = tree.nodes.new("ShaderNodeBsdfDiffuse")
    mix = tree.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.5
    output = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL')
    tree.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    tree.links.new(second.outputs["BSDF"], mix.inputs[2])
    tree.links.new(mix.outputs["Shader"], output.inputs["Surface"])
    sun()
    save("t18_refused_mix_shader")


def scene_cm_scale_refusal() -> None:
    """A centimetre scene is refused, not silently exported 100x too large.

    This guard is why an artist working in centimetres does not ship an asset
    the size of a building. The scene is otherwise identical to t01, so the two
    isolate the unit setting.
    """
    fresh()
    bpy.context.scene.unit_settings.scale_length = 0.01
    body = cube("Upright", location=(0, 0, 50.0), size=100.0)
    body.scale = (0.18, 0.18, 1.0)
    _t, bsdf, _m = material(body, "CmSurface")
    bsdf.inputs["Base Color"].default_value = (0.9, 0.4, 0.1, 1)
    sun()
    save("t19_cm_scale_refusal")


def scene_bake_mask_mix() -> None:
    """The bake lane: a graph direct export refuses, but baking resolves.

    A mask-driven Mix between two colours cannot be translated node for node.
    Exported directly it is refused with bake advice; run through
    ``bake-export`` it becomes a baked base-colour texture. The mask is a
    gradient, so a bake that lost the mix is a flat colour rather than a blend.
    """
    fresh(cycles=True, samples=16)
    obj = cube("MaskedCube", location=(0, 0, 0.5), size=1.0)
    unwrap(obj)
    tree, bsdf, _m = material(obj, "MaskedMix")
    mask = texture_node(tree, ramp_image("bake_mask", 64, data=False))
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = 'RGBA'
    mix.inputs["A"].default_value = (0.95, 0.15, 0.05, 1.0)
    mix.inputs["B"].default_value = (0.05, 0.35, 0.95, 1.0)
    tree.links.new(mask.outputs["Color"], mix.inputs["Factor"])
    tree.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    sun()
    save("t20_bake_mask_mix")


def scene_specular_tint_refusal() -> None:
    """An active Specular Tint is refused by the Portable profile.

    This replaces a 16 MB rigged character whose only job was to trip this
    refusal. The exporter clamps an overbright *achromatic* tint only when
    Normalize Unsupported Values is on; a coloured tint is refused outright,
    which is the case worth pinning.
    """
    fresh()
    obj = sphere("TintedBall", location=(0, 0, 0.6))
    _t, bsdf, _m = material(obj, "TintedSurface")
    bsdf.inputs["Base Color"].default_value = (0.7, 0.7, 0.75, 1)
    # Coloured and overbright: refused regardless of the normalization setting.
    bsdf.inputs["Specular Tint"].default_value = (1.8, 0.4, 0.4, 1.0)
    sun()
    save("t21_specular_tint_refusal")


SCENES = (
    scene_orientation,
    scene_uv_layout,
    scene_vertex_color,
    scene_multi_material,
    scene_metal_roughness,
    scene_normal_map,
    scene_emission,
    scene_opacity,
    scene_wrap_filter,
    scene_texture_transform,
    scene_transform_animation,
    scene_skinned,
    scene_shape_keys,
    scene_dropped_lights_cameras,
    scene_dropped_curves,
    scene_dropped_world,
    scene_procedural_noise,
    scene_refused_mix_shader,
    scene_cm_scale_refusal,
    scene_bake_mask_mix,
    scene_specular_tint_refusal,
)


def main() -> None:
    for builder in SCENES:
        builder()
    print(f"DONE {len(SCENES)} scenes -> {OUT}")


if __name__ == "__main__":
    main()
