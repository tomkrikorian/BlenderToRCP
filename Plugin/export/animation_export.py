"""
Animation export preparation for BlenderToRCP.

Concatenates all actions into a single sequential timeline per target and
bakes to a single action to improve compatibility with Reality Composer Pro.
"""

from __future__ import annotations

import math
from typing import Any

import bpy


def prepare_animation_export(context, settings, diagnostics=None) -> dict:
    """Prepare animation data for export by concatenating and baking actions.

    Returns a state dictionary that must be passed to restore_animation_export().
    """
    if not bool(getattr(settings, "export_animation", False)):
        return {}

    actions = _collect_actions()
    if not actions:
        if diagnostics:
            diagnostics.add_warning("Export animation enabled but no actions found.")
        return {}

    schedule, total_frames = _build_schedule(actions, diagnostics)
    if not schedule:
        if diagnostics:
            diagnostics.add_warning("Export animation schedule is empty; skipping bake.")
        return {}

    state = _init_state(context)
    scene = state["scene"]

    targets = _collect_targets(context, settings)
    if not targets and diagnostics:
        diagnostics.add_warning("Export animation enabled but no animated targets were found.")
    total_frames_int = max(1, int(total_frames))
    if diagnostics:
        diagnostics.set_animation_schedule(
            fps=scene.render.fps,
            total_frames=total_frames_int,
            segments=[
                {
                    "name": seg["name"],
                    "start_frame": seg["start_frame"],
                    "end_frame": seg["end_frame"],
                }
                for seg in schedule
            ],
            targets=[
                {
                    "name": t.get("name"),
                    "kind": t.get("kind"),
                    "object_type": t.get("object_type"),
                }
                for t in targets
            ],
        )

    scene.frame_start = 1
    scene.frame_end = total_frames_int
    try:
        scene.frame_set(scene.frame_start)
    except Exception:
        pass

    try:
        for target in targets:
            _prepare_target(context, target, schedule, total_frames_int, state, diagnostics)
    except Exception:
        restore_animation_export(state)
        raise

    _restore_selection(context, state)
    _ensure_object_mode(context)
    return state


def restore_animation_export(state: dict) -> None:
    """Restore Blender scene and animation state after export."""
    if not state:
        return

    scene = state.get("scene")
    if scene:
        try:
            scene.frame_start = int(state.get("frame_start", scene.frame_start))
            scene.frame_end = int(state.get("frame_end", scene.frame_end))
            scene.frame_set(int(state.get("frame_current", scene.frame_current)))
        except Exception:
            pass

    for item in state.get("targets", []):
        anim_data = item.get("anim_data")
        if anim_data is None:
            continue

        # Remove export track.
        export_name = item.get("export_track_name")
        if export_name:
            try:
                export_track = anim_data.nla_tracks.get(export_name)
                if export_track:
                    anim_data.nla_tracks.remove(export_track)
            except Exception:
                pass

        # Restore track mute/solo flags.
        for track, mute, solo in item.get("track_states", []):
            try:
                track_name = getattr(track, "name", None)
                if track_name and anim_data.nla_tracks.get(track_name) is not None:
                    if hasattr(track, "mute"):
                        track.mute = mute
                    if hasattr(track, "is_solo"):
                        track.is_solo = solo
            except Exception:
                continue

        # Restore action + NLA evaluation mode.
        try:
            anim_data.action = item.get("original_action")
            anim_data.use_nla = bool(item.get("original_use_nla"))
        except Exception:
            pass

        # Remove baked action if it was created for export.
        baked_action = item.get("baked_action")
        if baked_action and bpy.data.actions.get(baked_action.name) is not None:
            try:
                bpy.data.actions.remove(baked_action)
            except Exception:
                pass

        # Clear animation data if we created it.
        if item.get("created_anim_data"):
            owner = item.get("owner")
            try:
                if hasattr(owner, "animation_data_clear"):
                    owner.animation_data_clear()
            except Exception:
                pass

    _restore_selection_from_state(state)
    _restore_mode_from_state(state)


def _collect_actions() -> list:
    actions = list(bpy.data.actions)
    actions.sort(key=lambda action: action.name.lower())
    return actions


def _build_schedule(actions: list, diagnostics=None) -> tuple[list, int]:
    schedule = []
    current = 1
    for action in actions:
        start, end = action.frame_range
        length = float(end) - float(start)
        if length <= 0.0:
            length = 1.0
            if diagnostics:
                diagnostics.add_warning(
                    f"Action '{action.name}' has zero-length range; clamped to 1 frame."
                )
        length_frames = max(1, int(math.ceil(length)))
        segment = {
            "name": action.name,
            "action": action,
            "action_start": float(start),
            "action_end": float(end),
            "start_frame": int(current),
            "end_frame": int(current + length_frames),
            "length": float(length),
            "length_frames": int(length_frames),
        }
        schedule.append(segment)
        current += length_frames

    total_frames = schedule[-1]["end_frame"] if schedule else 0
    return schedule, total_frames


