"""
Live preview engine for BlenderToRCP.

Maintains a per-Blender-process "live session" that re-exports the current
scene to USD whenever it changes and publishes the result atomically into a
session directory under the user cache. A companion macOS app watches that
directory and reflects the scene in RealityKit (desktop) and/or streams it to
a connected Apple Vision Pro via the SpatialPreview framework (stream).

Design notes:
  * The scene export is the *fast* (no-bake) path, reusing the exact pipeline
    the `blendertorcp.export` operator uses:
        export_blender_scene() -> postprocess_usd.process_usd_stage()
            -> pack_usdz.create_usdz()  (stream / .usdz)
            -> publish_unpacked_export() (desktop / .usdc + sidecars)
  * Change detection uses a `depsgraph_update_post` handler (sets a dirty
    flag) plus a `bpy.app.timers` callback that flushes once the scene has
    been idle for `debounce` seconds. Both run on Blender's main thread.
  * A re-entrancy guard (`_exporting`) ignores the depsgraph updates that the
    export itself generates (selection changes, etc.).
  * Each flush writes a fresh `vNNN/` revision and then atomically rewrites
    `latest.json`, so the watcher never observes a half-written stage.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import bpy
from bpy.app.handlers import persistent


CACHE_NAMESPACE = "com.studiomeije.blendertorcp"
KIND_DESKTOP = "desktop"
KIND_STREAM = "stream"
_VALID_KINDS = {KIND_DESKTOP, KIND_STREAM}
_KEEP_REVISIONS = 3
_TICK_INTERVAL = 0.15


def _now() -> float:
    return time.monotonic()


class _SettingsOverride:
    """Proxy a scene export-settings PropertyGroup with a few overridden keys.

    Reads fall through to the real settings (so the full set of ~40 export
    options is honoured), writes fall through to the real settings too, but
    the overridden keys (e.g. ``export_format``) report our value. This lets
    the live engine pick the output format per-consumer without mutating the
    user's scene properties (which would itself trigger depsgraph updates).
    """

    def __init__(self, base, **overrides):
        object.__setattr__(self, "_base", base)
        object.__setattr__(self, "_overrides", overrides)

    def __getattr__(self, name):
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, "_base"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_base"), name, value)


class LiveSession:
    """Owns the live-export loop and the on-disk session directory."""

    def __init__(self, debounce: float = 0.4):
        self.session_dir: Path = _session_root() / str(os.getpid())
        self.consumers: set[str] = set()
        self.rev: int = 0
        self.debounce: float = debounce
        self.app_launched: bool = False
        self._dirty: bool = False
        self._last_edit: float = 0.0
        self._exporting: bool = False

    # -- consumer lifecycle ------------------------------------------------

    def start_consumer(self, context, kind: str) -> None:
        if kind not in _VALID_KINDS:
            raise ValueError(f"Unknown live preview consumer: {kind}")
        self.session_dir.mkdir(parents=True, exist_ok=True)
        first = not self.consumers
        self.consumers.add(kind)
        self.write_control()
        if first:
            _install_handlers()
        # Produce an initial revision immediately so the app has something to
        # show the moment it launches.
        self.flush(context, force=True)

    def stop_consumer(self, kind: str) -> None:
        self.consumers.discard(kind)
        self.write_control()
        if not self.consumers:
            _remove_handlers()

    def shutdown(self) -> None:
        self.consumers.clear()
        _remove_handlers()

    def is_active(self, kind: Optional[str] = None) -> bool:
        if kind is None:
            return bool(self.consumers)
        return kind in self.consumers

    # -- change tracking ---------------------------------------------------

    def mark_dirty(self) -> None:
        if self._exporting or not self.consumers:
            return
        self._dirty = True
        self._last_edit = _now()

    def tick(self) -> None:
        if self._exporting or not self._dirty:
            return
        if (_now() - self._last_edit) < self.debounce:
            return
        try:
            self.flush(bpy.context, force=False)
        except Exception as exc:  # never let the timer die on a bad export
            print(f"[BlenderToRCP live] flush failed: {exc}")
            self._dirty = False

    # -- export ------------------------------------------------------------

    def flush(self, context, force: bool = False):
        if self._exporting:
            return None
        if not self.consumers:
            return None
        settings = getattr(getattr(context, "scene", None), "blender_to_rcp_export_settings", None)
        if settings is None:
            return None

        self._exporting = True
        try:
            self.rev += 1
            rev_dir = self.session_dir / f"v{self.rev:04d}"
            rev_dir.mkdir(parents=True, exist_ok=True)
            artifacts: dict[str, str] = {}

            if KIND_DESKTOP in self.consumers:
                usdc = rev_dir / "scene.usdc"
                _run_pipeline(context, settings, str(usdc), "USDC")
                artifacts[KIND_DESKTOP] = f"v{self.rev:04d}/scene.usdc"

            if KIND_STREAM in self.consumers:
                usdz = rev_dir / "scene.usdz"
                _run_pipeline(context, settings, str(usdz), "USDZ")
                artifacts[KIND_STREAM] = f"v{self.rev:04d}/scene.usdz"

            self._write_latest(artifacts)
            self._gc_old_revs()
            self._dirty = False
            return self.rev, artifacts
        finally:
            self._exporting = False

    # -- handoff files -----------------------------------------------------

    def write_control(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(
            self.session_dir / "control.json",
            {
                "desktop": KIND_DESKTOP in self.consumers,
                "stream": KIND_STREAM in self.consumers,
                "pid": os.getpid(),
            },
        )

    def read_status(self) -> dict:
        try:
            return json.loads((self.session_dir / "status.json").read_text())
        except Exception:
            return {}

    def _write_latest(self, artifacts: dict[str, str]) -> None:
        _atomic_write_json(
            self.session_dir / "latest.json",
            {"rev": self.rev, "artifacts": artifacts, "consumers": sorted(self.consumers)},
        )

    def _gc_old_revs(self) -> None:
        try:
            revs = sorted(
                (p for p in self.session_dir.glob("v*") if p.is_dir()),
                key=lambda p: p.name,
            )
        except Exception:
            return
        for stale in revs[:-_KEEP_REVISIONS]:
            try:
                import shutil

                shutil.rmtree(stale)
            except Exception:
                pass


def _run_pipeline(context, settings, final_path: str, fmt: str) -> None:
    """Run the BlenderToRCP fast export pipeline for a single artifact."""
    from ..export import blender_usd_export, postprocess_usd, diagnostics

    diag = diagnostics.ExportDiagnostics()
    shim = _SettingsOverride(settings, export_format=fmt)

    temp = blender_usd_export.export_blender_scene(context, shim, final_path, diag)
    if not temp or not os.path.exists(temp):
        raise RuntimeError("USD export produced no file")
    postprocess_usd.process_usd_stage(temp, shim, context, diag)
    if fmt == "USDZ":
        _pack_usdz_arkit(temp, final_path, shim, context, diag)
    elif str(temp) != str(final_path):
        blender_usd_export.publish_unpacked_export(temp, final_path, diag)


def _pack_usdz_arkit(temp_usd: str, final_path: str, settings, context, diag) -> None:
    """Pack an ARKit-aligned USDZ for the Vision Pro stream.

    The companion app streams this single file to the headset, so it must be a
    valid (64-byte-aligned) ARKit USDZ. ``UsdUtils.CreateNewARKitUsdzPackage``
    is the canonical packer and is always available inside Blender's bundled
    USD; fall back to BlenderToRCP's packer if it is unavailable.
    """
    try:
        from pxr import Sdf, UsdUtils

        Path(final_path).parent.mkdir(parents=True, exist_ok=True)
        if os.path.exists(final_path):
            os.remove(final_path)
        if UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath(str(temp_usd)), str(final_path)):
            return
        print("[BlenderToRCP live] ARKit USDZ packaging returned False; using fallback packer")
    except Exception as exc:
        print(f"[BlenderToRCP live] ARKit USDZ packaging failed ({exc}); using fallback packer")

    from ..export import pack_usdz

    pack_usdz.create_usdz(temp_usd, final_path, settings, context, diag)


# -- module-level singleton + handlers ------------------------------------

_SESSION: Optional[LiveSession] = None


def get_session(context=None) -> LiveSession:
    global _SESSION
    if _SESSION is None:
        _SESSION = LiveSession(debounce=_debounce_pref(context))
    else:
        _SESSION.debounce = _debounce_pref(context)
    return _SESSION


def _debounce_pref(context=None) -> float:
    try:
        from .. import prefs as addon_prefs

        prefs = addon_prefs.get_preferences(context)
        if prefs is not None:
            return float(getattr(prefs, "live_preview_debounce", 0.4))
    except Exception:
        pass
    return 0.4


@persistent
def _on_depsgraph_update_post(*_args) -> None:
    if _SESSION is not None:
        _SESSION.mark_dirty()


def _timer_tick():
    if _SESSION is None or not _SESSION.consumers:
        return None  # unregister the timer
    _SESSION.tick()
    return _TICK_INTERVAL


def _install_handlers() -> None:
    handlers = bpy.app.handlers.depsgraph_update_post
    if _on_depsgraph_update_post not in handlers:
        handlers.append(_on_depsgraph_update_post)
    if not bpy.app.timers.is_registered(_timer_tick):
        bpy.app.timers.register(_timer_tick, first_interval=_TICK_INTERVAL, persistent=True)


def _remove_handlers() -> None:
    handlers = bpy.app.handlers.depsgraph_update_post
    if _on_depsgraph_update_post in handlers:
        try:
            handlers.remove(_on_depsgraph_update_post)
        except ValueError:
            pass
    if bpy.app.timers.is_registered(_timer_tick):
        try:
            bpy.app.timers.unregister(_timer_tick)
        except Exception:
            pass


def _session_root() -> Path:
    return Path.home() / "Library" / "Caches" / CACHE_NAMESPACE / "live"


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def shutdown() -> None:
    """Tear down the live loop (called on add-on unregister / file load)."""
    global _SESSION
    if _SESSION is not None:
        _SESSION.shutdown()
    else:
        _remove_handlers()


@persistent
def _on_load_post(*_args) -> None:
    # A new .blend was loaded; stop any live loop tied to the old scene.
    shutdown()


def register_load_handler() -> None:
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister_load_handler() -> None:
    if _on_load_post in bpy.app.handlers.load_post:
        try:
            bpy.app.handlers.load_post.remove(_on_load_post)
        except ValueError:
            pass
