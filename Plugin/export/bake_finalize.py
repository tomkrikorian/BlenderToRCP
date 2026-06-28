"""Shared post-bake export prep.

Used by both the interactive background runner (``bake_export_runner.py``) and
the CLI/API ``bake_export`` command so the two paths behave identically:
choosing Unlit vs Lit-PBR, and the optional Y-up geometry bake.
"""

from __future__ import annotations

import math

import bpy


def resolve_force_unlit(settings) -> bool:
    """Whether baked materials should be authored as RealityKit Unlit.

    "Lighting & Shadows" (LIT_IBL) bakes lighting into the albedo, so it must
    stay Unlit. "Material Color Only" (UNLIT_ALBEDO) honors the Unlit/Lit-PBR
    dropdown (default Unlit = original behavior; Lit PBR lets RealityKit light
    the baked color).
    """
    if str(getattr(settings, "bake_mode", "LIT_IBL")) == "UNLIT_ALBEDO":
        return str(getattr(settings, "bake_unlit_mode", "UNLIT")) == "UNLIT"
    return True


def apply_force_unlit(settings) -> None:
    settings.force_unlit_materials = resolve_force_unlit(settings)


def should_apply_yup(settings) -> bool:
    """Y-up geometry bake only applies when orientation conversion is enabled.

    The UI only exposes the ``apply_yup_geometry`` checkbox under
    ``convert_orientation``; this keeps the runtime behavior consistent with
    that, so a stale ``apply_yup_geometry=True`` does nothing while orientation
    conversion is off.
    """
    return bool(getattr(settings, "convert_orientation", False)) and bool(
        getattr(settings, "apply_yup_geometry", False)
    )


def apply_yup_geometry_bake(context, settings) -> None:
    """Bake a -90deg X rotation into geometry so the export is natively Y-up.

    Rotates and applies the rotation on the collection's direct children
    (top-level / unparented objects) only. Parented children inherit the
    rotation through their parent, so we don't recurse into deeper layers.
    Disables ``convert_orientation`` afterwards so the exporter doesn't author
    its own root -90deg on top.
    """
    from mathutils import Matrix

    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass

    ## Direct children of the collection = top-level (unparented) objects.
    roots = [obj for obj in context.scene.objects if obj.parent is None]

    Rg = Matrix.Rotation(math.radians(-90), 4, 'X')
    for obj in roots:
        obj.matrix_world = Rg @ obj.matrix_world
    context.view_layer.update()

    ## Bake the rotation into those same direct children.
    for obj in context.view_layer.objects:
        try:
            obj.select_set(False)
        except Exception:
            pass
    active = None
    for obj in roots:
        try:
            obj.select_set(True)
            if active is None:
                active = obj
        except Exception:
            continue
    if active is not None:
        context.view_layer.objects.active = active
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    ## Geometry is now natively Y-up; don't let the exporter add its own root -90deg.
    settings.convert_orientation = False


def set_stage_up_axis_y(usd_path) -> None:
    """Force the exported stage's upAxis to Y (geometry was baked Y-up).

    With ``convert_orientation=False`` the exporter won't author an up-axis, so
    set it explicitly to match the baked geometry.
    """
    try:
        from pxr import Usd, UsdGeom

        stage = Usd.Stage.Open(str(usd_path))
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        stage.GetRootLayer().Save()
    except Exception as exc:
        print("apply_yup_geometry: failed to set upAxis:", exc)