def _collect_targets(context, settings) -> list[dict]:
    selected_only = bool(getattr(settings, "selected_objects_only", False))
    objects = list(context.selected_objects) if selected_only else list(context.scene.objects)

    targets: list[dict] = []
    for obj in objects:
        if not _is_exportable_object(obj, settings):
            continue

        if obj.type == "ARMATURE":
            targets.append({
                "kind": "ARMATURE",
                "name": obj.name,
                "object": obj,
                "object_type": obj.type,
            })
        else:
            anim_data = getattr(obj, "animation_data", None)
            if anim_data and (anim_data.action or anim_data.nla_tracks):
                targets.append({
                    "kind": "OBJECT",
                    "name": obj.name,
                    "object": obj,
                    "object_type": obj.type,
                })

        if _has_shapekeys(obj, settings):
            targets.append({
                "kind": "SHAPEKEYS",
                "name": obj.name,
                "object": obj,
                "object_type": obj.type,
            })

    return targets


def _is_exportable_object(obj, settings) -> bool:
    export_flags = {
        "MESH": bool(getattr(settings, "export_meshes", True)),
        "LIGHT": bool(getattr(settings, "export_lights", True)),
        "CAMERA": bool(getattr(settings, "export_cameras", True)),
        "CURVE": bool(getattr(settings, "export_curves", True)),
        "POINTCLOUD": bool(getattr(settings, "export_points", True)),
        "VOLUME": bool(getattr(settings, "export_volumes", True)),
        "ARMATURE": bool(getattr(settings, "export_armatures", True)),
    }
    if obj.type in export_flags:
        return export_flags[obj.type]
    return True


def _has_shapekeys(obj, settings) -> bool:
    if not bool(getattr(settings, "export_shapekeys", True)):
        return False
    if obj.type != "MESH":
        return False
    data = getattr(obj, "data", None)
    if not data:
        return False
    return bool(getattr(data, "shape_keys", None))


def _prepare_target(context, target: dict, schedule: list, total_frames: int, state: dict, diagnostics=None) -> None:
    kind = target.get("kind")
    if kind == "ARMATURE":
        _prepare_armature(context, target, schedule, total_frames, state, diagnostics)
    elif kind == "OBJECT":
        _prepare_object(context, target, schedule, total_frames, state, diagnostics)
    elif kind == "SHAPEKEYS":
        _prepare_shapekeys(context, target, schedule, total_frames, state, diagnostics)


def _prepare_armature(context, target: dict, schedule: list, total_frames: int, state: dict, diagnostics=None) -> None:
    obj = target["object"]
    anim_data, created = _ensure_anim_data(obj)
    if anim_data is None:
        raise RuntimeError(f"Failed to create animation data for armature '{obj.name}'.")

    target_state = _snapshot_anim_data(anim_data, obj)
    export_track_name = _apply_schedule(anim_data, schedule)
    target_state["export_track_name"] = export_track_name
    target_state["created_anim_data"] = created
    state["targets"].append(target_state)

    _solo_export_track(anim_data, export_track_name)

    try:
        baked_action = _bake_armature(context, obj, anim_data, total_frames)
    except Exception as exc:
        if diagnostics:
            diagnostics.add_error(f"Failed to bake armature '{obj.name}': {exc}")
        raise
    target_state["baked_action"] = baked_action

    _mute_all_tracks(anim_data)
    anim_data.use_nla = False
    anim_data.action = baked_action


def _prepare_object(context, target: dict, schedule: list, total_frames: int, state: dict, diagnostics=None) -> None:
    obj = target["object"]
    anim_data, created = _ensure_anim_data(obj)
    if anim_data is None:
        raise RuntimeError(f"Failed to create animation data for object '{obj.name}'.")

    target_state = _snapshot_anim_data(anim_data, obj)
    export_track_name = _apply_schedule(anim_data, schedule)
    target_state["export_track_name"] = export_track_name
    target_state["created_anim_data"] = created
    state["targets"].append(target_state)

    _solo_export_track(anim_data, export_track_name)

    try:
        baked_action = _bake_object(context, obj, anim_data, total_frames)
    except Exception as exc:
        if diagnostics:
            diagnostics.add_error(f"Failed to bake object '{obj.name}': {exc}")
        raise
    target_state["baked_action"] = baked_action

    _mute_all_tracks(anim_data)
    anim_data.use_nla = False
    anim_data.action = baked_action


