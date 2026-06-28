"""
Export operator for BlenderToRCP
"""

import bpy
import os
import json
from pathlib import Path
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from .. import prefs as addon_prefs

class BLENDERTORCP_OT_export(Operator, ExportHelper):
    """Export scene to RealityKit-compatible USD/USDZ"""
    bl_idname = "blendertorcp.export"
    bl_label = "Export to RCP"
    bl_description = "Fast export without baking textures. Best-effort converts Blender materials to RealityKit's Shadergraph."
    bl_options = {'REGISTER', 'UNDO'}
    
    # ExportHelper properties
    filename_ext = ".usdz"
    filter_glob: StringProperty(
        default="*.usdz;*.usda;*.usdc",
        options={'HIDDEN'}
    )

    @staticmethod
    def _normalize_export_format(export_format: str) -> str:
        """Normalize export format values from older enum entries."""
        if export_format == 'USD':
            return 'USDC'
        return export_format

    @staticmethod
    def _format_extension(export_format: str) -> str:
        """Map export format to a file extension."""
        return {
            'USDA': '.usda',
            'USDC': '.usdc',
            'USDZ': '.usdz',
        }.get(export_format, '.usdz')

    @classmethod
    def _enforce_extension(cls, filepath: str, export_format: str) -> str:
        """Ensure filepath matches the chosen export format extension."""
        extension = cls._format_extension(export_format)
        path_obj = Path(filepath)
        if path_obj.suffix.lower() == extension:
            return str(path_obj)
        return str(path_obj.with_suffix(extension))
    
    def invoke(self, context, event):
        """Called when operator is invoked"""
        settings = context.scene.blender_to_rcp_export_settings
        _apply_persisted_settings(context, settings)
        export_format = self._normalize_export_format(settings.export_format)
        settings.export_format = export_format
        self.filepath = _resolve_output_path_from_settings(context, settings, export_format)
        if not self.filepath:
            self.report({'ERROR'}, "Set Output Path before exporting.")
            return {'CANCELLED'}
        return self.execute(context)
    
    def execute(self, context):
        """Execute the export"""
        import sys
        
        # Get settings
        settings = context.scene.blender_to_rcp_export_settings
        _apply_persisted_settings(context, settings)
        export_format = self._normalize_export_format(settings.export_format)
        settings.export_format = export_format
        self.filepath = _resolve_output_path_from_settings(
            context,
            settings,
            export_format,
            fallback=getattr(self, "filepath", ""),
        )
        if not self.filepath:
            self.report({'ERROR'}, "Set Output Path before exporting.")
            return {'CANCELLED'}
        settings.filepath = self.filepath

        from ..export import diagnostics
        from ..export.support_bundle import collect_environment, collect_scene_snapshot

        diag = diagnostics.ExportDiagnostics()
        diagnostics_enabled = bool(getattr(settings, "diagnostics_enabled", False))
        diag_path = Path(self.filepath).with_suffix('.diagnostics.json') if diagnostics_enabled else None
        if not diagnostics_enabled:
            settings.last_diagnostics_path = ""
        diag.set_export_context(
            command="ui_export",
            resolved_output_path=self.filepath,
            export_format=export_format,
            selected_only=bool(getattr(settings, "selected_objects_only", False)),
            blend_file=context.blend_data.filepath or None,
        )
        diag.set_environment(**collect_environment(context))
        diag.data["scene"] = collect_scene_snapshot(context)

        from ..nodes import validate as rk_validate

        materials = rk_validate.collect_scene_materials(context)
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
                self.report(
                    {'ERROR'},
                    f"Unsupported nodes found in material '{material.name}' ({error_count})."
                )
                for issue in result["errors"][:6]:
                    node_name = issue.get("node_name") or "<unknown>"
                    node_type = issue.get("node_type") or "?"
                    message = issue.get("message") or "Unsupported node."
                    self.report({'ERROR'}, f"{node_name} ({node_type}): {message}")
                if error_count > 6:
                    self.report({'ERROR'}, f"{error_count - 6} more errors in '{material.name}'.")
                _save_diagnostics(diag, diag_path)
                if diag_path:
                    settings.last_diagnostics_path = str(diag_path)
                return {'CANCELLED'}

        try:
            # Import export modules
            from ..export import blender_usd_export, postprocess_usd, pack_usdz
            
            # Step 1: Export from Blender to USD
            self.report({'INFO'}, "Exporting from Blender...")
            temp_usd_path = blender_usd_export.export_blender_scene(
                context,
                settings,
                self.filepath,
                diag,
            )
            
            if not temp_usd_path or not os.path.exists(temp_usd_path):
                self.report({'ERROR'}, "Blender USD export failed")
                return {'CANCELLED'}
            
            # Step 2: Post-process USD (material rewrite, etc.)
            self.report({'INFO'}, "Rewriting materials to RealityKit ShaderGraph...")
            postprocess_usd.process_usd_stage(
                temp_usd_path,
                settings,
                context,
                diag
            )
            
            # Fail fast on strict export errors before packaging.
            if diag.data.get('errors'):
                _save_diagnostics(diag, diag_path)
                if diag_path:
                    settings.last_diagnostics_path = str(diag_path)
                for error in diag.data['errors'][:5]:
                    self.report({'ERROR'}, str(error))
                if len(diag.data['errors']) > 5:
                    suffix = " (see diagnostics)" if diag_path else ""
                    self.report({'ERROR'}, f"{len(diag.data['errors']) - 5} more errors{suffix}")
                return {'CANCELLED'}

            # Step 3: Package as USDZ if requested
            if settings.export_format == 'USDZ':
                self.report({'INFO'}, "Packaging USDZ...")
                pack_usdz.create_usdz(
                    temp_usd_path,
                    self.filepath,
                    settings,
                    context,
                    diag
                )
            else:
                # Publish the staged USD and sidecar assets to the final location.
                if temp_usd_path != self.filepath:
                    blender_usd_export.publish_unpacked_export(temp_usd_path, self.filepath, diag)
            
            # Save diagnostics if enabled for this export.
            if diagnostics_enabled and diag_path:
                _save_diagnostics(diag, diag_path)
                settings.last_diagnostics_path = str(diag_path)

            if diag.data.get('warnings'):
                warning_count = len(diag.data['warnings'])
                for warning in diag.data['warnings'][:5]:
                    self.report({'WARNING'}, warning)
                if warning_count > 5:
                    suffix = " (see diagnostics)" if diag_path else ""
                    self.report({'WARNING'}, f"{warning_count - 5} more warnings{suffix}")
            
            self.report({'INFO'}, f"Export completed: {self.filepath}")
            _store_last_export_settings(context, settings)
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            diag.add_exception(e, stage="ui_export")
            try:
                _save_diagnostics(diag, diag_path)
                if diag_path:
                    settings.last_diagnostics_path = str(diag_path)
            except Exception:
                pass
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            traceback.print_exc()
            return {'CANCELLED'}
        finally:
            # Guarantee the .blendertorcp_temp staging tree is gone, even if the
            # export failed above (publish/pack only clean it on success).
            try:
                from ..export import blender_usd_export
                blender_usd_export.remove_export_staging_dir(self.filepath, diag)
            except Exception:
                pass

