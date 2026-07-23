"""
Background bake + export runner for BlenderToRCP.

Usage (invoked by Blender):
  blender --background <file.blend> --python bake_export_runner.py -- <settings.json>
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
import time
import threading

import bpy

PLUGIN_ROOT = Path(__file__).resolve().parent
_PACKAGE_NAME: str | None = None
_PACKAGE_MODULE = None


def _bootstrap_plugin_package() -> str:
    """Load the owning extension package once and return its actual name."""
    global _PACKAGE_NAME, _PACKAGE_MODULE
    if _PACKAGE_NAME is not None:
        return _PACKAGE_NAME

    bootstrap_path = PLUGIN_ROOT / "core" / "package_bootstrap.py"
    spec = importlib.util.spec_from_file_location(
        "_blendertorcp_package_bootstrap",
        bootstrap_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load BlenderToRCP package bootstrap: {bootstrap_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _PACKAGE_NAME, _PACKAGE_MODULE = module.load_extension_package(PLUGIN_ROOT)
    return _PACKAGE_NAME


def _import_package_module(suffix: str):
    package_name = _bootstrap_plugin_package()
    return importlib.import_module(f"{package_name}.{suffix}")


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
    addon_loader = _import_package_module("api.addon_loader")
    addon_loader.ensure_addon_loaded()


def _consume_loaded_scene_snapshot(payload: dict, job_dir: Path) -> dict:
    """Delete a verified worker snapshot after Blender has loaded it.

    The UI always names this disposable copy ``scene_snapshot.blend`` inside
    the job directory.  Keep it intact when startup did not load that exact
    file so a failed worker remains diagnosable and no unrelated file can be
    removed from a malformed payload.
    """
    snapshot_value = payload.get("blend_file")
    if not snapshot_value:
        return {
            "loaded": False,
            "removed": False,
            "cleanup_deferred": False,
            "cleanup_error": None,
        }

    snapshot = Path(snapshot_value).expanduser()
    expected = job_dir / "scene_snapshot.blend"
    try:
        snapshot_resolved = snapshot.resolve()
        expected_resolved = expected.resolve()
        loaded_resolved = Path(bpy.data.filepath).resolve()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Could not verify the background scene snapshot: {exc}") from exc

    if snapshot_resolved != expected_resolved:
        raise RuntimeError(
            "Refusing to consume an unexpected background scene snapshot path: "
            f"{snapshot}"
        )
    if loaded_resolved != snapshot_resolved:
        source = payload.get("source_blend_file") or "unsaved scene"
        raise RuntimeError(
            "Blender did not load the background scene snapshot. "
            f"Expected {snapshot}; loaded {bpy.data.filepath or '<none>'}; source {source}."
        )

    state = {
        "loaded": True,
        "removed": False,
        "cleanup_deferred": False,
        "cleanup_error": None,
    }
    try:
        snapshot.unlink()
    except OSError as exc:
        # Windows and some network filesystems can retain a sharing lock after
        # Blender has loaded the file.  The UI watcher and stale-job janitor own
        # the retry after this worker exits; a recoverable lock must not abort
        # an otherwise valid export.
        state["cleanup_deferred"] = True
        state["cleanup_error"] = f"{exc.__class__.__name__}: {exc}"
    else:
        state["removed"] = True
    return state


# Crash guard: while armed, an unexpected Blender shutdown writes a terminal
# error status so the UI job monitor never hangs on a stale "running" state.
_CRASH_GUARD: dict = {"status_path": None}


def _on_blender_exit(_user_exit: bool) -> None:
    status_path = _CRASH_GUARD.get("status_path")
    if status_path is None:
        return
    _CRASH_GUARD["status_path"] = None
    _update_status(
        Path(status_path),
        "error",
        message="Blender exited before the bake/export job finished.",
    )


def _arm_crash_guard(status_path: Path) -> None:
    import bpy

    _CRASH_GUARD["status_path"] = str(status_path)
    if _on_blender_exit not in bpy.app.handlers.exit_pre:
        bpy.app.handlers.exit_pre.append(_on_blender_exit)


def _update_status(
    status_path: Path,
    state: str,
    progress: float | None = None,
    message: str | None = None,
    log_path: str | None = None,
    export_path: str | None = None,
    diagnostics_path: str | None = None,
    step_elapsed_seconds: int | None = None,
    error_code: str | None = None,
    stage: str | None = None,
    timeout_seconds: int | None = None,
) -> None:
    if state in ("done", "error"):
        # Terminal state reached normally: the crash guard is no longer needed.
        _CRASH_GUARD["status_path"] = None
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
    if error_code:
        payload["error_code"] = error_code
    if stage:
        payload["stage"] = stage
    if timeout_seconds is not None:
        payload["timeout_seconds"] = int(timeout_seconds)
    tmp_path = status_path.with_name(
        f".{status_path.name}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
    )
    try:
        tmp_path.write_text(json.dumps(payload, indent=2))
        os.replace(tmp_path, status_path)
    except Exception:
        pass
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
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
        timeout_seconds: int = 0,
        on_timeout=None,
    ):
        # Imported lazily because this file is also executed directly before
        # the owning extension package has been bootstrapped.
        StepTimeoutWatchdog = _import_package_module("cli.bridge").StepTimeoutWatchdog

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
        self._timeout_latched = threading.Event()
        self._timeout_watchdog = StepTimeoutWatchdog(
            timeout_seconds,
            on_timeout or (lambda _step, _elapsed, _limit: None),
        )

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="BakeProgressHeartbeat", daemon=True)
        self._thread.start()
        self._timeout_watchdog.start(self._message)

    def stop(self) -> None:
        self._stop_event.set()
        self._timeout_watchdog.stop()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join()
        self._thread = None

    def latch_timeout(self) -> None:
        """Stop heartbeat writes before publishing terminal timeout status."""
        self._timeout_latched.set()
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=2.0)

    @property
    def timed_out(self) -> bool:
        return self._timeout_latched.is_set()

    def update(self, progress: float, message: str) -> None:
        now = time.time()
        step_changed = False
        with self._lock:
            self._progress = max(0.0, min(1.0, float(progress)))
            if message and message != self._message:
                self._message = message
                self._step_started = now
                self._tick = 0
                step_changed = True
        if step_changed:
            self._timeout_watchdog.enter_step(message)
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

    diagnostics_path = payload.get("diagnostics_path")

    _arm_crash_guard(status_path)
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
        snapshot_state = _consume_loaded_scene_snapshot(payload, job_dir)
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
        bake_ops = _import_package_module("ops.bake_export_operator")
        animation_export = _import_package_module("export.animation_export")
        asset_preflight = _import_package_module("export.asset_preflight")
        bake_finalize = _import_package_module("export.bake_finalize")
        bake_textures = _import_package_module("export.bake_textures")
        blender_usd_export = _import_package_module("export.blender_usd_export")
        postprocess_usd = _import_package_module("export.postprocess_usd")
        pack_usdz = _import_package_module("export.pack_usdz")
        diagnostics = _import_package_module("export.diagnostics")
        bake_export_command = _import_package_module("api.commands.bake_export")
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
        support_bundle = _import_package_module("export.support_bundle")
        collect_environment = support_bundle.collect_environment
        collect_scene_snapshot = support_bundle.collect_scene_snapshot
        source_blend_file = payload.get("source_blend_file") or None
        diag.set_export_context(
            command="background_bake_export",
            resolved_output_path=payload.get("export_path"),
            export_format=getattr(scene_settings, "export_format", None),
            selected_only=bool(payload.get("selected_only")),
            blend_file=source_blend_file,
            source_blend_file=source_blend_file,
            scene_snapshot_loaded=bool(snapshot_state["loaded"]),
            scene_snapshot_consumed=bool(snapshot_state["removed"]),
            scene_snapshot_cleanup_deferred=bool(snapshot_state["cleanup_deferred"]),
            job_dir=str(job_dir),
        )
        diag.set_environment(**collect_environment(bpy.context))
        scene_snapshot = collect_scene_snapshot(bpy.context)
        if isinstance(scene_snapshot, dict):
            scene_snapshot["file"] = source_blend_file
            scene_snapshot["loaded_from_temporary_snapshot"] = bool(
                snapshot_state["loaded"]
            )
        diag.data["scene"] = scene_snapshot
        diag.data["scene_snapshot_cleanup"] = dict(snapshot_state)
        if snapshot_state["cleanup_deferred"]:
            diag.add_warning(
                "Temporary scene snapshot cleanup was deferred until the background "
                f"worker exits: {snapshot_state['cleanup_error']}"
            )
    except Exception:
        pass
    diag.data.setdefault("validation", {})["skipped"] = True
    diag.data["validation"]["reason"] = (
        "Bake Textures & Export bakes source materials before export; "
        "source material graph validation only applies to Export Scene."
    )
    # The native USD scope intentionally excludes collection prototypes;
    # Blender expands them from a selected collection instance.  Processing
    # still has to include every prototype/parent mesh and material.
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

    processing_objects = animation_export.collect_processing_objects(
        bpy.context,
        objects_to_export,
    )
    missing_images = asset_preflight.collect_missing_image_files_for_objects(
        processing_objects,
        bpy,
    )
    if missing_images:
        asset_preflight.record_missing_image_files(diag, missing_images)
        _save_diagnostics(diag, diagnostics_path)
        _update_status(
            status_path,
            "error",
            1.0,
            asset_preflight.missing_images_status_message(missing_images),
            str(log_path),
            export_path=payload.get("export_path"),
            diagnostics_path=diagnostics_path,
        )
        return 1

    original_selection = list(bpy.context.selected_objects)
    original_active = bpy.context.view_layer.objects.active
    original_mode = original_active.mode if original_active else 'OBJECT'
    original_engine = bpy.context.scene.render.engine
    original_force_unlit = getattr(scene_settings, "force_unlit_materials", False)
    processing_link_state = {
        "scene": bpy.context.scene,
        "temporary_scene_links": [],
    }

    bake_result = None
    staging_dir = None
    temp_usd_path = None
    try:
        step_timeout_seconds = max(
            0,
            int(getattr(scene_settings, "bake_step_timeout_seconds", 0) or 0),
        )
    except (TypeError, ValueError):
        step_timeout_seconds = 0
    write_timeout_diagnostics = _import_package_module(
        "cli.bridge"
    ).write_timeout_diagnostics

    timeout_diagnostic_base = json.loads(json.dumps(diag.data, default=str))

    def _step_timed_out(step: str, elapsed: float, limit: float) -> None:
        limit_seconds = int(limit)
        elapsed_seconds = round(float(elapsed), 2)
        message = (
            f"Bake/export step '{step}' timed out after {limit_seconds}s; "
            "the background Blender worker was terminated."
        )
        timeout_details = {
            "code": "BAKE_STEP_TIMEOUT",
            "stage": step,
            "timeout_seconds": limit_seconds,
            "elapsed_seconds": elapsed_seconds,
        }
        progress_reporter.latch_timeout()
        _update_status(
            status_path,
            "error",
            1.0,
            message,
            str(log_path),
            export_path=payload.get("export_path"),
            diagnostics_path=diagnostics_path,
            step_elapsed_seconds=int(elapsed),
            error_code="BAKE_STEP_TIMEOUT",
            stage=step,
            timeout_seconds=limit_seconds,
        )
        print(message, file=sys.stderr, flush=True)
        try:
            write_timeout_diagnostics(
                diagnostics_path,
                timeout_diagnostic_base,
                timeout_details,
                message,
            )
        except Exception as exc:
            print(
                f"Unable to write timeout diagnostics: {exc}",
                file=sys.stderr,
                flush=True,
            )

    progress_reporter = _BakeProgressReporter(
        status_path,
        payload.get("export_path"),
        str(log_path),
        diagnostics_path,
        timeout_seconds=step_timeout_seconds,
        on_timeout=_step_timed_out,
    )
    progress_reporter.start()
    progress_reporter.update(0.1, "Preparing Blender scene")
    terminal_status = None

    def _defer_terminal_status(state: str, message: str) -> None:
        nonlocal terminal_status
        terminal_status = {
            "state": state,
            "message": message,
        }

    try:
        bake_ops._ensure_object_mode(bpy.context)
        bake_ops._set_render_engine(bpy.context.scene, 'CYCLES')
        animation_export._link_processing_objects_for_bake(
            bpy.context,
            processing_objects,
            processing_link_state,
        )

        # Allocate one unique staging attempt before baking. The exact same
        # directory is passed to the native export below so it preserves the
        # freshly baked textures without sharing state with another attempt.
        staging_dir = blender_usd_export.create_export_staging_dir(export_path, diag)
        texture_dir = staging_dir / "textures"

        def _set_running_stage(progress: float, message: str) -> None:
            progress_reporter.update(max(0.0, min(1.0, float(progress))), message)

        def _bake_progress(progress: float, message: str) -> None:
            _set_running_stage(0.15 + (0.35 * max(0.0, min(1.0, float(progress)))), message)

        _set_running_stage(0.15, "Baking textures")
        bake_result = bake_textures.bake_materials_for_objects(
            bpy.context,
            scene_settings,
            processing_objects,
            texture_dir,
            diag,
            progress_callback=_bake_progress,
        )

        _set_running_stage(0.48, "Finalizing baked materials")
        bake_finalize.apply_force_unlit(scene_settings)

        ## Y-up geometry bake when requested (and safe). This runner's scene is a
        ## throwaway background process, so the returned restore state is only
        ## used to decide whether to author upAxis=Y below - never to restore.
        _set_running_stage(0.49, "Applying Y-up geometry conversion")
        yup_state = bake_finalize.maybe_apply_yup_geometry_bake(
            bpy.context, scene_settings, objects_to_export, diag
        )

        bake_export_command._unlink_processing_scope(
            animation_export,
            processing_link_state,
            strict=True,
        )
        ## Set the export selection last so the Y-up bake's mesh-selection churn
        ## above can't clobber a selected-objects-only export.
        if getattr(scene_settings, "selected_objects_only", False):
            animation_export._set_export_selection(
                bpy.context,
                objects_to_export,
            )

        _set_running_stage(0.5, "Exporting USD")
        temp_usd_path = blender_usd_export.export_blender_scene(
            bpy.context,
            scene_settings,
            export_path,
            diag,
            reset_staging=False,
            staging_dir=staging_dir,
        )
        if not temp_usd_path or not Path(temp_usd_path).exists():
            _save_diagnostics(diag, diagnostics_path)
            _defer_terminal_status("error", "Blender USD export failed")
            return 1

        _set_running_stage(0.7, "Rewriting materials (Unlit)")
        postprocess_usd.process_usd_stage(
            temp_usd_path,
            scene_settings,
            bpy.context,
            diag,
            force_up_axis_y=yup_state is not None,
        )

        if diag.data.get("errors"):
            _save_diagnostics(diag, diagnostics_path)
            _defer_terminal_status(
                "error",
                "Postprocess failed; see diagnostics"
                if diagnostics_path
                else "Postprocess failed",
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
            _set_running_stage(0.9, "Publishing USD export")
            if temp_usd_path != export_path:
                blender_usd_export.publish_unpacked_export(temp_usd_path, export_path, diag)

        _set_running_stage(0.95, "Writing diagnostics")
        _save_diagnostics(diag, diagnostics_path)
        _defer_terminal_status("done", "Bake Textures & Export complete")
        return 0

    except Exception as exc:
        try:
            diag.add_exception(exc, stage="background_bake_export")
        except Exception:
            pass
        _save_diagnostics(diag, diagnostics_path)
        _defer_terminal_status("error", f"Exception: {exc}")
        print("Bake export error:", exc)
        traceback.print_exc()
        return 1
    finally:
        progress_reporter.update(0.98, "Restoring Blender scene")
        cleanup_errors = []

        def _cleanup_error(label: str, exc: Exception) -> None:
            cleanup_errors.append(f"{label}: {exc}")

        try:
            bake_export_command._unlink_processing_scope(
                animation_export,
                processing_link_state,
                strict=True,
            )
        except Exception as exc:
            _cleanup_error("unlink temporary bake dependencies", exc)
        try:
            scene_settings.force_unlit_materials = original_force_unlit
        except Exception as exc:
            _cleanup_error("restore material mode", exc)
        try:
            bpy.context.scene.render.engine = original_engine
        except Exception as exc:
            _cleanup_error("restore render engine", exc)
        if bake_result is not None:
            try:
                bake_textures.restore_baked_materials(
                    bake_result,
                    bool(getattr(scene_settings, "bake_keep_materials", False)),
                )
            except Exception as exc:
                _cleanup_error("restore baked materials", exc)
        try:
            bake_ops._restore_selection(bpy.context, original_selection, original_active)
        except Exception as exc:
            _cleanup_error("restore selection", exc)
        try:
            bake_ops._restore_mode(bpy.context, original_active, original_mode)
        except Exception as exc:
            _cleanup_error("restore object mode", exc)
        # Clean only this attempt. Prefer the directory proven by the returned
        # USD path; before export returns, fall back to the directory allocated
        # for the bake. A failing native export cleans its own attempt.
        cleanup_staging_dir = (
            Path(temp_usd_path).parent if temp_usd_path else staging_dir
        )
        if cleanup_staging_dir is not None:
            try:
                blender_usd_export.remove_export_staging_dir(
                    export_path,
                    diag,
                    staging_dir=cleanup_staging_dir,
                )
            except Exception as exc:
                _cleanup_error("remove staging directory", exc)
        progress_reporter.stop()

        if progress_reporter.timed_out:
            # The watchdog owns both status and process outcome once latched.
            # Returning 124 also keeps the result correct if normal interpreter
            # shutdown races the watchdog's os._exit(124).
            return 124

        if cleanup_errors:
            cleanup_message = "Cleanup failed: " + "; ".join(cleanup_errors[:3])
            try:
                diag.add_error(cleanup_message)
                _save_diagnostics(diag, diagnostics_path)
            except Exception:
                pass
            terminal_status = {
                "state": "error",
                "message": cleanup_message,
            }
        if terminal_status is None:
            terminal_status = {
                "state": "error",
                "message": "Background bake/export exited without a result.",
            }
        _update_status(
            status_path,
            terminal_status["state"],
            1.0,
            terminal_status["message"],
            str(log_path),
            export_path=payload.get("export_path"),
            diagnostics_path=diagnostics_path,
        )
        if cleanup_errors:
            return 1


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
