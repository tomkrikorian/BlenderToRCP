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

    "Material Color Only - Lit PBR" (LIT_ALBEDO) authors Lit PBR so
    RealityKit lights the baked color. Every other mode stays Unlit:
    "Material Color Only - Unlit" (UNLIT_ALBEDO) by design, and "Lighting &
    Shadows" (LIT_IBL) because it bakes lighting into the albedo.
    """
    return str(getattr(settings, "bake_mode", "LIT_IBL")) != "LIT_ALBEDO"


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


## Object-level transform channels whose animation would silently clobber the
## world matrices the Y-up bake assigns (fcurves re-evaluate on every depsgraph
## update, overwriting matrix_basis while the mesh data stays rotated).
_TRANSFORM_DATA_PATHS = (
    "location",
    "rotation_euler",
    "rotation_quaternion",
    "rotation_axis_angle",
    "scale",
    "delta_location",
    "delta_rotation_euler",
    "delta_rotation_quaternion",
    "delta_scale",
)


def _action_has_transform_fcurves(action) -> bool:
    try:
        return any(
            str(fcurve.data_path).startswith(_TRANSFORM_DATA_PATHS)
            for fcurve in getattr(action, "fcurves", []) or []
        )
    except Exception:
        # Can't inspect the action (e.g. a future layered-action API change):
        # treat it as animated, skipping the bake is always safe.
        return True


def _yup_unsafe_reason(obj) -> str | None:
    """Why the Y-up geometry bake cannot preserve *obj*, or None if it can.

    The bake works by assigning ``matrix_world`` (and rotating mesh data), which
    only holds for objects whose transform is authored by their loc/rot/scale
    channels. Anything that re-derives the transform at depsgraph evaluation -
    transform fcurves, drivers, NLA strips, enabled constraints - overwrites the
    assignment, leaving rotated verts under an un-rotated transform. Armature
    deformation is likewise unsafe: the skinned result lives in armature space,
    which the per-mesh conjugation does not account for.
    """
    anim = getattr(obj, "animation_data", None)
    if anim is not None:
        action = getattr(anim, "action", None)
        if action is not None and _action_has_transform_fcurves(action):
            return "animated transform"
        try:
            for driver in getattr(anim, "drivers", []) or []:
                if str(driver.data_path).startswith(_TRANSFORM_DATA_PATHS):
                    return "driver-driven transform"
        except Exception:
            return "driver-driven transform"
        try:
            for track in getattr(anim, "nla_tracks", []) or []:
                for strip in getattr(track, "strips", []) or []:
                    if _action_has_transform_fcurves(getattr(strip, "action", None)):
                        return "NLA-animated transform"
        except Exception:
            return "NLA-animated transform"
    try:
        if any(not getattr(c, "mute", False) for c in getattr(obj, "constraints", []) or []):
            return "constrained transform"
    except Exception:
        return "constrained transform"
    if getattr(obj, "type", None) == 'MESH':
        try:
            if any(m.type == 'ARMATURE' for m in getattr(obj, "modifiers", []) or []):
                return "armature-deformed"
        except Exception:
            return "armature-deformed"
    return None


def maybe_apply_yup_geometry_bake(context, settings, objects_to_export=None, diagnostics=None):
    """Single entry point for the pre-export Y-up geometry protocol.

    Owns the whole decision so the four export paths can't drift: the settings
    gate (``should_apply_yup``), the selected-objects scope, and a safety
    preflight that skips the bake when any scoped object's transform can't be
    preserved (animated / driver-driven / constrained transforms, or
    armature-deformed meshes - see ``_yup_unsafe_reason``).

    Returns the restore-state dict when the bake ran, else ``None``. On the
    skip path ``settings.convert_orientation`` is left untouched, so the
    exporter still authors its root orientation conversion and the export
    remains correct (just not natively Y-up). Callers pass
    ``force_up_axis_y=(state is not None)`` to
    ``postprocess_usd.process_usd_stage`` and, for live-scene exports, hand the
    state to ``restore_yup_geometry_bake`` in a ``finally``.
    """
    if not should_apply_yup(settings):
        return None

    if getattr(settings, "selected_objects_only", False):
        scope = (
            list(objects_to_export)
            if objects_to_export is not None
            else list(context.selected_objects)
        )
    else:
        scope = None

    check_objects = scope if scope is not None else list(context.scene.objects)
    unsafe = [
        (obj, reason)
        for obj, reason in ((obj, _yup_unsafe_reason(obj)) for obj in check_objects)
        if reason
    ]
    if unsafe:
        listed = ", ".join(f"'{obj.name}' ({reason})" for obj, reason in unsafe[:5])
        if len(unsafe) > 5:
            listed += f", and {len(unsafe) - 5} more"
        message = (
            f"Y-up geometry bake skipped: {len(unsafe)} object(s) have transforms "
            f"the bake cannot preserve ({listed}). Exporting with root "
            "orientation conversion instead."
        )
        print(message)
        if diagnostics is not None:
            try:
                diagnostics.add_warning(message)
            except Exception:
                pass
        return None

    return apply_yup_geometry_bake(context, settings, scope, diagnostics=diagnostics)


def apply_yup_geometry_bake(context, settings, objects=None, diagnostics=None) -> dict:
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
    Each unique mesh datablock whose users are all in scope is baked once
    (instancing preserved); then every object's transform is rewritten in
    closed form (see the basis-rewrite comment in the body). A baked mesh's
    object is conjugated (``Rg @ world @ Rg_inv``) so the baked verts land at
    ``Rg @ world``; lights / cameras / un-baked meshes are left-multiplied
    (``Rg @ world``) to carry the rotation on their transform. Plain grouping
    empties are conjugated too, keeping them valid parent frames (an empty at
    identity stays identity - no -90 wrapper appears on group roots).
    Collection-instance empties carry their prototype content, which lives
    outside the mesh bake, so their instance transform is adjusted to carry
    the rotation (see ``_instancer_world``).

    Disables ``convert_orientation`` afterwards so the exporter doesn't author
    its own root -90deg on top.

    Returns a restore-state dict (baked meshes, per-object local-transform
    snapshot, the inverse rotation, and the original ``convert_orientation``)
    that ``restore_yup_geometry_bake`` consumes to undo this for an in-process
    export. The background bake runner ignores it (its scene is throwaway).
    """
    from mathutils import Matrix, Vector

    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass

    orig_convert_orientation = bool(getattr(settings, "convert_orientation", False))
    scope = list(objects) if objects is not None else list(context.scene.objects)
    if not scope:
        settings.convert_orientation = False
        return {
            "baked_meshes": set(),
            "orig_basis": {},
            "orig_parent_inverse": {},
            "rg_inv": None,
            "orig_convert_orientation": orig_convert_orientation,
        }
    scope_set = set(scope)

    Rg = Matrix.Rotation(math.radians(-90), 4, 'X')
    Rg_inv = Rg.inverted()

    ## Snapshot each scope object's local transform and parent-inverse
    ## (order-independent, unlike matrix_world) so an in-process export can
    ## restore the scene exactly - the rewrite below touches both.
    orig_basis = {obj: obj.matrix_basis.copy() for obj in scope}
    orig_parent_inverse = {obj: obj.matrix_parent_inverse.copy() for obj in scope}

    ## Bake Rg into a mesh datablock only when every object using it is in scope,
    ## so the shared datablock bake is valid for all users and instancing is
    ## preserved (the datablock is touched at most once, never split). The user
    ## map is built from ``bpy.data.objects`` - not just this scene - to catch
    ## linked / other-scene users that the bake would otherwise corrupt.
    mesh_users = {}
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data is not None:
            mesh_users.setdefault(obj.data, set()).add(obj)

    baked_meshes = set()
    for obj in scope:
        if obj.type == 'MESH' and obj.data is not None and obj.data not in baked_meshes:
            mesh = obj.data
            if mesh_users.get(mesh, set()) <= scope_set:
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

    def _warn(message):
        print(message)
        if diagnostics is not None:
            try:
                diagnostics.add_warning(message)
            except Exception:
                pass

    def _instancer_world(obj):
        ## A collection-instance empty draws its prototype objects at
        ## E @ T(-offset) @ W_child, and those prototypes are usually NOT scene
        ## objects (the standard Add > Collection Instance workflow keeps the
        ## source collection unlinked), so the mesh bake above never touches
        ## them. The instance transform must therefore carry the rotation:
        ##   - prototypes untouched:            E' = Rg @ E
        ##   - prototypes in scope (Rg-form):   E' = Rg @ E @ D @ Rg_inv @ D_inv
        ##     (children contribute Rg @ W_child, so conjugating around the
        ##     instance-offset translation D lands the content at
        ##     Rg @ E @ D @ W_child - exactly the whole-scene rotation).
        collection = getattr(obj, "instance_collection", None)
        prototypes = list(getattr(collection, "all_objects", []) or []) if collection else []
        if not prototypes:
            return Rg @ old_world[obj]
        in_scope = sum(1 for proto in prototypes if proto in scope_set)
        if in_scope == 0:
            return Rg @ old_world[obj]
        offset = Matrix.Translation(-Vector(getattr(collection, "instance_offset", (0.0, 0.0, 0.0))))
        if in_scope < len(prototypes):
            ## Some prototypes were rotated by the bake, some weren't - no single
            ## instance transform can compensate both. Best effort + warning.
            _warn(
                f"apply_yup_geometry: collection instance '{obj.name}' mixes "
                "in-scope and out-of-scope prototype objects; its content may "
                "export mis-oriented."
            )
        return Rg @ old_world[obj] @ offset @ Rg_inv @ offset.inverted()

    def _target_world(obj):
        ## Baked mesh: conjugate so the baked verts (Rg @ v) land at Rg @ world.
        if obj.type == 'MESH' and obj.data in baked_meshes:
            return Rg @ old_world[obj] @ Rg_inv
        if obj.type == 'EMPTY':
            ## Collection-instance empties DO carry geometry (their prototype
            ## collection), which lives outside the mesh bake, so the instance
            ## transform must be adjusted - see _instancer_world.
            if getattr(obj, "instance_type", None) == 'COLLECTION':
                return _instancer_world(obj)
            ## Plain grouping empties carry no geometry, so any target works
            ## visually; conjugating keeps them valid parent frames for the
            ## closed-form child rewrite below (and stays identity for an
            ## empty at identity - no -90 wrapper appears on group roots).
            return Rg @ old_world[obj] @ Rg_inv
        ## Lights / cameras / un-baked meshes: rotate via the transform.
        return Rg @ old_world[obj]

    ## Rewrite transforms in closed form wherever possible, via matrix_basis +
    ## matrix_parent_inverse, NOT by assigning matrix_world. The matrix_world
    ## setter must decompose the solved local matrix into loc/rot/scale
    ## channels, which cannot hold shear - and a conjugated child under a
    ## rotated, non-uniformly-scaled parent requires a sheared local matrix, so
    ## the assignment silently drops it and the child lands visibly wrong. The
    ## closed form has no such loss: conjugating a TRS basis by Rg (an axis
    ## permutation) yields a clean TRS again, and matrix_parent_inverse stores
    ## a full 4x4, so conjugating every link of the hierarchy
    ## (basis' = Rg @ B @ Rg_inv, parent_inverse' = Rg @ PI @ Rg_inv) lands
    ## every world at exactly Rg @ W @ Rg_inv; left-multiplied objects use
    ## basis' = Rg @ B (also clean TRS) to land at Rg @ W. It is also
    ## declarative - no dependence on evaluation order or depsgraph staleness.
    def _has_delta_transform(obj):
        try:
            if Vector(obj.delta_location).length > 1e-9:
                return True
            if any(abs(s - 1.0) > 1e-9 for s in obj.delta_scale):
                return True
            dq = obj.delta_rotation_quaternion
            if abs(dq.w - 1.0) > 1e-9 or Vector((dq.x, dq.y, dq.z)).length > 1e-9:
                return True
            if Vector(obj.delta_rotation_euler).length > 1e-9:
                return True
        except Exception:
            return True
        return False

    def _classify(obj):
        ## 'conjugate': world -> Rg @ W @ Rg_inv via clean basis rewrite.
        ## 'left':      world -> Rg @ W (lights/cameras/un-baked meshes).
        ## 'fallback':  bespoke target (collection instancers) or transforms
        ##              the closed form doesn't model (delta transforms).
        if _has_delta_transform(obj):
            return 'fallback'
        if obj.type == 'EMPTY':
            if getattr(obj, "instance_type", None) == 'COLLECTION':
                return 'fallback'
            return 'conjugate'
        if obj.type == 'MESH' and obj.data in baked_meshes:
            return 'conjugate'
        return 'left'

    classes = {obj: _classify(obj) for obj in scope}

    def _closed_form_applies(obj):
        ## The rewrite is exact only against a parent frame that itself ends up
        ## Rg-conjugated: root objects, or in-scope 'conjugate' parents (their
        ## final world is Rg @ Pw @ Rg_inv whether they went through the closed
        ## form or the fallback).
        parent = obj.parent
        if parent is None:
            return True
        return parent in scope_set and classes.get(parent) == 'conjugate'

    ## Per-object guards keep one failing rewrite (e.g. a library-linked /
    ## locked object) from aborting before the restore state is returned: a
    ## skipped object is just un-rotated in the export, never an un-restorable
    ## scene.
    fallback_objects = []
    for obj in scope:
        cls = classes[obj]
        if cls == 'fallback' or not _closed_form_applies(obj):
            fallback_objects.append(obj)
            continue
        try:
            if obj.parent is not None:
                obj.matrix_parent_inverse = Rg @ orig_parent_inverse[obj] @ Rg_inv
            if cls == 'conjugate':
                obj.matrix_basis = Rg @ orig_basis[obj] @ Rg_inv
            else:
                obj.matrix_basis = Rg @ orig_basis[obj]
        except Exception as exc:
            print("apply_yup_geometry: basis rewrite failed:", exc)

    try:
        context.view_layer.update()
    except Exception as exc:
        print("apply_yup_geometry: view_layer.update failed:", exc)

    ## Remaining objects get their world assigned exactly, parents before
    ## children (by in-scope depth) with a view-layer update per level, so each
    ## child is solved against its parent's final evaluated world.
    def _in_scope_depth(obj):
        depth = 0
        parent = obj.parent
        while parent is not None:
            if parent in scope_set:
                depth += 1
            parent = parent.parent
        return depth

    if fallback_objects:
        by_depth = {}
        for obj in fallback_objects:
            by_depth.setdefault(_in_scope_depth(obj), []).append(obj)

        for depth in sorted(by_depth):
            for obj in by_depth[depth]:
                try:
                    obj.matrix_world = _target_world(obj)
                except Exception as exc:
                    print("apply_yup_geometry: matrix_world failed:", exc)
            try:
                context.view_layer.update()
            except Exception as exc:
                print("apply_yup_geometry: view_layer.update failed:", exc)

    ## Geometry is now natively Y-up; don't let the exporter add its own root -90deg.
    settings.convert_orientation = False

    return {
        "baked_meshes": baked_meshes,
        "orig_basis": orig_basis,
        "orig_parent_inverse": orig_parent_inverse,
        "rg_inv": Rg_inv,
        "orig_convert_orientation": orig_convert_orientation,
    }


