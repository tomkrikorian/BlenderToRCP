from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from Plugin.export.rcp_import_generator import (
    ImportGenerationError,
    SkeletalAnimation,
    SkeletonJoint,
    SkinningData,
    StaticMesh,
    TransformClip,
    _Ids,
    _skeleton_hierarchy_record,
    generate_static_import,
    load_static_asset,
)
from scripts._lib.rcp_import_contract import build_report, inspect_import

_CUBE_USDA = """#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "root"
{
    float3 xformOp:rotateXYZ = (-90, 0, 0)
    uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
    def Mesh "Cube"
    {
        int[] faceVertexCounts = [4, 4, 4, 4, 4, 4]
        int[] faceVertexIndices = [0, 4, 6, 2, 3, 2, 6, 7, 7, 6, 4, 5, 5, 1, 3, 7, 1, 0, 2, 3, 5, 4, 0, 1]
        point3f[] points = [(1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)]
        normal3f[] normals = [(0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1), (0, -1, 0), (0, -1, 0), (0, -1, 0), (0, -1, 0), (-1, 0, 0), (-1, 0, 0), (-1, 0, 0), (-1, 0, 0), (0, 0, -1), (0, 0, -1), (0, 0, -1), (0, 0, -1), (1, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0), (0, 1, 0)] (
            interpolation = "faceVarying"
        )
        texCoord2f[] primvars:st = [(0.625, 0.5), (0.875, 0.5), (0.875, 0.75), (0.625, 0.75), (0.375, 0.75), (0.625, 0.75), (0.625, 1), (0.375, 1), (0.375, 0), (0.625, 0), (0.625, 0.25), (0.375, 0.25), (0.125, 0.5), (0.375, 0.5), (0.375, 0.75), (0.125, 0.75), (0.375, 0.5), (0.625, 0.5), (0.625, 0.75), (0.375, 0.75), (0.375, 0.25), (0.625, 0.25), (0.625, 0.5), (0.375, 0.5)] (
            interpolation = "faceVarying"
        )
        uniform token subdivisionScheme = "none"
    }
}
"""


@pytest.fixture(autouse=True)
def _require_pxr() -> None:
    pytest.importorskip("pxr")


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "Cube.usda"
    source.write_text(_CUBE_USDA, encoding="utf-8")
    return source


def _material_source(tmp_path: Path, *, color_space: str) -> Path:
    source = tmp_path / "ColoredCube.usda"
    source.write_text(
        f"""#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "root"
{{
    def Mesh "Cube" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {{
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        rel material:binding = </root/_materials/Material>
    }}
    def Scope "_materials"
    {{
        def Material "Material" (
            prepend apiSchemas = ["ColorSpaceAPI"]
        )
        {{
            uniform token colorSpace:name = "{color_space}"
            token outputs:surface.connect = </root/_materials/Material/Preview.outputs:surface>
            def Shader "Preview"
            {{
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0.80000746, 0, 0.0030770362)
                token outputs:surface
            }}
        }}
    }}
}}
""",
        encoding="utf-8",
    )
    return source


def _textured_material_source(
    tmp_path: Path,
    *,
    filename: str = "Cube_Material_Baked_baseColor.png",
) -> tuple[Path, bytes]:
    texture_bytes = b"\x89PNG\r\n\x1a\nmeasured-source-payload"
    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    (texture_dir / filename).write_bytes(texture_bytes)
    source = tmp_path / "TexturedCube.usda"
    source.write_text(
        f"""#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "root"
{{
    def Mesh "Cube" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {{
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        texCoord2f[] primvars:st = [(0, 0), (1, 0), (0, 1)] (
            interpolation = "vertex"
        )
        rel material:binding = </root/_materials/Material_Baked>
    }}
    def Scope "_materials"
    {{
        def Material "Material_Baked" (
            customData = {{
                dictionary BlenderToRCP = {{
                    string surfaceProfile = "realitykit_unlit"
                }}
            }}
        )
        {{
            token outputs:mtlx:surface.connect = </root/_materials/Material_Baked/Unlit.outputs:out>
            token outputs:surface.connect = </root/_materials/Material_Baked/Preview.outputs:surface>
            def Shader "Unlit"
            {{
                uniform token info:id = "ND_realitykit_unlit_surfaceshader"
                token outputs:out
            }}
            def Shader "Image"
            {{
                uniform token info:id = "ND_image_color3"
                asset inputs:file = @textures/{filename}@
                color3f outputs:out
            }}
            def Shader "Preview"
            {{
                uniform token info:id = "UsdPreviewSurface"
                token outputs:surface
            }}
            def Shader "PreviewTexture"
            {{
                uniform token info:id = "UsdUVTexture"
                asset inputs:file = @textures/{filename}@
                float3 outputs:rgb
            }}
        }}
    }}
}}
""",
        encoding="utf-8",
    )
    return source, texture_bytes


