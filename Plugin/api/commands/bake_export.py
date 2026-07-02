"""bake_export command — bake textures and export scene.

This runs synchronously inside background Blender (blocking).
The CLI invocation already runs Blender in the background so the caller
(the bridge) can handle timeouts externally.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from ._settings_common import INTERNAL_KEYS, get_settings, coerce_value
from Plugin.api.errors import CommandError


def handle(args: dict) -> dict:
    import bpy
    from Plugin.export import (
        asset_preflight,
        bake_finalize,
        bake_textures,
        blender_usd_export,
        postprocess_usd,
        pack_usdz,
        diagnostics,
    )
    from Plugin.export.support_bundle import collect_environment, collect_scene_snapshot
    from Plugin.ops import bake_export_operator as bake_ops

    filepath = args.get("filepath")
    if not filepath:
        raise ValueError("'filepath' is required (output path).")

    settings = get_settings()
    no_diagnostics = args.get("no_diagnostics", False)

    # Apply overrides
    overrides = args.get("overrides", {})
    prop_defs = {prop.identifier: prop for prop in settings.bl_rna.properties}
    invalid_overrides = []
    for key, value in overrides.items():
        if key in INTERNAL_KEYS:
            invalid_overrides.append({"key": key, "reason": "internal setting"})
            continue
        prop = prop_defs.get(key)
        if prop is None:
            invalid_overrides.append({"key": key, "reason": "unknown setting"})
            continue
        try:
            setattr(settings, key, coerce_value(prop, value))
        except Exception as exc:
            invalid_overrides.append({"key": key, "reason": str(exc)})

    if invalid_overrides:
        raise CommandError(
            "Invalid bake-export setting override.",
            code="INVALID_SETTING_OVERRIDE",
            details=invalid_overrides,
        )

    # Apply direct args as setting overrides
    _DIRECT_OVERRIDES = {
        "format": "export_format",
        "bake_mode": "bake_mode",
        "resolution": None,  # handled specially
        "image_format": "bake_image_format",
        "margin": "bake_margin",
        "ibl_source": "bake_ibl_source",
        "ibl_filepath": "bake_ibl_filepath",
        "ibl_strength": "bake_ibl_strength",
        "ibl_rotation": "bake_ibl_rotation",
        "isolate_meshes": "bake_isolate_meshes_lit",
        "timeout": "bake_step_timeout_seconds",
    }
    for arg_key, setting_key in _DIRECT_OVERRIDES.items():
        if arg_key in args and setting_key is not None:
            prop = prop_defs.get(setting_key)
            if prop:
                try:
                    setattr(settings, setting_key, coerce_value(prop, args[arg_key]))
                except Exception:
                    pass

    # Handle resolution: could be a preset or custom int
    if "resolution" in args:
        settings.export_texture_settings_enabled = True
        res = args["resolution"]
        res_str = str(res)
        if res_str.upper().replace("-", "_") in {"ORIGINAL", "KEEP_ORIGINAL"}:
            settings.bake_resolution = "ORIGINAL"
        elif res_str in ("512", "1024", "2048", "4096"):
            settings.bake_resolution = res_str
        else:
            settings.bake_resolution = "CUSTOM"
            settings.bake_resolution_custom = int(res)
    if "image_format" in args:
        settings.export_texture_settings_enabled = True
    if "margin" in args:
        settings.export_texture_settings_enabled = True

    if args.get("selected_only"):
        settings.selected_objects_only = True
    if args.get("no_base_color"):
        settings.bake_base_color = False
    if args.get("no_opacity"):
        settings.bake_opacity = False
    if args.get("keep_materials"):
        settings.bake_keep_materials = True
    if args.get("diagnostics"):
        settings.diagnostics_enabled = True

    # Set format
    if "format" in args:
        settings.export_format = args["format"].upper()

    # Enforce extension
    ext_map = {"USDA": ".usda", "USDC": ".usdc", "USDZ": ".usdz"}
    ext = ext_map.get(settings.export_format, ".usdz")
    filepath = str(Path(filepath).with_suffix(ext))
    settings.filepath = filepath

    diag = diagnostics.ExportDiagnostics()
    diagnostics_enabled = bool(getattr(settings, "diagnostics_enabled", False)) and not no_diagnostics
    diagnostics_path = str(Path(filepath).with_suffix(".diagnostics.json")) if diagnostics_enabled else None
    diag.set_export_context(
        command="bake_export",
        requested_path=args.get("filepath"),
        resolved_output_path=filepath,
        export_format=settings.export_format,
        selected_only=bool(getattr(settings, "selected_objects_only", False)),
        blend_file=bpy.data.filepath or None,
    )
    diag.set_environment(**collect_environment(bpy.context))
    diag.data["scene"] = collect_scene_snapshot(bpy.context)
    diag.data.setdefault("validation", {})["skipped"] = True
    diag.data["validation"]["reason"] = (
        "Bake Textures & Export bakes source materials before export; "
        "source material graph validation only applies to Export Scene."
    )

    # Collect objects
    objects_to_export = bake_ops._collect_export_objects(bpy.context, settings)
    if not objects_to_export:
        _save_diagnostics(diag, diagnostics_path)
        raise CommandError(
            "No exportable objects found.",
            code="NO_EXPORTABLE_OBJECTS",
            stage="validation",
            artifacts=_artifacts(diagnostics_path, filepath, bpy.data.filepath),
        )

    missing_images = asset_preflight.collect_missing_image_files_for_objects(objects_to_export, bpy)
    if missing_images:
        asset_preflight.record_missing_image_files(diag, missing_images)
        _save_diagnostics(diag, diagnostics_path)
        raise CommandError(
            asset_preflight.missing_images_status_message(missing_images),
            code="MISSING_EXTERNAL_TEXTURES",
            stage="asset_preflight",
            details=missing_images,
            artifacts=_artifacts(diagnostics_path, filepath, bpy.data.filepath),
        )

    # Save originals for cleanup
    original_selection = list(bpy.context.selected_objects)
    original_active = bpy.context.view_layer.objects.active
    original_mode = original_active.mode if original_active else "OBJECT"
    original_engine = bpy.context.scene.render.engine
    original_force_unlit = getattr(settings, "force_unlit_materials", False)

    bake_result = None
    start_time = time.time()

    try:
        bake_ops._ensure_object_mode(bpy.context)
        bake_ops._set_render_engine(bpy.context.scene, "CYCLES")

        ## Reset the staging dir ONCE before baking textures into it; the export
        ## below passes reset_staging=False so it won't delete the baked textures.
        blender_usd_export._reset_export_staging_dir(
            blender_usd_export.get_export_staging_dir(filepath), diag
        )
        texture_dir = blender_usd_export.get_export_staging_dir(filepath) / "textures"
        resolved_image_format = bake_textures._resolve_bake_image_format(settings, diag, safe_for_blender_save=True)
        diag.data["bake"] = {
            "mode": getattr(settings, "bake_mode", None),
            "resolution": bake_textures._resolve_bake_resolution(settings),
            "image_format": resolved_image_format["file_format"],
            "margin": bake_textures._resolve_bake_margin(settings),
            "base_color": bool(getattr(settings, "bake_base_color", False)),
            "opacity": bool(getattr(settings, "bake_opacity", False)),
            "isolate_meshes_lit": bool(getattr(settings, "bake_isolate_meshes_lit", False)),
            "texture_settings_enabled": bool(getattr(settings, "export_texture_settings_enabled", False)),
            "object_count": len(objects_to_export),
            "texture_dir": str(texture_dir),
        }

        # Bake
        diag.begin_phase("bake_textures", {"texture_dir": str(texture_dir)})
        bake_result = bake_textures.bake_materials_for_objects(
            bpy.context, settings, objects_to_export, texture_dir, diag
        )
        diag.end_phase("bake_textures")

        # Author Lit PBR only for "Material Color Only - Lit PBR"; every other
        # bake mode stays Unlit — same as the interactive path.
        bake_finalize.apply_force_unlit(settings)

        # Capture BEFORE the Y-up bake, which clears convert_orientation.
        apply_yup = bake_finalize.should_apply_yup(settings)
        if apply_yup:
            yup_objects = (
                objects_to_export
                if getattr(settings, "selected_objects_only", False)
                else None
            )
            bake_finalize.apply_yup_geometry_bake(bpy.context, settings, yup_objects)

        if getattr(settings, "selected_objects_only", False):
            bake_ops._set_selection(bpy.context, objects_to_export)

        # Export
        diag.begin_phase("blender_usd_export", {"output_path": filepath})
        temp_usd_path = blender_usd_export.export_blender_scene(
            bpy.context, settings, filepath, diag, reset_staging=False
        )
        if not temp_usd_path or not Path(temp_usd_path).exists():
            raise CommandError(
                "Blender USD export failed.",
                code="BLENDER_USD_EXPORT_FAILED",
                stage="blender_usd_export",
            )
        diag.end_phase(
            "blender_usd_export",
            context={
                "temp_usd_path": temp_usd_path,
                "file_size": Path(temp_usd_path).stat().st_size if Path(temp_usd_path).exists() else None,
            },
        )

        # Post-process
        diag.begin_phase("postprocess_usd", {"usd_path": temp_usd_path})
        postprocess_usd.process_usd_stage(
            temp_usd_path, settings, bpy.context, diag
        )
        diag.end_phase("postprocess_usd")

        if diag.data.get("errors"):
            errors = diag.data["errors"][:5]
            _save_diagnostics(diag, diagnostics_path)
            raise CommandError(
                f"Post-processing errors ({len(diag.data['errors'])} total): "
                + "; ".join(str(e) for e in errors),
                code="POSTPROCESS_FAILED",
                stage="postprocess_usd",
                details=diag.data.get("material_issues"),
                artifacts=_artifacts(diagnostics_path, filepath, bpy.data.filepath),
            )

        if apply_yup:
            bake_finalize.set_stage_up_axis_y(temp_usd_path, diag)

        # Package
        if settings.export_format == "USDZ":
            diag.begin_phase("pack_usdz", {"output_path": filepath})
            pack_usdz.create_usdz(
                temp_usd_path, filepath, settings, bpy.context, diag
            )
            diag.end_phase(
                "pack_usdz",
                context={"file_size": Path(filepath).stat().st_size if Path(filepath).exists() else None},
            )
        else:
            if temp_usd_path != filepath:
                blender_usd_export.publish_unpacked_export(temp_usd_path, filepath, diag)
            else:
                diag.add_generated_file("export", filepath)

        duration = time.time() - start_time

        # Diagnostics
        saved_diagnostics_path = None
        if diagnostics_enabled:
            _save_diagnostics(diag, diagnostics_path)
            saved_diagnostics_path = diagnostics_path

        # Bake stats
        bake_stats = {
            "objects_baked": len(objects_to_export),
            "resolution": bake_textures._resolve_bake_resolution(settings),
            "image_format": bake_textures._resolve_bake_image_format(settings, diag, safe_for_blender_save=True)["file_format"],
        }

        return {
            "ok": True,
            "export_path": filepath,
            "format": settings.export_format,
            "duration_seconds": round(duration, 2),
            "bake_stats": bake_stats,
            "diagnostics_path": saved_diagnostics_path,
            "support_bundle_hint": _support_hint(bpy.data.filepath, filepath, saved_diagnostics_path),
        }
    except CommandError as exc:
        if exc.stage:
            diag.record_phase_error(exc.stage, exc)
        diag.add_exception(exc, stage=exc.stage or "bake_export")
        _save_diagnostics(diag, diagnostics_path)
        exc.artifacts.update(_artifacts(diagnostics_path, filepath, bpy.data.filepath))
        raise
    except Exception as exc:
        diag.add_exception(exc, stage="bake_export")
        _save_diagnostics(diag, diagnostics_path)
        raise CommandError(
            str(exc),
            code="BAKE_EXPORT_FAILED",
            stage="bake_export",
            artifacts=_artifacts(diagnostics_path, filepath, bpy.data.filepath),
        ) from exc

    finally:
        settings.force_unlit_materials = original_force_unlit
        try:
            bpy.context.scene.render.engine = original_engine
        except Exception:
            pass
        if bake_result is not None:
            bake_textures.restore_baked_materials(
                bake_result,
                bool(getattr(settings, "bake_keep_materials", False)),
            )
        bake_ops._restore_selection(bpy.context, original_selection, original_active)
        bake_ops._restore_mode(bpy.context, original_active, original_mode)
        # Guarantee the .blendertorcp_temp staging tree is gone, even if the
        # export failed or raised above (publish/pack only clean it on success).
        try:
            blender_usd_export.remove_export_staging_dir(filepath, diag)
        except Exception:
            pass


def _save_diagnostics(diag, diagnostics_path: str | None) -> None:
    if not diagnostics_path:
        return
    diag.set_artifact("diagnostics_path", diagnostics_path)
    diag.save(Path(diagnostics_path))


def _artifacts(diagnostics_path: str | None, output_path: str, blend_file: str | None) -> dict:
    return {
        "diagnostics_path": diagnostics_path,
        "support_bundle_hint": _support_hint(blend_file, output_path, diagnostics_path),
    }


def _support_hint(blend_file: str | None, output_path: str | None, diagnostics_path: str | None = None) -> str | None:
    if not blend_file:
        return None
    parts = ["blendertorcp", "support-bundle", blend_file]
    if output_path:
        parts.extend(["-o", output_path])
    if diagnostics_path:
        parts.extend(["--diagnostics", diagnostics_path])
    return " ".join(parts)
