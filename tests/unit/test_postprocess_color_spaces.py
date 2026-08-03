"""The postprocess must not ship colour-space tokens RCP cannot interpret.

Measured against RealityComposerPro.app 80.0.1.500.1: the CoreRE engine's
alias table knows ``srgb_texture``, ``srgb_rec709_scene``, ``lin_rec709``,
``lin_rec709_scene``, ``raw``/``data``/``none`` — but ``srgb_rec709_display``,
the token Blender 5.2 authors through ColorSpaceAPI on every sRGB texture
prim, appears nowhere in the app. Its decode behaviour is undefined, so the
postprocess retags it to the engine-known equivalent encoding,
``srgb_texture``, before preflight runs.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pxr")
from pxr import Sdf, Usd, UsdShade  # noqa: E402

from Plugin.export.diagnostics import ExportDiagnostics  # noqa: E402
from Plugin.export.postprocess_usd import (  # noqa: E402
    _retag_unmapped_color_space_names,
)


def _stage_with_api_color_space(token: str):
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Root", "Xform")
    stage.SetDefaultPrim(root)

    texture = UsdShade.Shader.Define(stage, "/Root/Material/Image_Texture")
    texture.CreateIdAttr("UsdUVTexture")
    prim = texture.GetPrim()
    Usd.ColorSpaceAPI.Apply(prim).CreateColorSpaceNameAttr(token)
    return stage, prim


def _name_token(prim) -> str:
    return str(prim.GetAttribute("colorSpace:name").Get())


def test_display_token_is_retagged_to_srgb_texture():
    stage, prim = _stage_with_api_color_space("srgb_rec709_display")
    diagnostics = ExportDiagnostics()

    _retag_unmapped_color_space_names(stage, diagnostics)

    assert _name_token(prim) == "srgb_texture"


def test_engine_known_tokens_are_left_alone():
    for token in ("srgb_texture", "srgb_rec709_scene", "lin_rec709_scene", "data"):
        stage, prim = _stage_with_api_color_space(token)

        _retag_unmapped_color_space_names(stage, None)

        assert _name_token(prim) == token, token


def test_retag_is_reported_as_info_not_warning():
    """Every sRGB-textured Blender export hits this rewrite; it is expected
    normalization, not a problem the user must react to."""
    stage, _prim = _stage_with_api_color_space("srgb_rec709_display")
    diagnostics = ExportDiagnostics()

    _retag_unmapped_color_space_names(stage, diagnostics)

    warnings = diagnostics.data.get("warnings") or []
    assert not any("srgb_rec709_display" in w for w in warnings)
    infos = diagnostics.data.get("info") or []
    assert any("srgb_rec709_display" in note for note in infos)


def test_preview_normal_map_scale_bias_is_clamped_to_spec():
    """Blender 5.2 writes scale (2,2,2,2) / bias (-1,-1,-1,-1) on normal-map
    textures. UsdPreviewSurface remaps only RGB; scaling alpha by 2 and biasing
    it by -1 is off-spec, and Reality Composer Pro converts the out-of-range
    alpha into NaN in the imported material."""
    from pxr import Gf
    from Plugin.export.postprocess_usd import _normalize_preview_normal_map_transform

    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Root", "Xform")
    stage.SetDefaultPrim(root)
    shader = UsdShade.Shader.Define(stage, "/Root/Material/Image_Texture")
    shader.CreateIdAttr("UsdUVTexture")
    shader.CreateInput("scale", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(2, 2, 2, 2))
    shader.CreateInput("bias", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(-1, -1, -1, -1))

    _normalize_preview_normal_map_transform(stage, None)

    assert tuple(shader.GetInput("scale").Get()) == (2.0, 2.0, 2.0, 1.0)
    assert tuple(shader.GetInput("bias").Get()) == (-1.0, -1.0, -1.0, 0.0)


def test_unrelated_scale_bias_is_left_alone():
    """Only the exact normal-map encoding pattern is rewritten."""
    from pxr import Gf
    from Plugin.export.postprocess_usd import _normalize_preview_normal_map_transform

    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Root", "Xform")
    stage.SetDefaultPrim(root)
    shader = UsdShade.Shader.Define(stage, "/Root/Material/Tint")
    shader.CreateIdAttr("UsdUVTexture")
    shader.CreateInput("scale", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(1, 1, 1, 1))
    shader.CreateInput("bias", Sdf.ValueTypeNames.Float4).Set(Gf.Vec4f(0, 0, 0, 0))

    _normalize_preview_normal_map_transform(stage, None)

    assert tuple(shader.GetInput("scale").Get()) == (1.0, 1.0, 1.0, 1.0)
    assert tuple(shader.GetInput("bias").Get()) == (0.0, 0.0, 0.0, 0.0)