def _prepare_shapekeys(context, target: dict, schedule: list, total_frames: int, state: dict, diagnostics=None) -> None:
    obj = target["object"]
    key = _get_shape_key_block(obj)
    if key is None:
        return

    anim_data, created = _ensure_anim_data(key)
    if anim_data is None:
        raise RuntimeError(f"Failed to create animation data for shape keys on '{obj.name}'.")

    target_state = _snapshot_anim_data(anim_data, key)
    export_track_name = _apply_schedule(anim_data, schedule)
    target_state["export_track_name"] = export_track_name
    target_state["created_anim_data"] = created
    state["targets"].append(target_state)

    _solo_export_track(anim_data, export_track_name)

    try:
        baked_action = _bake_shapekeys(context.scene, obj, key, anim_data, total_frames)
    except Exception as exc:
        if diagnostics:
            diagnostics.add_error(f"Failed to bake shape keys for '{obj.name}': {exc}")
        raise
    target_state["baked_action"] = baked_action

    _mute_all_tracks(anim_data)
    anim_data.use_nla = False
    anim_data.action = baked_action


def _ensure_anim_data(owner) -> tuple[Any, bool]:
    anim_data = getattr(owner, "animation_data", None)
    if anim_data is not None:
        return anim_data, False
    try:
        owner.animation_data_create()
    except Exception:
        return None, False
    return getattr(owner, "animation_data", None), True


def _snapshot_anim_data(anim_data, owner) -> dict:
    track_states = []
    for track in anim_data.nla_tracks:
        track_states.append((track, getattr(track, "mute", False), getattr(track, "is_solo", False)))
    return {
        "owner": owner,
        "anim_data": anim_data,
        "original_action": getattr(anim_data, "action", None),
        "original_use_nla": getattr(anim_data, "use_nla", False),
        "track_states": track_states,
        "export_track_name": None,
        "baked_action": None,
        "created_anim_data": False,
    }


def _apply_schedule(anim_data, schedule: list) -> str:
    track_name = _unique_nla_track_name(anim_data, "__BlenderToRCP_Export__")
    export_track = anim_data.nla_tracks.new()
    export_track.name = track_name

    for seg in schedule:
        strip = export_track.strips.new(seg["name"], seg["start_frame"], seg["action"])
        strip.frame_start = seg["start_frame"]
        strip.frame_end = seg["end_frame"]
        try:
            action_start = seg["action_start"]
            action_end = seg["action_end"]
            if action_end <= action_start:
                action_end = action_start + float(seg.get("length", seg.get("length_frames", 1)))
            strip.action_frame_start = action_start
            strip.action_frame_end = action_end
        except Exception:
            pass

    anim_data.use_nla = True
    anim_data.action = None
    return track_name


def _solo_export_track(anim_data, export_track_name: str) -> None:
    for track in anim_data.nla_tracks:
        if hasattr(track, "mute"):
            track.mute = (track.name != export_track_name)
        if hasattr(track, "is_solo"):
            track.is_solo = (track.name == export_track_name)


def _mute_all_tracks(anim_data) -> None:
    for track in anim_data.nla_tracks:
        if hasattr(track, "mute"):
            track.mute = True
        if hasattr(track, "is_solo"):
            track.is_solo = False


def _bake_armature(context, obj, anim_data, total_frames: int):
    _select_only(context, obj)
    _set_active(context, obj)
    _ensure_mode(context, "POSE")
    try:
        bpy.ops.pose.select_all(action="SELECT")
    except Exception:
        pass

    baked_action = _new_action(f"__B2RCP_BAKED_ARMATURE_{obj.name}")
    anim_data.action = baked_action

    try:
        bpy.ops.nla.bake(
            frame_start=1,
            frame_end=int(total_frames),
            only_selected=True,
            visual_keying=True,
            clear_constraints=False,
            clear_parents=False,
            use_current_action=True,
            bake_types={"POSE", "OBJECT"},
        )
    except TypeError:
        bpy.ops.nla.bake(
            frame_start=1,
            frame_end=int(total_frames),
            only_selected=True,
            visual_keying=True,
            clear_constraints=False,
            clear_parents=False,
            bake_types={"POSE", "OBJECT"},
        )

    _ensure_mode(context, "OBJECT")
    return anim_data.action or baked_action


