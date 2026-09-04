"""A refusal's remedy must be one that works.

The validator refuses Principled controls the selected surface cannot carry
and names an alternative profile. Two of those alternatives were measured
wrong. OpenPBR on RealityKit is not its own shading model: Reality Composer
Pro expands it into PBR Surface 2 and discards sheen, anisotropy and coat
colour on the way - the editor greys those inputs out on the node. So "select
OpenPBR 1.1" for Coat Tint or Sheen Roughness sent an artist to a profile
that drops exactly the control they were trying to keep, and "PBR Surface 2
or OpenPBR 1.1" offered a strictly worse second option for everything else.

The guidance is tested on synthetic nodes. The fact it rests on is tested
against Apple's shipped expansion, so a platform change that starts wiring
those inputs through fails here rather than going unnoticed.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Plugin.nodes imports bpy at module level. Seed the stub the sibling tests
# use, so this file collects on its own and not only behind one that already
# did - which is how it first passed while being unable to run alone.
_bpy_stub = sys.modules.setdefault("bpy", types.ModuleType("bpy"))
if not hasattr(_bpy_stub, "types"):
    _bpy_stub.types = types.SimpleNamespace(NodeTree=object)

from Plugin.nodes import validate  # noqa: E402
from scripts import check_shader_implementations as checker  # noqa: E402

# Blender 5.2 Principled defaults, read from the live node RNA. A stub at these
# values raises no issue at all, so every issue below is caused by one override.
_NEUTRAL = {
    "Base Color": (0.8, 0.8, 0.8, 1.0),
    "Metallic": 0.0,
    "Roughness": 0.5,
    "IOR": 1.5,
    "Alpha": 1.0,
    "Thin Wall": False,
    "Normal": (0.0, 0.0, 0.0),
    "Weight": 0.0,
    "Diffuse Roughness": 0.0,
    "Subsurface Weight": 0.0,
    "Subsurface Radius": (1.0, 0.2, 0.1),
    "Subsurface Scale": 0.005,
    "Subsurface IOR": 1.4,
    "Subsurface Anisotropy": 0.0,
    "Specular IOR Level": 0.5,
    "Specular Tint": (1.0, 1.0, 1.0, 1.0),
    "Anisotropic": 0.0,
    "Anisotropic Rotation": 0.0,
    "Tangent": (0.0, 0.0, 0.0),
    "Transmission Weight": 0.0,
    "Coat Weight": 0.0,
    "Coat Roughness": 0.03,
    "Coat IOR": 1.5,
    "Coat Tint": (1.0, 1.0, 1.0, 1.0),
    "Coat Normal": (0.0, 0.0, 0.0),
    "Sheen Weight": 0.0,
    "Sheen Roughness": 0.5,
    "Sheen Tint": (1.0, 1.0, 1.0, 1.0),
    "Emission Color": (1.0, 1.0, 1.0, 1.0),
    "Emission Strength": 0.0,
    "Thin Film Thickness": 0.0,
    "Thin Film IOR": 1.33,
}


def _principled(**overrides):
    inputs = {
        name: SimpleNamespace(default_value=overrides.get(name, value), is_linked=False)
        for name, value in _NEUTRAL.items()
    }
    return SimpleNamespace(inputs=inputs)


def _issues(profile: str, **overrides) -> list[str]:
    return validate._unsupported_principled_inputs(
        _principled(**overrides), surface_profile=profile
    )


def test_a_neutral_node_raises_nothing_under_any_profile():
    for profile in ("realitykit_portable", "realitykit_pbr2", "openpbr_1_1"):
        assert _issues(profile) == [], profile


# ---------------------------------------------------------------------------
# Controls no RealityKit surface delivers: the only honest remedy is bake
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profile", ["realitykit_portable", "realitykit_pbr2"])
def test_coat_tint_is_never_sent_to_openpbr(profile):
    """No surface carries a coat tint; OpenPBR declares one RCP discards."""
    (issue,) = [
        i for i in _issues(profile, **{"Coat Weight": 1.0, "Coat Tint": (1.0, 0.2, 0.2, 1.0)})
        if "Coat Tint" in i
    ]
    assert "OpenPBR" not in issue or "discards" in issue
    assert "select OpenPBR" not in issue
    assert "bake" in issue


@pytest.mark.parametrize("profile", ["realitykit_portable", "realitykit_pbr2"])
def test_sheen_roughness_is_never_sent_to_openpbr(profile):
    """PBR Surface 2 has no sheen roughness; OpenPBR's fuzz roughness is dropped."""
    (issue,) = [
        i for i in _issues(profile, **{"Sheen Weight": 1.0, "Sheen Roughness": 0.9})
        if "Sheen Roughness" in i
    ]
    assert "select OpenPBR" not in issue
    assert "bake" in issue


