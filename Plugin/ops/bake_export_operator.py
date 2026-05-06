"""
Bake Textures & Export operator for BlenderToRCP.
"""

from __future__ import annotations

import os
import json
import subprocess
import time
import tempfile
import errno
import re
import signal
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

_ACTIVE_JOB_STATES = {"queued", "running"}
_SERIALIZED_SETTINGS_SKIP_KEYS = {
    "rna_type",
    "name",
    "history_applied",
    "last_diagnostics_path",
    "persist_suspended",
    "background_job_dir",
    "background_job_pid",
    "filepath",
}


class BLENDERTORCP_OT_bake_export_background(Operator, ExportHelper):
    """Bake textures and export scene in a background Blender process."""
    bl_idname = "blendertorcp.bake_export_background"
    bl_label = "Bake Textures & Export (Background)"
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
        diagnostics_path = Path(self.filepath).with_suffix(".diagnostics.json")

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
            diagnostics_path=str(diagnostics_path),
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
                    "--factory-startup",
                    context.blend_data.filepath,
                    "--python",
                    str(runner_path),
                    "--",
                    str(settings_path),
                ],
                stdout=log_file,
                stderr=log_file,
            )

        _write_status(
            status_path,
            state="queued",
            progress=0.0,
            message="Queued background export",
            log_path=str(log_path),
            export_path=self.filepath,
            diagnostics_path=str(diagnostics_path),
            pid=proc.pid,
        )
        settings.background_job_dir = str(job_dir)
        settings.background_job_pid = proc.pid
        _store_last_export_settings(context, settings)
        try:
            bpy.ops.blendertorcp.watch_bake_export_job('INVOKE_DEFAULT')
        except Exception:
            pass

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

        status_path = Path(job_dir) / "status.json"
        status = _read_job_status(job_dir)
        if not status or status.get("state") not in _ACTIVE_JOB_STATES:
            settings.background_job_pid = 0
            settings.background_job_dir = ""
            self.report({'INFO'}, "Cleared stale background job state.")
            return {'FINISHED'}

        status_pid = _status_pid(status)
        if status_pid is None or status_pid != pid:
            settings.background_job_pid = 0
            settings.background_job_dir = ""
            self.report({'INFO'}, "Cleared stale background job state.")
            return {'FINISHED'}

        if _pid_is_running(pid):
            _terminate_process(pid)
        else:
            settings.background_job_pid = 0
            settings.background_job_dir = ""
            self.report({'INFO'}, "Cleared stale background job state.")
            return {'FINISHED'}

        _write_status(
            status_path,
            state="canceled",
            progress=1.0,
            message="Canceled by user",
            pid=pid,
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


class BLENDERTORCP_OT_watch_bake_export_job(Operator):
    """Modal watcher that keeps the panel refreshed and handles timeout/failure detection."""
    bl_idname = "blendertorcp.watch_bake_export_job"
    bl_label = "Watch Bake Export Job"
    bl_options = {'INTERNAL'}

    _timer = None

    def invoke(self, context, event):
        settings = context.scene.blender_to_rcp_export_settings
        if not getattr(settings, "background_job_dir", ""):
            return {'CANCELLED'}
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        settings = context.scene.blender_to_rcp_export_settings
        job_dir = getattr(settings, "background_job_dir", "")
        if not job_dir:
            self._stop(context)
            return {'CANCELLED'}

        status_path = Path(job_dir) / "status.json"
        status = _read_job_status(job_dir)
        if status is None and not status_path.exists():
            _tag_export_ui_redraw()
            self._stop(context)
            return {'FINISHED'}
        status = status or {}
        state = status.get("state")
        pid = int(getattr(settings, "background_job_pid", 0))

        _tag_export_ui_redraw()

        if state in {"done", "error", "canceled"}:
            settings.background_job_pid = 0
            self._stop(context)
            return {'FINISHED'}

        if pid > 0 and not _pid_is_running(pid):
            _write_status(
                status_path,
                state="error",
                progress=1.0,
                message="Background job exited unexpectedly.",
                log_path=status.get("log_path"),
                export_path=status.get("export_path") or getattr(settings, "filepath", ""),
                diagnostics_path=status.get("diagnostics_path"),
            )
            settings.background_job_pid = 0
            _tag_export_ui_redraw()
            self._stop(context)
            return {'FINISHED'}

        timeout_seconds = int(getattr(settings, "bake_step_timeout_seconds", 0) or 0)
        if timeout_seconds > 0 and state in {"queued", "running"} and pid > 0:
            step_elapsed = _extract_step_elapsed_seconds(status)
            if step_elapsed is not None and step_elapsed >= timeout_seconds:
                _terminate_process(pid)
                _write_status(
                    status_path,
                    state="error",
                    progress=1.0,
                    message=f"Timed out after {timeout_seconds}s in one step; background job canceled.",
                    log_path=status.get("log_path"),
                    export_path=status.get("export_path") or getattr(settings, "filepath", ""),
                    diagnostics_path=status.get("diagnostics_path"),
                )
                settings.background_job_pid = 0
                _tag_export_ui_redraw()
                self._stop(context)
                return {'FINISHED'}

        return {'PASS_THROUGH'}

    def cancel(self, context):
        self._stop(context)

    def _stop(self, context):
        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None


def _tag_export_ui_redraw() -> None:
    for wm in bpy.data.window_managers:
        for window in wm.windows:
            screen = getattr(window, "screen", None)
            if screen is None:
                continue
            for area in screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                area.tag_redraw()
                for region in area.regions:
                    if region.type in {'UI', 'WINDOW'}:
                        region.tag_redraw()


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as exc:
        if exc.errno == errno.EPERM:
            return True
        return False
    except Exception:
        return False


def _terminate_process(pid: int) -> None:
    if pid <= 0:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        return
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if not _pid_is_running(pid):
            return
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except Exception:
        pass


def _extract_step_elapsed_seconds(status: dict) -> int | None:
    if not isinstance(status, dict):
        return None
    raw = status.get("step_elapsed_seconds")
    if raw is not None:
        try:
            return int(raw)
        except Exception:
            pass
    message = str(status.get("message") or "")
    match = re.search(r"\((\d+)s\)", message)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _status_pid(status: dict) -> int | None:
    if not isinstance(status, dict):
        return None
    raw = status.get("pid")
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None



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
        if key in _SERIALIZED_SETTINGS_SKIP_KEYS:
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
    diagnostics_path: str | None = None,
    pid: int | None = None,
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
    if diagnostics_path:
        payload["diagnostics_path"] = diagnostics_path
    if pid is not None:
        payload["pid"] = int(pid)
    try:
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2))
        tmp_path.replace(path)
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
    bpy.utils.register_class(BLENDERTORCP_OT_watch_bake_export_job)
    bpy.utils.register_class(BLENDERTORCP_OT_cancel_bake_export)
    bpy.utils.register_class(BLENDERTORCP_OT_clear_bake_job)


def unregister():
    bpy.utils.unregister_class(BLENDERTORCP_OT_clear_bake_job)
    bpy.utils.unregister_class(BLENDERTORCP_OT_cancel_bake_export)
    bpy.utils.unregister_class(BLENDERTORCP_OT_watch_bake_export_job)
    bpy.utils.unregister_class(BLENDERTORCP_OT_bake_export_background)