class BLENDERTORCP_OT_show_diagnostics(Operator):
    """Show export diagnostics"""
    bl_idname = "blendertorcp.show_diagnostics"
    bl_label = "Show Diagnostics"
    bl_description = "Show last export diagnostics"
    bl_options = {'REGISTER'}

    _diag_path: str | None = None
    _diag_data: dict | None = None

    def invoke(self, context, event):
        """Show diagnostics in a dialog."""
        diag_path = _resolve_diagnostics_path(context)
        if not diag_path:
            self.report({'ERROR'}, "No diagnostics file found. Run an export first.")
            return {'CANCELLED'}

        try:
            self._diag_data = json.loads(Path(diag_path).read_text())
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to read diagnostics: {exc}")
            return {'CANCELLED'}

        self._diag_path = diag_path
        return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, context):
        layout = self.layout
        data = self._diag_data or {}
        layout.label(text=f"Diagnostics: {self._diag_path}")

        summary = layout.box()
        summary.label(text="Summary")
        materials = data.get('materials', {})
        textures = data.get('textures', {})
        nodes = data.get('nodes', {})
        summary.label(text=f"Materials converted: {materials.get('converted', 0)}")
        summary.label(text=f"Materials failed: {materials.get('failed', 0)}")
        summary.label(text=f"Textures copied: {textures.get('copied', 0)}")
        summary.label(text=f"Textures converted: {textures.get('converted', 0)}")
        summary.label(text=f"Fallback nodes: {len(nodes.get('fallback_used', []))}")
        summary.label(text=f"KTX-required nodes: {len(nodes.get('ktx_required', []))}")
        summary.label(text=f"Omitted nodes: {len(nodes.get('omitted', []))}")

        errors = data.get('errors', []) or []
        warnings = data.get('warnings', []) or []
        if errors:
            error_box = layout.box()
            error_box.label(text="Errors", icon='ERROR')
            for line in errors[:8]:
                error_box.label(text=str(line))
            if len(errors) > 8:
                error_box.label(text=f"... {len(errors) - 8} more")

        if warnings:
            warn_box = layout.box()
            warn_box.label(text="Warnings", icon='INFO')
            for line in warnings[:8]:
                warn_box.label(text=str(line))
            if len(warnings) > 8:
                warn_box.label(text=f"... {len(warnings) - 8} more")

        if self._diag_path:
            op = layout.operator(
                "blendertorcp.open_diagnostics_text",
                text="Open Diagnostics JSON in Text Editor",
                icon='TEXT',
            )
            op.filepath = self._diag_path

    def execute(self, context):
        """Dialog confirmed."""
        return {'FINISHED'}