# ---------------------------------------------------------------------------
# Controls PBR Surface 2 delivers: name it, and only it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"IOR": 1.33},
        {"Diffuse Roughness": 0.5},
        {"Subsurface Weight": 0.5},
        {"Coat Weight": 1.0, "Coat IOR": 1.7},
        {"Sheen Weight": 0.5},
        {"Sheen Weight": 0.5, "Sheen Tint": (1.0, 0.5, 0.5, 1.0)},
    ],
)
def test_portable_refusals_recommend_pbr_surface_2_alone(overrides):
    """OpenPBR delivers at most what PBR Surface 2 does; offering it is noise."""
    named = next(iter(overrides)) if len(overrides) == 1 else list(overrides)[-1]
    issues = [i for i in _issues("realitykit_portable", **overrides) if f"'{named}'" in i]
    assert issues, f"expected a refusal naming {named!r}"
    for issue in issues:
        assert "RealityKit PBR Surface 2" in issue
        assert "OpenPBR" not in issue


def test_specular_tint_guidance_is_unchanged():
    """A value-policy refusal, correct before and after; pinned so it stays."""
    issues = [
        i for i in _issues("realitykit_portable", **{"Specular Tint": (1.8, 0.4, 0.4, 1.0)})
        if "Specular Tint" in i
    ]
    assert issues
    for issue in issues:
        assert "bake" in issue
        assert "OpenPBR" not in issue


# ---------------------------------------------------------------------------
# The fact the guidance rests on, from Apple's shipped expansion
# ---------------------------------------------------------------------------

_OPENPBR_OVERRIDES = Path(
    checker._MATERIALX_XML, "Apple", "apple_nodedefs_overrides", "apple_open_pbr_overrides.mtlx"
)


@pytest.mark.skipif(
    not _OPENPBR_OVERRIDES.is_file(),
    reason="Reality Composer Pro's OpenPBR expansion is not installed here",
)
def test_apples_openpbr_expansion_really_drops_what_the_guidance_says():
    """Read the terminal PBR Surface 2 node of the realitykit-target nodegraph.

    Everything the guidance refuses to route through OpenPBR must be absent
    from that node's inputs, and everything it routes to PBR Surface 2 must be
    present. Asserting against the shipped file rather than our own table is
    the point: if Apple starts wiring fuzz through, this fails and the guidance
    is revisited.
    """
    text = _OPENPBR_OVERRIDES.read_text(encoding="utf-8", errors="replace")
    graph = re.search(
        r'<nodegraph name="NG_open_pbr_surface_surfaceshader_apple"[^>]*>.*?</nodegraph>',
        text,
        re.S,
    )
    assert graph, "the realitykit-target expansion has moved or been renamed"
    terminal = re.search(
        r'<realitykit_pbr_surfaceshader name="[^"]+"[^>]*>(.*?)</realitykit_pbr_surfaceshader>',
        graph.group(0),
        re.S,
    )
    assert terminal, "the expansion no longer terminates in a RealityKit PBR surface"
    received = set(re.findall(r'<input name="([^"]+)"', terminal.group(1)))
    wired_interfaces = set(re.findall(r'interfacename="([^"]+)"', terminal.group(1)))

    # Dropped: the guidance says bake, and here is why.
    assert "sheenColor" not in received
    assert "fuzz_weight" not in wired_interfaces
    assert "fuzz_roughness" not in wired_interfaces
    assert "coat_color" not in wired_interfaces
    assert "specularAnisotropyLevel" not in received

    # Delivered: the guidance says PBR Surface 2, and these reach it.
    for delivered in ("specularIOR", "subsurfaceWeight", "clearcoatIOR", "baseDiffuseRoughness"):
        assert delivered in received, delivered
