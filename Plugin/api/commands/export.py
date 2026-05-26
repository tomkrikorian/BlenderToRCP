"""export command — export scene to USD/USDZ."""

from __future__ import annotations

import os
import time
from pathlib import Path

from ._settings_common import INTERNAL_KEYS, get_settings, coerce_value
from Plugin.api.errors import CommandError


def handle(args: dict) -> dict:
    import bpy
    from Plugin.export import blender_usd_export, postprocess_usd, pack_usdz, diagnostics
    from Plugin.export.support_bundle import collect_environment, collect_scene_snapshot
    from Plugin.nodes import validate as rk_validate

    filepath = args.get("filepath")
    if not filepath:
        raise ValueError("'filepath' is required (output path).")

    settings = get_settings()
    no_diagnostics = args.get("no_diagnostics", False)

    # Apply overrides without persisting them
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
            "Invalid export setting override.",
            code="INVALID_SETTING_OVERRIDE",
            details=invalid_overrides,
        )

    # Apply format override
    fmt = args.get("format")
    if fmt:
        settings.export_format = fmt.upper()

    if args.get("selected_only"):
        settings.selected_objects_only = True

    if args.get("diagnostics"):
        settings.diagnostics_enabled = True

    # Enforce extension
    ext_map = {"USDA": ".usda", "USDC": ".usdc", "USDZ": ".usdz"}
    ext = ext_map.get(settings.export_format, ".usdz")
    filepath = str(Path(filepath).with_suffix(ext))
    settings.filepath = filepath

    diag = diagnostics.ExportDiagnostics()
    diagnostics_enabled = bool(getattr(settings, "diagnostics_enabled", False)) and not no_diagnostics
    diagnostics_path = str(Path(filepath).with_suffix(".diagnostics.json")) if diagnostics_enabled else None
    diag.set_export_context(
        command="export",
        requested_path=args.get("filepath"),
        resolved_output_path=filepath,
        export_format=settings.export_format,
        selected_only=bool(getattr(settings, "selected_objects_only", False)),
        blend_file=bpy.data.filepath or None,
    )
    diag.set_environment(**collect_environment(bpy.context))
    diag.data["scene"] = collect_scene_snapshot(bpy.context)

    # Validate materials (strict mode — same as the operator)
    materials = rk_validate.collect_scene_materials(bpy.context)
    for mat in materials:
        try:
            result = rk_validate.validate_material(mat, strict=True)
        except TypeError:
            result = rk_validate.validate_material(mat)
            if result.get("warnings"):
                result["errors"].extend(result["warnings"])
                result["warnings"] = []
            result["ok"] = not result["errors"]
        if result["errors"]:
            for issue in result["errors"]:
                diag.add_validation_issue(mat.name, issue, severity="error")
            error_msgs = [
                f"{e.get('node_name', '?')} ({e.get('node_type', '?')}): {e.get('message', '')}"
                for e in result["errors"][:10]
            ]
            _save_diagnostics(diag, diagnostics_path)
            raise CommandError(
                f"Unsupported nodes in material '{mat.name}'.",
                code="UNSUPPORTED_MATERIAL_NODES",
                stage="validation",
                details=result["errors"],
                artifacts=_artifacts(diagnostics_path, filepath, bpy.data.filepath),
                context={"material": mat.name, "errors": error_msgs},
            )

    start_time = time.time()
    try:
        # Step 1: Export from Blender to USD
        diag.begin_phase("blender_usd_export", {"output_path": filepath})
        temp_usd_path = blender_usd_export.export_blender_scene(
            bpy.context, settings, filepath, diag
        )
        if not temp_usd_path or not os.path.exists(temp_usd_path):
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

        # Step 2: Post-process (material rewrite)
        diag.begin_phase("postprocess_usd", {"usd_path": temp_usd_path})
        postprocess_usd.process_usd_stage(temp_usd_path, settings, bpy.context, diag)
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

        # Step 3: Package USDZ if needed
        if settings.export_format == "USDZ":
            diag.begin_phase("pack_usdz", {"output_path": filepath})
            pack_usdz.create_usdz(temp_usd_path, filepath, settings, bpy.context, diag)
            diag.end_phase(
                "pack_usdz",
                context={"file_size": Path(filepath).stat().st_size if Path(filepath).exists() else None},
            )
        else:
            if temp_usd_path != filepath:
                blender_usd_export.publish_unpacked_export(temp_usd_path, filepath, diag)
            else:
                diag.add_generated_file("export", filepath)
    except CommandError as exc:
        if exc.stage:
            diag.record_phase_error(exc.stage, exc)
        diag.add_exception(exc, stage=exc.stage or "export")
        _save_diagnostics(diag, diagnostics_path)
        exc.artifacts.update(_artifacts(diagnostics_path, filepath, bpy.data.filepath))
        raise
    except Exception as exc:
        diag.add_exception(exc, stage="export")
        _save_diagnostics(diag, diagnostics_path)
        raise CommandError(
            str(exc),
            code="EXPORT_FAILED",
            stage="export",
            artifacts=_artifacts(diagnostics_path, filepath, bpy.data.filepath),
        ) from exc

    duration = time.time() - start_time

    # Save diagnostics
    saved_diagnostics_path = None
    if diagnostics_enabled:
        _save_diagnostics(diag, diagnostics_path)
        saved_diagnostics_path = diagnostics_path

    return {
        "ok": True,
        "export_path": filepath,
        "format": settings.export_format,
        "duration_seconds": round(duration, 2),
        "diagnostics_path": saved_diagnostics_path,
        "support_bundle_hint": _support_hint(bpy.data.filepath, filepath, saved_diagnostics_path),
    }


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
