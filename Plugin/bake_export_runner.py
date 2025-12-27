"""
Background bake + export runner for BlenderToRCP.

Usage (invoked by Blender):
  blender --background <file.blend> --python bake_export_runner.py -- <settings.json>
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
import time

import bpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _ensure_addon_loaded() -> None:
    if hasattr(bpy.types.Scene, "blender_to_rcp_export_settings"):
        return
    for module_name in ("bl_ext.blender_local_addons.BlenderToRCP", "BlenderToRCP"):
        try:
            bpy.ops.preferences.addon_enable(module=module_name)
        except Exception:
            continue
        if hasattr(bpy.types.Scene, "blender_to_rcp_export_settings"):
            return


def _update_status(
    status_path: Path,
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
        status_path.write_text(json.dumps(payload, indent=2))
    except Exception:
        pass


def _apply_settings(scene_settings, data: dict) -> None:
    prop_defs = {prop.identifier for prop in scene_settings.bl_rna.properties}
    for key, value in data.items():
        if key in {"rna_type", "name", "history_applied", "last_diagnostics_path"}:
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

    _update_status(status_path, "running", 0.02, "Loading settings", str(log_path), payload.get("export_path"))

    _ensure_addon_loaded()
    if not hasattr(bpy.types.Scene, "blender_to_rcp_export_settings"):
        _update_status(status_path, "error", 1.0, "BlenderToRCP add-on not loaded", export_path=payload.get("export_path"))
        return 1

    scene_settings = bpy.context.scene.blender_to_rcp_export_settings
    _apply_settings(scene_settings, payload.get("export_settings", {}))

    export_path = payload.get("export_path")
    if export_path:
        scene_settings.filepath = export_path

    if payload.get("selected_only"):
        _select_objects(payload.get("selection") or [])

    _update_status(status_path, "running", 0.08, "Preparing bake", export_path=payload.get("export_path"))

    try:
        from Plugin.ops import bake_export_operator as bake_ops
        from Plugin.export import bake_textures, blender_usd_export, postprocess_usd, pack_usdz, diagnostics
        from Plugin.nodes import validate as rk_validate
    except Exception as exc:
        _update_status(status_path, "error", 1.0, f"Import failed: {exc}", export_path=payload.get("export_path"))
        print("Import error:", exc)
        traceback.print_exc()
        return 1

    diag = diagnostics.ExportDiagnostics()
    objects_to_export = bake_ops._collect_export_objects(bpy.context, scene_settings)

    if not objects_to_export:
        _update_status(status_path, "error", 1.0, "No exportable objects found", export_path=payload.get("export_path"))
        return 1

    original_selection = list(bpy.context.selected_objects)
    original_active = bpy.context.view_layer.objects.active
    original_mode = original_active.mode if original_active else 'OBJECT'
    original_engine = bpy.context.scene.render.engine
    original_force_unlit = getattr(scene_settings, "force_unlit_materials", False)

    bake_result = None

    try:
        bake_ops._ensure_object_mode(bpy.context)
        bake_ops._set_render_engine(bpy.context.scene, 'CYCLES')

        texture_dir = Path(export_path).parent / "textures"
        def _bake_progress(progress, message):
            _update_status(
                status_path,
                "running",
                0.15 + (0.35 * float(progress)),
                message,
                export_path=payload.get("export_path"),
            )

        _update_status(status_path, "running", 0.15, "Baking textures", export_path=payload.get("export_path"))
        bake_result = bake_textures.bake_materials_for_objects(
            bpy.context,
            scene_settings,
            objects_to_export,
            texture_dir,
            diag,
            progress_callback=_bake_progress,
        )

        scene_settings.force_unlit_materials = True

        if getattr(scene_settings, "selected_objects_only", False):
            bake_ops._set_selection(bpy.context, objects_to_export)

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
                _update_status(
                    status_path,
                    "error",
                    1.0,
                    f"Unsupported nodes in material '{material.name}' ({error_count})",
                    export_path=payload.get("export_path"),
                )
                return 1

        _update_status(status_path, "running", 0.55, "Exporting USD", export_path=payload.get("export_path"))
        temp_usd_path = blender_usd_export.export_blender_scene(
            bpy.context,
            scene_settings,
            export_path,
            diag,
        )
        if not temp_usd_path or not Path(temp_usd_path).exists():
            _update_status(status_path, "error", 1.0, "Blender USD export failed", export_path=payload.get("export_path"))
            return 1

        _update_status(status_path, "running", 0.7, "Rewriting materials (Unlit)", export_path=payload.get("export_path"))
        postprocess_usd.process_usd_stage(
            temp_usd_path,
            scene_settings,
            bpy.context,
            diag
        )

        if diag.data.get("errors"):
            _update_status(status_path, "error", 1.0, "Postprocess failed; see diagnostics", export_path=payload.get("export_path"))
            return 1

        if scene_settings.export_format == "USDZ":
            _update_status(status_path, "running", 0.85, "Packaging USDZ", export_path=payload.get("export_path"))
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

        _update_status(status_path, "done", 1.0, "Bake & Export complete", str(log_path), export_path)
        return 0

    except Exception as exc:
        _update_status(status_path, "error", 1.0, f"Exception: {exc}", export_path=payload.get("export_path"))
        print("Bake export error:", exc)
        traceback.print_exc()
        return 1
    finally:
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


if __name__ == "__main__":
    sys.exit(main())
