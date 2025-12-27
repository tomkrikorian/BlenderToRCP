"""
Reality Composer Pro animation library authoring.

Reality Composer Pro can create "clips" by defining an AnimationLibrary
component in the USD. This module authors that minimal structure from the
export-time animation schedule recorded in diagnostics.
"""

from __future__ import annotations

from .usd_utils import Sdf


DEFAULT_SOURCE_ANIMATION_NAME = "default subtree animation"
DEFAULT_TRANSFORM_ANIMATION_NAME = "transform animation"
DEFAULT_SCENE_ANIMATION_NAME = "default scene animation"


def author_animation_library(stage, settings, diagnostics=None) -> None:
    """Author a minimal RCP AnimationLibrary with clip start times."""
    if not bool(getattr(settings, "export_animation", False)):
        return
    if diagnostics is None:
        return

    anim = diagnostics.data.get("animations") or {}
    segments = list(anim.get("segments") or [])
    if not segments:
        return

    default_prim = stage.GetDefaultPrim()
    if not default_prim:
        default_prim = _ensure_default_prim(stage)
        if not default_prim:
            return

    # Ensure increasing order; we use start_frame as the primary key.
    segments.sort(key=lambda s: float(s.get("start_frame", 0.0)))

    clip_names = _dedupe_clip_names([str(seg.get("name", "") or "Clip") for seg in segments])

    stage_start = float(stage.GetStartTimeCode() or 0.0)
    tps = float(stage.GetTimeCodesPerSecond() or 24.0)
    if tps <= 0.0:
        tps = 24.0

    start_times = []
    for seg in segments:
        start_frame = float(seg.get("start_frame", 0.0))
        # RCP stores clip offsets in seconds from the stage start time.
        start_times.append((start_frame - stage_start) / tps)

    root_path = default_prim.GetPath()
    lib_path = root_path.AppendChild("AnimationLibrary")

    # Clean up any previous library so repeated exports don't accumulate clip defs.
    try:
        if stage.GetPrimAtPath(str(lib_path)):
            stage.RemovePrim(str(lib_path))
    except Exception:
        pass

    lib_prim = stage.DefinePrim(str(lib_path), "RealityKitComponent")
    _set_uniform_attr(lib_prim, "info:id", Sdf.ValueTypeNames.Token, "RealityKit.AnimationLibrary")

    source_names = _pick_source_animation_names(stage)
    primary_source = source_names[0] if source_names else DEFAULT_SOURCE_ANIMATION_NAME

    for source_name in source_names:
        clip_def_name = _clip_definition_name(source_name)
        clip_path = lib_path.AppendChild(clip_def_name)
        clip_prim = stage.DefinePrim(str(clip_path), "RealityKitClipDefinition")
        _set_uniform_attr(clip_prim, "clipNames", Sdf.ValueTypeNames.StringArray, clip_names)
        _set_uniform_attr(clip_prim, "sourceAnimationName", Sdf.ValueTypeNames.String, source_name)
        _set_uniform_attr(clip_prim, "startTimes", Sdf.ValueTypeNames.DoubleArray, start_times)

    diagnostics.add_warning(
        f"Authored RCP AnimationLibrary clips ({len(clip_names)}) "
        f"for: {', '.join(repr(s) for s in source_names)}."
    )


def _dedupe_clip_names(names: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    out: list[str] = []
    for name in names:
        base = name or "Clip"
        count = counts.get(base, 0) + 1
        counts[base] = count
        if count == 1:
            out.append(base)
        else:
            # Append a number for duplicates. First occurrence keeps the base name.
            out.append(f"{base} {count - 1}")
    return out


def _set_uniform_attr(prim, name: str, type_name, value):
    # Author non-custom, uniform attributes to match Reality Composer Pro output.
    attr = prim.CreateAttribute(
        name,
        type_name,
        custom=False,
        variability=Sdf.VariabilityUniform,
    )
    attr.Set(value)


def _pick_source_animation_name(stage) -> str:
    """
    Reality Composer Pro presents different animation "sources" depending on how
    the USD encodes animation.

    Heuristic:
    - If the stage contains UsdSkel animation, use "default subtree animation".
    - Else if there are time-sampled xformOps, use "transform animation".
    - Else fall back to "default subtree animation" (and let RCP decide).
    """
    try:
        if _stage_contains_prim_type(stage, {"SkelAnimation", "Skeleton", "SkelRoot"}):
            return DEFAULT_SOURCE_ANIMATION_NAME
        if _stage_has_timesampled_xform_ops(stage):
            return DEFAULT_TRANSFORM_ANIMATION_NAME
    except Exception:
        # If inspection fails for any reason, keep previous default.
        return DEFAULT_SOURCE_ANIMATION_NAME
    return DEFAULT_SOURCE_ANIMATION_NAME


def _pick_source_animation_names(stage) -> list[str]:
    """
    Return a prioritized list of possible Reality Composer Pro animation source names.

    RCP naming isn't fully documented and can vary based on the kind of animation
    authored in the USD. To avoid missing clips when the "sourceAnimationName"
    doesn't match what RCP generated, we author multiple clip definitions (same
    clip names/start times) keyed to likely sources.
    """
    primary = _pick_source_animation_name(stage)
    out: list[str] = []

    def add(name: str) -> None:
        if name and name not in out:
            out.append(name)

    add(primary)

    # Always include the classic subtree name as a fallback, since many RCP files use it.
    add(DEFAULT_SOURCE_ANIMATION_NAME)

    # For transform-only exports, RCP often exposes "transform animation".
    try:
        if _stage_has_timesampled_xform_ops(stage):
            add(DEFAULT_TRANSFORM_ANIMATION_NAME)
    except Exception:
        pass

    # Leave room for future: default scene animation, blendshape animation, etc.
    # add(DEFAULT_SCENE_ANIMATION_NAME)

    return out


def _clip_definition_name(source_animation_name: str) -> str:
    # Match RCP's naming convention: "Clip_" + source name with spaces replaced by "_".
    safe = "_".join((source_animation_name or "").strip().lower().split())
    safe = safe or "default_subtree_animation"
    return f"Clip_{safe}"


def _stage_contains_prim_type(stage, type_names: set[str]) -> bool:
    for prim in stage.Traverse():
        if prim.GetTypeName() in type_names:
            return True
    return False


def _stage_has_timesampled_xform_ops(stage) -> bool:
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            name = attr.GetName()
            if not name.startswith("xformOp:"):
                continue
            # ValueMightBeTimeVarying() is cheap and avoids querying samples for constants.
            try:
                if attr.ValueMightBeTimeVarying():
                    return True
            except Exception:
                # Fall back to counting samples if the USD API wrapper doesn't expose it.
                try:
                    if attr.GetNumTimeSamples() > 0:
                        return True
                except Exception:
                    continue
    return False


def _ensure_default_prim(stage):
    """Pick a stable default prim if the stage doesn't define one."""
    try:
        root = stage.GetPseudoRoot()
        children = list(root.GetChildren())
        if not children:
            return None
        # Prefer the first Xform-like prim (common in Blender exports).
        for prim in children:
            if prim and prim.GetTypeName() in {"Xform", "Scope"}:
                stage.SetDefaultPrim(prim)
                return prim
        stage.SetDefaultPrim(children[0])
        return children[0]
    except Exception:
        return None
