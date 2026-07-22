"""
Main UI panel for BlenderToRCP export
"""

import bpy
import errno
import json
import os
from pathlib import Path

from .. import prefs as addon_prefs
from ..api.commands._settings_common import (
    MATERIALX_SURFACE_PROFILE_DEFAULT,
    REALITYKIT_OS27_DEFAULTS,
    realitykit_os27_profile_deviations,
)
from bpy.app.handlers import persistent
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy.types import Panel, PropertyGroup

_PERSIST_APPLY_SCHEDULED = set()
_MISSING_BACKGROUND_STATUS_MESSAGE = (
    "Background job status file is missing. Clear stale job state, then run Bake Textures & Export again."
)
_STALE_BACKGROUND_STATUS_MESSAGE = (
    "Background job is no longer attached to this Blender session. Clear stale job state."
)
_ACTIVE_BACKGROUND_JOB_STATES = {"queued", "running"}
_EXPORT_FORMAT_EXTENSIONS = {
    "USDA": ".usda",
    "USDC": ".usdc",
    "USDZ": ".usdz",
}


def _bake_result_summary(settings) -> str:
    bake_mode = getattr(settings, "bake_mode", "LIT_IBL")
    if bake_mode == "LIT_IBL":
        return "Final export: RealityKit Unlit, baked lighting/shadows."
    if bake_mode == "LIT_ALBEDO":
        return "Final export: RealityKit Lit PBR, material color only."
    return "Final export: RealityKit Unlit, material color only."


def _bake_mode_help_lines(settings) -> tuple[str, str]:
    bake_mode = getattr(settings, "bake_mode", "LIT_IBL")
    if bake_mode == "LIT_IBL":
        return (
            "Matches the Blender preview.",
            "Lighting and shadows are baked into textures.",
        )
    if bake_mode == "LIT_ALBEDO":
        return (
            "Reality Composer Pro or RealityKit lights the baked color.",
            "Blender shadows are not baked.",
        )
    return (
        "Shown as-is, ignoring scene lighting (Unlit).",
        "Blender shadows are not baked.",
    )


def _persist_settings(context, settings) -> None:
    """Persist settings using the shared versioned 2.0 profile."""
    addon_prefs.persist_export_settings(context, settings)


def _normalize_export_format(export_format: str) -> str:
    if export_format == "USD":
        return "USDC"
    return export_format


def _output_path_with_format_extension(filepath: str, export_format: str) -> str:
    filepath = str(filepath or "").strip()
    if not filepath:
        return ""

    extension = _EXPORT_FORMAT_EXTENSIONS.get(_normalize_export_format(export_format), ".usdz")
    try:
        return str(Path(filepath).with_suffix(extension))
    except ValueError:
        return filepath


def _sync_output_path_extension(settings) -> bool:
    filepath = getattr(settings, "filepath", "")
    if not filepath:
        return False

    updated = _output_path_with_format_extension(
        filepath,
        getattr(settings, "export_format", "USDZ"),
    )
    if not updated or updated == filepath:
        return False

    settings.persist_suspended = True
    try:
        settings.filepath = updated
    finally:
        settings.persist_suspended = False
    return True


def _on_settings_changed(self, context) -> None:
    """Update callback for export settings."""
    if getattr(self, "persist_suspended", False):
        return
    _sync_output_path_extension(self)
    _persist_settings(context, self)



