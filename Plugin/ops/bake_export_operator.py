"""
Bake & Export operator for BlenderToRCP.
"""

from __future__ import annotations

import os
import json
import subprocess
import time
import tempfile
from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from .. import prefs as addon_prefs
from .export_operator import (
    BLENDERTORCP_OT_export,
    _apply_persisted_settings,
    _store_last_export_settings,
)


class BLENDERTORCP_OT_bake_export_background(Operator, ExportHelper):
    """Bake textures and export scene in a background Blender process."""
    bl_idname = "blendertorcp.bake_export_background"
    bl_label = "Bake & Export (Background)"
    bl_description = "Run bake + export in a background Blender process"
    bl_options = {'REGISTER'}

    filename_ext = ".usdz"
    filter_glob: StringProperty(
        default="*.usdz;*.usda;*.usdc",
        options={'HIDDEN'}
    )

    def invoke(self, context, event):
        settings = context.scene.blender_to_rcp_export_settings
        export_format = BLENDERTORCP_OT_export._normalize_export_format(settings.export_format)
        settings.export_format = export_format
        extension = BLENDERTORCP_OT_export._format_extension(export_format)
        self.filename_ext = extension
        self.filter_glob = f"*{extension}"

        blend_path = Path(context.blend_data.filepath) if context.blend_data.filepath else None
        blend_name = blend_path.stem if blend_path else "untitled"
        blend_dir = blend_path.parent if blend_path else None
        last_path = addon_prefs.get_last_export_path(context, blend_path)

        if last_path:
            self.filepath = BLENDERTORCP_OT_export._enforce_extension(str(last_path), export_format)
        elif blend_dir:
            suggested = blend_dir / f"{blend_name}{extension}"
            self.filepath = BLENDERTORCP_OT_export._enforce_extension(str(suggested), export_format)
        else:
            self.filepath = ""

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "No file path specified")
            return {'CANCELLED'}

        if not context.blend_data.filepath:
            self.report({'ERROR'}, "Save the .blend file before running background export.")
            return {'CANCELLED'}

        settings = context.scene.blender_to_rcp_export_settings
        _apply_persisted_settings(context, settings)

        export_format = BLENDERTORCP_OT_export._normalize_export_format(settings.export_format)
        settings.export_format = export_format
        self.filepath = BLENDERTORCP_OT_export._enforce_extension(self.filepath, export_format)
        settings.filepath = self.filepath

        if getattr(settings, "background_job_dir", ""):
            status = _read_job_status(settings.background_job_dir)
            if status and status.get("state") in {"queued", "running"}:
                self.report({'ERROR'}, "A background job is already running. Cancel it first.")
                return {'CANCELLED'}

        objects_to_export = _collect_export_objects(context, settings)
        if not objects_to_export:
            self.report({'ERROR'}, "No exportable objects found")
            return {'CANCELLED'}

        export_dir = Path(self.filepath).parent
        job_dir = _create_job_dir(export_dir)
        status_path = job_dir / "status.json"
        log_path = job_dir / "log.txt"

        selection_names = []
        if getattr(settings, "selected_objects_only", False):
            selection_names = [obj.name for obj in objects_to_export]

        payload = {
            "job_dir": str(job_dir),
            "blend_file": context.blend_data.filepath,
            "export_path": self.filepath,
            "export_settings": _serialize_settings(settings),
            "selected_only": bool(getattr(settings, "selected_objects_only", False)),
            "selection": selection_names,
        }
        settings_path = job_dir / "settings.json"
        settings_path.write_text(json.dumps(payload, indent=2))

        _write_status(
            status_path,
            state="queued",
            progress=0.0,
            message="Queued background export",
            log_path=str(log_path),
            export_path=self.filepath,
        )

        blender_bin = bpy.app.binary_path
        runner_path = Path(__file__).resolve().parents[1] / "bake_export_runner.py"
        if not runner_path.exists():
            self.report({'ERROR'}, f"Missing runner script: {runner_path}")
            return {'CANCELLED'}

        with open(log_path, "w") as log_file:
            proc = subprocess.Popen(
                [
                    blender_bin,
                    "--background",
                    context.blend_data.filepath,
                    "--python",
                    str(runner_path),
                    "--",
                    str(settings_path),
                ],
                stdout=log_file,
                stderr=log_file,
            )

        settings.background_job_dir = str(job_dir)
        settings.background_job_pid = proc.pid
        _store_last_export_settings(context, settings)

        self.report({'INFO'}, f"Background export started (PID {proc.pid}).")
        return {'FINISHED'}


