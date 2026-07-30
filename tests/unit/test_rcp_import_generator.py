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
                color3f inputs:diffuseColor.connect = </root/_materials/Material_Baked/PreviewTexture.outputs:rgb>
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


def _multi_material_source(
    tmp_path: Path,
    *,
    overlap: bool = False,
    red_indices: str = "[0]",
    blue_indices: str | None = "[1]",
    blue_family: str = "materialBind",
    face_count: int = 2,
    third_subset: bool = False,
    blue_binding: str = "Blue",
    second_mesh_binding: str | None = None,
    stray_subset: bool = False,
) -> Path:
    if overlap:
        blue_indices = "[0, 1]"
    counts = ", ".join(["3"] * face_count)
    indices = ", ".join(("0, 1, 2", "1, 3, 2", "2, 3, 0")[:face_count])
    blue_subset = (
        f"""
            def GeomSubset "BlueFaces" (
                prepend apiSchemas = ["MaterialBindingAPI"]
            )
            {{
                uniform token elementType = "face"
                uniform token familyName = "{blue_family}"
                int[] indices = {blue_indices}
                rel material:binding = </root/Materials/{blue_binding}>
            }}"""
        if blue_indices is not None
        else ""
    )
    green_subset = (
        """
            def GeomSubset "GreenFaces" (
                prepend apiSchemas = ["MaterialBindingAPI"]
            )
            {
                uniform token elementType = "face"
                uniform token familyName = "materialBind"
                int[] indices = [2]
                rel material:binding = </root/Materials/Green>
            }"""
        if third_subset
        else ""
    )
    second_mesh = (
        f"""
    def Xform "Second"
    {{
        def Mesh "SecondMesh" (
            prepend apiSchemas = ["MaterialBindingAPI"]
        )
        {{
            int[] faceVertexCounts = [3]
            int[] faceVertexIndices = [0, 1, 2]
            point3f[] points = [(0, 0, 5), (1, 0, 5), (0, 1, 5)]
            rel material:binding = </root/Materials/{second_mesh_binding}>
        }}
    }}"""
        if second_mesh_binding
        else ""
    )
    stray = (
        """
    def Scope "Stray"
    {
        def GeomSubset "Orphan"
        {
            uniform token elementType = "face"
            uniform token familyName = "materialBind"
            int[] indices = [0]
        }
    }"""
        if stray_subset
        else ""
    )
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
            int[] faceVertexCounts = [{counts}]
            int[] faceVertexIndices = [{indices}]
            point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)]
            def GeomSubset "RedFaces" (
                prepend apiSchemas = ["MaterialBindingAPI"]
            )
            {{
                uniform token elementType = "face"
                uniform token familyName = "materialBind"
                int[] indices = {red_indices}
                rel material:binding = </root/Materials/Red>
            }}{blue_subset}{green_subset}
        }}
    }}{second_mesh}{stray}
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
        def Material "Green" (
            prepend apiSchemas = ["ColorSpaceAPI"]
        )
        {{
            uniform token colorSpace:name = "lin_rec709_scene"
            token outputs:surface.connect = </root/Materials/Green/Preview.outputs:surface>
            def Shader "Preview"
            {{
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (0, 1, 0)
                token outputs:surface
            }}
        }}
    }}
}}
""",
        encoding="utf-8",
    )
    return source


def _multi_skeletal_source(
    tmp_path: Path,
    *,
    mixed_skinning: bool = False,
    nested_transform: bool = False,
    time_sampled_uv_indices: bool = False,
) -> Path:
    right_api = (
        'prepend apiSchemas = ["MaterialBindingAPI"]'
        if mixed_skinning
        else 'prepend apiSchemas = ["MaterialBindingAPI", "SkelBindingAPI"]'
    )
    right_skinning = (
        ""
        if mixed_skinning
        else """
            matrix4d primvars:skel:geomBindTransform = ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) )
            int[] primvars:skel:jointIndices = [0, 0, 0, 0, 0, 0, 0, 0, 0] (
                elementSize = 3
                interpolation = "vertex"
            )
            float[] primvars:skel:jointWeights = [1, 0, 0, 1, 0, 0, 1, 0, 0] (
                elementSize = 3
                interpolation = "vertex"
            )
            rel skel:skeleton = </root/Rig/Skeleton>
"""
    )
    rig_transform = (
        """
        double3 xformOp:translate = (1, 2, 3)
        float3 xformOp:scale = (2, 2, 2)
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
"""
        if nested_transform
        else ""
    )
    meshes_transform = ""
    uv_block = (
        """
                texCoord2f[] primvars:st = [(0, 0), (1, 0), (0, 1)] (
                    interpolation = "faceVarying"
                )
                int[] primvars:st:indices.timeSamples = {
                    1: [0, 1, 2],
                    2: [0, 1, 2],
                }
"""
        if time_sampled_uv_indices
        else ""
    )
    source = tmp_path / "TwoSkinnedMeshes.usda"
    source.write_text(
        f"""#usda 1.0
