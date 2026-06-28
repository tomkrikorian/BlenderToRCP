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


def apply_yup_geometry_bake(context, settings, objects=None) -> None:
    """Bake a -90deg X rotation into geometry so the export is natively Y-up.

    Every exported object's world geometry ends up rotated -90deg about X (Z-up
    -> Y-up). The rotation is baked into each unique *mesh datablock* exactly
    once (``mesh.transform``), and each object's transform is adjusted to hold
    its world placement, so linked / instanced duplicates keep sharing a single
    mesh. (The old approach rotated each object then called
    ``bpy.ops.object.transform_apply``, which refuses multi-user data and, on its
    ``make_single_user`` fallback, split shared meshes into per-object copies —
    silently destroying instancing.)

    Scope: a full-scene export rotates every object in the scene; a
    selected-objects-only export (``objects`` given) rotates exactly that set.
    Hierarchy-isolated objects (no in-scope parent or child) get their mesh
    baked and their transform conjugated; parented sub-hierarchies are rotated
    by left-multiplying their root only, so in-scope children inherit the
    rotation cleanly instead of being set explicitly.

    Disables ``convert_orientation`` afterwards so the exporter doesn't author
    its own root -90deg on top.
    """
    from mathutils import Matrix

    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass

    scope = list(objects) if objects is not None else list(context.scene.objects)
    if not scope:
        settings.convert_orientation = False
        return
    scope_set = set(scope)

    Rg = Matrix.Rotation(math.radians(-90), 4, 'X')
    Rg_inv = Rg.inverted()

    ## Classify scope objects by their in-scope hierarchy. We only ever set a
    ## child's world by inheritance, never explicitly: assigning a child's
    ## matrix_world right after its parent moved is unreliable in Blender (the
    ## next depsgraph update recomputes it from the basis and drifts it off).
    def has_in_scope_ancestor(obj):
        parent = obj.parent
        while parent is not None:
            if parent in scope_set:
                return True
            parent = parent.parent
        return False

    in_scope_ancestor = {obj: has_in_scope_ancestor(obj) for obj in scope}
    has_in_scope_descendant = {obj: False for obj in scope}
    for obj in scope:
        if in_scope_ancestor[obj]:
            parent = obj.parent
            while parent is not None:
                if parent in scope_set:
                    has_in_scope_descendant[parent] = True
                parent = parent.parent

    def isolated(obj):
        return not in_scope_ancestor[obj] and not has_in_scope_descendant[obj]

    ## Bake Rg into a mesh only when every object using it is (a) in scope and
    ## (b) hierarchy-isolated, so conjugating each user can't disturb a parented
    ## relative. ``mesh.transform`` mutates the datablock globally, so the user
    ## map is built from ``bpy.data.objects`` (not just this scene) to catch
    ## linked / other-scene users. Meshes that don't qualify stay un-baked and
    ## their objects rotate via the transform — instancing is preserved either
    ## way (a shared mesh is simply touched zero or one time, never split).
    mesh_users = {}
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data is not None:
            mesh_users.setdefault(obj.data, set()).add(obj)

    baked_meshes = set()
    for obj in scope:
        if obj.type == 'MESH' and obj.data is not None:
            mesh = obj.data
            if mesh in baked_meshes:
                continue
            users = mesh_users.get(mesh, set())
            if users <= scope_set and all(isolated(u) for u in users):
                try:
                    ## shape_keys=True so shape-key coordinates rotate with the
                    ## base mesh; otherwise keyed meshes would deform wrongly.
                    mesh.transform(Rg, shape_keys=True)
                    mesh.update()
                    baked_meshes.add(mesh)
                except Exception as exc:
                    print("apply_yup_geometry: mesh.transform failed:", exc)

    ## Snapshot world matrices before moving anything.
    old_world = {obj: obj.matrix_world.copy() for obj in scope}

    ## Isolated objects whose mesh was baked: conjugate so the world result is
    ## exactly Rg @ world (holds for any transform, incl. non-uniform scale)
    ## while the shared mesh is touched only once. These have no in-scope
    ## children, so nothing inherits this transform.
    for obj in scope:
        if obj.type == 'MESH' and obj.data in baked_meshes:
            obj.matrix_world = Rg @ old_world[obj] @ Rg_inv

    ## Everything else (lights/empties/cameras, un-baked meshes, and parented
    ## sub-hierarchies): rotate by left-multiply, but only on the roots of these
    ## sub-trees. In-scope children are skipped and inherit Rg through the
    ## parent — left-multiplication propagates cleanly to descendants, whereas
    ## conjugation does not.
    for obj in scope:
        if obj.type == 'MESH' and obj.data in baked_meshes:
            continue
        if obj.parent is not None and obj.parent in scope_set:
            continue  # in-scope child: inherits from its rotated ancestor
        obj.matrix_world = Rg @ old_world[obj]

    context.view_layer.update()

    ## Geometry is now natively Y-up; don't let the exporter add its own root -90deg.
    settings.convert_orientation = False


def set_stage_up_axis_y(usd_path, diagnostics=None) -> None:
    """Force the exported stage's upAxis to Y (geometry was baked Y-up).

    With ``convert_orientation=False`` the exporter won't author an up-axis, so
    set it explicitly to match the baked geometry. This is the linchpin of the
    Y-up feature, so a failure is surfaced through diagnostics (not just stdout)
    — otherwise the USD would silently ship mis-oriented.
    """
    try:
        from pxr import Usd, UsdGeom

        stage = Usd.Stage.Open(str(usd_path))
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        stage.GetRootLayer().Save()
    except Exception as exc:
        message = f"apply_yup_geometry: failed to set upAxis: {exc}"
        print(message)
        if diagnostics is not None:
            try:
                diagnostics.add_warning(message)
            except Exception:
                pass
