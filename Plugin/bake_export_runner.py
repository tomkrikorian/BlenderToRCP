"""
Background bake + export runner for BlenderToRCP.

Usage (invoked by Blender):
  blender --background <file.blend> --python bake_export_runner.py -- <settings.json>
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
import time
import threading
import importlib.util

import bpy

PLUGIN_ROOT = Path(__file__).resolve().parent


def _bootstrap_plugin_package() -> None:
    """Make absolute ``Plugin.*`` imports work from copied extension folders."""
    parent = PLUGIN_ROOT.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    if (parent / "Plugin" / "__init__.py").exists():
        return
    if "Plugin" in sys.modules:
        return

    init_path = PLUGIN_ROOT / "__init__.py"
    if not init_path.exists():
        return
    init_resolved = init_path.resolve()
    for module in list(sys.modules.values()):
        if Path(getattr(module, "__file__", "") or "") == init_resolved:
            sys.modules["Plugin"] = module
            return

    spec = importlib.util.spec_from_file_location(
        "Plugin",
        init_path,
        submodule_search_locations=[str(PLUGIN_ROOT)],
    )
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules["Plugin"] = module
    spec.loader.exec_module(module)


_APPLY_SETTINGS_SKIP_KEYS = {
    "rna_type",
    "name",
    "history_applied",
    "last_diagnostics_path",
    "persist_suspended",
    "background_job_dir",
    "background_job_pid",
    "filepath",
}


def _ensure_addon_loaded() -> None:
    from Plugin.api.addon_loader import ensure_addon_loaded as _load_blendertorcp_addon

    _load_blendertorcp_addon()


def _update_status(
    status_path: Path,
    state: str,
    progress: float | None = None,
    message: str | None = None,
    log_path: str | None = None,
    export_path: str | None = None,
    diagnostics_path: str | None = None,
    step_elapsed_seconds: int | None = None,
) -> None:
    payload = {
        "state": state,
        "time": time.time(),
        "pid": os.getpid(),
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
    if step_elapsed_seconds is not None:
        payload["step_elapsed_seconds"] = int(step_elapsed_seconds)
    try:
        tmp_path = status_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2))
        tmp_path.replace(status_path)
    except Exception:
        pass


class _BakeProgressReporter:
    """Tracks bake progress and emits heartbeat updates while bake ops are running."""

    def __init__(
        self,
        status_path: Path,
        export_path: str | None,
        log_path: str | None,
        diagnostics_path: str | None,
    ):
        self.status_path = status_path
        self.export_path = export_path
        self.log_path = log_path
        self.diagnostics_path = diagnostics_path
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._progress = 0.0
        self._message = "Preparing bake"
        self._step_started = time.time()
        self._tick = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="BakeProgressHeartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join()
        self._thread = None

    def update(self, progress: float, message: str) -> None:
        now = time.time()
        with self._lock:
            self._progress = max(0.0, min(1.0, float(progress)))
            if message and message != self._message:
                self._message = message
                self._step_started = now
                self._tick = 0
        self._emit(heartbeat=False)

    def _emit(self, heartbeat: bool) -> None:
        if self._stop_event.is_set():
            return
        with self._lock:
            progress = self._progress
            message = self._message
            step_started = self._step_started
            tick = self._tick

        if heartbeat and message:
            elapsed = int(max(0.0, time.time() - step_started))
            dots = "." * ((tick % 3) + 1)
            display = f"{message} ({elapsed}s){dots}"
        else:
            display = message
            elapsed = int(max(0.0, time.time() - step_started))

        _update_status(
            self.status_path,
            "running",
            progress,
            display,
            log_path=self.log_path,
            export_path=self.export_path,
            diagnostics_path=self.diagnostics_path,
            step_elapsed_seconds=elapsed,
        )

    def _run(self) -> None:
        while not self._stop_event.wait(1.0):
            with self._lock:
                self._tick += 1
            self._emit(heartbeat=True)


def _apply_settings(scene_settings, data: dict) -> None:
    prop_defs = {prop.identifier for prop in scene_settings.bl_rna.properties}
    for key, value in data.items():
        if key in _APPLY_SETTINGS_SKIP_KEYS:
            continue
        if key not in prop_defs:
            continue
        try:
            setattr(scene_settings, key, value)
        except Exception:
            continue


def _select_objects(names):
    if not names:
        return
    for obj in bpy.context.view_layer.objects:
        try:
            obj.select_set(False)
        except Exception:
            pass
    active = None
    for name in names:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        try:
            obj.select_set(True)
            if active is None:
                active = obj
        except Exception:
            continue
    if active:
        try:
            bpy.context.view_layer.objects.active = active
        except Exception:
            pass


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("Missing settings path.")
        return 1
    settings_path = Path(argv[argv.index("--") + 1])
    if not settings_path.exists():
        print(f"Settings file not found: {settings_path}")
        return 1

    payload = json.loads(settings_path.read_text())
    job_dir = Path(payload.get("job_dir", settings_path.parent))
    status_path = job_dir / "status.json"
    log_path = job_dir / "log.txt"

    diagnostics_path = str(Path(payload.get("export_path")).with_suffix(".diagnostics.json")) if payload.get("export_path") else None

    _update_status(
        status_path,
        "running",
        0.02,
        "Loading settings",
        str(log_path),
        payload.get("export_path"),
        diagnostics_path=diagnostics_path,
    )

    try:
        _bootstrap_plugin_package()
        _ensure_addon_loaded()
    except Exception as exc:
        _update_status(
            status_path,
            "error",
            1.0,
            f"Unable to load BlenderToRCP add-on: {exc}",
            str(log_path),
            payload.get("export_path"),
            diagnostics_path=diagnostics_path,
        )
        print("Addon load error:", exc)
        traceback.print_exc()
        return 1
    if not hasattr(bpy.types.Scene, "blender_to_rcp_export_settings"):
        _update_status(
            status_path,
            "error",
            1.0,
            "BlenderToRCP add-on not loaded",
            str(log_path),
            export_path=payload.get("export_path"),
            diagnostics_path=diagnostics_path,
        )
        return 1

    scene_settings = bpy.context.scene.blender_to_rcp_export_settings
    _apply_settings(scene_settings, payload.get("export_settings", {}))

    export_path = payload.get("export_path")
    if export_path:
        scene_settings.filepath = export_path

    if payload.get("selected_only"):
        _select_objects(payload.get("selection") or [])

    _update_status(
        status_path,
        "running",
        0.08,
        "Preparing bake",
        str(log_path),
        export_path=payload.get("export_path"),
        diagnostics_path=diagnostics_path,
    )

    try:
        from Plugin.ops import bake_export_operator as bake_ops
        from Plugin.export import bake_textures, blender_usd_export, postprocess_usd, pack_usdz, diagnostics
        from Plugin.nodes import validate as rk_validate
    except Exception as exc:
        _update_status(
            status_path,
            "error",
            1.0,
            f"Import failed: {exc}",
            str(log_path),
            export_path=payload.get("export_path"),
            diagnostics_path=diagnostics_path,
        )
        print("Import error:", exc)
        traceback.print_exc()
        return 1

    diag = diagnostics.ExportDiagnostics()
    try:
        from Plugin.export.support_bundle import collect_environment, collect_scene_snapshot
        diag.set_export_context(
            command="background_bake_export",
            resolved_output_path=payload.get("export_path"),
            export_format=getattr(scene_settings, "export_format", None),
            selected_only=bool(payload.get("selected_only")),
            blend_file=payload.get("blend_file"),
            job_dir=str(job_dir),
        )
        diag.set_environment(**collect_environment(bpy.context))
        diag.data["scene"] = collect_scene_snapshot(bpy.context)
    except Exception:
        pass
    objects_to_export = bake_ops._collect_export_objects(bpy.context, scene_settings)

    if not objects_to_export:
        _save_diagnostics(diag, diagnostics_path)
        _update_status(
            status_path,
            "error",
            1.0,
            "No exportable objects found",
            export_path=payload.get("export_path"),
            diagnostics_path=diagnostics_path,
        )
        return 1

    original_selection = list(bpy.context.selected_objects)
    original_active = bpy.context.view_layer.objects.active
    original_mode = original_active.mode if original_active else 'OBJECT'
    original_engine = bpy.context.scene.render.engine
    original_force_unlit = getattr(scene_settings, "force_unlit_materials", False)

    bake_result = None
    progress_reporter = None

    try:
        bake_ops._ensure_object_mode(bpy.context)
        bake_ops._set_render_engine(bpy.context.scene, 'CYCLES')

        if scene_settings.export_format == "USDZ":
            texture_dir = blender_usd_export.get_usdz_staging_dir(export_path) / "textures"
        else:
            texture_dir = Path(export_path).parent / "textures"
        progress_reporter = _BakeProgressReporter(
            status_path,
            payload.get("export_path"),
            str(log_path),
            diagnostics_path,
        )
        progress_reporter.start()

        def _set_running_stage(progress: float, message: str) -> None:
            progress_reporter.update(max(0.0, min(1.0, float(progress))), message)

        def _bake_progress(progress: float, message: str) -> None:
            _set_running_stage(0.15 + (0.35 * max(0.0, min(1.0, float(progress)))), message)

        _set_running_stage(0.15, "Baking textures")
        bake_result = bake_textures.bake_materials_for_objects(
            bpy.context,
            scene_settings,
            objects_to_export,
            texture_dir,
            diag,
            progress_callback=_bake_progress,
        )

        # Bake Textures & Export always authors Unlit materials.
        scene_settings.force_unlit_materials = True

        if getattr(scene_settings, "selected_objects_only", False):
            bake_ops._set_selection(bpy.context, objects_to_export)

        _set_running_stage(0.5, "Validating materials")
        materials = bake_ops._collect_materials_from_objects(objects_to_export)
        for material in materials:
            try:
                result = rk_validate.validate_material(material, strict=True)
            except TypeError:
                result = rk_validate.validate_material(material)
                if result.get("warnings"):
                    result["errors"].extend(result["warnings"])
                    result["warnings"] = []
                result["ok"] = not result["errors"]
            if result["errors"]:
                error_count = len(result["errors"])
                for issue in result["errors"]:
                    diag.add_validation_issue(material.name, issue, severity="error")
                progress_reporter.stop()
                _save_diagnostics(diag, diagnostics_path)
                _update_status(
                    status_path,
                    "error",
                    1.0,
                    f"Unsupported nodes in material '{material.name}' ({error_count})",
                    str(log_path),
                    export_path=payload.get("export_path"),
                    diagnostics_path=diagnostics_path,
                )
                return 1

        _set_running_stage(0.55, "Exporting USD")
        temp_usd_path = blender_usd_export.export_blender_scene(
            bpy.context,
            scene_settings,
            export_path,
            diag,
        )
        if not temp_usd_path or not Path(temp_usd_path).exists():
            progress_reporter.stop()
            _save_diagnostics(diag, diagnostics_path)
            _update_status(
                status_path,
                "error",
                1.0,
                "Blender USD export failed",
                str(log_path),
                export_path=payload.get("export_path"),
                diagnostics_path=diagnostics_path,
            )
            return 1

        _set_running_stage(0.7, "Rewriting materials (Unlit)")
        postprocess_usd.process_usd_stage(
            temp_usd_path,
            scene_settings,
            bpy.context,
            diag
        )

        if diag.data.get("errors"):
            progress_reporter.stop()
            _save_diagnostics(diag, diagnostics_path)
            _update_status(
                status_path,
                "error",
                1.0,
                "Postprocess failed; see diagnostics",
                str(log_path),
                export_path=payload.get("export_path"),
                diagnostics_path=diagnostics_path,
            )
            return 1

        if scene_settings.export_format == "USDZ":
            _set_running_stage(0.85, "Packaging USDZ")
            pack_usdz.create_usdz(
                temp_usd_path,
                export_path,
                scene_settings,
                bpy.context,
                diag
            )
        else:
            import shutil
            if temp_usd_path != export_path:
                shutil.move(temp_usd_path, export_path)

        progress_reporter.stop()
        _save_diagnostics(diag, diagnostics_path)
        _update_status(
            status_path,
            "done",
            1.0,
            "Bake Textures & Export complete",
            str(log_path),
            export_path,
            diagnostics_path=diagnostics_path,
        )
        return 0

    except Exception as exc:
        if progress_reporter is not None:
            progress_reporter.stop()
        try:
            diag.add_exception(exc, stage="background_bake_export")
        except Exception:
            pass
        _save_diagnostics(diag, diagnostics_path)
        _update_status(
            status_path,
            "error",
            1.0,
            f"Exception: {exc}",
            str(log_path),
            export_path=payload.get("export_path"),
            diagnostics_path=diagnostics_path,
        )
        print("Bake export error:", exc)
        traceback.print_exc()
        return 1
    finally:
        if progress_reporter is not None:
            progress_reporter.stop()
        scene_settings.force_unlit_materials = original_force_unlit
        try:
            bpy.context.scene.render.engine = original_engine
        except Exception:
            pass
        if bake_result is not None:
            bake_textures.restore_baked_materials(
                bake_result,
                bool(getattr(scene_settings, "bake_keep_materials", False)),
            )
        bake_ops._restore_selection(bpy.context, original_selection, original_active)
        bake_ops._restore_mode(bpy.context, original_active, original_mode)


def _save_diagnostics(diag, diagnostics_path: str | None) -> None:
    if not diagnostics_path:
        return
    try:
        diag.set_artifact("diagnostics_path", diagnostics_path)
        diag.save(Path(diagnostics_path))
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
