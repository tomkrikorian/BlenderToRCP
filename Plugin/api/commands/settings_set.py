"""settings_set command — modify export settings in a .blend file."""

from __future__ import annotations

from ._settings_common import (
    INTERNAL_KEYS,
    apply_setting_updates_transactionally,
    get_settings,
    prepare_setting_update,
    setting_value_issue,
)
from ..errors import CommandError


def handle(args: dict) -> dict:
    settings_dict = args.get("settings", {})
    save = args.get("save", False)
    dry_run = args.get("dry_run", False)

    if not settings_dict:
        raise ValueError("No settings provided. Pass 'settings': {'key': value, ...}")

    settings = get_settings()
    prop_defs = {prop.identifier: prop for prop in settings.bl_rna.properties}

    # Validate every key and value without touching the live PropertyGroup.
    to_apply = []
    invalid_keys = []
    invalid_values = []
    for key, value in settings_dict.items():
        if key in INTERNAL_KEYS:
            invalid_keys.append(
                setting_value_issue(key, value, "internal setting")
            )
            continue
        prop = prop_defs.get(key)
        if prop is None:
            invalid_keys.append(
                setting_value_issue(key, value, "unknown setting")
            )
            continue
        try:
            to_apply.append(
                prepare_setting_update(
                    prop,
                    value,
                    key=key,
                    source="settings_set",
                )
            )
        except Exception as exc:
            invalid_values.append(setting_value_issue(key, value, exc))

    if invalid_keys:
        raise CommandError(
            "Invalid setting key.",
            code="INVALID_SETTING_OVERRIDE",
            details=invalid_keys + invalid_values,
        )
    if invalid_values:
        raise CommandError(
            "Invalid setting value.",
            code="INVALID_SETTING_VALUE",
            details=invalid_values,
        )

    if dry_run:
        return {
            "valid": True,
            "would_update": [update.key for update in to_apply],
        }

    assignment_errors = apply_setting_updates_transactionally(settings, to_apply)
    if assignment_errors:
        raise CommandError(
            "Invalid setting value.",
            code="INVALID_SETTING_VALUE",
            details=assignment_errors,
        )
    updated = [update.key for update in to_apply]

    saved = False
    if save:
        import bpy
        if bpy.data.filepath:
            bpy.ops.wm.save_mainfile()
            saved = True

    return {"updated": updated, "saved": saved}