(
    defaultPrim = "root"
    endTimeCode = 2
    metersPerUnit = 1
    startTimeCode = 1
    timeCodesPerSecond = 24
    upAxis = "Y"
)
def Xform "root"
{{
    def SkelRoot "Rig"
    {{
{rig_transform}
        def Xform "Meshes"
        {{
{meshes_transform}
            def Mesh "Left" (
                prepend apiSchemas = ["MaterialBindingAPI", "SkelBindingAPI"]
            )
            {{
                int[] faceVertexCounts = [3]
                int[] faceVertexIndices = [0, 1, 2]
                point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
{uv_block}
                matrix4d primvars:skel:geomBindTransform = ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) )
                int[] primvars:skel:jointIndices = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] (
                    elementSize = 4
                    interpolation = "vertex"
                )
                float[] primvars:skel:jointWeights = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0] (
                    elementSize = 4
                    interpolation = "vertex"
                )
                rel material:binding = </root/Materials/Red>
                rel skel:skeleton = </root/Rig/Skeleton>
            }}
            def Mesh "Right" (
                {right_api}
            )
            {{
                int[] faceVertexCounts = [3]
                int[] faceVertexIndices = [0, 1, 2]
                point3f[] points = [(0, 0, 0), (-1, 0, 0), (0, 1, 0)]
{uv_block}
{right_skinning}
                rel material:binding = </root/Materials/Blue>
            }}
        }}
        def Skeleton "Skeleton" (
            prepend apiSchemas = ["SkelBindingAPI"]
        )
        {{
            uniform matrix4d[] bindTransforms = [( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) )]
            uniform token[] joints = ["Root"]
            uniform matrix4d[] restTransforms = [( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) )]
            rel skel:animationSource = </root/Rig/Skeleton/Animation>
            def SkelAnimation "Animation"
            {{
                uniform token[] joints = ["Root"]
                quatf[] rotations.timeSamples = {{
                    1: [(1, 0, 0, 0)],
                    2: [(1, 0, 0, 0)],
                }}
                float3[] translations.timeSamples = {{
                    1: [(0, 0, 0)],
                    2: [(0, 0.1, 0)],
                }}
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


def _skinned_multi_material_source(
    tmp_path: Path,
    *,
    single_source_mesh: bool = False,
    overlap: bool = False,
) -> Path:
    """Extend the measured skeletal fixture with two face materials on Left.

    Left gets an exhaustive two-subset partition (Red faces plus an Accent
    material used by no other mesh prim — the fail-closed boundary refuses
    slot materials shared across prims).
    """

    source = _multi_skeletal_source(tmp_path)
    text = source.read_text(encoding="utf-8")
    text = text.replace(
        "                int[] faceVertexCounts = [3]\n"
        "                int[] faceVertexIndices = [0, 1, 2]\n"
        "                point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]",
        "                int[] faceVertexCounts = [3, 3]\n"
        "                int[] faceVertexIndices = [0, 1, 2, 1, 3, 2]\n"
        "                point3f[] points = [(0, 0, 0), (1, 0, 0), "
        "(0, 1, 0), (1, 1, 0)]",
        1,
    )
    text = text.replace(
        "                int[] primvars:skel:jointIndices = "
        "[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] (",
        "                int[] primvars:skel:jointIndices = "
        "[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] (",
        1,
    )
    text = text.replace(
        "                float[] primvars:skel:jointWeights = "
        "[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0] (",
        "                float[] primvars:skel:jointWeights = "
        "[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0] (",
        1,
    )
    overlapping_subset = (
        """
                def GeomSubset "OverlappingRedFaces" (
                    prepend apiSchemas = ["MaterialBindingAPI"]
                )
                {
                    uniform token elementType = "face"
                    uniform token familyName = "materialBind"
                    int[] indices = [1]
                    rel material:binding = </root/Materials/Red>
                }
"""
        if overlap
        else ""
    )
    text = text.replace(
        "                rel material:binding = </root/Materials/Red>\n"
        "                rel skel:skeleton = </root/Rig/Skeleton>\n"
        "            }\n"
        '            def Mesh "Right" (',
        "                rel material:binding = </root/Materials/Red>\n"
        "                rel skel:skeleton = </root/Rig/Skeleton>\n"
        """
                def GeomSubset "RedFaces" (
                    prepend apiSchemas = ["MaterialBindingAPI"]
                )
                {
                    uniform token elementType = "face"
                    uniform token familyName = "materialBind"
                    int[] indices = [0]
                    rel material:binding = </root/Materials/Red>
                }
                def GeomSubset "AccentFaces" (
                    prepend apiSchemas = ["MaterialBindingAPI"]
                )
                {
                    uniform token elementType = "face"
                    uniform token familyName = "materialBind"
                    int[] indices = [1]
                    rel material:binding = </root/Materials/Accent>
                }
"""
        + overlapping_subset
        + "            }\n"
        + '            def Mesh "Right" (',
        1,
    )
    text = text.replace(
        '        def Material "Blue" (',
        """        def Material "Accent" (
            prepend apiSchemas = ["ColorSpaceAPI"]
        )
        {
            uniform token colorSpace:name = "lin_rec709_scene"
            token outputs:surface.connect = </root/Materials/Accent/Preview.outputs:surface>
            def Shader "Preview"
            {
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = (1, 1, 0)
                token outputs:surface
            }
        }
        def Material "Blue" (""",
        1,
    )
    if single_source_mesh:
        text = text.replace(
            '            def Mesh "Right" (\n',
            '            def Mesh "Right" (\n'
            "                active = false\n",
            1,
        )
    source.write_text(text, encoding="utf-8")
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


def test_generate_multi_material_mesh_authors_single_descriptor_with_subsets(
    tmp_path: Path,
) -> None:
    """One USD mesh with two material subsets stays ONE mesh with slots."""

    source = _multi_material_source(tmp_path)

    asset = load_static_asset(source)
    assert len(asset.meshes) == 1
    mesh = asset.meshes[0]
    assert [slot.name for slot in mesh.material_slots] == ["Red", "Blue"]
    # Full topology is retained once; subsets carry authored face ordinals
    # and the full USD GeomSubset prim paths.
    assert mesh.face_counts == (3, 3)
    assert len(mesh.face_indices) == 6
    assert [subset.name for subset in mesh.subsets] == [
        "/root/Panel/PanelMesh/RedFaces",
        "/root/Panel/PanelMesh/BlueFaces",
    ]
    assert mesh.subsets[0].face_indices == (0,)
    assert mesh.subsets[1].face_indices == (1,)

    destination = generate_static_import(source, tmp_path / "TwoMaterials.import")

    report = build_report(inspect_import(destination), rcp_build="80.0.1.500.1")
    assert report["record_types"]["tm_geometry"] == 1
    assert report["record_types"]["tm_mesh_descriptor"] == 1
    assert report["record_types"]["tm_mesh_resource"] == 1
    assert report["record_types"]["tm_material"] == 2
    assert report["counts"]["derived_or_unknown_hashed_buffers"] == 0
    assert [
        path.name
        for path in (destination / "meshes").glob("*.tm_mesh_resource")
    ] == ["Panel.tm_mesh_resource"]
    entity = (destination / "__TwoMaterials.tm_entity").read_text()
    assert entity.count('__type: "tm_model_component"') == 1


def test_multi_material_descriptor_subsets_record_shape(tmp_path: Path) -> None:
    """The subsets array matches the measured canonical record shape."""

    source = _multi_material_source(tmp_path)

    destination = generate_static_import(source, tmp_path / "TwoMaterials.import")

    descriptor = (
        destination / "mesh_descriptors" / "Panel.tm_mesh_descriptor"
    ).read_text()
    subsets_match = re.search(r"\nsubsets: \[\n(.*?)\n\]\n", descriptor, re.S)
    assert subsets_match is not None
    entries = re.findall(r"\t\{\n(.*?)\n\t\}", subsets_match.group(1), re.S)
    assert len(entries) == 2
    # Slot 0: index elided (defaulted uint32); slot 1: explicit index 1 —
    # exactly the measured Robot capture shape.
    assert 'name: "/root/Panel/PanelMesh/RedFaces"' in entries[0]
    assert "index:" not in entries[0]
    assert 'name: "/root/Panel/PanelMesh/BlueFaces"' in entries[1]
    assert "\t\tindex: 1" in entries[1]
    assert entries[0].count("face_count: 1") == 1
    assert entries[1].count("face_count: 1") == 1
    # No guessed material_bindings: its authored values were never captured.
    assert "material_bindings" not in descriptor
    # Deterministic per-subset UUIDs come from the namespaced machinery.
    first_uuids = re.findall(r'__uuid: "([0-9a-f-]{36})"', subsets_match.group(1))
    assert len(first_uuids) == len(set(first_uuids)) == 2


def test_multi_material_subset_buffers_hold_little_endian_face_ordinals(
    tmp_path: Path,
) -> None:
    """Subset payloads are packed uint32 face ordinals, content-hash named."""

    from scripts._lib.rcp_import_format import buffer_content_hash

    source = _multi_material_source(tmp_path)

    destination = generate_static_import(source, tmp_path / "TwoMaterials.import")

    descriptor = (
        destination / "mesh_descriptors" / "Panel.tm_mesh_descriptor"
    ).read_text()
    buffer_ids = re.findall(r'face_indices: "([0-9a-f-]{36})"', descriptor)
    assert len(buffer_ids) == 2
    buffer_dir = destination / "mesh_descriptors" / "Panel.tm_buffers"
    expected_payloads = (struct.pack("<I", 0), struct.pack("<I", 1))
    for buffer_id, expected in zip(buffer_ids, expected_payloads):
        payload_path = next(buffer_dir.glob(f"{buffer_id}.*"))
        data = payload_path.read_bytes()
        assert data == expected
        name_hash = payload_path.name.split(".")[1]
        assert int(name_hash, 16) == int(buffer_content_hash(data), 16)


def test_multi_material_model_component_orders_materials_like_subsets(
    tmp_path: Path,
) -> None:
    source = _multi_material_source(tmp_path)

    destination = generate_static_import(source, tmp_path / "TwoMaterials.import")

    red_uuid = re.search(
        r'^__uuid: "([0-9a-f-]{36})"',
        (destination / "materials" / "Red.tm_material").read_text(),
        flags=re.MULTILINE,
    ).group(1)
    blue_uuid = re.search(
        r'^__uuid: "([0-9a-f-]{36})"',
        (destination / "materials" / "Blue.tm_material").read_text(),
        flags=re.MULTILINE,
    ).group(1)
    for entity_name in ("__TwoMaterials.tm_entity", "__TwoMaterials_optimized.tm_entity"):
        entity = (destination / entity_name).read_text()
        materials_block = re.search(
            r"materials: \[\n(.*?)\n\t{6}\]", entity, re.S
        )
        assert materials_block is not None
        names = re.findall(r'name: "([^"]+)"\n\s*material: "([0-9a-f-]{36})"',
                           materials_block.group(1))
        # One entry per slot, in descriptor-subset order, named by material.
        assert names == [("Red", red_uuid), ("Blue", blue_uuid)]


def test_generate_multi_material_mesh_is_deterministic(tmp_path: Path) -> None:
    source = _multi_material_source(tmp_path)

    first = generate_static_import(
        source, tmp_path / "First.import", asset_name="TwoMaterials"
    )
    second = generate_static_import(
        source, tmp_path / "Second.import", asset_name="TwoMaterials"
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


def test_generate_multi_material_mesh_rejects_overlapping_subsets(
    tmp_path: Path,
) -> None:
    source = _multi_material_source(tmp_path, overlap=True)
    destination = tmp_path / "Overlap.import"

    with pytest.raises(ImportGenerationError, match="overlapping material subsets"):
        generate_static_import(source, destination)

    assert not destination.exists()


@pytest.mark.parametrize(
    ("source_kwargs", "message"),
    [
        pytest.param(
            {"blue_indices": "[5]"},
            "invalid face index 5",
            id="out-of-range-face-index",
        ),
        pytest.param(
            {"blue_indices": "[]"},
            "is empty; build-80 supports only non-empty face partitions",
            id="empty-subset",
        ),
        pytest.param(
            {"face_count": 3},
            "leave 1 of 3 faces unassigned",
            id="non-exhaustive-partition",
        ),
        pytest.param(
            {"blue_family": "physics"},
            "unmeasured family 'physics'",
            id="unsupported-subset-family",
        ),
        pytest.param(
            {"face_count": 3, "third_subset": True},
            "3 material slots on /root/Panel/PanelMesh exceed the measured "
            "2-slot build-80 corpus",
            id="three-material-slots",
        ),
        pytest.param(
            {"blue_binding": "Red"},
            "share one material",
            id="shared-material-across-subsets",
        ),
        pytest.param(
            {"second_mesh_binding": "Blue"},
            "shared between multi-material mesh",
            id="shared-material-across-mesh-prims",
        ),
        pytest.param(
            {"stray_subset": True},
            "not a direct child of a mesh",
            id="unsupported-subset-hierarchy",
        ),
    ],
)
def test_multi_material_mesh_fails_closed_on_unmeasured_subset_shapes(
    tmp_path: Path,
    source_kwargs: dict,
    message: str,
) -> None:
    source = _multi_material_source(tmp_path, **source_kwargs)
    destination = tmp_path / "Refused.import"

    with pytest.raises(ImportGenerationError, match=re.escape(message)):
        generate_static_import(source, destination)

    assert not destination.exists()


def test_single_exhaustive_subset_collapses_to_proven_single_material(
    tmp_path: Path,
) -> None:
    """One subset covering every face is the single-material degenerate."""

    source = _multi_material_source(
        tmp_path, red_indices="[0, 1]", blue_indices=None
    )

    asset = load_static_asset(source)

    assert len(asset.meshes) == 1
    mesh = asset.meshes[0]
    assert mesh.subsets == ()
    assert [slot.name for slot in mesh.material_slots] == ["Red"]

    destination = generate_static_import(source, tmp_path / "OneSubset.import")
    descriptor = (
        destination / "mesh_descriptors" / "Panel.tm_mesh_descriptor"
    ).read_text()
    assert "subsets" not in descriptor
    assert inspect_import(destination).errors == []


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


def test_generate_multi_skeletal_import_authors_shared_skeleton_and_materials(
    tmp_path: Path,
) -> None:
    source = _multi_skeletal_source(tmp_path)

    destination = generate_static_import(
        source,
        tmp_path / "TwoSkinnedMeshes.import",
    )

    report = build_report(
        inspect_import(destination),
        rcp_build="80.0.1.500.1",
    )
    assert report["record_types"]["tm_geometry"] == 2
    assert report["record_types"]["tm_mesh_descriptor"] == 2
    assert report["record_types"]["tm_mesh_resource"] == 3
    assert report["record_types"]["tm_material"] == 2
    assert report["record_types"]["tm_skeleton_hierarchy"] == 1
    assert report["record_types"]["tm_skeleton_definition"] == 1
    assert report["counts"]["derived_or_unknown_hashed_buffers"] == 0
    source_entity = (
        destination / "__TwoSkinnedMeshes.tm_entity"
    ).read_text()
    optimized_entity = (
        destination / "__TwoSkinnedMeshes_optimized.tm_entity"
    ).read_text()
    assert source_entity.count('__type: "tm_skinning_component"') == 2
    assert source_entity.count('__type: "tm_model_component"') == 2
    assert optimized_entity.count('__type: "tm_model_component"') == 1
    merged = (
        destination / "geometry" / "Skeleton_merged.tm_mesh_resource"
    ).read_text()
    assert merged.count("\t\tgeometry: ") == 2
    assert merged.count("\t\tskinning_data: {") == 2
    left_descriptor = (
        destination / "mesh_descriptors" / "Left.tm_mesh_descriptor"
    ).read_text()
    right_descriptor = (
        destination / "mesh_descriptors" / "Right.tm_mesh_descriptor"
    ).read_text()
    assert "influence_count_per_vertex: 4" in left_descriptor
    assert "influence_count_per_vertex: 3" in right_descriptor


@pytest.mark.parametrize("single_source_mesh", [False, True])
def test_generate_skeletal_material_subsets_author_single_descriptor(
    tmp_path: Path,
    single_source_mesh: bool,
) -> None:
    """A skinned mesh with two face materials stays one mesh with slots."""

    source = _skinned_multi_material_source(
        tmp_path,
        single_source_mesh=single_source_mesh,
    )

    asset = load_static_asset(source)

    expected_meshes = 1 if single_source_mesh else 2
    expected_materials = 2 if single_source_mesh else 3
    assert len(asset.meshes) == expected_meshes
    multi_slot = [mesh for mesh in asset.meshes if len(mesh.material_slots) > 1]
    assert len(multi_slot) == 1
    left = multi_slot[0]
    assert left.source_prim_path.endswith("/Left")
    assert [slot.name for slot in left.material_slots] == ["Red", "Accent"]
    assert [subset.name for subset in left.subsets] == [
        "/root/Rig/Meshes/Left/RedFaces",
        "/root/Rig/Meshes/Left/AccentFaces",
    ]
    # The mesh keeps its full topology and per-point skinning once: 4 points
    # across 2 faces, influences in source point order.
    assert left.face_counts == (3, 3)
    assert len(left.points) == 4
    assert left.skinning is not None
    assert len(left.skinning.joint_indices) == 4
    assert len(left.skinning.joint_weights) == 4

    destination = generate_static_import(
        source,
        tmp_path / "SkinnedMaterials.import",
    )
    report = build_report(
        inspect_import(destination),
        rcp_build="80.0.1.500.1",
    )
    assert report["record_types"]["tm_geometry"] == expected_meshes
    assert report["record_types"]["tm_mesh_descriptor"] == expected_meshes
    assert report["record_types"]["tm_mesh_resource"] == expected_meshes + 1
    assert report["record_types"]["tm_material"] == expected_materials
    assert report["counts"]["derived_or_unknown_hashed_buffers"] == 0
    source_entity = (
        destination / "__TwoSkinnedMeshes.tm_entity"
    ).read_text()
    optimized_entity = (
        destination / "__TwoSkinnedMeshes_optimized.tm_entity"
    ).read_text()
    # One skinning and one model component per SOURCE mesh; the skeleton and
    # timeline resources are not multiplied by the material count.
    assert source_entity.count('__type: "tm_skinning_component"') == expected_meshes
    assert source_entity.count('__type: "tm_model_component"') == expected_meshes
    assert optimized_entity.count('__type: "tm_model_component"') == 1
    # The optimized model component carries one material entry per slot,
    # multi-slot entries named by material in subset order.
    assert optimized_entity.count("material: ") == expected_materials
    assert report["record_types"]["tm_skeleton_hierarchy"] == 1
    assert report["record_types"]["tm_skeleton_definition"] == 1
    left_descriptor = (
        destination
        / "mesh_descriptors"
        / f"{left.mesh_name}.tm_mesh_descriptor"
    ).read_text()
    assert "\nsubsets: [" in left_descriptor
    assert left_descriptor.count("vertex_count: 4") == 2
    assert "material_bindings" not in left_descriptor


def _split_bounds_source(tmp_path: Path) -> Path:
    """Two far-apart triangles on one mesh, one material subset each."""

    source = tmp_path / "Split.usda"
    source.write_text(
        """#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "root"
{
    def Mesh "Plate"
    {
        int[] faceVertexCounts = [3, 3]
        int[] faceVertexIndices = [0, 1, 2, 3, 4, 5]
        point3f[] points = [
            (0, 0, 0), (1, 0, 0), (0, 1, 0),
            (100, 0, 0), (101, 0, 0), (100, 1, 0)
        ]
        def GeomSubset "NearFaces" (
            prepend apiSchemas = ["MaterialBindingAPI"]
        )
        {
            uniform token elementType = "face"
            uniform token familyName = "materialBind"
            int[] indices = [0]
            rel material:binding = </root/Materials/Red>
        }
        def GeomSubset "FarFaces" (
            prepend apiSchemas = ["MaterialBindingAPI"]
        )
        {
            uniform token elementType = "face"
            uniform token familyName = "materialBind"
            int[] indices = [1]
            rel material:binding = </root/Materials/Blue>
        }
    }
    def Scope "Materials"
    {
        def Material "Red"
        {
            token outputs:surface.connect = </root/Materials/Red/Preview.outputs:surface>
            def Shader "Preview"
            {
                uniform token info:id = "UsdPreviewSurface"
                token outputs:surface
            }
        }
        def Material "Blue"
        {
            token outputs:surface.connect = </root/Materials/Blue/Preview.outputs:surface>
            def Shader "Preview"
            {
                uniform token info:id = "UsdPreviewSurface"
                token outputs:surface
            }
        }
    }
}
""",
        encoding="utf-8",
    )
    return source


def _descriptor_points(destination: Path, mesh_name: str) -> list[tuple[float, ...]]:
    """Decode the points buffer a mesh descriptor actually points at."""

    descriptor = (
        destination / "mesh_descriptors" / f"{mesh_name}.tm_mesh_descriptor"
    ).read_text()
    buffer_id = re.search(
        r'name: "points".*?data: "([0-9a-f-]{36})"', descriptor, re.S
    ).group(1)
    payload = next(
        (destination / "mesh_descriptors" / f"{mesh_name}.tm_buffers").glob(
            f"{buffer_id}.*"
        )
    ).read_bytes()
    floats = struct.unpack(f"<{len(payload) // 4}f", payload)
    return [tuple(floats[index : index + 3]) for index in range(0, len(floats), 3)]


def _resource_bounds(destination: Path, mesh_name: str) -> dict[str, dict[str, float]]:
    text = (destination / "meshes" / f"{mesh_name}.tm_mesh_resource").read_text()
    bounds = {}
    for key in ("bounds_min", "bounds_max"):
        block = re.search(rf"{key}: \{{(.*?)\n\t\t\}}", text, re.S).group(1)
        bounds[key] = {
            axis: float(value)
            for axis, value in re.findall(r"(\w): (-?[\d.e+-]+)", block)
        }
    return bounds


def test_generate_static_import_keeps_full_topology_for_material_subsets(
    tmp_path: Path,
) -> None:
    """The canonical form keeps one whole mesh: full points, full bounds."""

    source = _split_bounds_source(tmp_path)

    destination = generate_static_import(source, tmp_path / "Split.import")

    descriptor = (
        destination / "mesh_descriptors" / "Plate.tm_mesh_descriptor"
    ).read_text()
    assert "vertex_count: 6" in descriptor
    assert "\nsubsets: [" in descriptor
    assert _descriptor_points(destination, "Plate") == [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (100.0, 0.0, 0.0),
        (101.0, 0.0, 0.0),
        (100.0, 1.0, 0.0),
    ]

    # One mesh resource spanning the whole source mesh.
    bounds = _resource_bounds(destination, "Plate")
    assert bounds["bounds_min"].get("x", 0.0) == 0.0
    assert bounds["bounds_max"].get("x", 0.0) == 101.0

    assert inspect_import(destination).errors == []


def test_generate_static_import_reindexes_unsplit_mesh_to_itself(
    tmp_path: Path,
) -> None:
    """A mesh that is not split must keep the source point order byte for byte."""

    source = _multi_mesh_source(tmp_path)

    destination = generate_static_import(source, tmp_path / "TwoMeshes.import")

    assert _descriptor_points(destination, "Left") == [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    ]


def test_generate_static_import_keeps_subset_mesh_skinning_whole(
    tmp_path: Path,
) -> None:
    """Material subsets must not clone or re-index per-point skinning."""

    source = _skinned_multi_material_source(tmp_path)
    # Move each of Left's 4 points' weight into a different influence slot so
    # any re-indexing or duplication of the influence table cannot pass
    # unnoticed. The skeleton has one joint, so the slot is the only thing
    # free to vary while every vertex still sums to 1.
    text = source.read_text(encoding="utf-8")
    text = text.replace(
        "float[] primvars:skel:jointWeights = "
        "[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0] (",
        "float[] primvars:skel:jointWeights = "
        "[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] (",
        1,
    )
    source.write_text(text, encoding="utf-8")

    asset = load_static_asset(source)

    left = next(
        mesh for mesh in asset.meshes if mesh.source_prim_path.endswith("/Left")
    )
    # One influence table in source point order — not per-material clones.
    assert left.skinning.joint_weights == (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )

    destination = generate_static_import(source, tmp_path / "Skinned.import")
    descriptor = (
        destination / "mesh_descriptors" / f"{left.mesh_name}.tm_mesh_descriptor"
    ).read_text()
    # skinning_data.vertex_count must agree with the retained full points.
    assert descriptor.count("vertex_count: 4") == 2
    assert inspect_import(destination).errors == []


def _reskinned_source(tmp_path: Path, *, indices: str, weights: str) -> Path:
    """The measured single-joint skeletal fixture with Left's influences rewritten."""

    source = _multi_skeletal_source(tmp_path)
    text = source.read_text(encoding="utf-8")
    text = text.replace(
        "int[] primvars:skel:jointIndices = "
        "[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] (",
        f"int[] primvars:skel:jointIndices = [{indices}] (",
        1,
    )
    text = text.replace(
        "float[] primvars:skel:jointWeights = "
        "[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0] (",
        f"float[] primvars:skel:jointWeights = [{weights}] (",
        1,
    )
    source.write_text(text, encoding="utf-8")
    return source


_VALID_INFLUENCES = ("0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0", "1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0")


@pytest.mark.parametrize(
    ("indices", "weights", "message"),
    [
        pytest.param(
            "7, 0, 0, 0, 9, 0, 0, 0, 0, 0, 0, 0",
            "3, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0",
            "outside the 1-joint skeleton",
            id="joint-index-past-palette",
        ),
        pytest.param(
            "-1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0",
            _VALID_INFLUENCES[1],
            "outside the 1-joint skeleton",
            id="negative-joint-index",
        ),
        pytest.param(
            _VALID_INFLUENCES[0],
            "0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0",
            "summing to 0.0, not 1",
            id="unweighted-vertex",
        ),
        pytest.param(
            _VALID_INFLUENCES[0],
            "0.5, 0.9, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0",
            "summing to 1.39",
            id="unnormalized-weights",
        ),
        pytest.param(
            _VALID_INFLUENCES[0],
            "1.5, -0.5, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0",
            "negative or non-finite skin weight",
            id="negative-weight",
        ),
        pytest.param(
            "0, 0, 0, 0, 0, 0, 0, 0",
            "1, 0, 0, 0, 1, 0, 0, 0",
            "cover 2 vertices but",
            id="influences-shorter-than-points",
        ),
    ],
)
def test_load_skinning_rejects_unusable_influences(
    tmp_path: Path,
    indices: str,
    weights: str,
    message: str,
) -> None:
    source = _reskinned_source(tmp_path, indices=indices, weights=weights)

    with pytest.raises(ImportGenerationError, match=re.escape(message)):
        generate_static_import(source, tmp_path / "Skinned.import")


def test_load_skinning_accepts_measured_influences(tmp_path: Path) -> None:
    indices, weights = _VALID_INFLUENCES
    source = _reskinned_source(tmp_path, indices=indices, weights=weights)

    destination = generate_static_import(source, tmp_path / "Skinned.import")

    assert inspect_import(destination).errors == []


def test_load_skinning_tolerates_float32_weight_rounding(tmp_path: Path) -> None:
    """Thirds cannot sum to exactly 1 in float32; that must still import."""

    source = _reskinned_source(
        tmp_path,
        indices="0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0",
        weights=(
            "0.3333333, 0.3333333, 0.3333333, 0, "
            "1, 0, 0, 0, "
            "1, 0, 0, 0"
        ),
    )

    destination = generate_static_import(source, tmp_path / "Skinned.import")

    assert inspect_import(destination).errors == []


def test_generate_skeletal_material_subsets_reject_overlap(
    tmp_path: Path,
) -> None:
    source = _skinned_multi_material_source(tmp_path, overlap=True)
    destination = tmp_path / "OverlappingSkinnedMaterials.import"

    with pytest.raises(ImportGenerationError, match="overlapping material subsets"):
        generate_static_import(source, destination)

    assert not destination.exists()


def test_generate_multi_skeletal_import_is_deterministic(tmp_path: Path) -> None:
    source = _multi_skeletal_source(tmp_path)
    first = generate_static_import(
        source,
        tmp_path / "FirstSkinned.import",
        asset_name="TwoSkinnedMeshes",
    )
    second = generate_static_import(
        source,
        tmp_path / "SecondSkinned.import",
        asset_name="TwoSkinnedMeshes",
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


def test_generate_skeletal_multi_material_import_is_deterministic(
    tmp_path: Path,
) -> None:
    source = _skinned_multi_material_source(tmp_path)
    first = generate_static_import(
        source,
        tmp_path / "FirstSkinnedMaterials.import",
        asset_name="TwoSkinnedMeshes",
    )
    second = generate_static_import(
        source,
        tmp_path / "SecondSkinnedMaterials.import",
        asset_name="TwoSkinnedMeshes",
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


def test_generate_multi_skeletal_import_flattens_nested_armature_transform(
    tmp_path: Path,
) -> None:
    source = _multi_skeletal_source(tmp_path, nested_transform=True)

    asset = load_static_asset(source)

    assert len(asset.meshes) == 2
    assert all(
        mesh.skinning.armature_translation == pytest.approx((1.0, 2.0, 3.0))
        for mesh in asset.meshes
    )
    assert all(
        mesh.skinning.armature_scale == pytest.approx((2.0, 2.0, 2.0))
        for mesh in asset.meshes
    )


def test_generate_multi_skeletal_import_reads_time_sampled_uv_indices(
    tmp_path: Path,
) -> None:
    source = _multi_skeletal_source(tmp_path, time_sampled_uv_indices=True)

    asset = load_static_asset(source)

    assert all(
        mesh.face_uvs == ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
        for mesh in asset.meshes
    )


def test_generate_multi_skeletal_import_rejects_mixed_skinning(
    tmp_path: Path,
) -> None:
    source = _multi_skeletal_source(tmp_path, mixed_skinning=True)
    destination = tmp_path / "MixedSkinned.import"

    with pytest.raises(ImportGenerationError, match="cannot mix"):
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


def test_generate_static_import_classifies_truncated_bake_filename_from_graph(
    tmp_path: Path,
) -> None:
    source, texture_bytes = _textured_material_source(
        tmp_path,
        filename="VeryLongBakedMaterial_baseCo-deadbeef.png",
    )

    destination = generate_static_import(source, tmp_path / "Textured.import")

    assert len(list((destination / "materials").glob("*.tm_material"))) == 1
    texture_payloads = [
        path.read_bytes()
        for path in (destination / "textures").glob("*.tm_buffers/*")
    ]
    assert texture_payloads == [texture_bytes]


def test_generate_static_import_bounds_long_texture_record_names(
    tmp_path: Path,
) -> None:
    filename = f"{'VeryLongMaterialTextureName' * 8}_baseColor.png"
    source, _ = _textured_material_source(tmp_path, filename=filename)

    destination = generate_static_import(source, tmp_path / "Textured.import")

    buffer_directory = next((destination / "textures").glob("*.tm_buffers"))
    assert len(buffer_directory.name.encode("utf-8")) <= 131
    second = generate_static_import(source, tmp_path / "Second.import")
    assert next((second / "textures").glob("*.tm_buffers")).name == (
        buffer_directory.name
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


def _colliding_texture_stem_source(tmp_path: Path) -> Path:
    """Two different texture files that happen to share one filename stem."""

    for directory in ("a", "b"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "foo.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + directory.encode() * 8
        )
    source = tmp_path / "Colliding.usda"
    source.write_text(
        """#usda 1.0
(
    defaultPrim = "root"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "root"
{
    def Mesh "Cube" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        texCoord2f[] primvars:st = [(0, 0), (1, 0), (0, 1)] (
            interpolation = "vertex"
        )
        rel material:binding = </root/_materials/M>
    }
    def Scope "_materials"
    {
        def Material "M"
        {
            token outputs:mtlx:surface.connect = </root/_materials/M/Surface.outputs:out>
            def Shader "Surface"
            {
                uniform token info:id = "ND_realitykit_pbr_surfaceshader"
                color3f inputs:baseColor.connect = </root/_materials/M/BaseImage.outputs:out>
                float inputs:roughness.connect = </root/_materials/M/RoughImage.outputs:out>
                token outputs:out
            }
            def Shader "BaseImage"
            {
                uniform token info:id = "ND_image_color3"
                asset inputs:file = @a/foo.png@
                color3f outputs:out
            }
            def Shader "RoughImage"
            {
                uniform token info:id = "ND_image_float"
                asset inputs:file = @b/foo.png@
                float outputs:out
            }
        }
    }
}
""",
        encoding="utf-8",
    )
    return source


def test_generate_static_import_separates_colliding_texture_stems(
    tmp_path: Path,
) -> None:
    source = _colliding_texture_stem_source(tmp_path)

    destination = generate_static_import(source, tmp_path / "Colliding.import")

    textures = destination / "textures"
    assert len(list(textures.glob("*.tm_texture"))) == 2
    assert len(list(textures.glob("*.tm_buffers"))) == 2
    payloads = {
        path.parent.name: path.read_bytes()
        for path in textures.glob("*.tm_buffers/*")
    }
    assert sorted(payloads.values()) == [
        b"\x89PNG\r\n\x1a\n" + b"a" * 8,
        b"\x89PNG\r\n\x1a\n" + b"b" * 8,
    ]

    defined = set()
    for record in textures.glob("*.tm_texture"):
        defined.update(re.findall(r'__uuid: "([0-9a-f-]{36})"', record.read_text()))
    material = (destination / "materials" / "M.tm_material").read_text()
    referenced = set(re.findall(r'resource: "([0-9a-f-]{36})"', material))
    assert len(referenced) == 2
    assert referenced <= defined

    report = build_report(inspect_import(destination), rcp_build="80.0.1.500.1")
    assert report["record_types"]["tm_texture"] == 2


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
