"""
RealityKit / Spatial preview operators for BlenderToRCP.

Two independent triggers, both macOS-only:
  * blendertorcp.preview_realitykit  - desktop RealityKit preview window.
  * blendertorcp.send_to_vision_pro  - stream to a connected Apple Vision Pro
                                       via the SpatialPreview framework.

Both share one live-export loop (see ``live_preview``). Each is a toggle:
invoke once to start, again to stop. The companion app updates live as the
scene changes.
"""

import sys

from bpy.types import Operator


class _LivePreviewToggle(Operator):
    """Base class for the two live-preview toggle operators."""

    bl_options = {'REGISTER'}

    #: One of live_preview.KIND_DESKTOP / KIND_STREAM. Set by subclasses.
    consumer_kind: str = ""

    @classmethod
    def poll(cls, context):
        if sys.platform != "darwin":
            cls.poll_message_set("The RealityKit / Spatial preview is macOS-only.")
            return False
        return True

    def execute(self, context):
        from .. import live_preview

        try:
            ok, message = live_preview.toggle_consumer(context, self.consumer_kind, launch=True)
        except Exception as exc:  # surface pipeline failures to the user
            import traceback

            traceback.print_exc()
            self.report({'ERROR'}, f"Live preview failed: {exc}")
            return {'CANCELLED'}

        if ok:
            self.report({'INFO'}, message)
            return {'FINISHED'}
        self.report({'ERROR'}, message)
        return {'CANCELLED'}


class BLENDERTORCP_OT_preview_realitykit(_LivePreviewToggle):
    """Preview the current scene in the RealityKit engine on the Mac.

    Exports a RealityKit-compatible USD and opens it in the RCPPreview
    companion app, then live-updates the window as you edit the scene.
    """

    bl_idname = "blendertorcp.preview_realitykit"
    bl_label = "Preview in RealityKit"
    bl_description = (
        "Open the current scene in the RealityKit preview window and keep it "
        "updated live as you edit (macOS only)"
    )

    consumer_kind = "desktop"


class BLENDERTORCP_OT_send_to_vision_pro(_LivePreviewToggle):
    """Stream the current scene to a connected Apple Vision Pro.

    Uses the macOS 27 SpatialPreview framework via the RCPPreview companion
    app. The Vision Pro must be connected to this Mac through Mac Virtual
    Display; no separate app is needed on the headset.
    """

    bl_idname = "blendertorcp.send_to_vision_pro"
    bl_label = "Send to Vision Pro"
    bl_description = (
        "Stream the current scene to a connected Apple Vision Pro and keep it "
        "updated live as you edit (macOS only; requires Mac Virtual Display)"
    )

    consumer_kind = "stream"


_classes = (
    BLENDERTORCP_OT_preview_realitykit,
    BLENDERTORCP_OT_send_to_vision_pro,
)


def register():
    import bpy

    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    import bpy

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
