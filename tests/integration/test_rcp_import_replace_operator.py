"""Integration test — the sidebar Export operator honours Replace Existing .import.

The CLI and the Blender sidebar reach the RCP_IMPORT lane through different
code, so the sidebar's ``rcp_import_replace`` checkbox is exercised here through
the real ``bpy.ops.blendertorcp.export`` operator rather than through the API
command.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKER = "RCP_IMPORT_REPLACE_RESULT:"

DRIVER = '''
import hashlib, json, sys
from pathlib import Path

sys.path.insert(0, {repo_root!r})

import bpy
from Plugin.api.addon_loader import ensure_addon_loaded

MARKER = {marker!r}
DESTINATION = Path({destination!r})


def fingerprint(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=2)
    cube = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode='OBJECT')
    material = bpy.data.materials.new("Flat")
    material.use_nodes = True
    cube.data.materials.append(material)

    ensure_addon_loaded()
    from Plugin import prefs as addon_prefs

    settings = bpy.context.scene.blender_to_rcp_export_settings
    # A pristine scene is unstamped, so the first RNA update would otherwise
    # migrate the whole payload back to defaults (see bake_export_runner).
    addon_prefs.ensure_current_export_settings_scene_profile(settings)
    settings.export_format = 'RCP_IMPORT'
    settings.filepath = str(DESTINATION)

    result = {{}}
    result["first"] = list(bpy.ops.blendertorcp.export())
    result["first_exists"] = DESTINATION.is_dir()
    result["first_fingerprint"] = fingerprint(DESTINATION) if DESTINATION.is_dir() else None

    # Without the checkbox the refusal stands and nothing is touched. Blender
    # re-raises an operator that reported an ERROR, so catch it here.
    try:
        result["refused"] = list(bpy.ops.blendertorcp.export())
    except RuntimeError as exc:
        result["refused"] = ["CANCELLED"]
        result["refusal_message"] = str(exc)
    result["after_refusal_fingerprint"] = fingerprint(DESTINATION)

    settings.rcp_import_replace = True
    result["replaced"] = list(bpy.ops.blendertorcp.export())
    result["after_replace_fingerprint"] = fingerprint(DESTINATION)
    result["leftovers"] = sorted(
        entry.name
        for entry in DESTINATION.parent.iterdir()
        if entry.name.startswith(".blendertorcp-import-")
    )

    print(MARKER + json.dumps(result))


main()
'''


def _blender() -> str:
    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


def test_sidebar_export_operator_honours_replace_setting(tmp_path):
    destination = tmp_path / "Sidebar.import"
    script = tmp_path / "driver.py"
    script.write_text(
        DRIVER.format(
            repo_root=str(REPO_ROOT),
            marker=MARKER,
            destination=str(destination),
        )
    )

    proc = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script)],
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    payload = None
    for line in proc.stdout.splitlines():
        if line.startswith(MARKER):
            payload = json.loads(line[len(MARKER):])
    assert payload is not None, proc.stdout + proc.stderr

    assert payload["first"] == ["FINISHED"]
    assert payload["first_exists"] is True
    # The default refusal is unchanged, and it changes nothing on disk.
    assert payload["refused"] == ["CANCELLED"]
    assert "Refusing to overwrite existing .import directory" in payload[
        "refusal_message"
    ]
    assert payload["after_refusal_fingerprint"] == payload["first_fingerprint"]
    # The checkbox refreshes the package, deterministically.
    assert payload["replaced"] == ["FINISHED"]
    assert payload["after_replace_fingerprint"] == payload["first_fingerprint"]
    assert payload["leftovers"] == []
