"""Build-pinned Reality Composer Pro 3 ``.import`` generator.

This module implements only contracts measured against Reality Composer Pro
3.0 build 80.0.1.500.1. It intentionally omits RCP's volatile optimizer and
session caches; live acceptance showed those caches are optional. Unknown USD
features fail closed instead of being silently flattened.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import struct
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

RCP_VERSION = "3.0"
RCP_BUILD = "80.0.1.500.1"
_NAMESPACE = uuid.UUID("71eed068-2b17-5a2f-98ee-139ccbc938da")
_MURMUR_MULTIPLIER = 0xC6A4A7935BD1E995
_MURMUR_SHIFT = 47
_U64_MASK = (1 << 64) - 1
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")
_BOOTSTRAP_GEOMETRY_VALIDITY_HASH = "2cfcf0b4ccf2dcd8"


class ImportGenerationError(RuntimeError):
    """Raised when a source is outside the measured build-80 contract."""


@dataclass(frozen=True)
class StaticMesh:
    asset_name: str
    root_name: str
    mesh_name: str
    material_name: str
    points: tuple[tuple[float, float, float], ...]
    face_counts: tuple[int, ...]
    face_indices: tuple[int, ...]
    face_uvs: tuple[tuple[float, float], ...]
    face_normals: tuple[tuple[float, float, float], ...]
    base_color: tuple[float, float, float]
    metallic: float
    roughness: float
    opacity: float
    root_translation: tuple[float, float, float]
    root_rotation: tuple[float, float, float, float]
    root_scale: tuple[float, float, float]
    mesh_translation: tuple[float, float, float]
    mesh_rotation: tuple[float, float, float, float]
    mesh_scale: tuple[float, float, float]


@dataclass(frozen=True)
class TransformClip:
    name: str
    start: float
    end: float


@dataclass(frozen=True)
class TransformAnimation:
    name: str
    node_name: str
    frames_per_second: float
    frames: tuple[float, ...]
    positions: tuple[tuple[float, float, float], ...]
    clips: tuple[TransformClip, ...]

    @property
    def duration(self) -> float:
        return (self.frames[-1] - self.frames[0]) / self.frames_per_second


class _Ids:
    def __init__(self, identity: str):
        self.identity = identity

    def __call__(self, label: str) -> str:
        return str(uuid.uuid5(_NAMESPACE, f"{self.identity}|{label}"))


def _murmur_hash64a(data: bytes) -> int:
    value = (len(data) * _MURMUR_MULTIPLIER) & _U64_MASK
    whole_words = len(data) // 8
    for index in range(whole_words):
        offset = index * 8
        word = int.from_bytes(data[offset : offset + 8], "little")
        word = (word * _MURMUR_MULTIPLIER) & _U64_MASK
        word ^= word >> _MURMUR_SHIFT
        word = (word * _MURMUR_MULTIPLIER) & _U64_MASK
        value ^= word
        value = (value * _MURMUR_MULTIPLIER) & _U64_MASK
    tail = data[whole_words * 8 :]
    for index, byte in enumerate(tail):
        value ^= byte << (index * 8)
    if tail:
        value = (value * _MURMUR_MULTIPLIER) & _U64_MASK
    value ^= value >> _MURMUR_SHIFT
    value = (value * _MURMUR_MULTIPLIER) & _U64_MASK
    value ^= value >> _MURMUR_SHIFT
    return value


def _content_hash(data: bytes) -> str:
    return f"{_murmur_hash64a(data):016x}"


def _safe_name(value: str, fallback: str) -> str:
    normalized = _SAFE_NAME.sub("_", value.strip()).strip("._")
    return normalized or fallback


def _f(value: float) -> str:
    value = float(value)
    if not math.isfinite(value):
        raise ImportGenerationError("non-finite numeric value")
    if value == 0:
        return "0"
    if value.is_integer():
        return str(int(value))
    return repr(float(value))


def _vector_fields(
    values: Sequence[float], names: Sequence[str], *, indent: str
) -> str:
    return "".join(
        f"{indent}{name}: {_f(float(value))}\n"
        for name, value in zip(names, values)
        if float(value) != 0
    )


def _transform_component(ids: _Ids, label: str, mesh: StaticMesh, root: bool) -> str:
    translation = mesh.root_translation if root else mesh.mesh_translation
    rotation = mesh.root_rotation if root else mesh.mesh_rotation
    scale = mesh.root_scale if root else mesh.mesh_scale
    rotation_text = _vector_fields(
        rotation[:3], ("x", "y", "z"), indent="\t\t\t\t\t"
    )
    if rotation[3] != 1.0:
        rotation_text += f"\t\t\t\t\tw: {_f(rotation[3])}\n"
    scale_text = "".join(
        f"\t\t\t\t\t\t{axis}: {_f(value)}\n"
        for axis, value in zip(("x", "y", "z"), scale)
        if value != 1.0
    )
    return (
        "{\n"
        '\t\t\t\t__type: "tm_transform_component"\n'
        f'\t\t\t\t__uuid: "{ids(label + ".component")}"\n'
        "\t\t\t\tlocal_position_double: {\n"
        f'\t\t\t\t\t__uuid: "{ids(label + ".position")}"\n'
        + _vector_fields(translation, ("x", "y", "z"), indent="\t\t\t\t\t")
        + "\t\t\t\t}\n"
        "\t\t\t\tlocal_rotation: {\n"
        f'\t\t\t\t\t__uuid: "{ids(label + ".rotation")}"\n'
        + rotation_text
        + "\t\t\t\t}\n"
        "\t\t\t\tlocal_scale: {\n"
        f'\t\t\t\t\t__uuid: "{ids(label + ".scale")}"\n'
        + scale_text
        + "\t\t\t\t}\n"
        "\t\t\t}"
    )


def _directory_record(ids: _Ids, label: str, name: str, parent: str | None) -> str:
    parent_line = f'\nparent: "{parent}"' if parent else ""
    return (
        '__type: "tm_asset_directory"\n'
        f'__uuid: "{ids(label)}"\n'
        f'name: "{name}"'
        f"{parent_line}"
    )


def _pack_floats(values: Iterable[float]) -> bytes:
    flattened = tuple(float(value) for value in values)
    return struct.pack(f"<{len(flattened)}f", *flattened)


def _pack_i32(values: Sequence[int]) -> bytes:
    return struct.pack(f"<{len(values)}i", *values)


def _write_buffer(directory: Path, buffer_id: str, data: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{buffer_id}.{_content_hash(data)}").write_bytes(data)


def _triangulated_corner_indices(face_counts: Sequence[int]) -> tuple[int, ...]:
    result: list[int] = []
    corner = 0
    for count in face_counts:
        if count < 3:
            raise ImportGenerationError("faces must have at least three vertices")
        for index in range(1, count - 1):
            result.extend((corner, corner + index, corner + index + 1))
        corner += count
    if corner > 65535:
        raise ImportGenerationError(
            "build-80 minimal generator supports at most 65,535 face corners"
        )
    return tuple(result)


def _write_mesh_buffers(destination: Path, mesh: StaticMesh, ids: _Ids) -> dict[str, str]:
    buffer_ids = {
        key: ids(f"buffer.{key}")
        for key in ("face_counts", "face_indices", "points", "uvs", "normals", "geometry", "triangles")
    }
    descriptor_dir = destination / "mesh_descriptors" / f"{mesh.mesh_name}.tm_buffers"
    _write_buffer(descriptor_dir, buffer_ids["face_counts"], _pack_i32(mesh.face_counts))
    _write_buffer(descriptor_dir, buffer_ids["face_indices"], _pack_i32(mesh.face_indices))
    _write_buffer(
        descriptor_dir,
        buffer_ids["points"],
        _pack_floats(value for point in mesh.points for value in point),
    )
    _write_buffer(
        descriptor_dir,
        buffer_ids["uvs"],
        _pack_floats(value for uv in mesh.face_uvs for value in uv),
    )
    _write_buffer(
        descriptor_dir,
        buffer_ids["normals"],
        _pack_floats(value for normal in mesh.face_normals for value in normal),
    )

    expanded_points = tuple(mesh.points[index] for index in mesh.face_indices)
    geometry = (
        _pack_floats(value for point in expanded_points for value in point)
        + _pack_floats(value for uv in mesh.face_uvs for value in uv)
        + _pack_floats(value for normal in mesh.face_normals for value in normal)
    )
    triangles = _triangulated_corner_indices(mesh.face_counts)
    triangle_data = struct.pack(f"<{len(triangles)}H", *triangles)
    geometry_dir = destination / "geometry" / f"{mesh.mesh_name}.tm_buffers"
    _write_buffer(geometry_dir, buffer_ids["geometry"], geometry)
    _write_buffer(geometry_dir, buffer_ids["triangles"], triangle_data)
    return buffer_ids


def _write_transform_animation_buffers(
    destination: Path,
    animation: TransformAnimation,
    ids: _Ids,
) -> dict[str, str]:
    buffer_ids = {
        "positions": ids("animation.positions_buffer"),
        "times": ids("animation.times_buffer"),
    }
    settings_buffers = destination / "settings.tm_buffers"
    _write_buffer(
        settings_buffers,
        buffer_ids["positions"],
        _pack_floats(
            component
            for position in animation.positions
            for component in position
        ),
    )
    _write_buffer(
        settings_buffers,
        buffer_ids["times"],
        _pack_floats(animation.frames),
    )
    return buffer_ids


def _local_transform(prim) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float],
]:
    from pxr import Gf, Usd, UsdGeom

    xform = UsdGeom.Xformable(prim)
    matrix = xform.GetLocalTransformation(Usd.TimeCode.Default())
    transform = Gf.Transform(matrix)
    translation = tuple(float(value) for value in transform.GetTranslation())
    quaternion = transform.GetRotation().GetQuat()
    imaginary = quaternion.GetImaginary()
    rotation = (
        float(imaginary[0]),
        float(imaginary[1]),
        float(imaginary[2]),
        float(quaternion.GetReal()),
    )
    scale = tuple(float(value) for value in transform.GetScale())
    return translation, rotation, scale


def _face_varying_values(
    values: Sequence[Sequence[float]],
    interpolation: str,
    face_counts: Sequence[int],
    face_indices: Sequence[int],
) -> tuple[tuple[float, ...], ...]:
    corner_count = len(face_indices)
    if interpolation == "faceVarying":
        if len(values) != corner_count:
            raise ImportGenerationError("face-varying attribute count mismatch")
        return tuple(tuple(float(component) for component in value) for value in values)
    if interpolation in {"vertex", "varying"}:
        return tuple(
            tuple(float(component) for component in values[index])
            for index in face_indices
        )
    if interpolation == "uniform":
        result = []
        for face_index, count in enumerate(face_counts):
            result.extend([tuple(float(c) for c in values[face_index])] * count)
        return tuple(result)
    if interpolation == "constant":
        value = tuple(float(component) for component in values[0])
        return tuple(value for _ in range(corner_count))
    raise ImportGenerationError(f"unsupported interpolation {interpolation!r}")


def _computed_face_normals(
    points: Sequence[Sequence[float]],
    face_counts: Sequence[int],
    face_indices: Sequence[int],
) -> tuple[tuple[float, float, float], ...]:
    result: list[tuple[float, float, float]] = []
    offset = 0
    for count in face_counts:
        indices = face_indices[offset : offset + count]
        a, b, c = (points[index] for index in indices[:3])
        ab = tuple(b[i] - a[i] for i in range(3))
        ac = tuple(c[i] - a[i] for i in range(3))
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        length = math.sqrt(sum(value * value for value in cross))
        if length == 0:
            raise ImportGenerationError("degenerate face cannot produce a normal")
        normal = tuple(value / length for value in cross)
        result.extend([normal] * count)
        offset += count
    return tuple(result)


def load_static_mesh(source: str | Path, *, asset_name: str | None = None) -> StaticMesh:
    """Load the fail-closed static subset from one USD stage."""

    try:
        from pxr import Usd, UsdGeom, UsdShade, UsdSkel
    except ImportError as error:  # pragma: no cover - Blender/macOS provides USD
        raise ImportGenerationError("Pixar USD Python bindings are required") from error

    source_path = Path(source).resolve()
    stage = Usd.Stage.Open(str(source_path))
    if stage is None:
        raise ImportGenerationError(f"cannot open USD stage: {source_path}")
    mesh_prims = [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]
    if len(mesh_prims) != 1:
        raise ImportGenerationError(
            f"build-80 static subset requires exactly one mesh, found {len(mesh_prims)}"
        )
    mesh_prim = mesh_prims[0]
    if mesh_prim.HasAPI(UsdSkel.BindingAPI):
        raise ImportGenerationError("skinned meshes require the skeletal generator")
    mesh_schema = UsdGeom.Mesh(mesh_prim)
    points = tuple(tuple(float(c) for c in value) for value in mesh_schema.GetPointsAttr().Get())
    face_counts = tuple(int(value) for value in mesh_schema.GetFaceVertexCountsAttr().Get())
    face_indices = tuple(int(value) for value in mesh_schema.GetFaceVertexIndicesAttr().Get())
    if not points or sum(face_counts) != len(face_indices):
        raise ImportGenerationError("invalid or empty mesh topology")

    normals_raw = mesh_schema.GetNormalsAttr().Get() or ()
    if normals_raw:
        normals = _face_varying_values(
            normals_raw,
            str(mesh_schema.GetNormalsInterpolation()),
            face_counts,
            face_indices,
        )
    else:
        normals = _computed_face_normals(points, face_counts, face_indices)

    st = UsdGeom.PrimvarsAPI(mesh_prim).GetPrimvar("st")
    if st and st.HasValue():
        uv_raw = st.ComputeFlattened() or ()
        uvs = _face_varying_values(
            uv_raw, str(st.GetInterpolation()), face_counts, face_indices
        )
    else:
        uvs = tuple((0.0, 0.0) for _ in face_indices)

    material = UsdShade.MaterialBindingAPI(mesh_prim).ComputeBoundMaterial()[0]
    material_name = _safe_name(material.GetPrim().GetName(), "Material") if material else "Material"
    base_color = (0.8, 0.8, 0.8)
    metallic, roughness, opacity = 0.0, 0.5, 1.0
    if material:
        surface = material.ComputeSurfaceSource("mtlx")[0] or material.ComputeSurfaceSource()[0]
        if surface:
            shader = UsdShade.Shader(surface)
            for input_name, fallback in (
                ("baseColor", base_color),
                ("diffuseColor", base_color),
            ):
                shader_input = shader.GetInput(input_name)
                if shader_input:
                    value = shader_input.Get()
                    if value is not None:
                        base_color = tuple(float(component) for component in value[:3])
                        break
            for input_name, fallback in (
                ("metallic", metallic),
                ("roughness", roughness),
                ("opacity", opacity),
            ):
                shader_input = shader.GetInput(input_name)
                value = shader_input.Get() if shader_input else None
                if value is not None:
                    if input_name == "metallic":
                        metallic = float(value)
                    elif input_name == "roughness":
                        roughness = float(value)
                    else:
                        opacity = float(value)

    root_prim = stage.GetDefaultPrim()
    parent = mesh_prim.GetParent()
    if not root_prim:
        raise ImportGenerationError("USD stage requires a defaultPrim")
    if parent == root_prim:
        model_prim = mesh_prim
    elif (
        parent.GetParent() == root_prim
        and parent.IsA(UsdGeom.Xform)
        and len(tuple(parent.GetChildren())) == 1
    ):
        # Blender 5.2 writes an object Xform containing its Mesh data. RCP's
        # entity graph collapses that pair to one model entity.
        model_prim = parent
    else:
        raise ImportGenerationError(
            "build-80 subset requires a mesh directly below defaultPrim or "
            "inside one single-mesh object Xform"
        )
    root_translation, root_rotation, root_scale = _local_transform(root_prim)
    mesh_translation, mesh_rotation, mesh_scale = _local_transform(model_prim)
    return StaticMesh(
        asset_name=_safe_name(asset_name or source_path.stem, "Asset"),
        root_name=_safe_name(root_prim.GetName(), "root"),
        mesh_name=_safe_name(model_prim.GetName(), "Mesh"),
        material_name=material_name,
        points=points,
        face_counts=face_counts,
        face_indices=face_indices,
        face_uvs=tuple(tuple(value) for value in uvs),
        face_normals=tuple(tuple(value) for value in normals),
        base_color=base_color,
        metallic=metallic,
        roughness=roughness,
        opacity=opacity,
        root_translation=root_translation,
        root_rotation=root_rotation,
        root_scale=root_scale,
        mesh_translation=mesh_translation,
        mesh_rotation=mesh_rotation,
        mesh_scale=mesh_scale,
    )


def load_transform_animation(
    source: str | Path,
    mesh: StaticMesh,
) -> TransformAnimation | None:
    """Load the measured build-80 translation-sampled animation subset."""

    from pxr import Usd, UsdGeom

    source_path = Path(source).resolve()
    stage = Usd.Stage.Open(str(source_path))
    if stage is None:
        raise ImportGenerationError(f"cannot open USD stage: {source_path}")
    mesh_prim = stage.GetDefaultPrim().GetChild(mesh.mesh_name)
    if not mesh_prim or not (
        mesh_prim.IsA(UsdGeom.Mesh) or mesh_prim.IsA(UsdGeom.Xform)
    ):
        raise ImportGenerationError("animated mesh path no longer matches static mesh")

    animated_ops = []
    for op in UsdGeom.Xformable(mesh_prim).GetOrderedXformOps():
        samples = tuple(float(value) for value in op.GetTimeSamples())
        if len(samples) > 1:
            animated_ops.append((str(op.GetOpName()), op, samples))
    if not animated_ops:
        return None
    unsupported = [name for name, _, _ in animated_ops if name != "xformOp:translate"]
    if unsupported:
        raise ImportGenerationError(
            "build-80 transform subset supports sampled translation only; "
            f"found {unsupported}"
        )
    if len(animated_ops) != 1:
        raise ImportGenerationError("multiple sampled translation ops are unsupported")

    start_frame = float(stage.GetStartTimeCode())
    end_frame = float(stage.GetEndTimeCode())
    if not start_frame.is_integer() or not end_frame.is_integer():
        raise ImportGenerationError("fractional stage frame boundaries are unsupported")
    if end_frame <= start_frame:
        raise ImportGenerationError("animated stage requires a positive frame range")
    frames_per_second = float(stage.GetTimeCodesPerSecond())
    if not math.isfinite(frames_per_second) or frames_per_second <= 0:
        raise ImportGenerationError("animated stage requires a positive frame rate")
    frames = tuple(
        float(frame)
        for frame in range(int(start_frame), int(end_frame) + 1)
    )
    translate_op = animated_ops[0][1]
    positions = tuple(
        tuple(float(component) for component in translate_op.Get(Usd.TimeCode(frame)))
        for frame in frames
    )
    duration = (end_frame - start_frame) / frames_per_second

    clip_contracts: set[tuple[tuple[str, ...], tuple[float, ...]]] = set()
    for prim in stage.Traverse():
        if prim.GetTypeName() != "RealityKitClipDefinition":
            continue
        names_attr = prim.GetAttribute("clipNames")
        starts_attr = prim.GetAttribute("startTimes")
        names = tuple(str(value) for value in (names_attr.Get() or ()))
        starts = tuple(float(value) for value in (starts_attr.Get() or ()))
        if not names and not starts:
            continue
        if len(names) != len(starts):
            raise ImportGenerationError("AnimationLibrary clip names/times mismatch")
        clip_contracts.add((names, starts))
    if len(clip_contracts) > 1:
        raise ImportGenerationError(
            "conflicting AnimationLibrary clip definitions are unsupported"
        )
    if clip_contracts:
        names, starts = next(iter(clip_contracts))
    else:
        names = (f"{mesh.asset_name}_transform",)
        starts = (0.0,)
    if not names:
        raise ImportGenerationError("animation clip list is empty")
    if any(not math.isfinite(value) for value in starts):
        raise ImportGenerationError("animation clip times must be finite")
    if tuple(sorted(starts)) != starts or len(set(starts)) != len(starts):
        raise ImportGenerationError("animation clip start times must be unique and sorted")
    if starts[0] < 0 or starts[-1] >= duration:
        raise ImportGenerationError("animation clip times fall outside stage duration")
    safe_names = tuple(_safe_name(name, "Clip") for name in names)
    if len(set(safe_names)) != len(safe_names):
        raise ImportGenerationError("animation clip names collide after normalization")
    clips = tuple(
        TransformClip(
            name=name,
            start=starts[index],
            end=starts[index + 1] if index + 1 < len(starts) else duration,
        )
        for index, name in enumerate(safe_names)
    )
    return TransformAnimation(
        name=f"{mesh.asset_name}_transform",
        node_name=str(mesh_prim.GetPath()).lstrip("/"),
        frames_per_second=frames_per_second,
        frames=frames,
        positions=positions,
        clips=clips,
    )


def _mesh_descriptor_record(mesh: StaticMesh, ids: _Ids, buffers: dict[str, str]) -> str:
    corner_count = len(mesh.face_indices)
    return f'''__type: "tm_mesh_descriptor"
__uuid: "{ids("mesh_descriptor")}"
vertex_count: {len(mesh.points)}
face_vertex_counts: {{
\t__uuid: "{ids("mesh_descriptor.face_counts")}"
\tdata: "{buffers["face_counts"]}"
\tformat: 83886112
\tvalue_count: {len(mesh.face_counts)}
}}
indices: {{
\t__uuid: "{ids("mesh_descriptor.indices")}"
\tdata: "{buffers["face_indices"]}"
\tformat: 83886112
\tvalue_count: {corner_count}
}}
attributes: [
\t{{
\t\t__uuid: "{ids("mesh_descriptor.points_attribute")}"
\t\tname: "points"
\t\tinterpolation: 2
\t\tsemantic: 1
\t\tvalues: {{
\t\t\t__uuid: "{ids("mesh_descriptor.points_values")}"
\t\t\tdata: "{buffers["points"]}"
\t\t\tformat: 16910368
\t\t\tvalue_count: {len(mesh.points)}
\t\t}}
\t}}
\t{{
\t\t__uuid: "{ids("mesh_descriptor.uv_attribute")}"
\t\tname: "primvars:st"
\t\tinterpolation: 3
\t\tsemantic: 5
\t\tvalues: {{
\t\t\t__uuid: "{ids("mesh_descriptor.uv_values")}"
\t\t\tdata: "{buffers["uvs"]}"
\t\t\tformat: 16779296
\t\t\tvalue_count: {corner_count}
\t\t}}
\t}}
\t{{
\t\t__uuid: "{ids("mesh_descriptor.normal_attribute")}"
\t\tname: "normals"
\t\tinterpolation: 3
\t\tsemantic: 2
\t\tvalues: {{
\t\t\t__uuid: "{ids("mesh_descriptor.normal_values")}"
\t\t\tdata: "{buffers["normals"]}"
\t\t\tformat: 16910368
\t\t\tvalue_count: {corner_count}
\t\t}}
\t}}
]
__asset_uuid: "{ids("mesh_descriptor.asset")}"'''


def _geometry_block(
    mesh: StaticMesh,
    ids: _Ids,
    buffers: dict[str, str],
    *,
    label: str,
    physical_buffers: bool,
) -> str:
    corner_count = len(mesh.face_indices)
    triangle_count = len(_triangulated_corner_indices(mesh.face_counts))
    vertex_buffer = ids(f"{label}.vertex_buffer")
    index_buffer = ids(f"{label}.index_buffer")
    tangent_buffer = ids(f"{label}.tangent_buffer")
    bitangent_buffer = ids(f"{label}.bitangent_buffer")
    buffer_lines = (
        f'\n\t\t\tbuffer: "{buffers["geometry"]}"' if physical_buffers else ""
    )
    index_lines = (
        f'\n\t\t\tbuffer: "{buffers["triangles"]}"' if physical_buffers else ""
    )
    extra_buffers = ""
    extra_channels = ""
    if not physical_buffers:
        extra_buffers = f'''
\t\t{{
\t\t\t__uuid: "{tangent_buffer}"
\t\t\tindex: 2
\t\t}}
\t\t{{
\t\t\t__uuid: "{bitangent_buffer}"
\t\t\tindex: 3
\t\t}}'''
        extra_channels = f'''
\t\t{{
\t\t\t__uuid: "{ids(f"{label}.tangent_channel")}"
\t\t\tsemantic: 3
\t\t\tcount: {corner_count}
\t\t\tbuffer: "{tangent_buffer}"
\t\t\tstride: 16
\t\t\tformat: 25298976
\t\t}}
\t\t{{
\t\t\t__uuid: "{ids(f"{label}.bitangent_channel")}"
\t\t\tsemantic: 4
\t\t\tcount: {corner_count}
\t\t\tbuffer: "{bitangent_buffer}"
\t\t\tstride: 12
\t\t\tformat: 16910368
\t\t}}'''
    return f'''{{
\t__uuid: "{ids(label)}"
\tbuffers: [
\t\t{{
\t\t\t__uuid: "{vertex_buffer}"{buffer_lines}
\t\t}}
\t\t{{
\t\t\t__uuid: "{index_buffer}"
\t\t\tindex: 1{index_lines}
\t\t}}{extra_buffers}
\t]
\tchannels: [
\t\t{{
\t\t\t__uuid: "{ids(f"{label}.points_channel")}"
\t\t\tsemantic: 1
\t\t\tcount: {corner_count}
\t\t\tbuffer: "{vertex_buffer}"
\t\t\tstride: 12
\t\t\tformat: 16910368
\t\t\tprimvar_name: "points"
\t\t}}
\t\t{{
\t\t\t__uuid: "{ids(f"{label}.uv_channel")}"
\t\t\tsemantic: 5
\t\t\tcount: {corner_count}
\t\t\tbuffer: "{vertex_buffer}"
\t\t\toffset: {corner_count * 12}
\t\t\tstride: 8
\t\t\tformat: 16779296
\t\t\tprimvar_name: "st"
\t\t}}
\t\t{{
\t\t\t__uuid: "{ids(f"{label}.normal_channel")}"
\t\t\tsemantic: 2
\t\t\tcount: {corner_count}
\t\t\tbuffer: "{vertex_buffer}"
\t\t\toffset: {corner_count * 20}
\t\t\tstride: 12
\t\t\tformat: 16910368
\t\t\tprimvar_name: "normals"
\t\t}}{extra_channels}
\t]
\tindices: {{
\t\t__uuid: "{ids(f"{label}.indices")}"
\t\tsemantic: 9
\t\tcount: {triangle_count}
\t\tbuffer: "{index_buffer}"
\t\tstride: 2
\t\tformat: 67108880
\t}}
}}'''


def _geometry_transform_settings(mesh: StaticMesh, ids: _Ids) -> str:
    inputs = (
        ("weld", "Weld Vertices", "weld_vertices", "tm_bool", True, None),
        ("normals", "Generate Normals", "generate_normals", "tm_bool", True, 1),
        ("tangents", "Generate Tangents", "generate_tangents", "tm_bool", True, 2.1),
        ("replace_normals", "Replace Existing Normals", "replace_existing_normals", "tm_bool", False, 2),
        ("cache", "Optimize Vertex Cache", "optimize_vertex_cache", "tm_bool", True, 2.1),
    )
    entries = []
    for label, name, input_id, value_type, enabled, order in inputs:
        bool_line = "\n\t\t\t\t\t\t\t\tbool: true" if enabled else ""
        order_line = f"\n\t\t\t\t\t\torder: {_f(float(order))}" if order is not None else ""
        entries.append(
            f'''{{
\t\t\t\t\t\t__uuid: "{ids(f"transform.input.{label}")}"
\t\t\t\t\t\tname: "{name}"
\t\t\t\t\t\tid: "{input_id}"
\t\t\t\t\t\tvalue: {{
\t\t\t\t\t\t\t__type: "{value_type}"
\t\t\t\t\t\t\t__uuid: "{ids(f"transform.input.{label}.value")}"{bool_line}
\t\t\t\t\t\t}}
\t\t\t\t\t\tpublic: true{order_line}
\t\t\t\t\t}}'''
        )
    channel_entries = "\n".join(
        f'''\t\t\t\t\t\t\t{{
\t\t\t\t\t\t\t\t__uuid: "{ids(f"transform.primvar.{name}")}"
\t\t\t\t\t\t\t\tchannel: "{ids(f"input_geometry.{name}_channel")}"
\t\t\t\t\t\t\t}}'''
        for name in ("points", "uv", "normal")
    )
    entries.insert(
        3,
        f'''{{
\t\t\t\t\t\t__uuid: "{ids("transform.input.lightmap")}"
\t\t\t\t\t\tname: "Lightmap Settings"
\t\t\t\t\t\tid: "lightmap_settings"
\t\t\t\t\t\tvalue: {{
\t\t\t\t\t\t\t__type: "tm_lightmap_geometry_settings"
\t\t\t\t\t\t\t__uuid: "{ids("transform.input.lightmap.value")}"
\t\t\t\t\t\t\tsource_uvs: 1
\t\t\t\t\t\t\tresolution_scale: 1
\t\t\t\t\t\t}}
\t\t\t\t\t\tpublic: true
\t\t\t\t\t\torder: 3
\t\t\t\t\t}}''',
    )
    entries.extend(
        [
            f'''{{
\t\t\t\t\t\t__uuid: "{ids("transform.input.filter")}"
\t\t\t\t\t\tname: "Primvar Filter"
\t\t\t\t\t\tid: "primvar_filters"
\t\t\t\t\t\tvalue: {{
\t\t\t\t\t\t\t__type: "tm_primvar_filter_set"
\t\t\t\t\t\t\t__uuid: "{ids("transform.input.filter.value")}"
\t\t\t\t\t\t}}
\t\t\t\t\t\tpublic: true
\t\t\t\t\t\torder: 5
\t\t\t\t\t}}''',
            f'''{{
\t\t\t\t\t\t__uuid: "{ids("transform.input.primvars")}"
\t\t\t\t\t\tname: "Primvars"
\t\t\t\t\t\tid: "primvar_settings"
\t\t\t\t\t\tvalue: {{
\t\t\t\t\t\t\t__type: "tm_primvar_settings_set"
\t\t\t\t\t\t\t__uuid: "{ids("transform.input.primvars.value")}"
\t\t\t\t\t\t\tset: [
{channel_entries}
\t\t\t\t\t\t\t]
\t\t\t\t\t\t}}
\t\t\t\t\t\tpublic: true
\t\t\t\t\t\torder: 6
\t\t\t\t\t}}''',
            f'''{{
\t\t\t\t\t\t__uuid: "{ids("transform.input.retain")}"
\t\t\t\t\t\tname: "Retain Original Mesh"
\t\t\t\t\t\tid: "retain_original_mesh"
\t\t\t\t\t\tvalue: {{
\t\t\t\t\t\t\t__type: "tm_mesh_descriptor_reference"
\t\t\t\t\t\t\t__uuid: "{ids("transform.input.retain.value")}"
\t\t\t\t\t\t\tmesh_descriptor: "{ids("mesh_descriptor")}"
\t\t\t\t\t\t}}
\t\t\t\t\t}}''',
        ]
    )
    entries_text = "\n\t\t\t\t\t".join(entries)
    return f'''{{
\t__uuid: "{ids("transform.settings")}"
\tgraph: {{
\t\t__uuid: "{ids("transform.graph")}"
\t\tinterface: {{
\t\t\t__uuid: "{ids("transform.interface")}"
\t\t\tinputs: [
\t\t\t\t\t{entries_text}
\t\t\t]
\t\t}}
\t}}
}}'''


def _geometry_record(
    mesh: StaticMesh,
    ids: _Ids,
    buffers: dict[str, str],
) -> str:
    input_geometry = _geometry_block(
        mesh, ids, buffers, label="input_geometry", physical_buffers=True
    )
    output_geometry = _geometry_block(
        mesh, ids, buffers, label="output_geometry", physical_buffers=False
    )
    return f'''__type: "tm_geometry"
__uuid: "{ids("geometry")}"
name: "{mesh.mesh_name}"
input_geometry: {input_geometry}
transform: "3865a2eea51b6038"
transform_settings: {_geometry_transform_settings(mesh, ids)}
output_geometry: {output_geometry}
validity_hash: "{_BOOTSTRAP_GEOMETRY_VALIDITY_HASH}"
__asset_uuid: "{ids("geometry.asset")}"'''


def _mesh_resource_record(mesh: StaticMesh, ids: _Ids) -> str:
    minima = tuple(min(point[index] for point in mesh.points) for index in range(3))
    maxima = tuple(max(point[index] for point in mesh.points) for index in range(3))
    minimum_fields = _vector_fields(minima, ("x", "y", "z"), indent="\t\t\t")
    maximum_fields = _vector_fields(maxima, ("x", "y", "z"), indent="\t\t\t")
    return f'''__type: "tm_mesh_resource"
__uuid: "{ids("mesh_resource")}"
models: [
\t{{
\t\t__uuid: "{ids("mesh_resource.model")}"
\t\tname: "{mesh.mesh_name}"
\t\tgeometry: "{ids("geometry")}"
\t\tbounds_min: {{
\t\t\t__uuid: "{ids("mesh_resource.bounds_min")}"
{minimum_fields}\t\t}}
\t\tbounds_max: {{
\t\t\t__uuid: "{ids("mesh_resource.bounds_max")}"
{maximum_fields}\t\t}}
\t}}
]
__asset_uuid: "{ids("mesh_resource.asset")}"'''


def _material_record(mesh: StaticMesh, ids: _Ids) -> str:
    color = mesh.base_color
    data_entries = (
        ("pbr", "base_color", "b25bebfe670e1bb3", "tm_color_aces2065_rgb", color),
        ("pbr", "metallic", "7da4d360d4218a66", "tm_float", mesh.metallic),
        ("pbr", "opacity", "2bbe599c6c8fe881", "tm_float", mesh.opacity),
        ("pbr", "opacity_threshold", "f949ab44d6ee04e9", "tm_float", 0.0),
        ("pbr", "roughness", "ea2298b545b7e617", "tm_float", mesh.roughness),
        ("pbr", "specular", "b043861ba01513f5", "tm_float", 0.5),
        ("preview", "clearcoat", "f7f9e94981b63d28", "tm_float", 0.0),
        ("preview", "clearcoat_roughness", "eaa02bddffa7ad4d", "tm_float", 0.03),
        ("preview", "diffuse", "cb836048226639e6", "tm_color_aces2065_rgb", color),
        ("preview", "ior", "19494c8dda094901", "tm_float", 1.5),
        ("preview", "metallic", "7da4d360d4218a66", "tm_float", mesh.metallic),
        ("preview", "opacity", "2bbe599c6c8fe881", "tm_float", mesh.opacity),
        ("preview", "roughness", "ea2298b545b7e617", "tm_float", mesh.roughness),
        ("preview", "specular", "b043861ba01513f5", "tm_float", 0.5),
    )
    rendered_data = []
    for node, label, connector, value_type, value in data_entries:
        if isinstance(value, tuple):
            value_fields = _vector_fields(
                value, ("r", "g", "b"), indent="\t\t\t\t\t"
            )
        else:
            value_fields = (
                f"\t\t\t\t\tfloat: {_f(float(value))}\n" if float(value) != 0 else ""
            )
        rendered_data.append(
            f'''{{
\t\t\t\t__uuid: "{ids(f"material.data.{node}.{label}")}"
\t\t\t\tto_node: "{ids(f"material.{node}_node")}"
\t\t\t\tto_connector_hash: "{connector}"
\t\t\t\tdata: {{
\t\t\t\t\t__type: "{value_type}"
\t\t\t\t\t__uuid: "{ids(f"material.data.{node}.{label}.value")}"
{value_fields}\t\t\t\t}}
\t\t\t}}'''
        )
    data_text = "\n\t\t\t".join(rendered_data)
    return f'''__type: "tm_material"
__uuid: "{ids("material")}"
shader: {{
\t__uuid: "{ids("material.shader")}"
}}
shader_graph: {{
\t__uuid: "{ids("material.shader_graph")}"
\tgraph: {{
\t\t__uuid: "{ids("material.graph")}"
\t\tnodes: [
\t\t\t{{
\t\t\t\t__uuid: "{ids("material.output_node")}"
\t\t\t\ttype: "tm_output_node"
\t\t\t\tposition: {{
\t\t\t\t\t__uuid: "{ids("material.output_position")}"
\t\t\t\t\tx: -250
\t\t\t\t\ty: 112
\t\t\t\t}}
\t\t\t}}
\t\t\t{{
\t\t\t\t__uuid: "{ids("material.pbr_node")}"
\t\t\t\ttype: "ND_realitykit_pbr_surfaceshader"
\t\t\t\tlabel: "pbr_surfaceshader_1"
\t\t\t\tposition: {{
\t\t\t\t\t__uuid: "{ids("material.pbr_position")}"
\t\t\t\t\ty: 8
\t\t\t\t}}
\t\t\t}}
\t\t\t{{
\t\t\t\t__uuid: "{ids("material.preview_node")}"
\t\t\t\ttype: "ND_UsdPreviewSurface_surfaceshader"
\t\t\t\tlabel: "Principled_BSDF"
\t\t\t\tposition: {{
\t\t\t\t\t__uuid: "{ids("material.preview_position")}"
\t\t\t\t\tx: 250
\t\t\t\t}}
\t\t\t}}
\t\t]
\t\tconnections: [
\t\t\t{{
\t\t\t\t__uuid: "{ids("material.connection")}"
\t\t\t\tfrom_node: "{ids("material.pbr_node")}"
\t\t\t\tto_node: "{ids("material.output_node")}"
\t\t\t\tfrom_connector_hash: "685a9889b8402b60"
\t\t\t\tto_connector_hash: "c1549ebf90daa052"
\t\t\t}}
\t\t\t{{
\t\t\t\t__uuid: "{ids("material.preview_connection")}"
\t\t\t\tfrom_node: "{ids("material.preview_node")}"
\t\t\t\tto_node: "{ids("material.output_node")}"
\t\t\t\tfrom_connector_hash: "685a9889b8402b60"
\t\t\t\tto_connector_hash: "891f23467e3e5272"
\t\t\t}}
\t\t]
\t\tdata: [
\t\t\t{data_text}
\t\t]
\t\tinterface: {{
\t\t\t__uuid: "{ids("material.interface")}"
\t\t\toutputs: [
\t\t\t\t{{
\t\t\t\t\t__uuid: "{ids("material.interface.output")}"
\t\t\t\t\tname: "surface"
\t\t\t\t\tdisplay_name: "surface"
\t\t\t\t\tid: "outputs:mtlx:surface"
\t\t\t\t\ttype_hash: "c3f642cf65c817b8"
\t\t\t\t\tedit_type_hash: "c3f642cf65c817b8"
\t\t\t\t}}
\t\t\t\t{{
\t\t\t\t\t__uuid: "{ids("material.interface.preview_output")}"
\t\t\t\t\tname: "surface"
\t\t\t\t\tdisplay_name: "surface"
\t\t\t\t\tid: "outputs:surface"
\t\t\t\t\ttype_hash: "c3f642cf65c817b8"
\t\t\t\t\tedit_type_hash: "c3f642cf65c817b8"
\t\t\t\t}}
\t\t\t]
\t\t}}
\t}}
}}
descriptor: {{
\t__uuid: "{ids("material.descriptor")}"
}}
__asset_uuid: "{ids("material.asset")}"
__asset_thumbnail: {{
\t__uuid: "{ids("material.thumbnail")}"
}}'''


def _entity_record(
    mesh: StaticMesh,
    ids: _Ids,
    *,
    optimized: bool,
    animation: TransformAnimation | None,
) -> str:
    prefix = "optimized" if optimized else "source"
    root_transform = _transform_component(ids, f"{prefix}.root_transform", mesh, True)
    mesh_transform = _transform_component(ids, f"{prefix}.mesh_transform", mesh, False)
    animation_component = ""
    if animation is not None:
        animation_component = f'''
\t\t\t{{
\t\t\t\t__type: "tm_animation_library_component"
\t\t\t\t__uuid: "{ids(f"{prefix}.animation_library_component")}"
\t\t\t}}'''
    return f'''__type: "tm_entity"
__uuid: "{ids(f"{prefix}.entity")}"
name: "/"
components: [
\t{{
\t\t__type: "tm_transform_component"
\t\t__uuid: "{ids(f"{prefix}.scene_transform.component")}"
\t\tlocal_position_double: {{
\t\t\t__uuid: "{ids(f"{prefix}.scene_transform.position")}"
\t\t}}
\t\tlocal_rotation: {{
\t\t\t__uuid: "{ids(f"{prefix}.scene_transform.rotation")}"
\t\t}}
\t\tlocal_scale: {{
\t\t\t__uuid: "{ids(f"{prefix}.scene_transform.scale")}"
\t\t}}
\t}}
]
children: [
\t{{
\t\t__uuid: "{ids(f"{prefix}.root")}"
\t\tname: "{mesh.root_name}"
\t\tcomponents: [
\t\t\t{root_transform}
\t\t\t{animation_component}
\t\t]
\t\tchildren: [
\t\t\t{{
\t\t\t\t__uuid: "{ids(f"{prefix}.mesh")}"
\t\t\t\tname: "{mesh.mesh_name}"
\t\t\t\tcomponents: [
\t\t\t\t\t{mesh_transform}
\t\t\t\t\t{{
\t\t\t\t\t\t__type: "tm_model_component"
\t\t\t\t\t\t__uuid: "{ids(f"{prefix}.model_component")}"
\t\t\t\t\t\tmesh_resource: {{
\t\t\t\t\t\t\t__type: "tm_mesh_resource_reference"
\t\t\t\t\t\t\t__uuid: "{ids(f"{prefix}.mesh_reference")}"
\t\t\t\t\t\t\tmesh_resource: "{ids("mesh_resource")}"
\t\t\t\t\t\t}}
\t\t\t\t\t\tmaterials: [
\t\t\t\t\t\t\t{{
\t\t\t\t\t\t\t\t__uuid: "{ids(f"{prefix}.material_binding")}"
\t\t\t\t\t\t\t\tname: "{mesh.mesh_name}"
\t\t\t\t\t\t\t\tmaterial: "{ids("material")}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t]
\t\t\t\t\t}}
\t\t\t\t]
\t\t\t}}
\t\t]
\t}}
]
__asset_uuid: "{ids(f"{prefix}.asset")}"
__asset_labels: [
\t"2cbc16a459dc040f"
]'''


def _proxy_record(mesh: StaticMesh, ids: _Ids) -> str:
    return f'''__type: "tm_entity"
__uuid: "{ids("proxy.entity")}"
__prototype_type: "tm_entity"
__prototype_uuid: "{ids("optimized.entity")}"
__asset_uuid: "{ids("proxy.asset")}"'''


def _animation_settings_block(
    animation: TransformAnimation,
    ids: _Ids,
    buffers: dict[str, str],
) -> str:
    position_buffer = ids("animation.positions")
    rotation_buffer = ids("animation.rotations")
    scale_buffer = ids("animation.scales")
    position_time_buffer = ids("animation.position_times")
    rotation_time_buffer = ids("animation.rotation_times")
    scale_time_buffer = ids("animation.scale_times")
    clip_refs = "\n".join(
        f'\t\t\t\t\t"{ids(f"clip.{clip.name}.timeline")}"'
        for clip in animation.clips
    )
    return f'''\t{{
\t\t__type: "tm_usd_animation_settings"
\t\t__uuid: "{ids("animation.settings")}"
\t\tanimations: [
\t\t\t{{
\t\t\t\t__type: "tm_timeline"
\t\t\t\t__uuid: "{ids("animation.sampled_timeline")}"
\t\t\t\tname: "{animation.name}"
\t\t\t\ttype: 2
\t\t\t\tproperties: {{
\t\t\t\t\t__type: "tm_timeline_sampled"
\t\t\t\t\t__uuid: "{ids("animation.sampled_properties")}"
\t\t\t\t\tsamples_per_second: {_f(animation.frames_per_second)}
\t\t\t\t\tusd_samples: {{
\t\t\t\t\t\t__uuid: "{ids("animation.usd_samples")}"
\t\t\t\t\t\tsample_count: {len(animation.frames)}
\t\t\t\t\t\tframes_per_second: {_f(animation.frames_per_second)}
\t\t\t\t\t\tbuffers: [
\t\t\t\t\t\t\t{{
\t\t\t\t\t\t\t\t__uuid: "{position_buffer}"
\t\t\t\t\t\t\t\tdata: "{buffers["positions"]}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t{{
\t\t\t\t\t\t\t\t__uuid: "{rotation_buffer}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t{{
\t\t\t\t\t\t\t\t__uuid: "{scale_buffer}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t{{
\t\t\t\t\t\t\t\t__uuid: "{position_time_buffer}"
\t\t\t\t\t\t\t\tdata: "{buffers["times"]}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t{{
\t\t\t\t\t\t\t\t__uuid: "{rotation_time_buffer}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t{{
\t\t\t\t\t\t\t\t__uuid: "{scale_time_buffer}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t]
\t\t\t\t\t\tnode_animations: [
\t\t\t\t\t\t\t{{
\t\t\t\t\t\t\t\t__uuid: "{ids("animation.node")}"
\t\t\t\t\t\t\t\tnode_name: "{animation.node_name}"
\t\t\t\t\t\t\t\tposition_keys: {{
\t\t\t\t\t\t\t\t\t__uuid: "{ids("animation.position_keys")}"
\t\t\t\t\t\t\t\t\tcount: {len(animation.frames)}
\t\t\t\t\t\t\t\t\ttime_buffer: "{position_time_buffer}"
\t\t\t\t\t\t\t\t\ttime_stride: 4
\t\t\t\t\t\t\t\t\tkey_buffer: "{position_buffer}"
\t\t\t\t\t\t\t\t\tkey_stride: 12
\t\t\t\t\t\t\t\t\tkey_format: 16910368
\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t]
\t\t\t\t\t\tmeters_per_unit: 1
\t\t\t\t\t}}
\t\t\t\t\tsample_count: {len(animation.frames)}
\t\t\t\t}}
\t\t\t\tclips: [
{clip_refs}
\t\t\t\t]
\t\t\t}}
\t\t]
\t}}'''


def _settings_record(
    mesh: StaticMesh,
    ids: _Ids,
    source_path: str,
    *,
    animation: TransformAnimation | None,
    animation_buffers: dict[str, str] | None,
) -> str:
    animation_settings = ""
    if animation is not None:
        if animation_buffers is None:
            raise ImportGenerationError("animation buffers are required")
        animation_settings = (
            "\n" + _animation_settings_block(animation, ids, animation_buffers)
        )
    return f'''__type: "tm_usd_asset"
__uuid: "{ids("settings")}"
source_path: "{source_path}"
settings: [
\t{{
\t\t__type: "tm_scene_optimizer"
\t\t__uuid: "{ids("settings.optimizer")}"
\t\tsettings: {{
\t\t\t__uuid: "{ids("settings.optimizer.settings")}"
\t\t\tgraph: {{
\t\t\t\t__uuid: "{ids("settings.optimizer.graph")}"
\t\t\t\tinterface: {{
\t\t\t\t\t__uuid: "{ids("settings.optimizer.interface")}"
\t\t\t\t\tinputs: [
\t\t\t\t\t\t{{
\t\t\t\t\t\t\t__uuid: "{ids("settings.optimizer.merging")}"
\t\t\t\t\t\t\tname: "Merging Mode"
\t\t\t\t\t\t\tid: "scene_optimizer_settings__merging_mode"
\t\t\t\t\t\t\tvalue: {{
\t\t\t\t\t\t\t\t__type: "tm_scene_optimizer_merging_mode"
\t\t\t\t\t\t\t\t__uuid: "{ids("settings.optimizer.merging.value")}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\tpublic: true
\t\t\t\t\t\t}}
\t\t\t\t\t\t{{
\t\t\t\t\t\t\t__uuid: "{ids("settings.optimizer.keep")}"
\t\t\t\t\t\t\tname: "Entities to Keep"
\t\t\t\t\t\t\tid: "scene_optimizer_settings__keep_entities_list"
\t\t\t\t\t\t\tvalue: {{
\t\t\t\t\t\t\t\t__type: "tm_scene_optimizer_keep_entities_list"
\t\t\t\t\t\t\t\t__uuid: "{ids("settings.optimizer.keep.value")}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\tpublic: true
\t\t\t\t\t\t}}
\t\t\t\t\t]
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
\t{{
\t\t__type: "tm_lod_generator"
\t\t__uuid: "{ids("settings.lod")}"
\t}}{animation_settings}
]
pro_settings: [
\t{{
\t\t__type: "tm_usd_purpose_settings"
\t\t__uuid: "{ids("settings.purpose")}"
\t}}
\t{{
\t\t__type: "tm_usd_dev_settings"
\t\t__uuid: "{ids("settings.dev")}"
\t\tmesh_creation_graph: "feefd623-b26a-6155-97b0-2dd807e0e1c3"
\t}}
]
variants: [
\t{{
\t\t__uuid: "{ids("settings.variant")}"
\t\tname: "Default"
\t\troot_entity: "{ids("source.entity")}"
\t\tproxy_entity: "{ids("proxy.entity")}"
\t}}
]
__asset_uuid: "{ids("settings.asset")}"'''


def _transform_clip_record(
    clip: TransformClip,
    animation: TransformAnimation,
    ids: _Ids,
) -> str:
    start_line = f"\tstart: {_f(clip.start)}\n" if clip.start else ""
    return f'''__type: "tm_timeline"
__uuid: "{ids(f"clip.{clip.name}.timeline")}"
name: "{clip.name}"
type: 1
properties: {{
\t__type: "tm_timeline_clip"
\t__uuid: "{ids(f"clip.{clip.name}.properties")}"
{start_line}\tend: {_f(clip.end)}
\tspeed: 1
\tloop_duration: {_f(animation.duration)}
\tsource_group: {{
\t\t__uuid: "{ids(f"clip.{clip.name}.source_group")}"
\t\treferenced_member: [
\t\t\t"{ids("animation.sampled_timeline")}"
\t\t]
\t\tmembers_sort_values: [
\t\t\t{{
\t\t\t\t__uuid: "{ids(f"clip.{clip.name}.sort_value")}"
\t\t\t\tdouble: 2
\t\t\t}}
\t\t]
\t}}
\tloop_duration_infinite: true
}}
__asset_uuid: "{ids(f"clip.{clip.name}.asset")}"'''


def generate_static_import(
    source: str | Path,
    destination: str | Path,
    *,
    asset_name: str | None = None,
) -> Path:
    """Generate a complete build-80 static or sampled-translation artifact."""

    source_path = Path(source).resolve()
    destination_path = Path(destination).resolve()
    if not source_path.is_file():
        raise ImportGenerationError(f"source USD does not exist: {source_path}")
    if destination_path.suffix != ".import":
        raise ImportGenerationError("destination must end in .import")
    if destination_path.exists():
        raise ImportGenerationError(f"refusing to overwrite {destination_path}")

    mesh = load_static_mesh(source_path, asset_name=asset_name)
    animation = load_transform_animation(source_path, mesh)
    identity = hashlib.sha256(source_path.read_bytes()).hexdigest()
    ids = _Ids(f"{RCP_BUILD}|{identity}|{mesh.asset_name}")
    destination_path.mkdir(parents=True)
    try:
        buffers = _write_mesh_buffers(destination_path, mesh, ids)
        animation_buffers = (
            _write_transform_animation_buffers(destination_path, animation, ids)
            if animation is not None
            else None
        )
        root_dir_id = ids("directory.root")
        records = {
            f"{mesh.asset_name}.tm_entity": _proxy_record(mesh, ids),
            f"__{mesh.asset_name}.tm_entity": _entity_record(
                mesh, ids, optimized=False, animation=animation
            ),
            f"__{mesh.asset_name}_optimized.tm_entity": _entity_record(
                mesh, ids, optimized=True, animation=animation
            ),
            "__tm_directory.tm_dir": _directory_record(
                ids, "directory.root", f"{mesh.asset_name}.import", None
            ),
            "settings.tm_usd": _settings_record(
                mesh,
                ids,
                os.path.relpath(source_path, destination_path.parent).replace(
                    os.sep, "/"
                ),
                animation=animation,
                animation_buffers=animation_buffers,
            ),
            f"geometry/{mesh.mesh_name}.tm_geometry": _geometry_record(
                mesh, ids, buffers
            ),
            "geometry/__tm_directory.tm_dir": _directory_record(
                ids, "directory.geometry", "geometry", root_dir_id
            ),
            f"materials/{mesh.material_name}.tm_material": _material_record(
                mesh, ids
            ),
            "materials/__tm_directory.tm_dir": _directory_record(
                ids, "directory.materials", "materials", root_dir_id
            ),
            f"mesh_descriptors/{mesh.mesh_name}.tm_mesh_descriptor": _mesh_descriptor_record(
                mesh, ids, buffers
            ),
            "mesh_descriptors/__tm_directory.tm_dir": _directory_record(
                ids, "directory.mesh_descriptors", "mesh_descriptors", root_dir_id
            ),
            f"meshes/{mesh.mesh_name}.tm_mesh_resource": _mesh_resource_record(
                mesh, ids
            ),
            "meshes/__tm_directory.tm_dir": _directory_record(
                ids, "directory.meshes", "meshes", root_dir_id
            ),
        }
        if animation is not None:
            records["animations/__tm_directory.tm_dir"] = _directory_record(
                ids, "directory.animations", "animations", root_dir_id
            )
            records.update(
                {
                    f"animations/{clip.name}.tm_animation": _transform_clip_record(
                        clip, animation, ids
                    )
                    for clip in animation.clips
                }
            )
        for relative_path, text in records.items():
            output = destination_path / relative_path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
    except Exception:
        # Destination did not exist before this call and is fully owned here.
        import shutil

        shutil.rmtree(destination_path, ignore_errors=True)
        raise
    return destination_path
