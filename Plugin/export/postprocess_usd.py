"""
USD post-processing pipeline for RealityKit compatibility.

Runs scene normalization, material rewriting, and texture preparation.
"""

from .materials.rewrite import rewrite_materials
from .usd_animation_library import author_animation_library
from .usd_scene import normalize_scene
from .usd_textures import prepare_textures
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

    _run_step(diagnostics, "normalize_scene", normalize_scene, stage, settings)

    if force_up_axis_y:
        stage.SetMetadata("upAxis", "Y")

    _run_step(diagnostics, "rewrite_materials", rewrite_materials, stage, settings, context, diagnostics)

    _run_step(diagnostics, "author_animation_library", author_animation_library, stage, settings, diagnostics)

    _run_step(diagnostics, "prepare_textures", prepare_textures, stage, usd_path, settings, diagnostics)
    _run_step(diagnostics, "prepare_assets", prepare_assets, stage, usd_path, diagnostics)

    if diagnostics:
        diagnostics.begin_phase("stage_save", {"usd_path": usd_path})
    stage.Save()
    if diagnostics:
        diagnostics.end_phase("stage_save")

    if diagnostics:
        diagnostics.add_warning("USD stage post-processed for RealityKit compatibility")


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
