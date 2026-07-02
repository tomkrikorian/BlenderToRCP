"""
Launch helper for the RCPPreview companion macOS app.

Tries LaunchServices by bundle id first (so the app is found wherever it is
installed), then falls back to the explicit `companion_app_path` add-on
preference. The app watches the session directory passed via `--session`, so
it only needs to be launched once per session; subsequent consumer changes are
communicated through `control.json`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import bpy

BUNDLE_ID = "com.studiomeije.blendertorcp.preview"


def launch_companion(session_dir, prefs=None) -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "The RealityKit / Spatial preview is macOS-only."

    args = ["--session", str(session_dir)]

    # 1) Try by bundle id (works once the app has been registered with
    #    LaunchServices, i.e. built/opened at least once).
    if _open(["-n", "-b", BUNDLE_ID, "--args", *args]):
        return True, f"Launched {BUNDLE_ID}"

    # 2) Fall back to an explicit app path from preferences.
    app_path = (getattr(prefs, "companion_app_path", "") or "").strip() if prefs else ""
    if app_path:
        resolved = bpy.path.abspath(app_path)
        if Path(resolved).exists():
            if _open(["-n", resolved, "--args", *args]):
                return True, f"Launched {resolved}"
            return False, f"Failed to launch companion app at {resolved}"
        return False, f"Companion app not found at {resolved}"

    return False, (
        "RCPPreview.app not found. Build the companion app (Companion/) or set "
        "'RealityKit Preview App' in the BlenderToRCP add-on preferences."
    )


def _open(open_args: list[str]) -> bool:
    try:
        subprocess.run(["open", *open_args], check=True, capture_output=True)
        return True
    except Exception:
        return False
