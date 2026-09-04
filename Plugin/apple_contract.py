"""Non-configurable RealityKit and Reality Composer Pro spatial contract."""

from __future__ import annotations


REALITYKIT_FORWARD_AXIS = "-Z"
REALITYKIT_USD_EXPORT_FORWARD_AXIS = "NEGATIVE_Z"
REALITYKIT_UP_AXIS = "Y"
REALITYKIT_SCENE_UNITS = "METERS"
REALITYKIT_METERS_PER_UNIT = 1.0

# The MaterialX surface a new scene exports through. RealityKit PBR Surface 2
# is the 30-input surface, the richest RealityKit has, implemented in Metal
# and verified by import into Reality Composer Pro 3 - it arrives as a native
# "PBR Surface 2 (RealityKit)" node and renders. The 13-input portable surface
# it replaces refuses IOR, specular tint, subsurface, sheen, anisotropy and
# coat IOR; it stays selectable for pipelines pinned to it. Every ``or
# <profile>`` fallback and signature default reads this name, so a caller
# passing nothing gets the same surface the panel does.
MATERIALX_SURFACE_PROFILE_DEFAULT = "realitykit_pbr2"
