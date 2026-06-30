"""Unit tests for Mix/MixRGB node classification in material extraction.

Guards the regression where a MULTIPLY mix (e.g. diffuse x AO) was treated as a
plain mix and collapsed to input B (the AO map) at Factor 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Plugin.export.materials.extract.core import (
    _is_identity_mix,
    _is_supported_mix,
    _mix_node_params,
)


class FakeSocket:
    def __init__(self, *, is_linked=False, default_value=0.0):
        self.is_linked = is_linked
        self.default_value = default_value


class FakeInputs(dict):
    def get(self, key, default=None):  # noqa: D401 - dict-like socket map
        return super().get(key, default)


class FakeMixNode:
    type = 'MIX'

    def __init__(self, *, blend_type, factor, a_linked, b_linked):
        self.blend_type = blend_type
        self.inputs = FakeInputs(
            Factor=FakeSocket(default_value=factor),
            A=FakeSocket(is_linked=a_linked),
            B=FakeSocket(is_linked=b_linked),
        )


def _mix(blend_type, factor, a_linked=True, b_linked=True):
    return FakeMixNode(blend_type=blend_type, factor=factor, a_linked=a_linked, b_linked=b_linked)


def test_params_reads_blend_factor_and_sockets():
    blend, fac, a, b = _mix_node_params(_mix('MULTIPLY', 1.0))
    assert blend == 'MULTIPLY'
    assert fac == 1.0
    assert a.is_linked and b.is_linked


def test_factor_zero_is_passthrough_for_every_blend():
    # out = lerp(A, op(A, B), 0) == A regardless of blend mode.
    for blend in ('MIX', 'MULTIPLY', 'ADD', 'SUBTRACT'):
        assert _is_identity_mix(_mix(blend, 0.0)), blend


def test_plain_mix_factor_one_is_passthrough_of_b():
    assert _is_identity_mix(_mix('MIX', 1.0))


def test_multiply_factor_one_is_not_a_passthrough():
    # The regression: MULTIPLY at Factor 1 is A*B, never just B.
    node = _mix('MULTIPLY', 1.0)
    assert not _is_identity_mix(node)
    # ...but it IS expressible as a real MaterialX multiply node, so no bake.
    assert _is_supported_mix(node)


def test_combining_blends_supported_only_when_both_inputs_linked():
    assert _is_supported_mix(_mix('MULTIPLY', 1.0, a_linked=True, b_linked=True))
    assert not _is_supported_mix(_mix('MULTIPLY', 1.0, a_linked=True, b_linked=False))
    assert _is_supported_mix(_mix('ADD', 0.5))
    assert _is_supported_mix(_mix('SUBTRACT', 0.5))


def test_unhandled_blend_is_not_supported():
    # Blends with no MaterialX op emitter still require baking.
    assert not _is_supported_mix(_mix('DODGE', 1.0))


def test_linked_factor_cannot_be_folded():
    node = _mix('MIX', 1.0)
    node.inputs['Factor'].is_linked = True
    _, fac, _, _ = _mix_node_params(node)
    assert fac is None
    assert not _is_supported_mix(node)