class BLENDERTORCP_OT_open_diagnostics_text(Operator):
    """Load diagnostics JSON into a Text datablock."""
    bl_idname = "blendertorcp.open_diagnostics_text"
    bl_label = "Open Diagnostics JSON"
    bl_description = "Load diagnostics JSON into Blender's Text Editor"

    filepath: StringProperty(
        name="Diagnostics Path",
        description="Path to diagnostics JSON",
        subtype='FILE_PATH'
    )

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "No diagnostics path provided.")
            return {'CANCELLED'}
        path = Path(self.filepath)
        if not path.exists():
            self.report({'ERROR'}, f"Diagnostics file not found: {path}")
            return {'CANCELLED'}
        try:
            content = path.read_text()
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to read diagnostics: {exc}")
            return {'CANCELLED'}

        text_name = "BlenderToRCP Diagnostics"
        text_block = bpy.data.texts.get(text_name)
        if text_block is None:
            text_block = bpy.data.texts.new(text_name)
        text_block.clear()
        text_block.write(content)
        self.report({'INFO'}, f"Loaded diagnostics into Text Editor: {text_name}")
        return {'FINISHED'}


class BLENDERTORCP_OT_open_support_text(Operator):
    """Load a support text file into a Text datablock."""
    bl_idname = "blendertorcp.open_support_text"
    bl_label = "Open Support File"
    bl_description = "Load a support log/status file into Blender's Text Editor"

    filepath: StringProperty(
        name="File Path",
        description="Path to support text file",
        subtype='FILE_PATH'
    )

    text_name: StringProperty(
        name="Text Name",
        description="Blender Text datablock name",
        default="BlenderToRCP Support"
    )

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "No file path provided.")
            return {'CANCELLED'}
        path = Path(self.filepath)
        if not path.exists():
            self.report({'ERROR'}, f"Support file not found: {path}")
            return {'CANCELLED'}
        try:
            content = path.read_text(errors="replace")
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to read support file: {exc}")
            return {'CANCELLED'}

        text_block = bpy.data.texts.get(self.text_name)
        if text_block is None:
            text_block = bpy.data.texts.new(self.text_name)
        text_block.clear()
        text_block.write(content)
        self.report({'INFO'}, f"Loaded support file into Text Editor: {self.text_name}")
        return {'FINISHED'}


