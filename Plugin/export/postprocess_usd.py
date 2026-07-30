"""
USD post-processing pipeline for RealityKit compatibility.

Runs scene normalization, material rewriting, and texture preparation.
"""

from .materials.rewrite import rewrite_materials
from .materials.extract import (
    begin_image_staging_session,
    cleanup_image_staging_session,
)
from .usd_animation_library import author_animation_library
from .realitykit_preflight import (
    _record_diagnostics,
    validate_stage,
)
from .usd_scene import normalize_scene, _normalize_owned_double_sided_mesh_specs
from .usd_assets import prepare_assets
from .usd_utils import Usd, require_pxr


def process_usd_stage(usd_path: str, settings, context, diagnostics=None) -> None:
    """Post-process a USD stage for RealityKit compatibility."""
    require_pxr()

    stage = Usd.Stage.Open(usd_path, Usd.Stage.LoadAll)
    if not stage:
        raise RuntimeError(f"Failed to open USD stage: {usd_path}")

    # Material extraction may snapshot dirty/generated image pixels to disk.
    # Keep those files alive through the final texture localization, then clear
    # every export-local cache entry and temp file even if a later phase fails.
    begin_image_staging_session(diagnostics)
    try:
        # Resolve asset opinions while external source layers still retain their
        # original resolver anchors. Composition layers are then copied into the
        # export-owned namespace before any namespace or schema mutation occurs.
        writable_layer_paths = _run_step(
            diagnostics,
            "localize_source_dependencies",
            _prepare_assets,
            stage,
            usd_path,
            settings,
            diagnostics,
        )
        _run_step(
            diagnostics,
            "normalize_scene",
            _normalize_localized_scene,
            stage,
            settings,
            writable_layer_paths,
            diagnostics,
        )

        # Persist the localized, normalized layer stack before later passes can
        # add or rewrite composition arcs. Even a semantically identical Sdf
        # arc edit may trigger recomposition; no such reload may resurrect the
        # pre-normalized bytes copied from an external source layer.
        _run_step(
            diagnostics,
            "save_localized_layers",
            _save_stage,
            stage,
        )

        _run_step(diagnostics, "rewrite_materials", rewrite_materials, stage, settings, context, diagnostics)

        _run_step(diagnostics, "author_animation_library", author_animation_library, stage, settings, diagnostics)

        # Catch any asset opinions authored by material/animation post-processing.
        # All composition arcs already point to output-owned layers at this point.
        final_writable_layer_paths = _run_step(
            diagnostics,
            "finalize_assets",
            _prepare_assets,
            stage,
            usd_path,
            settings,
            diagnostics,
        )
        # Material/animation authoring normally adds only root-layer schemas,
        # but the final localization pass is the authoritative ownership set.
        # Re-run the raw Sdf normalization over that exact set so a newly
        # discovered inactive USD-valued asset cannot bypass the portable
        # double-sided contract. Already-normalized owners do not warn twice.
        _run_step(
            diagnostics,
            "normalize_finalized_meshes",
            _normalize_finalized_meshes,
            stage,
            final_writable_layer_paths,
            diagnostics,
        )
        # Before preflight: the retained preview network must not contradict
        # the MaterialX graph about the same image's colour space.
        _run_step(
            diagnostics,
            "normalize_preview_color_spaces",
            _normalize_preview_network_color_spaces,
            stage,
            diagnostics,
        )
        _run_step(
            diagnostics,
            "retag_unmapped_color_spaces",
            _retag_unmapped_color_space_names,
            stage,
            diagnostics,
        )
        _run_step(
            diagnostics,
            "realitykit_preflight",
            _require_realitykit_preflight,
            stage,
            usd_path,
            settings,
            diagnostics,
        )

        if diagnostics:
            diagnostics.begin_phase("stage_save", {"usd_path": usd_path})
        stage.Save()
        if diagnostics:
            diagnostics.end_phase("stage_save")

        if diagnostics:
            # A progress note, not a warning: it fires on every successful
            # export and consumed one of the few user-visible warning slots.
            diagnostics.add_info("USD stage post-processed for RealityKit compatibility")
    finally:
        cleanup_image_staging_session(diagnostics)


def _run_step(diagnostics, name: str, func, *args):
    if diagnostics:
        diagnostics.begin_phase(name)
    try:
        result = func(*args)
    except Exception as exc:
        if diagnostics:
            diagnostics.record_phase_error(name, exc)
        raise
    if diagnostics:
        diagnostics.end_phase(name)
    return result


def _normalize_localized_scene(stage, settings, writable_layer_paths, diagnostics=None):
    """Normalize only the root and dependency layers owned by this export."""
    return normalize_scene(
        stage,
        settings,
        writable_layer_paths=writable_layer_paths,
        diagnostics=diagnostics,
    )


def _normalize_finalized_meshes(stage, writable_layer_paths, diagnostics=None):
    """Normalize Mesh specs discovered by the authoritative final asset pass."""
    return _normalize_owned_double_sided_mesh_specs(
        writable_layer_paths,
        stage=stage,
        diagnostics=diagnostics,
    )


def _prepare_assets(stage, usd_path: str, settings, diagnostics=None):
    """Localize every direct asset opinion without composing it into root.

    Layer traversal preserves variant and instance-prototype authorship.  A
    composed ``Usd.Attribute.Set`` pass would instead create a stronger edit in
    the root layer and can silently collapse those authored choices.
    """
    return prepare_assets(
        stage,
        usd_path,
        diagnostics,
        settings=settings,
    )


def _save_stage(stage):
    """Persist only the root and currently composed output-owned layers."""
    stage.Save()