def _bake_object(context, obj, anim_data, total_frames: int):
    _select_only(context, obj)
    _set_active(context, obj)
    _ensure_mode(context, "OBJECT")

    baked_action = _new_action(f"__B2RCP_BAKED_OBJECT_{obj.name}")
    anim_data.action = baked_action

    try:
        bpy.ops.nla.bake(
            frame_start=1,
            frame_end=int(total_frames),
            only_selected=True,
            visual_keying=True,
            clear_constraints=False,
            clear_parents=False,
            use_current_action=True,
            bake_types={"OBJECT"},
        )
    except TypeError:
        bpy.ops.nla.bake(
            frame_start=1,
            frame_end=int(total_frames),
            only_selected=True,
            visual_keying=True,
            clear_constraints=False,
            clear_parents=False,
            bake_types={"OBJECT"},
        )

    return anim_data.action or baked_action


def _bake_shapekeys(scene, obj, key, anim_data, total_frames: int):
    baked_action = _new_action(f"__B2RCP_BAKED_SHAPEKEYS_{obj.name}")

    key_blocks = [kb for kb in key.key_blocks if kb.name != "Basis"]
    if not key_blocks:
        return baked_action

    fcurves = {}
    for kb in key_blocks:
        data_path = f'key_blocks["{kb.name}"].value'
        fcurves[kb.name] = baked_action.fcurves.new(data_path=data_path, index=0)

    for frame in range(1, int(total_frames) + 1):
        scene.frame_set(frame)
        for kb in key_blocks:
            fcurve = fcurves[kb.name]
            fcurve.keyframe_points.insert(frame, kb.value, options={"FAST"})

    return baked_action


def _get_shape_key_block(obj):
    data = getattr(obj, "data", None)
    if not data:
        return None
    return getattr(data, "shape_keys", None)


def _new_action(base_name: str):
    name = _unique_action_name(base_name)
    return bpy.data.actions.new(name)


def _unique_action_name(base: str) -> str:
    name = base
    suffix = 1
    while bpy.data.actions.get(name) is not None:
        suffix += 1
        name = f"{base}_{suffix}"
    return name


def _unique_nla_track_name(anim_data, base: str) -> str:
    name = base
    suffix = 1
    while anim_data.nla_tracks.get(name) is not None:
        suffix += 1
        name = f"{base}_{suffix}"
    return name


def _init_state(context) -> dict:
    active = context.view_layer.objects.active
    mode = None
    try:
        mode = active.mode if active else None
    except Exception:
        mode = None
    return {
        "scene": context.scene,
        "frame_start": context.scene.frame_start,
        "frame_end": context.scene.frame_end,
        "frame_current": context.scene.frame_current,
        "selection": [obj.name for obj in context.selected_objects],
        "active": active.name if active else None,
        "mode": mode,
        "targets": [],
    }


def _restore_selection(context, state: dict) -> None:
    try:
        for obj in context.view_layer.objects:
            obj.select_set(False)
    except Exception:
        pass
    names = set(state.get("selection", []))
    for obj in context.scene.objects:
        if obj.name in names:
            try:
                obj.select_set(True)
            except Exception:
                pass
    active_name = state.get("active")
    if active_name:
        obj = context.scene.objects.get(active_name)
        if obj:
            try:
                context.view_layer.objects.active = obj
            except Exception:
                pass


def _restore_selection_from_state(state: dict) -> None:
    scene = state.get("scene")
    if scene is None:
        return
    try:
        view_layer = bpy.context.view_layer
    except Exception:
        view_layer = None

    try:
        if view_layer is not None:
            for obj in view_layer.objects:
                obj.select_set(False)
        else:
            for obj in scene.objects:
                obj.select_set(False)
    except Exception:
        pass
    names = set(state.get("selection", []))
    for obj in scene.objects:
        if obj.name in names:
            try:
                obj.select_set(True)
            except Exception:
                pass
    active_name = state.get("active")
    if active_name and scene.objects.get(active_name):
        try:
            bpy.context.view_layer.objects.active = scene.objects.get(active_name)
        except Exception:
            pass


def _restore_mode_from_state(state: dict) -> None:
    mode = state.get("mode")
    if not mode:
        return
    try:
        bpy.ops.object.mode_set(mode=mode)
    except Exception:
        pass


def _ensure_mode(context, mode: str) -> None:
    try:
        bpy.ops.object.mode_set(mode=mode)
    except Exception:
        pass


def _ensure_object_mode(context) -> None:
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass


def _select_only(context, obj) -> None:
    try:
        for o in context.view_layer.objects:
            o.select_set(False)
    except Exception:
        pass
    try:
        obj.select_set(True)
    except Exception:
        pass


def _set_active(context, obj) -> None:
    context.view_layer.objects.active = obj
