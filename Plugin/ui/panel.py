"""
Main UI panel for BlenderToRCP export
"""

import bpy
import json
from pathlib import Path

from .. import prefs as addon_prefs
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy.types import Panel, PropertyGroup

_PERSIST_APPLY_SCHEDULED = set()

def _persist_settings(context, settings) -> None:
    """Persist settings to add-on preferences."""
    prefs = addon_prefs.get_preferences(context) if context else None
    if not prefs:
        return
    data = {}
    for prop in settings.bl_rna.properties:
        key = prop.identifier
        if key in {"rna_type", "name", "history_applied", "last_diagnostics_path", "persist_suspended", "background_job_dir", "background_job_pid", "filepath"}:
            continue
        try:
            data[key] = getattr(settings, key)
        except Exception:
            continue
    try:
        prefs.last_export_settings_json = json.dumps(data)
    except Exception:
        pass
    if context and getattr(context.blend_data, "filepath", None):
        addon_prefs.set_last_export_path(context, getattr(settings, "filepath", ""))


def _on_settings_changed(self, context) -> None:
    """Update callback for export settings."""
    if getattr(self, "persist_suspended", False):
        return
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
        description="Author USD attributes with Blender object/data names",
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

    convert_orientation: BoolProperty(
        name="Convert Orientation",
        description="Convert scene orientation for USD export",
        default=False,
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
        default='-Z',
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
        default='Y',
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
        default='METERS',
        update=_on_settings_changed,
    )

    meters_per_unit: FloatProperty(
        name="Meters Per Unit",
        description="Custom meters-per-unit value for USD stage",
        min=0.0001,
        max=1000.0,
        default=1.0,
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
        default=True,
        update=_on_settings_changed,
    )

    export_lights: BoolProperty(
        name="Lights",
        description="Export lights",
        default=True,
        update=_on_settings_changed,
    )

    convert_world_material: BoolProperty(
        name="World Dome Light",
        description="Convert world material to a USD dome light",
        default=True,
        update=_on_settings_changed,
    )

    export_cameras: BoolProperty(
        name="Cameras",
        description="Export cameras",
        default=True,
        update=_on_settings_changed,
    )

    export_curves: BoolProperty(
        name="Curves",
        description="Export curves",
        default=True,
        update=_on_settings_changed,
    )

    export_points: BoolProperty(
        name="Point Clouds",
        description="Export point clouds",
        default=True,
        update=_on_settings_changed,
    )

    export_volumes: BoolProperty(
        name="Volumes",
        description="Export volumes",
        default=True,
        update=_on_settings_changed,
    )

    export_hair: BoolProperty(
        name="Hair",
        description="Export hair particle systems as curves",
        default=False,
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

    bake_resolution: EnumProperty(
        name="Bake Resolution",
        description="Resolution for baked textures",
        items=[
            ('512', "512", "512x512"),
            ('1024', "1024", "1024x1024"),
            ('2048', "2048", "2048x2048"),
            ('4096', "4096", "4096x4096"),
            ('CUSTOM', "Custom", "Use a custom resolution"),
        ],
        default='2048',
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

    force_unlit_materials: BoolProperty(
        name="Force Unlit Materials",
        description="Force rewrite to RealityKit Unlit materials",
        default=False,
        options={'HIDDEN'},
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
        options={'HIDDEN'}
    )

    background_job_pid: IntProperty(
        name="Background Job PID",
        description="PID for the active background job",
        default=0,
        options={'HIDDEN'}
    )

    history_applied: BoolProperty(
        name="History Applied",
        description="Whether persisted settings were applied",
        default=False,
        options={'HIDDEN'}
    )

    persist_suspended: BoolProperty(
        name="Persist Suspended",
        description="Suspend settings persistence while loading",
        default=False,
        options={'HIDDEN'}
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
            layout.operator("blendertorcp.export", icon='EXPORT', text="Export")
            return

        try:
            _apply_persisted_settings(context)
            export_box = layout.box()
            export_box.label(text="Export Settings", icon='EXPORT')
            export_box.enabled = not _is_job_running(settings)
            export_box.prop(settings, "filepath")
            export_box.prop(settings, "export_format")

            actions_box = layout.box()
            actions_box.label(text="Actions", icon='PLAY')
            status = _read_background_job_status(settings)
            job_state = status.get("state") if status else None
            job_running = job_state in {"queued", "running"}

            export_row = actions_box.row()
            export_row.enabled = not job_running
            export_row.operator("blendertorcp.export", icon='EXPORT', text="Export")

            bake_row = actions_box.row()
            bake_row.enabled = not job_running
            bake_row.operator(
                "blendertorcp.bake_export_background",
                icon='RENDER_STILL',
                text="Bake & Export"
            )

            if status:
                monitor = actions_box.box()
                monitor.label(text=f"State: {job_state or 'unknown'}")
                progress = status.get("progress")
                if progress is not None:
                    try:
                        monitor.label(text=f"Progress: {int(progress * 100)}%")
                    except Exception:
                        pass
                if status.get("export_path"):
                    monitor.label(text=f"Output: {status.get('export_path')}")
                if status.get("message"):
                    monitor.label(text=status.get("message"))

                if job_running:
                    monitor.operator(
                        "blendertorcp.cancel_bake_export",
                        icon='CANCEL',
                        text="Cancel Background Job"
                    )
                else:
                    monitor.operator(
                        "blendertorcp.clear_bake_job",
                        icon='TRASH',
                        text="Clear Background Job"
                    )
            prefs = addon_prefs.get_preferences(context)
            if prefs and prefs.enable_diagnostics:
                actions_box.operator("blendertorcp.show_diagnostics", icon='INFO', text="Show Diagnostics")
        except Exception as exc:
            layout.label(text=f"UI error: {exc}")
            layout.operator("blendertorcp.export", icon='EXPORT', text="Export")


class BLENDERTORCP_PT_export_usd_root(Panel):
    """USD export settings root panel"""
    bl_label = "USD Export Settings"
    bl_idname = "BLENDERTORCP_PT_export_usd_root"
    bl_parent_id = "BLENDERTORCP_PT_export_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.blender_to_rcp_export_settings
        layout.enabled = not _is_job_running(settings)
        layout.label(text="Advanced USD exporter options.")


class BLENDERTORCP_PT_export_usd_general(Panel):
    """USD exporter general settings"""
    bl_label = "USD Export: General"
    bl_idname = "BLENDERTORCP_PT_export_usd_general"
    bl_parent_id = "BLENDERTORCP_PT_export_usd_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        settings = context.scene.blender_to_rcp_export_settings
        layout.enabled = not _is_job_running(settings)
        layout.prop(settings, "root_prim_name")

        include_row = layout.row(align=True)
        include_row.label(text="Include")
        include_row.prop(settings, "selected_objects_only", text="Selection Only")
        include_row.prop(settings, "export_animation", text="Animation")

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
            layout.prop(settings, "forward_axis")
            layout.prop(settings, "up_axis")
        layout.prop(settings, "convert_scene_units")
        if settings.convert_scene_units == 'CUSTOM':
            layout.prop(settings, "meters_per_unit")
        layout.prop(settings, "xform_op_mode")
        layout.prop(settings, "evaluation_mode")
        layout.prop(settings, "use_instancing")


class BLENDERTORCP_PT_export_usd_object_types(Panel):
    """USD exporter object type toggles"""
    bl_label = "USD Export: Object Types"
    bl_idname = "BLENDERTORCP_PT_export_usd_object_types"
    bl_parent_id = "BLENDERTORCP_PT_export_usd_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        settings = context.scene.blender_to_rcp_export_settings
        layout.enabled = not _is_job_running(settings)
        layout.prop(settings, "export_meshes")
        layout.prop(settings, "export_lights")
        layout.prop(settings, "convert_world_material")
        layout.prop(settings, "export_cameras")
        layout.prop(settings, "export_curves")
        layout.prop(settings, "export_points")
        layout.prop(settings, "export_volumes")
        layout.prop(settings, "export_hair")


class BLENDERTORCP_PT_export_usd_geometry(Panel):
    """USD exporter geometry settings"""
    bl_label = "USD Export: Geometry"
    bl_idname = "BLENDERTORCP_PT_export_usd_geometry"
    bl_parent_id = "BLENDERTORCP_PT_export_usd_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        settings = context.scene.blender_to_rcp_export_settings
        layout.enabled = not _is_job_running(settings)
        layout.prop(settings, "export_uvmaps")
        layout.prop(settings, "rename_uvmaps")
        layout.prop(settings, "export_normals")
        layout.prop(settings, "merge_parent_xform")
        layout.prop(settings, "triangulate_meshes")
        if settings.triangulate_meshes:
            layout.prop(settings, "quad_method")
            layout.prop(settings, "ngon_method")
        layout.prop(settings, "export_subdivision")


class BLENDERTORCP_PT_export_usd_rigging(Panel):
    """USD exporter rigging settings"""
    bl_label = "USD Export: Rigging"
    bl_idname = "BLENDERTORCP_PT_export_usd_rigging"
    bl_parent_id = "BLENDERTORCP_PT_export_usd_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        settings = context.scene.blender_to_rcp_export_settings
        layout.enabled = not _is_job_running(settings)
        layout.prop(settings, "export_shapekeys")
        layout.prop(settings, "export_armatures")
        layout.prop(settings, "only_deform_bones")


class BLENDERTORCP_PT_export_bake_settings(Panel):
    """Bake & Export settings"""
    bl_label = "Bake Settings"
    bl_idname = "BLENDERTORCP_PT_export_bake_settings"
    bl_parent_id = "BLENDERTORCP_PT_export_usd_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        settings = context.scene.blender_to_rcp_export_settings
        layout.enabled = not _is_job_running(settings)
        layout.prop(settings, "bake_resolution")
        if settings.bake_resolution == 'CUSTOM':
            layout.prop(settings, "bake_resolution_custom")
        layout.prop(settings, "bake_margin")
        layout.prop(settings, "bake_base_color")
        layout.prop(settings, "bake_opacity")
        layout.prop(settings, "bake_keep_materials")



def register():
    """Register UI classes"""
    bpy.utils.register_class(BlenderToRCPExportSettings)
    bpy.utils.register_class(BLENDERTORCP_PT_export_panel)
    bpy.utils.register_class(BLENDERTORCP_PT_export_usd_root)
    bpy.utils.register_class(BLENDERTORCP_PT_export_usd_general)
    bpy.utils.register_class(BLENDERTORCP_PT_export_usd_object_types)
    bpy.utils.register_class(BLENDERTORCP_PT_export_usd_geometry)
    bpy.utils.register_class(BLENDERTORCP_PT_export_usd_rigging)
    bpy.utils.register_class(BLENDERTORCP_PT_export_bake_settings)
    
    # Register property on Scene
    bpy.types.Scene.blender_to_rcp_export_settings = bpy.props.PointerProperty(
        type=BlenderToRCPExportSettings
    )


def unregister():
    """Unregister UI classes"""
    del bpy.types.Scene.blender_to_rcp_export_settings
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_bake_settings)
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_usd_rigging)
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_usd_geometry)
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_usd_object_types)
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_usd_general)
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_usd_root)
    bpy.utils.unregister_class(BLENDERTORCP_PT_export_panel)
    bpy.utils.unregister_class(BlenderToRCPExportSettings)


def _apply_persisted_settings_now(context, settings) -> None:
    """Apply persisted export settings immediately (safe outside draw)."""
    if settings.history_applied:
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


def _apply_persisted_settings(context) -> None:
    """Schedule applying persisted export settings once per scene."""
    scene = context.scene
    settings = scene.blender_to_rcp_export_settings
    if settings.history_applied:
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
        return None
    try:
        data = json.loads(status_path.read_text())
    except Exception:
        return None
    return data


def _is_job_running(settings) -> bool:
    status = _read_background_job_status(settings)
    if not status:
        return False
    return status.get("state") in {"queued", "running"}