def _multi_mesh_source(tmp_path: Path, *, shared_material: bool = False) -> Path:
    right_binding = "Red" if shared_material else "Blue"
    source = tmp_path / "TwoMeshes.usda"
    source.write_text(
        f"""#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "root"
{{
    def Xform "Left"
    {{
        double3 xformOp:translate = (-1, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
        def Mesh "LeftMesh" (
            prepend apiSchemas = ["MaterialBindingAPI"]
        )
        {{
            int[] faceVertexCounts = [3]
            int[] faceVertexIndices = [0, 1, 2]
            point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
            rel material:binding = </root/Materials/Red>
        }}
    }}
    def Xform "Right"
    {{
        double3 xformOp:translate = (1, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
        def Mesh "RightMesh" (
            prepend apiSchemas = ["MaterialBindingAPI"]
        )
        {{
            int[] faceVertexCounts = [3]
            int[] faceVertexIndices = [0, 1, 2]
            point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
            rel material:binding = </root/Materials/{right_binding}>
        }}
    }}
    def Scope "Materials"
    {{
        def Material "Red" (
            prepend apiSchemas = ["ColorSpaceAPI"]
        )
        {{
            uniform token colorSpace:name = "lin_rec709_scene"
            token outputs:surface.connect = </root/Materials/Red/Preview.outputs:surface>
            def Shader "Preview"
            {{
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (1, 0, 0)
                token outputs:surface
            }}
        }}
        def Material "Blue" (
            prepend apiSchemas = ["ColorSpaceAPI"]
        )
        {{
            uniform token colorSpace:name = "lin_rec709_scene"
            token outputs:surface.connect = </root/Materials/Blue/Preview.outputs:surface>
            def Shader "Preview"
            {{
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0, 0, 1)
                token outputs:surface
            }}
        }}
    }}
}}
""",
        encoding="utf-8",
    )
    return source


def _multi_material_source(tmp_path: Path, *, overlap: bool = False) -> Path:
    blue_indices = "[0, 1]" if overlap else "[1]"
    source = tmp_path / "TwoMaterials.usda"
    source.write_text(
        f"""#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "root"
{{
    def Xform "Panel"
    {{
        def Mesh "PanelMesh"
        {{
            int[] faceVertexCounts = [3, 3]
            int[] faceVertexIndices = [0, 1, 2, 1, 3, 2]
            point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)]
            def GeomSubset "RedFaces" (
                prepend apiSchemas = ["MaterialBindingAPI"]
            )
            {{
                uniform token elementType = "face"
                uniform token familyName = "materialBind"
                int[] indices = [0]
                rel material:binding = </root/Materials/Red>
            }}
            def GeomSubset "BlueFaces" (
                prepend apiSchemas = ["MaterialBindingAPI"]
            )
            {{
                uniform token elementType = "face"
                uniform token familyName = "materialBind"
                int[] indices = {blue_indices}
                rel material:binding = </root/Materials/Blue>
            }}
        }}
    }}
    def Scope "Materials"
    {{
        def Material "Red" (
            prepend apiSchemas = ["ColorSpaceAPI"]
        )
        {{
            uniform token colorSpace:name = "lin_rec709_scene"
            token outputs:surface.connect = </root/Materials/Red/Preview.outputs:surface>
            def Shader "Preview"
            {{
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (1, 0, 0)
                token outputs:surface
            }}
        }}
        def Material "Blue" (
            prepend apiSchemas = ["ColorSpaceAPI"]
        )
        {{
            uniform token colorSpace:name = "lin_rec709_scene"
            token outputs:surface.connect = </root/Materials/Blue/Preview.outputs:surface>
            def Shader "Preview"
            {{
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0, 0, 1)
                token outputs:surface
            }}
        }}
    }}
}}
""",
        encoding="utf-8",
    )
    return source