class BlenderToRCPExportSettings(PropertyGroup):
    """Export settings stored in scene"""
    
    filepath: StringProperty(
        name="Output Path",
        description="Path where the USD/USDZ file will be exported",
        default="",
        maxlen=1024,
        subtype='FILE_PATH',
        update=_on_settings_changed,
    )
    
    export_format: EnumProperty(
        name="Format",
        description="Export format and file extension",
        items=[
            ('USDA', "USD ASCII (.usda)", "Export as USD ASCII (.usda)"),
            ('USDC', "USD Binary (.usdc)", "Export as USD binary (.usdc)"),
            ('USDZ', "USDZ Package (.usdz)", "Export as USDZ package (.usdz)"),
        ],
        default='USDA',
        update=_on_settings_changed,
    )
    
    root_prim_name: StringProperty(
        name="Root Prim",
        description="Root prim path or name (e.g. /root or Scene)",
        default="/root",
        update=_on_settings_changed,
    )
    

    export_animation: BoolProperty(
        name="Export Animation",
        description="Include animation data in the USD export",
        default=False,
        update=_on_settings_changed,
    )

    author_animation_library: BoolProperty(
        name="RCP Clip Library",
        description=(
            "Author Reality Composer Pro AnimationLibrary clip metadata. "
            "Leave off for RealityKit runtime exports; split imported animations in app code."
        ),
        default=False,
        update=_on_settings_changed,
    )

    selected_objects_only: BoolProperty(
        name="Selection Only",
        description="Only export selected objects",
        default=False,
        update=_on_settings_changed,
    )

    export_custom_properties: BoolProperty(
        name="Custom Properties",
        description="Export custom properties as USD attributes",
        default=True,
        update=_on_settings_changed,
    )

    custom_properties_namespace: StringProperty(
        name="Namespace",
        description="Namespace prefix for custom property names",
        default="userProperties",
        update=_on_settings_changed,
    )

    author_blender_name: BoolProperty(
        name="Blender Names",
        description="Author USD attributes with Blender object/data names. Requires Custom Properties export to be enabled",
        default=True,
        update=_on_settings_changed,
    )

    allow_unicode: BoolProperty(
        name="Allow Unicode",
        description="Preserve UTF-8 characters in USD names (USD 24.03+)",
        default=True,
        update=_on_settings_changed,
    )

    relative_paths: BoolProperty(
        name="Relative Paths",
        description="Use relative paths for external files",
        default=True,
        update=_on_settings_changed,
    )

    materialx_surface_profile: EnumProperty(
        name="Surface Profile",
        description="MaterialX surface contract used when rewriting Blender materials",
        items=[
            (
                'realitykit_portable',
                "RealityKit Portable (Recommended)",
                "Verified portable RealityKit PBR profile (recommended)",
            ),
            (
                'realitykit_pbr2',
                "RealityKit PBR Surface 2 (Experimental)",
                "Experimental OS 27 PBR Surface 2 profile; currently incompatible with Quick Look and USDKit, and may be rejected by strict USD/USDZ validation",
            ),
            (
                'openpbr_1_1',
                "OpenPBR 1.1 / MaterialX 1.39 (Experimental)",
                "Experimental OpenPBR 1.1 profile; some MaterialX 1.39 nodes remain unsupported in current Apple betas",
            ),
        ],
        default=MATERIALX_SURFACE_PROFILE_DEFAULT,
        update=_on_settings_changed,
    )

    convert_orientation: BoolProperty(
        name="Convert Orientation",
        description="Convert Blender's Z-up scene to the RealityKit Y-up USD convention",
        default=REALITYKIT_OS27_DEFAULTS["convert_orientation"],
        update=_on_settings_changed,
    )

    forward_axis: EnumProperty(
        name="Forward Axis",
        description="Forward axis when converting orientation",
        items=[
            ('X', "X", "Positive X"),
            ('Y', "Y", "Positive Y"),
            ('Z', "Z", "Positive Z"),
            ('-X', "-X", "Negative X"),
            ('-Y', "-Y", "Negative Y"),
            ('-Z', "-Z", "Negative Z"),
        ],
        default=REALITYKIT_OS27_DEFAULTS["forward_axis"],
        update=_on_settings_changed,
    )

    up_axis: EnumProperty(
        name="Up Axis",
        description="Up axis when converting orientation",
        items=[
            ('X', "X", "Positive X"),
            ('Y', "Y", "Positive Y"),
            ('Z', "Z", "Positive Z"),
            ('-X', "-X", "Negative X"),
            ('-Y', "-Y", "Negative Y"),
            ('-Z', "-Z", "Negative Z"),
        ],
        default=REALITYKIT_OS27_DEFAULTS["up_axis"],
        update=_on_settings_changed,
    )

    convert_scene_units: EnumProperty(
        name="Units",
        description="Set the USD stage meters-per-unit",
        items=[
            ('METERS', "Meters", "Scene meters per unit to 1.0"),
            ('KILOMETERS', "Kilometers", "Scene meters per unit to 1000.0"),
            ('CENTIMETERS', "Centimeters", "Scene meters per unit to 0.01"),
            ('MILLIMETERS', "Millimeters", "Scene meters per unit to 0.001"),
            ('INCHES', "Inches", "Scene meters per unit to 0.0254"),
            ('FEET', "Feet", "Scene meters per unit to 0.3048"),
            ('YARDS', "Yards", "Scene meters per unit to 0.9144"),
            ('CUSTOM', "Custom", "Specify a custom meters-per-unit value"),
        ],
        default=REALITYKIT_OS27_DEFAULTS["convert_scene_units"],
        update=_on_settings_changed,
    )

    meters_per_unit: FloatProperty(
        name="Meters Per Unit",
        description="Custom meters-per-unit value for USD stage",
        min=0.0001,
        max=1000.0,
        default=REALITYKIT_OS27_DEFAULTS["meters_per_unit"],
        update=_on_settings_changed,
    )

    xform_op_mode: EnumProperty(
        name="Xform Ops",
        description="Transform operator convention to write",
        items=[
            ('TRS', "Translate, Rotate, Scale", "Write translate, rotate, scale ops"),
            ('TOS', "Translate, Orient, Scale", "Write translate, orient, scale ops"),
            ('MAT', "Matrix", "Write matrix transform op"),
        ],
        default='TRS',
        update=_on_settings_changed,
    )

    evaluation_mode: EnumProperty(
        name="Use Settings for",
        description="Choose viewport or render evaluation settings",
        items=[
            ('RENDER', "Render", "Use render settings"),
            ('VIEWPORT', "Viewport", "Use viewport settings"),
        ],
        default='RENDER',
        update=_on_settings_changed,
    )

    export_meshes: BoolProperty(
        name="Meshes",
        description="Export meshes",
        default=REALITYKIT_OS27_DEFAULTS["export_meshes"],
        update=_on_settings_changed,
    )

    export_uvmaps: BoolProperty(
        name="UV Maps",
        description="Include all mesh UV maps in export",
        default=True,
        update=_on_settings_changed,
    )

    rename_uvmaps: BoolProperty(
        name="Rename UV Maps",
        description="Rename active render UV map to 'st'",
        default=True,
        update=_on_settings_changed,
    )

    export_normals: BoolProperty(
        name="Normals",
        description="Include normals of exported meshes",
        default=True,
        update=_on_settings_changed,
    )

    merge_parent_xform: BoolProperty(
        name="Merge Parent Xform",
        description="Merge parent transforms into geometry",
        default=False,
        update=_on_settings_changed,
    )

    triangulate_meshes: BoolProperty(
        name="Triangulate Meshes",
        description="Triangulate meshes during export",
        default=False,
        update=_on_settings_changed,
    )

    quad_method: EnumProperty(
        name="Quad Method",
        description="Method for splitting quads into triangles",
        items=[
            ('SHORTEST_DIAGONAL', "Shortest Diagonal", "Split along the shortest diagonal"),
            ('BEAUTY', "Beauty", "Split for best-looking results"),
            ('FIXED', "Fixed", "Split quads on the first diagonal"),
            ('FIXED_ALTERNATE', "Fixed Alternate", "Split quads on the opposite diagonal"),
        ],
        default='SHORTEST_DIAGONAL',
        update=_on_settings_changed,
    )

    ngon_method: EnumProperty(
        name="N-gon Method",
        description="Method for splitting n-gons into triangles",
        items=[
            ('BEAUTY', "Beauty", "Split for best-looking results"),
            ('EAR_CLIP', "Ear Clip", "Clip ears to split n-gons"),
        ],
        default='BEAUTY',
        update=_on_settings_changed,
    )

    export_subdivision: EnumProperty(
        name="Subdivision",
        description="How subdivision modifiers are exported",
        items=[
            ('IGNORE', "Ignore", "Export base mesh without subdivision"),
            ('TESSELLATE', "Tessellate", "Export subdivided mesh without subdivision scheme"),
            ('BEST_MATCH', "Best Match", "Export subdivision scheme when possible"),
        ],
        default='BEST_MATCH',
        update=_on_settings_changed,
    )

    export_armatures: BoolProperty(
        name="Armatures",
        description="Export armatures as USD skeletons",
        default=True,
        update=_on_settings_changed,
    )

    only_deform_bones: BoolProperty(
        name="Only Deform Bones",
        description="Export only deform bones and parents",
        default=False,
        update=_on_settings_changed,
    )

    export_shapekeys: BoolProperty(
        name="Shape Keys",
        description="Export shape keys as USD blend shapes",
        default=True,
        update=_on_settings_changed,
    )

    use_instancing: BoolProperty(
        name="Instancing",
        description="Export instanced objects as USD references",
        default=True,
        update=_on_settings_changed,
    )

    bake_mode: EnumProperty(
        name="Texture Bake Includes",
        description="Choose whether baked textures include material color only (Unlit or Lit PBR) or Blender lighting and shadows",
        items=[
            ('UNLIT_ALBEDO', "Material Color Only - Unlit", "Bake light-independent material color and author RealityKit Unlit materials — shown as-is, ignoring scene lighting. Blender shadows are not baked."),
            ('LIT_ALBEDO', "Material Color Only - Lit PBR", "Bake light-independent material color and author Lit PBR materials so Reality Composer Pro or RealityKit lights the baked color. Blender shadows are not baked."),
            ('LIT_IBL', "Lighting & Shadows", "Use when the export should match the Blender preview. Blender lighting and shadows are baked into textures (authored Unlit)."),
        ],
        default='LIT_IBL',
        update=_on_settings_changed,
    )

    bake_ibl_source: EnumProperty(
        name="Lighting Source",
        description="Select which scene world or HDRI lighting source is baked into textures",
        items=[
            ('SCENE_WORLD', "Scene World", "Use the current scene World for the lighting bake"),
            ('HDRI_FILE', "HDRI File", "Use a specific HDRI file for the lighting bake"),
        ],
        default='SCENE_WORLD',
        update=_on_settings_changed,
    )

    bake_ibl_filepath: StringProperty(
        name="HDRI File",
        description="HDRI file used when baking lighting and shadows",
        default="",
        maxlen=1024,
        subtype='FILE_PATH',
        update=_on_settings_changed,
    )

    bake_ibl_strength: FloatProperty(
        name="Lighting Strength",
        description="Lighting strength multiplier for the HDRI bake",
        default=1.0,
        min=0.0,
        update=_on_settings_changed,
    )

    bake_ibl_rotation: FloatProperty(
        name="Lighting Rotation",
        description="Z rotation for the HDRI lighting source",
        default=0.0,
        subtype='ANGLE',
        update=_on_settings_changed,
    )

    bake_isolate_meshes_lit: BoolProperty(
        name="Isolate Meshes for Shadows",
        description="When baking lighting and shadows, hide other meshes while baking each mesh to avoid cross-mesh shadows",
        default=False,
        update=_on_settings_changed,
    )

    bake_step_timeout_seconds: IntProperty(
        name="Step Timeout (sec)",
        description="Maximum duration of one background bake/export step; use 0 for no timeout",
        default=0,
        min=0,
        update=_on_settings_changed,
    )

    export_texture_settings_enabled: BoolProperty(
        name="Override Textures",
        description="Resize and transcode exported textures with the USD Export: Texture panel",
        default=False,
        update=_on_settings_changed,
    )

    bake_resolution: EnumProperty(
        name="Texture Resolution",
        description="Resolution for baked textures and opt-in exported texture overrides",
        items=[
            ('ORIGINAL', "Keep Original", "Do not resize existing exported textures"),
            ('512', "512", "512 px"),
            ('1024', "1024", "1024 px"),
            ('2048', "2048", "2048 px"),
            ('4096', "4096", "4096 px"),
            ('CUSTOM', "Custom", "Use a custom resolution"),
        ],
        default='2048',
        update=_on_settings_changed,
    )

    bake_image_format: EnumProperty(
        name="Image Format",
        description="File format for texture overrides (Original keeps Apple-compatible encodings and normalizes unsupported LDR inputs to PNG)",
        items=[
            ('ORIGINAL', "Original", "Keep AVIF, PNG, JPEG, and OpenEXR encodings; normalize unsupported LDR inputs to PNG"),
            ('AVIF', ".avif", "Bake textures as AVIF with alpha"),
            ('PNG', ".png", "Bake textures as PNG with alpha"),
        ],
        default='AVIF',
        update=_on_settings_changed,
    )

    bake_resolution_custom: IntProperty(
        name="Custom Resolution",
        description="Custom bake resolution (pixels)",
        default=2048,
        min=32,
        update=_on_settings_changed,
    )

    bake_margin: IntProperty(
        name="Bake Margin",
        description="Bake padding in pixels",
        default=8,
        min=0,
        update=_on_settings_changed,
    )

    bake_base_color: BoolProperty(
        name="Bake Base Color",
        description="Bake base color textures",
        default=True,
        update=_on_settings_changed,
    )

    bake_opacity: BoolProperty(
        name="Bake Opacity",
        description="Bake opacity textures",
        default=True,
        update=_on_settings_changed,
    )

    bake_keep_materials: BoolProperty(
        name="Keep Baked Materials",
        description="Keep baked materials assigned after export",
        default=False,
        update=_on_settings_changed,
    )

    bake_roughness_mode: EnumProperty(
        name="Roughness",
        description="How Lit PBR roughness is exported ('Material Color Only - Lit PBR' only)",
        items=[
            ('TEXTURE', "Bake Roughness Maps", "Bake a per-texel roughness texture (accurate, larger file)."),
            ('AVERAGE', "Average to Single Value", "Use one averaged roughness constant — no roughness texture exported (smaller file)."),
        ],
        default='TEXTURE',
        update=_on_settings_changed,
    )

    apply_yup_geometry: BoolProperty(
        name="Apply RealityKit (Y-Up) to Geometry",
        description="Bake a −90° X rotation (about the scene origin) into the mesh data and export as a native Y-up USD with no root orientation. Skipped automatically (falling back to root orientation conversion) when the scene has animated, constrained or armature-deformed transforms the bake cannot preserve.",
        default=False,
        update=_on_settings_changed,
    )

    force_unlit_materials: BoolProperty(
        name="Force Unlit Materials",
        description="Force rewrite to RealityKit Unlit materials",
        default=False,
        options={'HIDDEN'},
        update=_on_settings_changed,
    )

    diagnostics_enabled: BoolProperty(
        name="Enable Diagnostics",
        description="Write an export diagnostics JSON sidecar next to the output file",
        default=False,
        update=_on_settings_changed,
    )
    

    last_diagnostics_path: StringProperty(
        name="Last Diagnostics Path",
        description="Last diagnostics JSON file path",
        default="",
        options={'HIDDEN'}
    )

    background_job_dir: StringProperty(
        name="Background Job Dir",
        description="Path to the active background bake/export job",
        default="",
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    background_job_pid: IntProperty(
        name="Background Job PID",
        description="PID for the active background job",
        default=0,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    history_applied: BoolProperty(
        name="History Applied",
        description="Whether persisted settings were applied",
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    persist_suspended: BoolProperty(
        name="Persist Suspended",
        description="Suspend settings persistence while loading",
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    


class BLENDERTORCP_PT_export_panel(Panel):
    """Main export panel"""
    bl_label = "BlenderToRCP Export"
    bl_idname = "BLENDERTORCP_PT_export_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"
    
    def draw(self, context):
        """Draw panel UI"""
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = getattr(context.scene, "blender_to_rcp_export_settings", None)
        if settings is None:
            layout.label(text="Export settings unavailable. Reload the add-on.")
            layout.operator("blendertorcp.export", icon='EXPORT', text="Export Scene")
            return

        try:
            _apply_persisted_settings(context)
            status = _read_background_job_status(settings)
            job_state = status.get("state") if status else None
            job_running = job_state in {"queued", "running"}

            # Job monitor first: while a job runs (and everything below is
            # locked), state, progress and the cancel affordance must be
            # visible without scrolling.
            if status:
                _draw_job_monitor(layout, status, job_state, job_running)

            export_box = layout.box()
            export_box.label(text="Export Settings", icon='EXPORT')
            export_box.enabled = not job_running
            export_box.prop(settings, "filepath", placeholder="//export/scene.usdz")
            export_box.prop(settings, "export_format")

            actions_box = layout.box()
            actions_box.label(text="Actions", icon='PLAY')

            export_row = actions_box.row()
            export_row.enabled = not job_running
            export_row.operator("blendertorcp.export", icon='EXPORT', text="Export Scene")

            bake_row = actions_box.row()
            bake_row.enabled = not job_running
            bake_row.operator(
                "blendertorcp.bake_export_background",
                icon='RENDER_STILL',
                text="Bake Textures & Export"
            )

            timeout_row = actions_box.row()
            timeout_row.enabled = not job_running
            timeout_row.prop(settings, "bake_step_timeout_seconds")
            if settings.bake_step_timeout_seconds == 0:
                actions_box.label(text="Background steps have no time limit.", icon='INFO')
            else:
                actions_box.label(
                    text=f"Each step stops after {settings.bake_step_timeout_seconds} seconds.",
                    icon='TIME',
                )
        except Exception as exc:
            layout.label(text=f"UI error: {exc}")
            layout.operator("blendertorcp.export", icon='EXPORT', text="Export Scene")


def _draw_job_monitor(layout, status, job_state, job_running):
    """Background-job status card.

    Header row carries the state plus a compact cancel/clear button, running
    jobs get a real progress bar (the runner's step message doubles as the bar
    label) and a note explaining why the rest of the panel is greyed out, and
    failures render in Blender's alert styling instead of a plain label.
    """
    monitor = layout.box()
    header = monitor.row(align=True)
    if job_running:
        header.label(text="Background Job - Running", icon='TIME')
        header.operator("blendertorcp.cancel_bake_export", text="", icon='CANCEL')
    else:
        state_row = header.row(align=True)
        if job_state == "error":
            state_row.alert = True
            state_row.label(text="Background Job - Failed", icon='ERROR')
        elif job_state == "done":
            state_row.label(text="Background Job - Done", icon='CHECKMARK')
        elif job_state == "canceled":
            state_row.label(text="Background Job - Canceled", icon='CANCEL')
        else:
            state_row.label(text=f"Background Job - {job_state or 'Unknown'}", icon='QUESTION')
        header.operator("blendertorcp.clear_bake_job", text="", icon='TRASH')

    message = str(status.get("message") or "")
    if job_running:
        factor = 0.0
        try:
            factor = max(0.0, min(1.0, float(status.get("progress"))))
        except (TypeError, ValueError):
            pass
        monitor.progress(text=message or f"{int(factor * 100)}%", factor=factor, type='BAR')
        monitor.label(
            text="Settings are locked until the job finishes or is canceled.",
            icon='LOCKED',
        )
    elif message:
        message_column = monitor.column()
        message_column.alert = job_state == "error"
        message_column.label(
            text=message,
            icon='ERROR' if job_state == "error" else 'INFO',
        )

    if status.get("export_path"):
        monitor.label(text=f"Output: {status.get('export_path')}", icon='FILE')

    file_row = monitor.row(align=True)
    if status.get("log_path"):
        op = file_row.operator("blendertorcp.open_support_text", icon='TEXT', text="Open Log")
        op.filepath = status.get("log_path")
        op.text_name = "BlenderToRCP Background Log"
    if status.get("diagnostics_path"):
        op = file_row.operator(
            "blendertorcp.open_diagnostics_text", icon='INFO', text="Open Diagnostics"
        )
        op.filepath = status.get("diagnostics_path")


class BLENDERTORCP_PT_export_usd_root(Panel):
    """USD export settings root panel.

    All setting groups are drawn as inline collapsible sections
    (``layout.panel``) instead of separately registered sub-panels: one less
    nesting level to click through, section open/closed state is remembered
    per region, and the sections stay expandable while a background job runs
    (only their contents grey out, with a note explaining why).
    """
    bl_label = "USD Export Settings"
    bl_idname = "BLENDERTORCP_PT_export_usd_root"
    bl_parent_id = "BLENDERTORCP_PT_export_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.blender_to_rcp_export_settings
        job_running = _is_job_running(settings)
        if job_running:
            layout.label(text="Locked while a background job runs.", icon='LOCKED')

        for idname, title, draw_section in _USD_EXPORT_SECTIONS:
            header, body = layout.panel(idname, default_closed=True)
            header.label(text=title)
            if body is not None:
                body.enabled = not job_running
                draw_section(body, settings)


def _draw_usd_general_section(layout, settings):
    deviations = realitykit_os27_profile_deviations(settings)
    if deviations:
        layout.label(text="Custom profile (differs from OS 27 defaults)", icon='INFO')
    else:
        layout.label(text="RealityKit OS 27 profile: Y-up, meters", icon='CHECKMARK')
    layout.prop(settings, "root_prim_name", placeholder="Scene")

    include_row = layout.row(align=True)
    include_row.label(text="Include")
    include_row.prop(settings, "selected_objects_only", text="Selection Only")
    include_row.prop(settings, "export_animation", text="Animation")
    if settings.export_animation:
        layout.prop(settings, "author_animation_library")

    layout.prop(settings, "export_custom_properties")
    if settings.export_custom_properties:
        layout.prop(settings, "custom_properties_namespace")
        layout.prop(settings, "author_blender_name")
    else:
        row = layout.row()
        row.enabled = False
        row.prop(settings, "author_blender_name")
    layout.prop(settings, "allow_unicode")
    layout.prop(settings, "relative_paths")
    layout.prop(settings, "convert_orientation")
    if settings.convert_orientation:
        layout.prop(settings, "apply_yup_geometry")
        # Y-up geometry bake forces a native Y-up export and disables the
        # exporter's own orientation conversion, so the forward/up axis
        # dropdowns no longer apply — hide them while it is enabled.
        if not settings.apply_yup_geometry:
            layout.prop(settings, "forward_axis")
            layout.prop(settings, "up_axis")
    layout.prop(settings, "convert_scene_units")
    if settings.convert_scene_units == 'CUSTOM':
        layout.prop(settings, "meters_per_unit")
    layout.prop(settings, "xform_op_mode")
    layout.prop(settings, "evaluation_mode")
    layout.prop(settings, "use_instancing")


def _draw_usd_object_types_section(layout, settings):
    layout.prop(settings, "export_meshes")


def _draw_usd_geometry_section(layout, settings):
    layout.prop(settings, "export_uvmaps")
    layout.prop(settings, "rename_uvmaps")
    layout.prop(settings, "export_normals")
    layout.prop(settings, "merge_parent_xform")
    layout.prop(settings, "triangulate_meshes")
    if settings.triangulate_meshes:
        layout.prop(settings, "quad_method")
        layout.prop(settings, "ngon_method")
    layout.prop(settings, "export_subdivision")


def _draw_usd_rigging_section(layout, settings):
    layout.prop(settings, "export_shapekeys")
    layout.prop(settings, "export_armatures")
    layout.prop(settings, "only_deform_bones")


def _draw_usd_texture_section(layout, settings):
    layout.prop(settings, "export_texture_settings_enabled")

    column = layout.column()
    column.enabled = bool(settings.export_texture_settings_enabled)
    column.prop(settings, "bake_resolution")
    column.prop(settings, "bake_image_format")
    if settings.bake_resolution == 'CUSTOM':
        column.prop(settings, "bake_resolution_custom")
    column.prop(settings, "bake_margin")


def _draw_usd_material_section(layout, settings):
    profile = getattr(
        settings,
        "materialx_surface_profile",
        MATERIALX_SURFACE_PROFILE_DEFAULT,
    )
    layout.prop(settings, "materialx_surface_profile")

    caveats = layout.box()
    if profile == MATERIALX_SURFACE_PROFILE_DEFAULT:
        layout.label(
            text="Portable RealityKit PBR is the verified shipping profile.",
            icon='CHECKMARK',
        )
        caveats.label(text="Experimental profile caveats", icon='INFO')
    else:
        caveats.alert = True
        caveats.label(text="Experimental Apple beta material path", icon='ERROR')
    caveats.label(text="PBR Surface 2: incompatible with Quick Look and USDKit.")
    caveats.label(text="PBR Surface 2: use USDC/RCP3; strict USDZ validation may reject it.")
    caveats.label(text="OpenPBR: some MaterialX 1.39 nodes remain unsupported.")


def _draw_usd_bake_section(layout, settings):
    layout.prop(settings, "bake_mode")
    layout.label(text=_bake_result_summary(settings), icon='INFO')

    # The per-mode explanation lives in a collapsible sub-section instead of
    # permanently occupying panel rows.
    help_header, help_body = layout.panel("blendertorcp_bake_mode_help", default_closed=True)
    help_header.label(text="About This Mode")
    if help_body is not None:
        help_column = help_body.column(align=True)
        for line in _bake_mode_help_lines(settings):
            help_column.label(text=line)

    if settings.bake_mode == 'LIT_IBL':
        lighting_box = layout.box()
        lighting_box.label(text="Lighting Source")
        lighting_box.prop(settings, "bake_ibl_source")
        if settings.bake_ibl_source == 'HDRI_FILE':
            lighting_box.prop(settings, "bake_ibl_filepath", placeholder="//studio.hdr")
            lighting_box.prop(settings, "bake_ibl_strength")
            lighting_box.prop(settings, "bake_ibl_rotation")
        lighting_box.prop(settings, "bake_isolate_meshes_lit")

    advanced_header, advanced_body = layout.panel("blendertorcp_bake_advanced", default_closed=True)
    advanced_header.label(text="Advanced")
    if advanced_body is not None:
        if settings.bake_mode == 'LIT_ALBEDO':
            advanced_body.prop(settings, "bake_roughness_mode")
        advanced_body.prop(settings, "bake_base_color")
        advanced_body.prop(settings, "bake_opacity")
        advanced_body.prop(settings, "bake_step_timeout_seconds")
        advanced_body.prop(settings, "bake_keep_materials")


_USD_EXPORT_SECTIONS = (
    ("blendertorcp_usd_general", "General", _draw_usd_general_section),
    ("blendertorcp_usd_object_types", "Object Types", _draw_usd_object_types_section),
    ("blendertorcp_usd_geometry", "Geometry", _draw_usd_geometry_section),
    ("blendertorcp_usd_rigging", "Rigging", _draw_usd_rigging_section),
    ("blendertorcp_usd_materials", "Materials (Advanced)", _draw_usd_material_section),
    ("blendertorcp_usd_texture", "Texture", _draw_usd_texture_section),
    ("blendertorcp_usd_baking", "Baking", _draw_usd_bake_section),
)


class BLENDERTORCP_PT_export_diagnostics(Panel):
    """Diagnostics and support actions."""
    bl_label = "Diagnostics"
    bl_idname = "BLENDERTORCP_PT_export_diagnostics"
    bl_parent_id = "BLENDERTORCP_PT_export_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        settings = context.scene.blender_to_rcp_export_settings
        job_running = _is_job_running(settings)
        toggle_row = layout.row()
        toggle_row.enabled = not job_running
        toggle_row.prop(settings, "diagnostics_enabled")

        if not settings.diagnostics_enabled:
            return

        diag_path = _diagnostics_output_path(settings)
        if diag_path:
            layout.label(text=f"Path: {diag_path}", icon='FILE')

        actions = layout.row(align=True)
        actions.operator("blendertorcp.show_diagnostics", icon='INFO', text="Show Diagnostics")
        actions.operator("blendertorcp.create_support_bundle", icon='FILE_FOLDER', text="Create Support Bundle")



def _diagnostics_output_path(settings) -> str:
    status = _read_background_job_status(settings)
    if status and status.get("diagnostics_path"):
        return str(status.get("diagnostics_path"))
    filepath = str(getattr(settings, "filepath", "") or "").strip()
    if not filepath:
        return ""
    try:
        return str(Path(filepath).with_suffix(".diagnostics.json"))
    except Exception:
        return ""


def register():
    """Register UI classes"""
    bpy.utils.register_class(BlenderToRCPExportSettings)
    bpy.utils.register_class(BLENDERTORCP_PT_export_panel)
    bpy.utils.register_class(BLENDERTORCP_PT_export_usd_root)
    bpy.utils.register_class(BLENDERTORCP_PT_export_diagnostics)

    # Register property on Scene
    bpy.types.Scene.blender_to_rcp_export_settings = bpy.props.PointerProperty(
        type=BlenderToRCPExportSettings
    )
    _remove_background_job_load_handlers()
    bpy.app.handlers.load_post.append(_clear_background_job_state_on_load)
    _clear_missing_background_job_status()


def unregister():
    """Unregister UI classes"""
    _remove_background_job_load_handlers()
    del bpy.types.Scene.blender_to_rcp_export_settings
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_diagnostics)
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_usd_root)
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_panel)
    bpy.utils.unregister_class(BlenderToRCPExportSettings)


def _apply_persisted_settings_now(context, settings) -> None:
    """Apply persisted export settings immediately (safe outside draw)."""
    result = addon_prefs.apply_persisted_export_settings(context, settings)

    if _sync_output_path_extension(settings):
        _persist_settings(context, settings)
    return result


def _apply_persisted_settings(context) -> None:
    """Schedule applying persisted export settings once per scene."""
    scene = context.scene
    settings = scene.blender_to_rcp_export_settings
    if (
        settings.history_applied
        and addon_prefs.export_settings_scene_is_current(settings)
    ):
        return

    key = scene.as_pointer()
    if key in _PERSIST_APPLY_SCHEDULED:
        return

    _PERSIST_APPLY_SCHEDULED.add(key)

    def _apply():
        try:
            _apply_persisted_settings_now(bpy.context, settings)
        finally:
            _PERSIST_APPLY_SCHEDULED.discard(key)
        return None

    bpy.app.timers.register(_apply, first_interval=0.0)


def _read_background_job_status(settings):
    job_dir = getattr(settings, "background_job_dir", "")
    if not job_dir:
        return None
    status_path = Path(job_dir) / "status.json"
    if not status_path.exists():
        if int(getattr(settings, "background_job_pid", 0)) > 0:
            return {"state": "error", "message": _MISSING_BACKGROUND_STATUS_MESSAGE}
        return None
    try:
        data = json.loads(status_path.read_text())
    except Exception:
        if int(getattr(settings, "background_job_pid", 0)) > 0:
            return {"state": "error", "message": "Background job status file could not be read. Clear stale job state."}
        return None
    if data.get("state") in _ACTIVE_BACKGROUND_JOB_STATES:
        pid = _safe_int(getattr(settings, "background_job_pid", 0)) or 0
        status_pid = _safe_int(data.get("pid"))
        if pid <= 0 or status_pid is None or status_pid != pid or not _pid_is_running(pid):
            stale = dict(data)
            stale["state"] = "error"
            stale["message"] = _STALE_BACKGROUND_STATUS_MESSAGE
            return stale
    return data


def _is_job_running(settings) -> bool:
    status = _read_background_job_status(settings)
    if not status:
        return False
    return status.get("state") in {"queued", "running"}


def _clear_background_job_state(settings) -> None:
    try:
        settings.background_job_dir = ""
    except Exception:
        pass
    try:
        settings.background_job_pid = 0
    except Exception:
        pass


def _clear_missing_background_job_status() -> None:
    for scene in getattr(bpy.data, "scenes", []):
        settings = getattr(scene, "blender_to_rcp_export_settings", None)
        if settings is None:
            continue
        job_dir = getattr(settings, "background_job_dir", "")
        if not job_dir:
            continue
        if not (Path(job_dir) / "status.json").exists():
            _clear_background_job_state(settings)


@persistent
def _clear_background_job_state_on_load(_dummy) -> None:
    for scene in getattr(bpy.data, "scenes", []):
        settings = getattr(scene, "blender_to_rcp_export_settings", None)
        if settings is not None:
            _clear_background_job_state(settings)


def _remove_background_job_load_handlers() -> None:
    for handler in list(bpy.app.handlers.load_post):
        if getattr(handler, "__name__", "") == "_clear_background_job_state_on_load":
            try:
                bpy.app.handlers.load_post.remove(handler)
            except ValueError:
                pass


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


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
