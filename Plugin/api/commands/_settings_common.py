"""Shared helpers for settings commands."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


# BlenderToRCP 2.0 deliberately targets the current RealityKit / Reality
# Composer Pro generation.  Keep the baseline in one import-safe module so the
# Blender UI, CLI schema tests, and diagnostics all describe the same contract.
#
# Raw Blender cameras, lights, World dome lights, curves, point clouds,
# volumes, and hair are intentionally not settings in the 2.x contract:
# RealityKit's cross-platform renderer profile cannot consume those ordinary
# USD schemas, so accepting an opt-in would only produce a nonportable asset.
REALITYKIT_OS27_PROFILE_NAME = "REALITYKIT_OS27"
MATERIALX_SURFACE_PROFILE_DEFAULT = "realitykit_portable"
MATERIALX_SURFACE_PROFILES = (
    MATERIALX_SURFACE_PROFILE_DEFAULT,
    "realitykit_pbr2",
    "openpbr_1_1",
)
REALITYKIT_OS27_DEFAULTS: dict[str, Any] = {
    "convert_orientation": True,
    "forward_axis": "-Z",
    "up_axis": "Y",
    "convert_scene_units": "METERS",
    "meters_per_unit": 1.0,
    "export_meshes": True,
    "materialx_surface_profile": MATERIALX_SURFACE_PROFILE_DEFAULT,
}

REALITYKIT_OS27_ADVANCED_CONTENT_KEYS = frozenset()

# Keys that are internal bookkeeping and should not be exposed via the CLI
INTERNAL_KEYS = frozenset({
    "rna_type",
    "name",
    "history_applied",
    "last_diagnostics_path",
    "persist_suspended",
    "background_job_dir",
    "background_job_pid",
    "force_unlit_materials",
})

# CLI boolean values are intentionally closed sets.  Keeping the accepted
# spellings here makes the command contract inspectable and prevents a typo
# such as ``flase`` from silently disabling an export option.
BOOLEAN_TRUE_TOKENS = ("true", "1", "yes")
BOOLEAN_FALSE_TOKENS = ("false", "0", "no")
_BOOLEAN_TRUE_TOKEN_SET = frozenset(BOOLEAN_TRUE_TOKENS)
_BOOLEAN_FALSE_TOKEN_SET = frozenset(BOOLEAN_FALSE_TOKENS)
_UNSET = object()

SETTING_GROUPS: dict[str, set[str]] = {
    "general": {
        "filepath",
        "export_format",
        "root_prim_name",
        "export_animation",
        "author_animation_library",
        "selected_objects_only",
        "export_custom_properties",
        "custom_properties_namespace",
        "author_blender_name",
        "allow_unicode",
        "relative_paths",
        "convert_orientation",
        "forward_axis",
        "up_axis",
        "convert_scene_units",
        "meters_per_unit",
        "xform_op_mode",
        "evaluation_mode",
        "use_instancing",
    },
    "objects": {
        "export_meshes",
    },
    "geometry": {
        "export_uvmaps",
        "rename_uvmaps",
        "export_normals",
        "merge_parent_xform",
        "triangulate_meshes",
        "quad_method",
        "ngon_method",
        "export_subdivision",
    },
    "rigging": {
        "export_armatures",
        "only_deform_bones",
        "export_shapekeys",
    },
    "texture": {
        "export_texture_settings_enabled",
        "bake_resolution",
        "bake_resolution_custom",
        "bake_image_format",
        "bake_margin",
    },
    "materials": {
        "materialx_surface_profile",
    },
    "bake": {
        "bake_mode",
        "bake_ibl_source",
        "bake_ibl_filepath",
        "bake_ibl_strength",
        "bake_ibl_rotation",
        "bake_isolate_meshes_lit",
        "bake_base_color",
        "bake_opacity",
        "bake_keep_materials",
        "bake_step_timeout_seconds",
        "bake_roughness_mode",
        "apply_yup_geometry",
    },
    "diagnostics": {
        "diagnostics_enabled",
    },
}


def get_settings():
    """Return the scene export settings PropertyGroup instance."""
    import bpy

    settings = getattr(bpy.context.scene, "blender_to_rcp_export_settings", None)
    if settings is None:
        raise RuntimeError("BlenderToRCP addon not loaded — export settings unavailable.")
    return settings


@contextmanager
def suspend_setting_persistence(settings):
    """Keep command-local RNA writes out of the user's saved preferences.

    Export and bake-export run in a short-lived Blender worker and apply CLI
    arguments to the scene PropertyGroup for that invocation only.  Those RNA
    properties share the UI's persistence callback, however, so assigning the
    first command override in a pristine scene can make the profile migrator
    interpret that just-authored value as legacy state and reset it to the
    default.  It can also leak one-off CLI paths or formats into UI history.

    Hold the PropertyGroup's existing persistence guard for the complete
    command and restore its prior state on every success or failure path.
    """
    try:
        previous = bool(getattr(settings, "persist_suspended"))
        settings.persist_suspended = True
    except Exception:
        # Non-Blender test doubles do not necessarily expose the internal
        # guard.  They also have no RNA update callback to suppress.
        previous = None

    try:
        yield settings
    finally:
        if previous is not None:
            settings.persist_suspended = previous


@dataclass(frozen=True)
class PreparedSettingUpdate:
    """One fully coerced setting write, staged without mutating Blender RNA."""

    key: str
    value: Any
    input_key: str
    input_value: Any
    source: str = "override"


def setting_value_issue(
    key: str,
    value: Any,
    reason: str | Exception,
    *,
    setting_key: str | None = None,
) -> dict[str, Any]:
    """Build the stable structured detail shared by CLI setting errors."""
    detail: dict[str, Any] = {
        "key": str(key),
        "value": value,
        "reason": str(reason),
    }
    if setting_key is not None and setting_key != key:
        detail["setting"] = str(setting_key)
    return detail


def prepare_setting_update(
    prop,
    value: Any,
    *,
    key: str | None = None,
    input_key: str | None = None,
    input_value: Any = _UNSET,
    source: str = "override",
) -> PreparedSettingUpdate:
    """Coerce one update without assigning it to the live PropertyGroup."""
    setting_key = str(key or prop.identifier)
    return PreparedSettingUpdate(
        key=setting_key,
        value=coerce_value(prop, value),
        input_key=str(input_key or setting_key),
        input_value=value if input_value is _UNSET else input_value,
        source=source,
    )


def apply_setting_updates_transactionally(
    settings,
    updates: list[PreparedSettingUpdate],
) -> list[dict[str, Any]]:
    """Apply staged RNA writes atomically from the caller's perspective.

    Every input must already be coerced before this function is called.  RNA
    update callbacks can still reject an otherwise well-typed assignment, so
    all requested writes are attempted to aggregate those failures.  If any
    write fails, every touched property is restored to its original value.
    The returned details identify the original CLI key/value rather than an
    implementation-only PropertyGroup name.
    """
    if not updates:
        return []

    originals: dict[str, Any] = {}
    read_errors: list[dict[str, Any]] = []
    for update in updates:
        if update.key in originals:
            continue
        try:
            originals[update.key] = getattr(settings, update.key)
        except Exception as exc:
            detail = setting_value_issue(
                update.input_key,
                update.input_value,
                f"could not read current setting value: {exc}",
                setting_key=update.key,
            )
            detail["source"] = update.source
            read_errors.append(detail)
    if read_errors:
        return read_errors

    assignment_errors: list[dict[str, Any]] = []
    for update in updates:
        try:
            setattr(settings, update.key, update.value)
        except Exception as exc:
            detail = setting_value_issue(
                update.input_key,
                update.input_value,
                f"could not apply setting: {exc}",
                setting_key=update.key,
            )
            detail["source"] = update.source
            assignment_errors.append(detail)

    if not assignment_errors:
        return []

    rollback_errors: dict[str, str] = {}
    for key, original in reversed(list(originals.items())):
        try:
            setattr(settings, key, original)
        except Exception as exc:
            rollback_errors[key] = str(exc)

    if rollback_errors:
        assignment_errors.append({
            "key": "<transaction>",
            "value": None,
            "reason": "could not restore one or more settings after a failed assignment",
            "rollback_errors": rollback_errors,
            "source": "transaction",
        })
    return assignment_errors


def coerce_value(prop, value):
    """Coerce a CLI string/JSON value to the correct Python type for a Blender property."""
    if prop.type == "BOOLEAN":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            token = value.strip().casefold()
            if token in _BOOLEAN_TRUE_TOKEN_SET:
                return True
            if token in _BOOLEAN_FALSE_TOKEN_SET:
                return False
        elif isinstance(value, int) and value in (0, 1):
            return bool(value)
        raise ValueError(
            f"Invalid boolean value '{value}' for '{prop.identifier}'. "
            f"Allowed true tokens: {list(BOOLEAN_TRUE_TOKENS)}; "
            f"allowed false tokens: {list(BOOLEAN_FALSE_TOKENS)}"
        )

    if prop.type == "INT":
        coerced = int(value)
        _validate_numeric_range(prop, coerced)
        return coerced

    if prop.type == "FLOAT":
        coerced = float(value)
        _validate_numeric_range(prop, coerced)
        return coerced

    if prop.type == "ENUM":
        requested = str(value)
        valid = {item.identifier for item in prop.enum_items}
        if requested in valid:
            return requested

        # Preserve each property's canonical identifier casing.  Most Blender
        # enums use uppercase identifiers, while the MaterialX surface-profile
        # contract intentionally uses the lowercase values consumed by the
        # material authoring layer.
        casefolded = {identifier.casefold(): identifier for identifier in valid}
        canonical = casefolded.get(requested.casefold())
        if canonical is None:
            raise ValueError(
                f"Invalid value '{value}' for '{prop.identifier}'. "
                f"Allowed: {sorted(valid)}"
            )
        return canonical

    if prop.type == "STRING":
        return str(value)

    return value


def _validate_numeric_range(prop, value: int | float) -> None:
    """Reject values Blender RNA would otherwise clamp without reporting."""
    try:
        minimum = prop.hard_min
    except Exception:
        minimum = None
    try:
        maximum = prop.hard_max
    except Exception:
        maximum = None

    if minimum is not None and value < minimum:
        raise ValueError(
            f"Invalid value '{value}' for '{prop.identifier}': minimum is {minimum}"
        )
    if maximum is not None and value > maximum:
        raise ValueError(
            f"Invalid value '{value}' for '{prop.identifier}': maximum is {maximum}"
        )


def realitykit_os27_profile_deviations(settings) -> dict[str, dict[str, Any]]:
    """Return settings that differ from the strict RealityKit OS 27 baseline.

    Deviations are informational: the advanced raw-USD switches remain valid
    explicit opt-ins.  Including this data in diagnostics makes it clear when
    an issue was reproduced with the strict profile versus a custom pipeline.
    """
    deviations: dict[str, dict[str, Any]] = {}
    for key, expected in REALITYKIT_OS27_DEFAULTS.items():
        try:
            actual = getattr(settings, key)
        except Exception:
            continue
        if actual != expected:
            deviations[key] = {"expected": expected, "actual": actual}
    return deviations