def test_generate_static_import_passes_structural_contract(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "Cube.import"

    generate_static_import(source, destination)

    inspection = inspect_import(destination)
    assert inspection.errors == []
    report = build_report(inspection, rcp_build="80.0.1.500.1")
    assert report["counts"]["records"] == 13
    assert report["counts"]["content_hashed_buffers"] == 7
    assert report["counts"]["derived_or_unknown_hashed_buffers"] == 0
    assert report["source"]["exists"] is True
    assert not (destination / "settings.tm_buffers").exists()
    geometry = (destination / "geometry" / "Cube.tm_geometry").read_text()
    assert 'validity_hash: "2cfcf0b4ccf2dcd8"' in geometry


def test_generate_multi_mesh_import_authors_each_resource_and_material(
    tmp_path: Path,
) -> None:
    source = _multi_mesh_source(tmp_path)

    destination = generate_static_import(source, tmp_path / "TwoMeshes.import")

    report = build_report(
        inspect_import(destination),
        rcp_build="80.0.1.500.1",
    )
    assert report["record_types"]["tm_geometry"] == 2
    assert report["record_types"]["tm_mesh_descriptor"] == 2
    assert report["record_types"]["tm_mesh_resource"] == 2
    assert report["record_types"]["tm_material"] == 2
    assert report["counts"]["derived_or_unknown_hashed_buffers"] == 0
    source_entity = (destination / "__TwoMeshes.tm_entity").read_text()
    optimized_entity = (
        destination / "__TwoMeshes_optimized.tm_entity"
    ).read_text()
    assert source_entity.count('__type: "tm_model_component"') == 2
    assert optimized_entity.count('__type: "tm_model_component"') == 2
    assert sorted(path.name for path in (destination / "meshes").glob("*.tm_mesh_resource")) == [
        "Left.tm_mesh_resource",
        "Right.tm_mesh_resource",
    ]
    assert sorted(path.name for path in (destination / "materials").glob("*.tm_material")) == [
        "Blue.tm_material",
        "Red.tm_material",
    ]


def test_generate_multi_mesh_import_reuses_shared_material(tmp_path: Path) -> None:
    source = _multi_mesh_source(tmp_path, shared_material=True)

    destination = generate_static_import(source, tmp_path / "Shared.import")

    assert len(list((destination / "meshes").glob("*.tm_mesh_resource"))) == 2
    assert [path.name for path in (destination / "materials").glob("*.tm_material")] == [
        "Red.tm_material"
    ]
    material_uuid = re.search(
        r'^__uuid: "([^"]+)"',
        (destination / "materials" / "Red.tm_material").read_text(),
        flags=re.MULTILINE,
    )
    assert material_uuid is not None
    assert (
        destination / "__TwoMeshes.tm_entity"
    ).read_text().count(f'material: "{material_uuid.group(1)}"') == 2


def test_generate_multi_mesh_import_is_deterministic(tmp_path: Path) -> None:
    source = _multi_mesh_source(tmp_path)

    first = generate_static_import(
        source,
        tmp_path / "First.import",
        asset_name="TwoMeshes",
    )
    second = generate_static_import(
        source,
        tmp_path / "Second.import",
        asset_name="TwoMeshes",
    )

    first_files = {
        path.relative_to(first): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files


def test_generate_multi_material_mesh_splits_faces_without_loss(
    tmp_path: Path,
) -> None:
    source = _multi_material_source(tmp_path)

    asset = load_static_asset(source)
    assert len(asset.meshes) == 2
    assert {mesh.material_name for mesh in asset.meshes} == {"Red", "Blue"}
    assert all(mesh.face_counts == (3,) for mesh in asset.meshes)
    assert sum(len(mesh.face_indices) for mesh in asset.meshes) == 6

    destination = generate_static_import(source, tmp_path / "TwoMaterials.import")
    assert sorted(path.name for path in (destination / "meshes").glob("*.tm_mesh_resource")) == [
        "Panel_Blue.tm_mesh_resource",
        "Panel_Red.tm_mesh_resource",
    ]
    entity = (destination / "__TwoMaterials.tm_entity").read_text()
    assert entity.count('__type: "tm_model_component"') == 2


def test_generate_multi_material_mesh_rejects_overlapping_subsets(
    tmp_path: Path,
) -> None:
    source = _multi_material_source(tmp_path, overlap=True)
    destination = tmp_path / "Overlap.import"

    with pytest.raises(ImportGenerationError, match="overlapping material subsets"):
        generate_static_import(source, destination)

    assert not destination.exists()


def test_generate_multi_mesh_import_rejects_unmeasured_animation(
    tmp_path: Path,
) -> None:
    source = _multi_mesh_source(tmp_path)
    source.write_text(
        source.read_text().replace(
            'def Xform "root"\n{',
            '''def Xform "root"
{
    double3 xformOp:translate.timeSamples = {
        1: (0, 0, 0),
        2: (1, 0, 0),
    }
    uniform token[] xformOpOrder = ["xformOp:translate"]''',
            1,
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "AnimatedMulti.import"

    with pytest.raises(ImportGenerationError, match="does not yet support animation"):
        generate_static_import(source, destination)

    assert not destination.exists()


def test_generate_static_import_converts_rec709_material_to_aces2065(
    tmp_path: Path,
) -> None:
    source = _material_source(tmp_path, color_space="lin_rec709_scene")

    destination = generate_static_import(source, tmp_path / "ColoredCube.import")

    material = (destination / "materials" / "Material.tm_material").read_text()
    color = re.search(
        r'__type: "tm_color_aces2065_rgb".*?'
        r"\n\s+r: ([^\n]+)\n\s+g: ([^\n]+)\n\s+b: ([^\n]+)",
        material,
        flags=re.DOTALL,
    )
    assert color is not None
    assert tuple(float(component) for component in color.groups()) == pytest.approx(
        (0.3522519171, 0.0721185282, 0.0167149641),
        abs=1e-4,
    )


def test_generate_static_import_rejects_unmeasured_material_color_space(
    tmp_path: Path,
) -> None:
    source = _material_source(tmp_path, color_space="srgb_rec709_scene")

    with pytest.raises(
        ImportGenerationError,
        match="requires an authored, measured color space",
    ):
        generate_static_import(source, tmp_path / "ColoredCube.import")


def test_generate_static_import_copies_measured_baked_texture_payload(
    tmp_path: Path,
) -> None:
    source, texture_bytes = _textured_material_source(tmp_path)

    destination = generate_static_import(source, tmp_path / "TexturedCube.import")

    report = build_report(
        inspect_import(destination),
        rcp_build="80.0.1.500.1",
    )
    assert report["record_types"]["tm_texture"] == 1
    assert report["counts"]["records"] == 15
    texture_record = next((destination / "textures").glob("*.tm_texture"))
    record_text = texture_record.read_text()
    assert 'source_texture: "' in record_text
    assert "TexturedCube.usda[textures/Cube_Material_Baked_baseColor.png]" in record_text
    payload = next((destination / "textures").glob("*.tm_buffers/*"))
    assert payload.read_bytes() == texture_bytes
    material = (destination / "materials" / "Material_Baked.tm_material").read_text()
    assert 'type: "ND_realitykit_unlit_surfaceshader"' in material
    assert 'resource__type: "tm_texture"' in material


def test_generate_static_import_rejects_unmeasured_texture_role(
    tmp_path: Path,
) -> None:
    source, _ = _textured_material_source(
        tmp_path,
        filename="Cube_Material_Baked_normal.png",
    )

    with pytest.raises(ImportGenerationError, match="does not yet support"):
        generate_static_import(source, tmp_path / "TexturedCube.import")


def test_generate_static_import_is_deterministic(tmp_path: Path) -> None:
    source = _source(tmp_path)
    first = generate_static_import(source, tmp_path / "First.import", asset_name="Cube")
    second = generate_static_import(source, tmp_path / "Second.import", asset_name="Cube")

    first_files = {
        path.relative_to(first): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files


def test_generate_static_import_supports_other_validated_topology(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Triangle.usda"
    source.write_text(
        """#usda 1.0
(defaultPrim = "root")
def Xform "root"
{
    def Mesh "Triangle"
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    }
}
""",
        encoding="utf-8",
    )
    destination = tmp_path / "Triangle.import"

    generate_static_import(source, destination)

    geometry = (destination / "geometry" / "Triangle.tm_geometry").read_text()
    assert 'validity_hash: "2cfcf0b4ccf2dcd8"' in geometry


def test_generate_transform_import_preserves_named_clips_and_samples(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Animated.usda"
    source.write_text(
        """#usda 1.0
(
    defaultPrim = "root"
    startTimeCode = 1
    endTimeCode = 5
    timeCodesPerSecond = 2
)
def Xform "root"
{
    def Mesh "Triangle"
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        double3 xformOp:translate.timeSamples = {
            1: (0, 0, 0),
            3: (1, 0, 0),
            5: (2, 0, 0),
        }
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
    def RealityKitComponent "AnimationLibrary"
    {
        def RealityKitClipDefinition "Clips"
        {
            uniform string[] clipNames = ["First", "Second"]
            uniform double[] startTimes = [0, 1]
        }
    }
}
""",
        encoding="utf-8",
    )

    destination = generate_static_import(source, tmp_path / "Animated.import")
    report = build_report(
        inspect_import(destination, expected_profile="transform"),
        expected_profile="transform",
        rcp_build="80.0.1.500.1",
    )
    assert report["record_types"]["tm_timeline"] == 2
    assert report["counts"]["content_hashed_buffers"] == 9
    assert (destination / "animations" / "First.tm_animation").is_file()
    assert (destination / "animations" / "Second.tm_animation").is_file()
    settings = (destination / "settings.tm_usd").read_text()
    assert 'name: "Animated_transform"' in settings
    assert "sample_count: 5" in settings
    buffers = sorted(
        (destination / "settings.tm_buffers").iterdir(),
        key=lambda path: path.stat().st_size,
    )
    assert struct.unpack("<5f", buffers[0].read_bytes()) == (1, 2, 3, 4, 5)
    assert struct.unpack("<15f", buffers[1].read_bytes()) == (
        0,
        0,
        0,
        0.5,
        0,
        0,
        1,
        0,
        0,
        1.5,
        0,
        0,
        2,
        0,
        0,
    )


def test_generate_transform_import_rejects_unmeasured_rotation_samples(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Rotating.usda"
    source.write_text(
        """#usda 1.0
(
    defaultPrim = "root"
    startTimeCode = 1
    endTimeCode = 2
)
def Xform "root"
{
    def Mesh "Triangle"
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        float3 xformOp:rotateXYZ.timeSamples = {
            1: (0, 0, 0),
            2: (0, 90, 0),
        }
        uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
    }
}
""",
        encoding="utf-8",
    )
    destination = tmp_path / "Rotating.import"

    with pytest.raises(ImportGenerationError, match="translation only"):
        generate_static_import(source, destination)

    assert not destination.exists()


def test_generate_static_import_refuses_overwrite(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "Cube.import"
    destination.mkdir()

    with pytest.raises(ImportGenerationError, match="overwrite"):
        generate_static_import(source, destination)


def test_skeleton_hierarchy_quantizes_before_omitting_identity_fields() -> None:
    joint = SkeletonJoint(
        name="root",
        parent_index=0,
        rest_position=(1e-50, 0.0, 0.0),
        rest_rotation=(0.0, 0.0, 0.0, 1.0),
        rest_scale=(1.0 + 1e-8, 1.0000001, 1.0),
        inverse_bind_matrix=(
            (1.0, 1e-50, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ),
    )
    animation = SkeletalAnimation(
        name="Rig",
        frames_per_second=24.0,
        frames=(0.0,),
        translations=(((0.0, 0.0, 0.0),),),
        rotations=(((0.0, 0.0, 0.0, 1.0),),),
        clips=(TransformClip(name="Rest", start=0.0, end=0.0),),
    )
    skinning = SkinningData(
        armature_name="Armature",
        skeleton_name="root",
        skeleton_path="/root",
        armature_translation=(0.0, 0.0, 0.0),
        armature_rotation=(0.0, 0.0, 0.0, 1.0),
        armature_scale=(1.0, 1.0, 1.0),
        joint_indices=((0, 0, 0, 0),),
        joint_weights=((1.0, 0.0, 0.0, 0.0),),
        geom_bind_transform=(
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ),
        joints=(joint,),
        animation=animation,
    )
    mesh = StaticMesh(
        asset_name="Rig",
        root_name="root",
        mesh_name="Mesh",
        material_name="Material",
        points=((0.0, 0.0, 0.0),),
        face_counts=(),
        face_indices=(),
        face_uvs=(),
        face_normals=(),
        base_color=(1.0, 1.0, 1.0),
        metallic=0.0,
        roughness=1.0,
        opacity=1.0,
        root_translation=(0.0, 0.0, 0.0),
        root_rotation=(0.0, 0.0, 0.0, 1.0),
        root_scale=(1.0, 1.0, 1.0),
        mesh_translation=(0.0, 0.0, 0.0),
        mesh_rotation=(0.0, 0.0, 0.0, 1.0),
        mesh_scale=(1.0, 1.0, 1.0),
        skinning=skinning,
    )

    record = _skeleton_hierarchy_record(mesh, _Ids("near-identity"))

    assert "\t\t\t\tx:" not in record
    assert "\t\t\t\ty: 1.0000001192092896" in record
    assert "\t\t\txy:" not in record
