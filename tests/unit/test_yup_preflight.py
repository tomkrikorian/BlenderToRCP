"""Unit tests for the Y-up geometry bake safety preflight.

The bake assigns ``matrix_world`` (and rotates mesh data), which only holds for
objects whose transform is authored by their loc/rot/scale channels. Transform
fcurves, drivers, NLA strips and enabled constraints all re-derive the
transform at depsgraph evaluation - overwriting the assignment while the mesh
stays rotated - and armature deformation bypasses the per-mesh conjugation.
``_yup_unsafe_reason`` must catch every one of those so
``maybe_apply_yup_geometry_bake`` can fall back to root orientation conversion.

``bake_finalize`` imports ``bpy`` at module load, so a stub is injected first.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules.setdefault("bpy", types.ModuleType("bpy"))

from Plugin.export.bake_finalize import _yup_unsafe_reason  # noqa: E402


def _fcurve(data_path):
    return types.SimpleNamespace(data_path=data_path)


def _obj(**overrides):
    base = dict(
        name="Obj",
        type='MESH',
        animation_data=None,
        constraints=[],
        modifiers=[],
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _anim(action_fcurves=None, drivers=None, nla_actions=None):
    action = (
        types.SimpleNamespace(fcurves=[_fcurve(p) for p in action_fcurves])
        if action_fcurves is not None
        else None
    )
    tracks = []
    for paths in nla_actions or []:
        strip = types.SimpleNamespace(
            action=types.SimpleNamespace(fcurves=[_fcurve(p) for p in paths])
        )
        tracks.append(types.SimpleNamespace(strips=[strip]))
    return types.SimpleNamespace(
        action=action,
        drivers=[_fcurve(p) for p in (drivers or [])],
        nla_tracks=tracks,
    )


def test_static_object_is_safe():
    assert _yup_unsafe_reason(_obj()) is None


def test_keyframed_transform_is_unsafe():
    obj = _obj(animation_data=_anim(action_fcurves=["location"]))
    assert _yup_unsafe_reason(obj) == "animated transform"


def test_non_transform_animation_is_safe():
    # Animating e.g. a custom property or material value doesn't touch the
    # object transform, so the bake still holds.
    obj = _obj(animation_data=_anim(action_fcurves=['["my_prop"]', "hide_viewport"]))
    assert _yup_unsafe_reason(obj) is None


def test_transform_driver_is_unsafe():
    obj = _obj(animation_data=_anim(drivers=["rotation_euler"]))
    assert _yup_unsafe_reason(obj) == "driver-driven transform"


def test_nla_transform_strip_is_unsafe():
    obj = _obj(animation_data=_anim(nla_actions=[["scale"]]))
    assert _yup_unsafe_reason(obj) == "NLA-animated transform"


def test_enabled_constraint_is_unsafe():
    obj = _obj(constraints=[types.SimpleNamespace(mute=False)])
    assert _yup_unsafe_reason(obj) == "constrained transform"


def test_muted_constraint_is_safe():
    obj = _obj(constraints=[types.SimpleNamespace(mute=True)])
    assert _yup_unsafe_reason(obj) is None


def test_armature_deformed_mesh_is_unsafe():
    obj = _obj(modifiers=[types.SimpleNamespace(type='ARMATURE')])
    assert _yup_unsafe_reason(obj) == "armature-deformed"


def test_armature_modifier_on_non_mesh_ignored():
    # Only meshes carry deformation the bake would corrupt.
    obj = _obj(type='EMPTY', modifiers=[])
    assert _yup_unsafe_reason(obj) is None


def test_delta_transform_animation_is_unsafe():
    obj = _obj(animation_data=_anim(action_fcurves=["delta_location"]))
    assert _yup_unsafe_reason(obj) == "animated transform"
