"""
Support bundle creation for BlenderToRCP.

Bundles are redacted by default and are intended to be safe first-response
artifacts for user bug reports. Source `.blend` files and exported assets are
included only when explicitly requested.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any


_TEXT_LOG_LIMIT_LINES = 2000
_PATH_KEYS = {
    "filepath",
    "blend_file",
    "export_path",
    "log_path",
    "diagnostics_path",
    "materialx_library_path",
    "usdzip_path",
    "bake_ibl_filepath",
    "background_job_dir",
}


def collect_environment(context=None) -> dict:
    """Collect runtime metadata for diagnostics and support reports."""
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "cwd": os.getcwd(),
        "process_id": os.getpid(),
    }

    try:
        import bpy

        info["blender"] = {
            "version": ".".join(str(v) for v in bpy.app.version),
            "version_string": getattr(bpy.app, "version_string", ""),
            "binary_path": getattr(bpy.app, "binary_path", ""),
            "background": bool(getattr(bpy.app, "background", False)),
        }
        info["blend_file"] = getattr(bpy.data, "filepath", "") or None
    except Exception:
        pass

    try:
        from .. import bl_info

        info["addon"] = {
            "name": bl_info.get("name", "BlenderToRCP"),
            "version": ".".join(str(v) for v in bl_info.get("version", ())),
            "blender_required": ".".join(str(v) for v in bl_info.get("blender", ())),
        }
    except Exception:
        info["addon"] = {"name": "BlenderToRCP", "version": "unknown"}

    try:
        from ..core import paths
        from ..manifest import materialx_nodes

        manifest_path = materialx_nodes.get_manifest_path()
        info["resources"] = {
            "addon_root": str(paths.addon_root()),
            "runner_path": str(Path(__file__).resolve().parents[1] / "api" / "runner.py"),
            "manifest_path": str(manifest_path),
            "manifest_exists": manifest_path.exists(),
            "manifest_schema_version": getattr(materialx_nodes, "MANIFEST_SCHEMA_VERSION", None),
            "nodegroups_asset_path": str(paths.nodegroups_asset_path()),
            "nodegroups_asset_exists": paths.nodegroups_asset_path().exists(),
        }
    except Exception as exc:
        info["resources_error"] = str(exc)

    try:
        import bpy
        from .. import prefs as addon_prefs

        prefs = addon_prefs.get_preferences(context or bpy.context)
        if prefs is not None:
            info["preferences"] = {
                "usdzip_path": getattr(prefs, "usdzip_path", ""),
                "materialx_library_path": getattr(prefs, "materialx_library_path", ""),
                "default_export_format": getattr(prefs, "default_export_format", None),
                "enable_diagnostics": bool(getattr(prefs, "enable_diagnostics", False)),
                "last_export_settings_json_valid": _json_is_valid(
                    getattr(prefs, "last_export_settings_json", "")
                ),
                "last_export_paths_json_valid": _json_is_valid(
                    getattr(prefs, "last_export_paths_json", "")
                ),
            }
    except Exception as exc:
        info["preferences_error"] = str(exc)

    return _json_safe(info)


def collect_scene_snapshot(context=None) -> dict:
    """Collect compact scene and export settings metadata."""
    try:
        import bpy

        context = context or bpy.context
        scene = context.scene
        settings = getattr(scene, "blender_to_rcp_export_settings", None)
        materials = set()
        for obj in scene.objects:
            for slot in getattr(obj, "material_slots", []):
                if slot.material:
                    materials.add(slot.material.name)
        snapshot = {
            "file": getattr(bpy.data, "filepath", "") or None,
            "scene": scene.name,
            "frame_range": [scene.frame_start, scene.frame_end],
            "fps": scene.render.fps,
            "unit_system": scene.unit_settings.system,
            "unit_scale": scene.unit_settings.scale_length,
            "object_count": len(scene.objects),
            "selected_object_count": len(getattr(context, "selected_objects", []) or []),
            "material_count": len(materials),
        }
        if settings is not None:
            snapshot["export_settings"] = _serialize_settings(settings)
        return _json_safe(snapshot)
    except Exception as exc:
        return {"error": str(exc)}


def collect_validation_snapshot(context=None) -> dict:
    """Collect material validation data without failing bundle creation."""
    try:
        import bpy
        from ..nodes import validate as rk_validate

        context = context or bpy.context
        materials = rk_validate.collect_scene_materials(context)
        entries = []
        total_errors = 0
        total_warnings = 0
        for material in materials:
            result = rk_validate.validate_material(material, strict=True)
            total_errors += len(result.get("errors", []))
            total_warnings += len(result.get("warnings", []))
            entries.append({
                "name": result.get("material", material.name),
                "ok": result.get("ok", False),
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
            })
        return _json_safe({
            "ok": total_errors == 0,
            "error_count": total_errors,
            "warning_count": total_warnings,
            "materials": entries,
        })
    except Exception as exc:
        return {"error": str(exc)}


def create_support_bundle(
    *,
    context=None,
    blend_file: str | None = None,
    export_path: str | None = None,
    diagnostics_path: str | None = None,
    job_dir: str | None = None,
    bundle_output: str | None = None,
    include_output: bool = False,
    include_blend: bool = False,
    full_log: bool = False,
    redact: bool = True,
) -> dict:
    """Create a redacted support bundle ZIP and return metadata."""
    export = Path(export_path).expanduser() if export_path else None
    blend = Path(blend_file).expanduser() if blend_file else None
    job = Path(job_dir).expanduser() if job_dir else None

    if diagnostics_path:
        diagnostics = Path(diagnostics_path).expanduser()
    elif export:
        diagnostics = export.with_suffix(".diagnostics.json")
    else:
        diagnostics = None

    output_dir = None
    if bundle_output:
        bundle_path = Path(bundle_output).expanduser()
        output_dir = bundle_path.parent
    elif export:
        output_dir = export.parent
    elif blend:
        output_dir = blend.parent
    elif job:
        output_dir = job.parent
    else:
        output_dir = Path.cwd()

    stem = (blend.stem if blend else export.stem if export else "scene") or "scene"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bundle_name = f"BlenderToRCP-support-{stem}-{stamp}"
    bundle_path = Path(bundle_output).expanduser() if bundle_output else output_dir / f"{bundle_name}.zip"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)

    tokens = _build_redaction_tokens(blend, export)
    files: list[dict[str, str]] = []

    def add_json(zf: zipfile.ZipFile, rel: str, data: Any) -> None:
        payload = _redact_json(data, tokens) if redact else _json_safe(data)
        zf.writestr(f"{bundle_name}/{rel}", json.dumps(payload, indent=2, default=str))
        files.append({"path": rel, "source": "generated"})

    def add_text(zf: zipfile.ZipFile, rel: str, text: str) -> None:
        payload = _redact_text(text, tokens) if redact else text
        zf.writestr(f"{bundle_name}/{rel}", payload)
        files.append({"path": rel, "source": "generated"})

    def add_file(zf: zipfile.ZipFile, source: Path, rel: str, *, redact_file: bool = False) -> None:
        if not source or not source.exists() or not source.is_file():
            return
        if redact_file:
            text = source.read_text(errors="replace")
            if not full_log:
                lines = text.splitlines()
                if len(lines) > _TEXT_LOG_LIMIT_LINES:
                    text = "\n".join(lines[-_TEXT_LOG_LIMIT_LINES:])
            add_text(zf, rel, text)
            files[-1]["source"] = str(source)
            return
        zf.write(source, f"{bundle_name}/{rel}")
        files.append({"path": rel, "source": str(source)})

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        add_text(
            zf,
            "README.txt",
            "BlenderToRCP support bundle. Redacted by default. "
            "Attach this ZIP to a support request with a short description of the failure.\n",
        )
        add_json(zf, "environment/version.json", collect_environment(context))
        add_json(zf, "environment/scene-info.json", collect_scene_snapshot(context))
        add_json(zf, "diagnostics/validate.json", collect_validation_snapshot(context))

        if diagnostics and diagnostics.exists():
            add_file(zf, diagnostics, "diagnostics/export.diagnostics.json", redact_file=redact)

        if job and job.exists():
            add_file(zf, job / "status.json", "job/status.json", redact_file=redact)
            add_file(zf, job / "settings.json", "job/settings.redacted.json", redact_file=redact)
            add_file(zf, job / "log.txt", "job/log.redacted.txt", redact_file=redact)

        if include_output and export and export.exists():
            add_file(zf, export, f"output/{export.name}")
            _add_sidecar_directory(zf, files, bundle_name, export.parent / "textures", "output/textures")
            _add_sidecar_directory(zf, files, bundle_name, export.parent / "assets", "output/assets")

        if include_blend and blend and blend.exists():
            add_file(zf, blend, f"source/{blend.name}")

        manifest = {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "bundle": bundle_name,
            "redacted": redact,
            "include_output": include_output,
            "include_blend": include_blend,
            "sources": _redact_json({
                "blend_file": str(blend) if blend else None,
                "export_path": str(export) if export else None,
                "diagnostics_path": str(diagnostics) if diagnostics else None,
                "job_dir": str(job) if job else None,
            }, tokens) if redact else {
                "blend_file": str(blend) if blend else None,
                "export_path": str(export) if export else None,
                "diagnostics_path": str(diagnostics) if diagnostics else None,
                "job_dir": str(job) if job else None,
            },
            "files": files,
        }
        add_json(zf, "manifest.json", manifest)

    return {
        "support_bundle_path": str(bundle_path),
        "file_count": len(files),
        "redacted": redact,
        "included_output": include_output,
        "included_blend": include_blend,
    }


def _add_sidecar_directory(
    zf: zipfile.ZipFile,
    files: list[dict[str, str]],
    bundle_name: str,
    source_dir: Path,
    rel_root: str,
) -> None:
    if not source_dir.exists() or not source_dir.is_dir():
        return
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            rel = f"{rel_root}/{path.relative_to(source_dir)}"
            zf.write(path, f"{bundle_name}/{rel}")
            files.append({"path": rel, "source": str(path)})


def _serialize_settings(settings) -> dict:
    try:
        from ..api.commands._settings_common import INTERNAL_KEYS
    except Exception:
        INTERNAL_KEYS = {"rna_type", "name"}

    data = {}
    for prop in settings.bl_rna.properties:
        key = prop.identifier
        if key in INTERNAL_KEYS:
            continue
        try:
            data[key] = getattr(settings, key)
        except Exception:
            continue
    return data


def _json_is_valid(value: str) -> bool:
    if not value:
        return True
    try:
        json.loads(value)
        return True
    except Exception:
        return False


def _build_redaction_tokens(blend: Path | None, export: Path | None) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    home = str(Path.home())
    if home:
        tokens.append((home, "$HOME"))
    if blend and blend.parent:
        tokens.append((str(blend.parent), "$BLEND_DIR"))
    if export and export.parent:
        tokens.append((str(export.parent), "$EXPORT_DIR"))
    return sorted(tokens, key=lambda item: len(item[0]), reverse=True)


def _redact_json(value: Any, tokens: list[tuple[str, str]], key: str | None = None):
    if isinstance(value, dict):
        return {str(k): _redact_json(v, tokens, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_json(item, tokens, key) for item in value]
    if isinstance(value, str):
        redacted = _redact_text(value, tokens)
        if key in _PATH_KEYS and redacted:
            return redacted
        return redacted
    return value


def _redact_text(text: str, tokens: list[tuple[str, str]]) -> str:
    redacted = str(text)
    for source, token in tokens:
        redacted = redacted.replace(source, token)
    redacted = re.sub(r"(?i)(api[_-]?key|token|secret|password)=\S+", r"\1=<redacted>", redacted)
    return redacted


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
