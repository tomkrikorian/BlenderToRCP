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


class _KeyframeStrip:
    type = "KEYFRAME"

    def __init__(self, slot, paths):
        self._slot = slot
        self._bag = types.SimpleNamespace(fcurves=[_fcurve(path) for path in paths])

    def channelbag(self, slot):
        return self._bag if slot is self._slot else None


def _layered_action(slot, paths):
    strip = _KeyframeStrip(slot, paths)
    layer = types.SimpleNamespace(strips=[strip])
    return types.SimpleNamespace(layers=[layer])


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
    action_slot = object()
    action = (
        _layered_action(action_slot, action_fcurves)
        if action_fcurves is not None
        else None
    )
    tracks = []
    for paths in nla_actions or []:
        strip_slot = object()
        strip = types.SimpleNamespace(
            action=_layered_action(strip_slot, paths),
            action_slot=strip_slot,
        )
        tracks.append(types.SimpleNamespace(strips=[strip]))
    return types.SimpleNamespace(
        action=action,
        action_slot=action_slot,
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


def test_transform_curve_in_another_action_slot_is_ignored():
    active_slot = object()
    other_slot = object()
    active_strip = _KeyframeStrip(active_slot, ['["custom"]'])
    other_strip = _KeyframeStrip(other_slot, ["location"])

    class _MultiSlotStrip:
        type = "KEYFRAME"

        def channelbag(self, slot):
            if slot is active_slot:
                return active_strip._bag
            if slot is other_slot:
                return other_strip._bag
            return None

    action = types.SimpleNamespace(
        layers=[types.SimpleNamespace(strips=[_MultiSlotStrip()])]
    )
    anim = types.SimpleNamespace(
        action=action,
        action_slot=active_slot,
        drivers=[],
        nla_tracks=[],
    )
    assert _yup_unsafe_reason(_obj(animation_data=anim)) is None


def test_slotless_layered_action_is_conservatively_unsafe():
    action = _layered_action(object(), ['["custom"]'])
    anim = types.SimpleNamespace(
        action=action,
        action_slot=None,
        drivers=[],
        nla_tracks=[],
    )
    assert _yup_unsafe_reason(_obj(animation_data=anim)) == "animated transform"


def test_loose_owned_action_slot_transform_is_unsafe(monkeypatch):
    """Animation export schedules owner-backed slots even when not active/NLA."""
    owner = _obj(animation_data=_anim())

    class _OwnedSlot:
        def users(self):
            return [owner]

    slot = _OwnedSlot()
    action = _layered_action(slot, ["rotation_quaternion"])
    action.slots = [slot]
    monkeypatch.setattr(
        sys.modules["bpy"],
        "data",
        types.SimpleNamespace(actions=[action]),
        raising=False,
    )

    assert _yup_unsafe_reason(owner) == "animated transform"


def test_uninspectable_loose_action_slot_is_conservatively_unsafe(monkeypatch):
    owner = _obj(animation_data=_anim())

    class _BrokenSlot:
        def users(self):
            raise RuntimeError("RNA lookup failed")

    slot = _BrokenSlot()
    action = _layered_action(slot, ['["custom"]'])
    action.slots = [slot]
    monkeypatch.setattr(
        sys.modules["bpy"],
        "data",
        types.SimpleNamespace(actions=[action]),
        raising=False,
    )

    assert _yup_unsafe_reason(owner) == "animated transform"
