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
    bl_description = "Export Blender scene to RealityKit-compatible USD or USDZ format"
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
        # Set default filepath from scene settings
        settings = context.scene.blender_to_rcp_export_settings
        export_format = self._normalize_export_format(settings.export_format)
        settings.export_format = export_format
        extension = self._format_extension(export_format)
        self.filename_ext = extension
        self.filter_glob = f"*{extension}"

        blend_path = Path(context.blend_data.filepath) if context.blend_data.filepath else None
        blend_name = blend_path.stem if blend_path else "untitled"
        blend_dir = blend_path.parent if blend_path else None
        last_path = addon_prefs.get_last_export_path(context, blend_path)

        if last_path:
            self.filepath = self._enforce_extension(str(last_path), export_format)
        elif blend_dir:
            suggested = blend_dir / f"{blend_name}{extension}"
            self.filepath = self._enforce_extension(str(suggested), export_format)
        else:
            self.filepath = ""
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        """Execute the export"""
        import sys
        
        # Validate filepath
        if not self.filepath:
            self.report({'ERROR'}, "No file path specified")
            return {'CANCELLED'}
        
        # Get settings
        settings = context.scene.blender_to_rcp_export_settings
        _apply_persisted_settings(context, settings)
        export_format = self._normalize_export_format(settings.export_format)
        settings.export_format = export_format
        self.filepath = self._enforce_extension(self.filepath, export_format)
        settings.filepath = self.filepath

        prefs = addon_prefs.get_preferences(context)
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
                return {'CANCELLED'}

        try:
            # Import export modules
            from ..export import blender_usd_export, postprocess_usd, pack_usdz, diagnostics
            
            # Create diagnostics instance
            diag = diagnostics.ExportDiagnostics()
            
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
                if prefs and prefs.enable_diagnostics:
                    diag_path = Path(self.filepath).with_suffix('.diagnostics.json')
                    diag.save(diag_path)
                    settings.last_diagnostics_path = str(diag_path)
                for error in diag.data['errors'][:5]:
                    self.report({'ERROR'}, str(error))
                if len(diag.data['errors']) > 5:
                    self.report({'ERROR'}, f"{len(diag.data['errors']) - 5} more errors (see diagnostics)")
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
                # Just copy/move the USD file to final location
                import shutil
                if temp_usd_path != self.filepath:
                    shutil.move(temp_usd_path, self.filepath)
            
            # Save diagnostics if enabled
            if prefs and prefs.enable_diagnostics:
                diag_path = Path(self.filepath).with_suffix('.diagnostics.json')
                diag.save(diag_path)
                settings.last_diagnostics_path = str(diag_path)

            if diag.data.get('warnings'):
                warning_count = len(diag.data['warnings'])
                for warning in diag.data['warnings'][:5]:
                    self.report({'WARNING'}, warning)
                if warning_count > 5:
                    self.report({'WARNING'}, f"{warning_count - 5} more warnings (see diagnostics)")
            
            self.report({'INFO'}, f"Export completed: {self.filepath}")
            _store_last_export_settings(context, settings)
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            traceback.print_exc()
            return {'CANCELLED'}
    
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


def _resolve_diagnostics_path(context) -> str | None:
    settings = context.scene.blender_to_rcp_export_settings
    candidates = []
    if getattr(settings, "last_diagnostics_path", ""):
        candidates.append(settings.last_diagnostics_path)
    if getattr(settings, "filepath", ""):
        candidates.append(str(Path(settings.filepath).with_suffix('.diagnostics.json')))

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
    if not serialized:
        settings.history_applied = True
        return
    try:
        data = json.loads(serialized)
    except Exception:
        settings.history_applied = True
        return
    prop_defs = {prop.identifier for prop in settings.bl_rna.properties}
    settings.persist_suspended = True
    try:
        for key, value in data.items():
            if key in {"history_applied", "last_diagnostics_path", "persist_suspended", "background_job_dir", "background_job_pid", "filepath"}:
                continue
            if key not in prop_defs:
                continue
            try:
                setattr(settings, key, value)
            except Exception:
                continue
    finally:
        settings.persist_suspended = False
    blend_path = getattr(context.blend_data, "filepath", None)
    if blend_path:
        last_path = addon_prefs.get_last_export_path(context, blend_path)
        if last_path:
            try:
                settings.filepath = last_path
            except Exception:
                pass
    else:
        try:
            settings.filepath = ""
        except Exception:
            pass
    settings.history_applied = True


def register():
    """Register operators"""
    bpy.utils.register_class(BLENDERTORCP_OT_export)
    bpy.utils.register_class(BLENDERTORCP_OT_show_diagnostics)
    bpy.utils.register_class(BLENDERTORCP_OT_open_diagnostics_text)


def unregister():
    """Unregister operators"""
    bpy.utils.unregister_class(BLENDERTORCP_OT_open_diagnostics_text)
    bpy.utils.unregister_class(BLENDERTORCP_OT_show_diagnostics)
    bpy.utils.unregister_class(BLENDERTORCP_OT_export)