class BLENDERTORCP_OT_create_support_bundle(Operator):
    """Create a redacted support bundle for the latest export."""
    bl_idname = "blendertorcp.create_support_bundle"
    bl_label = "Create Support Bundle"
    bl_description = "Create a redacted support ZIP for sharing BlenderToRCP diagnostics"
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = context.scene.blender_to_rcp_export_settings
        try:
            from ..export.support_bundle import create_support_bundle

            result = create_support_bundle(
                context=context,
                blend_file=bpy.data.filepath or None,
                export_path=getattr(settings, "filepath", "") or None,
                diagnostics_path=_resolve_diagnostics_path(context),
                job_dir=getattr(settings, "background_job_dir", "") or None,
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to create support bundle: {exc}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Support bundle created: {result.get('support_bundle_path')}")
        return {'FINISHED'}


def _resolve_diagnostics_path(context) -> str | None:
    settings = context.scene.blender_to_rcp_export_settings
    if not bool(getattr(settings, "diagnostics_enabled", False)):
        return None
    candidates = []
    job_candidates = []
    job_dir = getattr(settings, "background_job_dir", "")
    if job_dir:
        status_path = Path(job_dir) / "status.json"
        try:
            status = json.loads(status_path.read_text()) if status_path.exists() else {}
        except Exception:
            status = {}
        if status.get("diagnostics_path"):
            job_candidates.append(status["diagnostics_path"])
    if getattr(settings, "filepath", ""):
        current_diag = str(Path(settings.filepath).with_suffix('.diagnostics.json'))
        candidates.append(current_diag)
        if job_dir:
            job_candidates.append(current_diag)
    if job_candidates:
        for candidate in job_candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return job_candidates[0]
    if getattr(settings, "last_diagnostics_path", ""):
        candidates.append(settings.last_diagnostics_path)

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    search_dirs = []
    if getattr(settings, "filepath", ""):
        search_dirs.append(Path(settings.filepath).parent)
    if bpy.data.filepath:
        search_dirs.append(Path(bpy.data.filepath).parent)
    search_dirs.append(Path.cwd())

    latest = None
    latest_mtime = -1.0
    for directory in search_dirs:
        if not directory or not directory.exists():
            continue
        for path in directory.glob("*.diagnostics.json"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest = path
    return str(latest) if latest else None


def _save_diagnostics(diag, diag_path: Path | None) -> None:
    if diag_path is None:
        return
    diag.set_artifact("diagnostics_path", str(diag_path))
    diag.save(diag_path)


def _store_last_export_settings(context, settings) -> None:
    prefs = addon_prefs.get_preferences(context)
    if not prefs:
        return
    data = {}
    for prop in settings.bl_rna.properties:
        key = prop.identifier
        if key in {"rna_type", "name", "history_applied", "last_diagnostics_path", "background_job_dir", "background_job_pid", "filepath"}:
            continue
        try:
            data[key] = getattr(settings, key)
        except Exception:
            continue
    try:
        prefs.last_export_settings_json = json.dumps(data)
    except Exception:
        pass
    addon_prefs.set_last_export_path(context, getattr(settings, "filepath", ""), getattr(context.blend_data, "filepath", None))


def _apply_persisted_settings(context, settings) -> None:
    if getattr(settings, "history_applied", False):
        return
    prefs = addon_prefs.get_preferences(context)
    if not prefs:
        settings.history_applied = True
        return
    serialized = getattr(prefs, "last_export_settings_json", "")
    prop_defs = {prop.identifier for prop in settings.bl_rna.properties}
    settings.persist_suspended = True
    try:
        if serialized:
            try:
                data = json.loads(serialized)
            except Exception:
                data = {}
            if isinstance(data, dict):
                for key, value in data.items():
                    if key in {"history_applied", "last_diagnostics_path", "persist_suspended", "background_job_dir", "background_job_pid", "filepath"}:
                        continue
                    if key not in prop_defs:
                        continue
                    try:
                        setattr(settings, key, value)
                    except Exception:
                        continue
        if not getattr(settings, "filepath", ""):
            addon_prefs.apply_last_export_path(context, settings)
    finally:
        settings.persist_suspended = False
    settings.history_applied = True


def _resolve_output_path_from_settings(context, settings, export_format: str, fallback: str = "") -> str:
    filepath = str(getattr(settings, "filepath", "") or fallback or "").strip()
    if not filepath:
        return ""

    try:
        filepath = bpy.path.abspath(filepath)
    except Exception:
        pass

    path = Path(filepath).expanduser()
    if not path.is_absolute():
        blend_file = getattr(getattr(context, "blend_data", None), "filepath", "")
        if blend_file:
            path = Path(blend_file).parent / path
        else:
            path = Path.cwd() / path

    return BLENDERTORCP_OT_export._enforce_extension(str(path), export_format)


def register():
    """Register operators"""
    bpy.utils.register_class(BLENDERTORCP_OT_export)
    bpy.utils.register_class(BLENDERTORCP_OT_show_diagnostics)
    bpy.utils.register_class(BLENDERTORCP_OT_open_diagnostics_text)
    bpy.utils.register_class(BLENDERTORCP_OT_open_support_text)
    bpy.utils.register_class(BLENDERTORCP_OT_create_support_bundle)


def unregister():
    """Unregister operators"""
    bpy.utils.unregister_class(BLENDERTORCP_OT_create_support_bundle)
    bpy.utils.unregister_class(BLENDERTORCP_OT_open_support_text)
    bpy.utils.unregister_class(BLENDERTORCP_OT_open_diagnostics_text)
    bpy.utils.unregister_class(BLENDERTORCP_OT_show_diagnostics)
    bpy.utils.unregister_class(BLENDERTORCP_OT_export)
