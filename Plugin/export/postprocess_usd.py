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


def process_usd_stage(usd_path: str, settings, context, diagnostics=None) -> None:
    """Post-process a USD stage for RealityKit compatibility."""
    require_pxr()

    stage = Usd.Stage.Open(usd_path, Usd.Stage.LoadAll)
    if not stage:
        raise RuntimeError(f"Failed to open USD stage: {usd_path}")

    normalize_scene(stage, settings)

    rewrite_materials(stage, settings, context, diagnostics)

    author_animation_library(stage, settings, diagnostics)

    prepare_textures(stage, usd_path, settings, diagnostics)
    prepare_assets(stage, usd_path, diagnostics)

    stage.Save()

    if diagnostics:
        diagnostics.add_warning("USD stage post-processed for RealityKit compatibility")
