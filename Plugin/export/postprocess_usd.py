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


def process_usd_stage(usd_path: str, settings, context, diagnostics=None, *, force_up_axis_y: bool = False) -> None:
    """Post-process a USD stage for RealityKit compatibility.

    ``force_up_axis_y`` is set by exports that ran the Y-up geometry bake: the
    bake clears ``convert_orientation`` (so ``normalize_scene`` won't author an
    up-axis and the exporter adds no root rotation), and the stage must be
    stamped ``upAxis=Y`` to match the natively Y-up geometry. Authoring it here,
    on the already-open stage, is the linchpin of the Y-up feature - without it
    the USD ships silently mis-oriented.
    """
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

        if force_up_axis_y:
            stage.SetMetadata("upAxis", "Y")

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
            diagnostics.add_warning("USD stage post-processed for RealityKit compatibility")
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