def restore_yup_geometry_bake(context, settings, state) -> None:
    """Undo ``apply_yup_geometry_bake`` so an in-process export leaves the live
    scene exactly as it was.

    Reverses the mesh rotation (``Rg_inv`` on each baked datablock, once),
    restores every scope object's local transform and parent-inverse from the
    snapshots, and puts ``convert_orientation`` back. Run from a ``finally`` so
    a failed export can't leave the user's scene rotated.
    """
    if not state:
        return

    rg_inv = state.get("rg_inv")
    if rg_inv is not None:
        for mesh in state.get("baked_meshes", set()):
            try:
                mesh.transform(rg_inv, shape_keys=True)
                mesh.update()
            except Exception as exc:
                print("restore_yup_geometry_bake: mesh.transform failed:", exc)

    for obj, parent_inverse in state.get("orig_parent_inverse", {}).items():
        try:
            obj.matrix_parent_inverse = parent_inverse
        except Exception:
            pass

    for obj, basis in state.get("orig_basis", {}).items():
        try:
            obj.matrix_basis = basis
        except Exception:
            pass

    if settings is not None and "orig_convert_orientation" in state:
        try:
            settings.convert_orientation = state["orig_convert_orientation"]
        except Exception:
            pass

    try:
        context.view_layer.update()
    except Exception:
        pass
