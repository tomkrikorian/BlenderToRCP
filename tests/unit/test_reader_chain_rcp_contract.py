"""The MaterialX reader chains Reality Composer Pro 3.0 can instantiate.

RCP 3.0 (80.0.1.500.1) substitutes a striped placeholder material for the whole
ShaderGraph when it cannot instantiate a node chain. Two authoring habits of
this exporter triggered that: a four-channel ``ND_image_vector4`` read paired
with ``ND_swizzle_vector4_float``, and a lowercase ``colorSpace = "raw"`` token
on the reader's ``inputs:file``.

Neither id nor that token appears in any RCP-authored or shipping RealityKit
package. The chains pinned here are the ones that do:

* packed scalars  -> ``ND_image_color3`` + ``ND_swizzle_color3_float``
* normal maps     -> ``ND_image_vector3`` + ``ND_normal_map_decode``
* genuine alpha   -> ``ND_image_color4`` + ``ND_separate4_color4``

and data-role readers author no color space at all.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from Plugin.export.materials.author import create_materialx_material
from Plugin.export.materials.graph import MaterialXGraphBuilder
from Plugin.export.materials.textures import _create_texture_connection
from Plugin.export.usd_utils import PXR_AVAILABLE, Usd, UsdShade
from Plugin.manifest.materialx_nodes import load_manifest


pytestmark = pytest.mark.skipif(
    not PXR_AVAILABLE, reason="OpenUSD bindings required"
)

#: Reader and extractor ids present in the manifest but absent from every
#: working RealityKit package measured on macOS 27 / RCP 3.0.
UNSUPPORTED_READER_IDS = (
    "ND_image_vector4",
    "ND_swizzle_vector4_float",
    "ND_extract_vector4",
    "ND_separate4_vector4",
)


def _manifest():
    return load_manifest()


class _Diagnostics:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def add_warning(self, message):
        self.warnings.append(message)

    def add_error(self, message):
        self.errors.append(message)

    def add_ktx_required_node(self, *args, **kwargs):  # pragma: no cover
        pass


def _shaders_by_id(stage) -> dict[str, list]:
    result: dict[str, list] = {}
    for prim in stage.Traverse():
        shader = UsdShade.Shader(prim)
        if not shader:
            continue
        shader_id = str(shader.GetIdAttr().Get() or "")
        if shader_id:
            result.setdefault(shader_id, []).append(shader)
    return result


def _authored_ids(stage) -> set[str]:
    return set(_shaders_by_id(stage))


def _source_id(shader, input_name: str) -> str:
    source = shader.GetInput(input_name).GetConnectedSource()
    assert source, f"{input_name} is not connected"
    return str(UsdShade.Shader(source[0].GetPrim()).GetIdAttr().Get() or "")


def _packed_orm_stage():
    """Roughness from G and metallic from B of one three-channel ORM file."""
    stage = Usd.Stage.CreateInMemory()
    manifest = _manifest()
    cache: dict = {}
    for input_name, channel in (("roughness", "g"), ("metallic", "b")):
        _create_texture_connection(
            stage,
            "/Material",
            input_name,
            {
                "path": "textures/orm.png",
                "type": "texture",
                "output_type": "float",
                "channel": channel,
                "colorspace": "raw",
                "colorspace_role": "data",
                "source_has_alpha": False,
            },
            manifest,
            "Material",
            cache,
        )
    return stage


def test_packed_orm_reads_one_color3_reader_with_two_component_reads():
    stage = _packed_orm_stage()
    shaders = _shaders_by_id(stage)

    readers = shaders.get("ND_image_color3", [])
    assert len(readers) == 1, (
        "one file, one reader: every working package hangs N component reads "
        f"off a single image node, got {sorted(shaders)}"
    )
    # A component read is convert + dotproduct-with-a-unit-mask. `swizzle`
    # resolves in RealityKit's nodedef store but has no Metal implementation,
    # so it yields a material with no compiled shader graph.
    assert not shaders.get("ND_swizzle_color3_float")
    converts = shaders.get("ND_convert_color3_vector3", [])
    assert len(converts) == 1, "one reader, one convert, N masks"
    dots = shaders.get("ND_dotproduct_vector3", [])
    assert len(dots) == 2
    masks = {tuple(shader.GetInput("in2").Get()) for shader in dots}
    assert masks == {(0.0, 1.0, 0.0), (0.0, 0.0, 1.0)}, masks
    for shader in dots:
        assert _source_id(shader, "in1") == "ND_convert_color3_vector3"


def test_packed_orm_authors_no_vector4_reader_or_swizzle():
    authored = _authored_ids(_packed_orm_stage())
    assert not authored & set(UNSUPPORTED_READER_IDS), (
        "RCP 3.0 replaces the whole material with the striped placeholder "
        f"when these are authored: {sorted(authored & set(UNSUPPORTED_READER_IDS))}"
    )


def test_data_reader_authors_no_color_space_and_color_reader_keeps_srgb():
    stage = Usd.Stage.CreateInMemory()
    manifest = _manifest()
    _create_texture_connection(
        stage,
        "/Material",
        "roughness",
        {
            "path": "textures/orm.png",
            "type": "texture",
            "output_type": "float",
            "channel": "g",
            "colorspace": "raw",
            "colorspace_role": "data",
        },
        manifest,
        "Material",
    )
    _create_texture_connection(
        stage,
        "/Material",
        "baseColor",
        {
            "path": "textures/albedo.png",
            "type": "texture",
            "output_type": "color3",
            "colorspace": "srgb",
            "colorspace_role": "color",
        },
        manifest,
        "Material",
    )
    shaders = _shaders_by_id(stage)
    spaces = {
        str(shader.GetInput("file").Get().path):
            shader.GetInput("file").GetAttr().GetColorSpace()
        for shader in shaders["ND_image_color3"]
    }
    assert spaces["textures/orm.png"] == "", (
        "an absent color space is MaterialX's no-transform contract; the "
        "lowercase 'raw' token appears in no shipping RealityKit package"
    )
    assert spaces["textures/albedo.png"] == "srgb_texture"


def test_data_texture_tagged_srgb_still_fails_closed():
    stage = Usd.Stage.CreateInMemory()
    with pytest.raises(ValueError, match="must use Blender Non-Color/raw"):
        _create_texture_connection(
            stage,
            "/Material",
            "roughness",
            {
                "path": "textures/orm.png",
                "type": "texture",
                "output_type": "float",
                "channel": "g",
                "colorspace": "srgb",
                "colorspace_role": "data",
            },
            _manifest(),
            "Material",
        )


@pytest.mark.parametrize(
    "profile,surface_id",
    [
        ("realitykit_portable", "ND_realitykit_pbr_surfaceshader"),
        ("realitykit_pbr2", "ND_realitykit_pbr_surfaceshader_2_0"),
    ],
)
def test_normal_map_chain_is_identical_on_both_surface_profiles(profile, surface_id):
    manifest = _manifest()
    graph = MaterialXGraphBuilder(manifest, surface_profile=profile).build_pbr_material(
        {
            "normal_texture": "textures/normal.png",
            "normal_texture_colorspace": "raw",
            "normal_texture_space": "tangent",
        }
    )
    stage = Usd.Stage.CreateInMemory()
    create_materialx_material(stage, "/Material", "Material", graph, manifest)
    shaders = _shaders_by_id(stage)

    assert set(shaders) & set(UNSUPPORTED_READER_IDS) == set()
    reader = shaders["ND_image_vector3"][0]
    assert reader.GetInput("file").GetAttr().GetColorSpace() == ""
    assert tuple(reader.GetInput("default").Get()) == (0.5, 0.5, 1.0), (
        "an unresolved normal reader must fall back to a flat normal, not to "
        "the nodedef's (0,0,0), which decodes to (-1,-1,-1)"
    )

    decode = shaders["ND_normal_map_decode"][0]
    assert _source_id(decode, "in") == "ND_image_vector3"

    surface = shaders[surface_id][0]
    assert _source_id(surface, "normal") == "ND_normal_map_decode"


def test_alpha_from_a_three_channel_source_is_refused_not_read_as_color4():
    """A 4-channel read of a 3-channel file is the reported defect."""
    stage = Usd.Stage.CreateInMemory()
    diagnostics = _Diagnostics()
    output = _create_texture_connection(
        stage,
        "/Material",
        "opacity",
        {
            "path": "textures/orm.png",
            "type": "texture",
            "output_type": "float",
            "channel": "a",
            "colorspace": "raw",
            "colorspace_role": "data",
            "source_has_alpha": False,
            "source_channels": 3,
        },
        _manifest(),
        "Material",
        diagnostics=diagnostics,
    )
    assert output is None, "the input must fall back to its authored default"
    assert _authored_ids(stage) == set()
    assert any(
        "orm.png" in message and "alpha" in message.lower()
        for message in diagnostics.warnings
    ), diagnostics.warnings


def test_alpha_from_a_four_channel_source_uses_color4_and_separate4():
    stage = Usd.Stage.CreateInMemory()
    _create_texture_connection(
        stage,
        "/Material",
        "opacity",
        {
            "path": "textures/sprite.png",
            "type": "texture",
            "output_type": "float",
            "channel": "a",
            "colorspace": "srgb",
            "colorspace_role": "data",
            "source_has_alpha": True,
            "source_channels": 4,
        },
        _manifest(),
        "Material",
    )
    shaders = _shaders_by_id(stage)
    assert list(shaders["ND_image_color4"])
    separate = shaders["ND_separate4_color4"][0]
    assert _source_id(separate, "in") == "ND_image_color4"
    assert set(shaders) & set(UNSUPPORTED_READER_IDS) == set()


def test_every_authored_id_is_manifest_backed_and_editor_resolvable():
    manifest = _manifest()
    stages = [_packed_orm_stage()]
    for profile in ("realitykit_portable", "realitykit_pbr2"):
        graph = MaterialXGraphBuilder(
            manifest, surface_profile=profile
        ).build_pbr_material(
            {
                "base_color_texture": "textures/albedo.png",
                "base_color_texture_colorspace": "sRGB",
                "roughness_texture": "textures/orm.png",
                "roughness_texture_channel": "g",
                "roughness_texture_colorspace": "raw",
                "metallic_texture": "textures/orm.png",
                "metallic_texture_channel": "b",
                "metallic_texture_colorspace": "raw",
                "normal_texture": "textures/normal.png",
                "normal_texture_colorspace": "raw",
            }
        )
        stage = Usd.Stage.CreateInMemory()
        create_materialx_material(stage, "/Material", "Material", graph, manifest)
        stages.append(stage)

    authored: set[str] = set()
    for stage in stages:
        authored |= _authored_ids(stage)
    assert authored

    nodes = manifest["nodes"]
    missing = sorted(name for name in authored if name not in nodes)
    assert missing == [], f"fabricated nodedefs: {missing}"
    unresolvable = sorted(
        name
        for name in authored
        if nodes[name].get("policy", {}).get("editor_unresolvable")
    )
    assert unresolvable == [], (
        f"nodedefs Reality Composer Pro's editor cannot resolve: {unresolvable}"
    )
    assert authored & set(UNSUPPORTED_READER_IDS) == set()