def _require_realitykit_preflight(stage, usd_path: str, settings, diagnostics=None):
    """Fail the shared UI/CLI/bake pipeline on strict OS 27 findings."""
    report = validate_stage(stage, usd_path, settings)
    if diagnostics is not None:
        _record_diagnostics(diagnostics, report)
    if report.errors:
        preview = "; ".join(issue.format() for issue in report.errors[:5])
        remaining = len(report.errors) - 5
        if remaining > 0:
            preview = f"{preview}; {remaining} more"
        raise RuntimeError(
            f"RealityKit OS 27 preflight failed with {len(report.errors)} "
            f"error(s): {preview}"
        )
    return report


def _normalize_preview_network_color_spaces(stage, diagnostics=None) -> None:
    """Make Blender's retained preview network agree with the MaterialX graph.

    The exporter emits two networks for the same material: the MaterialX
    ShaderGraph that RealityKit consumes, and the native UsdPreviewSurface
    network Blender authored, which is kept for other USD consumers such as
    Quick Look.

    ``textures._materialx_file_colorspace`` already decides that a Blender
    Non-Color image feeding a perceptual colour input is scene-linear, and
    authors ``lin_rec709`` for it. Blender tags its own copy of that same image
    ``data``, so the two networks disagreed about one file and preflight - which
    inspects the whole stage - rejected the export with
    TEXTURE_COLOR_SPACE_MISMATCH on the preview network's texture. The material
    was legal and the MaterialX graph was correct; nothing the user could change
    in Blender would fix it.

    Apply the same rule to the retained network rather than deleting it or
    exempting it from preflight: deleting would break the Quick Look path this
    network exists to serve, and exempting would let a genuinely wrong preview
    network ship unchecked.
    """
    from pxr import Sdf, UsdShade

    from .realitykit_preflight import (
        _COLOR_INPUT_TERMS,
        _DATA_TEXTURE_COLOR_SPACES,
        _normalize_color_space,
        _texture_color_space,
    )

    retagged = []
    for prim in stage.Traverse():
        shader = UsdShade.Shader(prim)
        if not shader:
            continue
        shader_id = shader.GetShaderId() if hasattr(shader, "GetShaderId") else None
        if str(shader_id or "") != "UsdUVTexture":
            continue

        file_input = shader.GetInput("file")
        if not file_input:
            continue
        attr = file_input.GetAttr()
        if not attr or attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
            continue

        # Resolve exactly the way preflight does. Blender authors this through
        # ColorSpaceAPI (`colorSpace:name`) on an ancestor prim rather than as
        # metadata on the attribute, so reading GetColorSpace() alone sees
        # nothing and every texture would be skipped.
        resolved = _normalize_color_space(_texture_color_space(file_input, shader))
        if resolved not in _DATA_TEXTURE_COLOR_SPACES:
            continue

        if not _feeds_perceptual_color_input(stage, shader, _COLOR_INPUT_TERMS):
            continue

        # Attribute metadata is the first thing preflight consults, so this
        # overrides the inherited ColorSpaceAPI opinion for this texture only.
        attr.SetColorSpace("lin_rec709")
        retagged.append(str(prim.GetPath()))

    if retagged and diagnostics:
        diagnostics.add_warning(
            "Retagged the retained preview network's colour textures as "
            "lin_rec709 to match the MaterialX graph: "
            + ", ".join(sorted(retagged))
        )


#: ColorSpaceAPI tokens Blender 5.2 authors that RCP 3.0 (80.0.1.500.1) has no
#: alias for, mapped to the engine-known token with the same encoding.
#: Measured: CoreRE's alias table carries ``srgb_texture``/``sRGB``/``srgb_tx``
#: and ``srgb_rec709_scene``, but the string ``srgb_rec709_display`` appears
#: nowhere in the app bundle — its decode behaviour is undefined. Both names
#: describe the same sRGB transfer on Rec.709 primaries, so the rewrite is a
#: renaming, not a conversion.
_COLOR_SPACE_NAME_REWRITES = {
    "srgb_rec709_display": "srgb_texture",
}


def _retag_unmapped_color_space_names(stage, diagnostics=None) -> None:
    """Rewrite authored ``colorSpace:name`` tokens RCP cannot interpret."""
    retagged = {}
    for prim in stage.Traverse():
        attribute = prim.GetAttribute("colorSpace:name")
        if not attribute or not attribute.HasAuthoredValue():
            continue
        authored = str(attribute.Get() or "")
        replacement = _COLOR_SPACE_NAME_REWRITES.get(authored)
        if replacement is None:
            continue
        attribute.Set(replacement)
        retagged[str(prim.GetPath())] = (authored, replacement)

    if retagged and diagnostics:
        pairs = sorted({change for change in retagged.values()})
        diagnostics.add_info(
            "Renamed Blender colour-space tokens RealityKit has no alias for: "
            + ", ".join(f"{old} -> {new}" for old, new in pairs)
            + f" ({len(retagged)} prims)"
        )


def _feeds_perceptual_color_input(stage, shader, color_terms) -> bool:
    """Whether this texture shader drives a colour input on a surface shader."""
    from pxr import UsdShade

    source_path = shader.GetPath()
    for prim in stage.Traverse():
        consumer = UsdShade.Shader(prim)
        if not consumer:
            continue
        for consumer_input in consumer.GetInputs():
            name = consumer_input.GetBaseName().lower().replace("-", "_")
            if not any(term in name for term in color_terms):
                continue
            for connection in consumer_input.GetAttr().GetConnections():
                if connection.GetPrimPath() == source_path:
                    return True
    return False