class BLENDERTORCP_OT_cancel_bake_export(Operator):
    """Cancel the active background bake/export job."""
    bl_idname = "blendertorcp.cancel_bake_export"
    bl_label = "Cancel Background Bake"
    bl_description = "Cancel the background bake/export job"
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = context.scene.blender_to_rcp_export_settings
        pid = int(getattr(settings, "background_job_pid", 0))
        job_dir = getattr(settings, "background_job_dir", "")
        if not pid or not job_dir:
            self.report({'ERROR'}, "No background job to cancel.")
            return {'CANCELLED'}

        try:
            os.kill(pid, 15)
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to cancel job: {exc}")
            return {'CANCELLED'}

        status_path = Path(job_dir) / "status.json"
        _write_status(
            status_path,
            state="canceled",
            progress=1.0,
            message="Canceled by user",
        )

        settings.background_job_pid = 0
        settings.background_job_dir = ""
        self.report({'INFO'}, "Background job canceled.")
        return {'FINISHED'}


class BLENDERTORCP_OT_clear_bake_job(Operator):
    """Clear background bake/export job state."""
    bl_idname = "blendertorcp.clear_bake_job"
    bl_label = "Clear Bake Job"
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = context.scene.blender_to_rcp_export_settings
        settings.background_job_dir = ""
        settings.background_job_pid = 0
        self.report({'INFO'}, "Cleared background job state.")
        return {'FINISHED'}




def _collect_export_objects(context, settings):
    if getattr(settings, "selected_objects_only", False):
        selection = list(context.selected_objects)
        if selection:
            return selection
    return list(context.scene.objects)


def _collect_materials_from_objects(objects):
    materials = []
    seen = set()
    for obj in objects:
        for slot in getattr(obj, "material_slots", []):
            mat = slot.material
            if mat and mat not in seen:
                seen.add(mat)
                materials.append(mat)
    return materials


def _ensure_object_mode(context) -> None:
    active = context.view_layer.objects.active
    if active and active.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def _set_render_engine(scene, engine: str) -> None:
    try:
        scene.render.engine = engine
    except Exception:
        pass


def _restore_selection(context, selection, active) -> None:
    try:
        for obj in context.view_layer.objects:
            obj.select_set(False)
    except Exception:
        pass
    for obj in selection:
        try:
            obj.select_set(True)
        except Exception:
            pass
    if active:
        try:
            context.view_layer.objects.active = active
        except Exception:
            pass


def _set_selection(context, objects) -> None:
    try:
        for obj in context.view_layer.objects:
            obj.select_set(False)
    except Exception:
        pass
    for obj in objects:
        try:
            obj.select_set(True)
        except Exception:
            pass


    active = None
    for obj in objects:
        try:
            obj.select_set(True)
            if active is None:
                active = obj
        except Exception:
            continue
    if active:
        try:
            context.view_layer.objects.active = active
        except Exception:
            pass


def _serialize_settings(settings) -> dict:
    data = {}
    for prop in settings.bl_rna.properties:
        key = prop.identifier
        if key in {"rna_type", "name", "history_applied", "last_diagnostics_path"}:
            continue
        try:
            data[key] = getattr(settings, key)
        except Exception:
            continue
    return data


def _create_job_dir(export_dir: Path) -> Path:
    root = export_dir / ".blendertorcp_jobs"
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    job_dir = Path(tempfile.mkdtemp(prefix=f"bake_export_{stamp}_", dir=root))
    return job_dir


def _write_status(
    path: Path,
    state: str,
    progress: float | None = None,
    message: str | None = None,
    log_path: str | None = None,
    export_path: str | None = None,
) -> None:
    payload = {
        "state": state,
        "time": time.time(),
    }
    if progress is not None:
        payload["progress"] = progress
    if message:
        payload["message"] = message
    if log_path:
        payload["log_path"] = log_path
    if export_path:
        payload["export_path"] = export_path
    try:
        path.write_text(json.dumps(payload, indent=2))
    except Exception:
        pass


def _read_job_status(job_dir: str):
    if not job_dir:
        return None
    status_path = Path(job_dir) / "status.json"
    if not status_path.exists():
        return None
    try:
        return json.loads(status_path.read_text())
    except Exception:
        return None


def _restore_mode(context, active, mode: str) -> None:
    if not active:
        return
    try:
        context.view_layer.objects.active = active
    except Exception:
        return
    try:
        if mode and active.mode != mode:
            bpy.ops.object.mode_set(mode=mode)
    except Exception:
        pass


def register():
    bpy.utils.register_class(BLENDERTORCP_OT_bake_export_background)
    bpy.utils.register_class(BLENDERTORCP_OT_cancel_bake_export)
    bpy.utils.register_class(BLENDERTORCP_OT_clear_bake_job)


def unregister():
    bpy.utils.unregister_class(BLENDERTORCP_OT_clear_bake_job)
    bpy.utils.unregister_class(BLENDERTORCP_OT_cancel_bake_export)
    bpy.utils.unregister_class(BLENDERTORCP_OT_bake_export_background)
