"""
Live preview subpackage for BlenderToRCP.

Public API used by the operators / UI:
  * toggle_consumer(context, kind, launch=True) -> (ok, message)
  * is_active(kind=None) -> bool
  * get_status() -> dict        (status.json written by the companion app)
  * register() / unregister()
"""

_needs_reload = "bpy" in locals()

import bpy  # noqa: F401

from . import engine
from . import launcher

if _needs_reload:
    import importlib

    engine = importlib.reload(engine)
    launcher = importlib.reload(launcher)


KIND_DESKTOP = engine.KIND_DESKTOP
KIND_STREAM = engine.KIND_STREAM


def toggle_consumer(context, kind: str, launch: bool = True) -> tuple[bool, str]:
    """Start the consumer if inactive, otherwise stop it. Returns (ok, msg)."""
    session = engine.get_session(context)

    if session.is_active(kind):
        session.stop_consumer(kind)
        return True, f"Stopped {kind} preview"

    session.start_consumer(context, kind)

    if launch:
        from .. import prefs as addon_prefs

        ok, msg = launcher.launch_companion(session.session_dir, addon_prefs.get_preferences(context))
        if not ok:
            session.stop_consumer(kind)
            return False, msg

    label = "RealityKit preview" if kind == KIND_DESKTOP else "Vision Pro stream"
    return True, f"Started {label}"


def is_active(kind: str | None = None) -> bool:
    session = engine._SESSION
    if session is None:
        return False
    return session.is_active(kind)


def get_status() -> dict:
    session = engine._SESSION
    if session is None:
        return {}
    return session.read_status()


def register() -> None:
    engine.register_load_handler()


def unregister() -> None:
    engine.shutdown()
    engine.unregister_load_handler()
