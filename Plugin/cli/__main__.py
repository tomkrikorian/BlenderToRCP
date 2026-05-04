#!/usr/bin/env python3
"""
BlenderToRCP CLI — command-line interface for the BlenderToRCP Blender plugin.

Usage::

    python3 <Plugin-path> <command> [options]
    blendertorcp <command> [options]

All commands output JSON to stdout and status messages to stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import bridge


def _print_json(data, pretty: bool = True) -> None:
    """Print JSON to stdout."""
    if pretty:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(json.dumps(data, default=str))


def _log(msg: str, quiet: bool = False) -> None:
    """Print status message to stderr."""
    if not quiet:
        print(msg, file=sys.stderr)


def _run(command: str, args: dict, parsed: argparse.Namespace) -> dict:
    """Run a command through the bridge with common options."""
    return bridge.run(
        command=command,
        args=args,
        blend_file=getattr(parsed, "blend_file", None),
        blender_path=parsed.blender,
        timeout=getattr(parsed, "timeout", 600),
        verbose=parsed.verbose,
    )


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_version(parsed: argparse.Namespace) -> int:
    result = _run("version", {}, parsed)
    _print_json(result)
    return 0


def cmd_info(parsed: argparse.Namespace) -> int:
    result = _run("info", {}, parsed)
    _print_json(result)
    return 0


def cmd_list_objects(parsed: argparse.Namespace) -> int:
    args = {}
    if parsed.type:
        args["type"] = parsed.type
    if parsed.selected:
        args["selected"] = True
    result = _run("list_objects", args, parsed)
    _print_json(result)
    return 0


def cmd_list_materials(parsed: argparse.Namespace) -> int:
    args = {}
    if parsed.unused:
        args["unused"] = True
    result = _run("list_materials", args, parsed)
    _print_json(result)
    return 0


def cmd_validate(parsed: argparse.Namespace) -> int:
    args = {}
    if parsed.material:
        args["material"] = parsed.material
    if parsed.strict:
        args["strict"] = True
    if parsed.only_errors:
        args["only_errors"] = True
    result = _run("validate", args, parsed)
    _print_json(result)
    return 0 if result.get("ok") else 1


def cmd_settings_get(parsed: argparse.Namespace) -> int:
    args = {}
    if parsed.keys:
        args["keys"] = parsed.keys
    if parsed.group:
        args["group"] = parsed.group
    result = _run("settings_get", args, parsed)
    _print_json(result)
    return 0


def cmd_settings_set(parsed: argparse.Namespace) -> int:
    # Parse key=value pairs
    settings = {}
    for pair in parsed.settings:
        if "=" not in pair:
            print(f"Invalid setting format: '{pair}'. Expected key=value.", file=sys.stderr)
            return 1
        key, value = pair.split("=", 1)
        settings[key.strip()] = value.strip()
    args = {"settings": settings}
    if parsed.save:
        args["save"] = True
    if parsed.dry_run:
        args["dry_run"] = True
    result = _run("settings_set", args, parsed)
    _print_json(result)
    return 0


def cmd_settings_list(parsed: argparse.Namespace) -> int:
    # settings list needs blender but no specific .blend file
    # We pass a dummy blend_file=None, the runner handles it
    result = _run("settings_list", {}, parsed)
    _print_json(result)
    return 0


def cmd_export(parsed: argparse.Namespace) -> int:
    args = {"filepath": parsed.output}
    if parsed.format:
        args["format"] = parsed.format
    if parsed.selected_only:
        args["selected_only"] = True
    if parsed.no_diagnostics:
        args["no_diagnostics"] = True

    # Collect --key=value overrides
    overrides = {}
    for override in (parsed.overrides or []):
        if "=" not in override:
            continue
        key, value = override.split("=", 1)
        # Convert hyphens to underscores
        key = key.lstrip("-").replace("-", "_")
        overrides[key] = value
    if overrides:
        args["overrides"] = overrides

    _log(f"Exporting to {parsed.output}...", parsed.quiet)
    result = _run("export", args, parsed)
    _print_json(result)
    _log(f"Done in {result.get('duration_seconds', '?')}s", parsed.quiet)
    return 0


def cmd_bake_export(parsed: argparse.Namespace) -> int:
    args = {"filepath": parsed.output}

    if parsed.format:
        args["format"] = parsed.format
    if parsed.bake_mode:
        args["bake_mode"] = parsed.bake_mode
    if parsed.resolution:
        args["resolution"] = parsed.resolution
    if parsed.image_format:
        args["image_format"] = parsed.image_format
    if parsed.margin is not None:
        args["margin"] = parsed.margin
    if parsed.selected_only:
        args["selected_only"] = True
    if parsed.no_diagnostics:
        args["no_diagnostics"] = True
    if parsed.ibl_source:
        args["ibl_source"] = parsed.ibl_source
    if parsed.ibl_filepath:
        args["ibl_filepath"] = parsed.ibl_filepath
    if parsed.ibl_strength is not None:
        args["ibl_strength"] = parsed.ibl_strength
    if parsed.ibl_rotation is not None:
        args["ibl_rotation"] = parsed.ibl_rotation
    if parsed.isolate_meshes:
        args["isolate_meshes"] = True
    if parsed.no_base_color:
        args["no_base_color"] = True
    if parsed.no_opacity:
        args["no_opacity"] = True
    if parsed.keep_materials:
        args["keep_materials"] = True
    if parsed.timeout_step is not None:
        args["timeout"] = parsed.timeout_step

    # Collect extra overrides
    overrides = {}
    for override in (parsed.overrides or []):
        if "=" not in override:
            continue
        key, value = override.split("=", 1)
        key = key.lstrip("-").replace("-", "_")
        overrides[key] = value
    if overrides:
        args["overrides"] = overrides

    _log(f"Baking & exporting to {parsed.output}...", parsed.quiet)
    result = _run("bake_export", args, parsed)
    _print_json(result)
    _log(f"Done in {result.get('duration_seconds', '?')}s", parsed.quiet)
    return 0


def cmd_support_bundle(parsed: argparse.Namespace) -> int:
    args = {
        "blend_file": parsed.blend_file,
    }
    if parsed.output:
        args["export_path"] = parsed.output
    if parsed.bundle_output:
        args["bundle_output"] = parsed.bundle_output
    if parsed.job_dir:
        args["job_dir"] = parsed.job_dir
    if parsed.diagnostics:
        args["diagnostics_path"] = parsed.diagnostics
    if parsed.include_output:
        args["include_output"] = True
    if parsed.include_blend:
        args["include_blend"] = True
    if parsed.full_log:
        args["full_log"] = True
    if parsed.no_redact:
        args["no_redact"] = True

    _log("Creating support bundle...", parsed.quiet)
    result = _run("support_bundle", args, parsed)
    _print_json(result)
    _log(f"Support bundle: {result.get('support_bundle_path', '?')}", parsed.quiet)
    return 0


def cmd_preferences_get(parsed: argparse.Namespace) -> int:
    result = _run("preferences_get", {}, parsed)
    _print_json(result)
    return 0


def cmd_preferences_set(parsed: argparse.Namespace) -> int:
    settings = {}
    for pair in parsed.settings:
        if "=" not in pair:
            print(f"Invalid format: '{pair}'. Expected key=value.", file=sys.stderr)
            return 1
        key, value = pair.split("=", 1)
        settings[key.strip()] = value.strip()
    result = _run("preferences_set", {"settings": settings}, parsed)
    _print_json(result)
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blendertorcp",
        description="BlenderToRCP CLI — export, bake, validate, and manage settings.",
    )

    # Global options
    parser.add_argument(
        "--blender", default=None,
        help="Path to Blender executable (default: $BLENDERTORCP_BLENDER or 'blender')",
    )
    parser.add_argument(
        "--json", dest="json_only", action="store_true",
        help="JSON-only output (suppress stderr messages)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print Blender startup output to stderr",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress all stderr output",
    )

    subs = parser.add_subparsers(dest="command", required=True)

    # --- version ---
    p = subs.add_parser("version", help="Print version information")
    p.set_defaults(func=cmd_version)

    # --- info ---
    p = subs.add_parser("info", help="Get scene metadata from a .blend file")
    p.add_argument("blend_file", help="Path to .blend file")
    p.set_defaults(func=cmd_info)

    # --- list-objects ---
    p = subs.add_parser("list-objects", help="List objects in the scene")
    p.add_argument("blend_file", help="Path to .blend file")
    p.add_argument("--type", action="append", help="Filter by object type (repeatable)")
    p.add_argument("--selected", action="store_true", help="Only selected objects")
    p.set_defaults(func=cmd_list_objects)

    # --- list-materials ---
    p = subs.add_parser("list-materials", help="List materials in the file")
    p.add_argument("blend_file", help="Path to .blend file")
    p.add_argument("--unused", action="store_true", help="Include unused materials")
    p.set_defaults(func=cmd_list_materials)

    # --- validate ---
    p = subs.add_parser("validate", help="Check materials for RealityKit compatibility")
    p.add_argument("blend_file", help="Path to .blend file")
    p.add_argument("--material", help="Validate a single material by name")
    p.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    p.add_argument("--only-errors", action="store_true", help="Suppress warnings")
    p.set_defaults(func=cmd_validate)

    # --- settings (subcommand group) ---
    settings_parser = subs.add_parser("settings", help="Read or modify export settings")
    settings_subs = settings_parser.add_subparsers(dest="settings_command", required=True)

    # settings get
    p = settings_subs.add_parser("get", help="Read export settings")
    p.add_argument("blend_file", help="Path to .blend file")
    p.add_argument("--keys", nargs="+", help="Return only these keys")
    p.add_argument("--group", help="Return settings from a group: general, objects, geometry, rigging, bake")
    p.set_defaults(func=cmd_settings_get)

    # settings set
    p = settings_subs.add_parser("set", help="Modify export settings")
    p.add_argument("blend_file", help="Path to .blend file")
    p.add_argument("settings", nargs="+", metavar="key=value", help="Settings to change")
    p.add_argument("--save", action="store_true", help="Save the .blend file after applying")
    p.add_argument("--dry-run", action="store_true", help="Validate without applying")
    p.set_defaults(func=cmd_settings_set)

    # settings list
    p = settings_subs.add_parser("list", help="List all setting keys with schema info")
    p.set_defaults(func=cmd_settings_list)

    # --- export ---
    p = subs.add_parser("export", help="Export scene to USD/USDZ")
    p.add_argument("blend_file", help="Path to .blend file")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--format", choices=["USDA", "USDC", "USDZ"], help="Export format")
    p.add_argument("--selected-only", action="store_true", help="Export selected objects only")
    p.add_argument("--no-diagnostics", action="store_true", help="Skip diagnostics")
    p.add_argument("overrides", nargs="*", metavar="--key=value", help="Setting overrides")
    p.set_defaults(func=cmd_export)

    # --- bake-export ---
    p = subs.add_parser("bake-export", help="Bake textures and export scene")
    p.add_argument("blend_file", help="Path to .blend file")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--format", choices=["USDA", "USDC", "USDZ"], help="Export format")
    p.add_argument("--bake-mode", choices=["UNLIT_ALBEDO", "LIT_IBL"], help="Bake mode")
    p.add_argument("--resolution", help="Bake resolution (512, 1024, 2048, 4096, or custom int)")
    p.add_argument("--image-format", choices=["AVIF", "PNG"], help="Baked texture format")
    p.add_argument("--margin", type=int, help="Bake padding in pixels")
    p.add_argument("--selected-only", action="store_true", help="Only bake/export selected objects")
    p.add_argument("--no-diagnostics", action="store_true", help="Skip diagnostics")
    # IBL options
    p.add_argument("--ibl-source", choices=["SCENE_WORLD", "HDRI_FILE"], help="IBL source (LIT_IBL mode)")
    p.add_argument("--ibl-filepath", help="Path to HDRI file")
    p.add_argument("--ibl-strength", type=float, help="IBL strength multiplier")
    p.add_argument("--ibl-rotation", type=float, help="IBL Z rotation in radians")
    p.add_argument("--isolate-meshes", action="store_true", help="Isolate meshes during lit bake")
    # Channel options
    p.add_argument("--no-base-color", action="store_true", help="Skip base color bake")
    p.add_argument("--no-opacity", action="store_true", help="Skip opacity bake")
    # Advanced
    p.add_argument("--keep-materials", action="store_true", help="Keep baked materials after export")
    p.add_argument("--timeout", dest="timeout_step", type=int, help="Per-step timeout in seconds")
    p.add_argument("overrides", nargs="*", metavar="--key=value", help="Setting overrides")
    p.set_defaults(func=cmd_bake_export)

    # --- support-bundle ---
    p = subs.add_parser("support-bundle", help="Create a redacted support bundle")
    p.add_argument("blend_file", help="Path to .blend file")
    p.add_argument("-o", "--output", help="Existing export output path")
    p.add_argument("--bundle-output", help="Destination ZIP path")
    p.add_argument("--job-dir", help="Background bake/export job directory")
    p.add_argument("--diagnostics", help="Diagnostics JSON path")
    p.add_argument("--include-output", action="store_true", help="Include exported USD/USDZ and sidecar assets")
    p.add_argument("--include-blend", action="store_true", help="Include the source .blend file")
    p.add_argument("--full-log", action="store_true", help="Include full redacted logs instead of the last 2000 lines")
    p.add_argument("--no-redact", action="store_true", help="Disable support bundle redaction")
    p.set_defaults(func=cmd_support_bundle)

    # --- preferences (subcommand group) ---
    prefs_parser = subs.add_parser("preferences", help="Read or modify addon preferences")
    prefs_subs = prefs_parser.add_subparsers(dest="prefs_command", required=True)

    p = prefs_subs.add_parser("get", help="Read addon preferences")
    p.set_defaults(func=cmd_preferences_get)

    p = prefs_subs.add_parser("set", help="Modify addon preferences")
    p.add_argument("settings", nargs="+", metavar="key=value", help="Preferences to change")
    p.set_defaults(func=cmd_preferences_set)

    return parser


def main() -> int:
    parser = build_parser()
    parsed = parser.parse_args()

    # Handle --json flag: implies --quiet
    if parsed.json_only:
        parsed.quiet = True

    try:
        return parsed.func(parsed)
    except bridge.BridgeError as exc:
        msg = str(exc)
        if parsed.json_only:
            _print_json(exc.to_json())
        else:
            print(f"Error: {msg}", file=sys.stderr)
            if exc.response:
                artifacts = exc.response.get("artifacts") or {}
                diagnostics_path = artifacts.get("diagnostics_path")
                if diagnostics_path:
                    print(f"Diagnostics: {diagnostics_path}", file=sys.stderr)
                support_hint = artifacts.get("support_bundle_hint")
                if support_hint:
                    print(f"Support bundle: {support_hint}", file=sys.stderr)
        if "Blender not found" in msg:
            return 2
        if "Plugin not loaded" in msg or "Failed to import" in msg:
            return 3
        return 1
    except RuntimeError as exc:
        msg = str(exc)
        if parsed.json_only:
            _print_json({"ok": False, "error": msg})
        else:
            print(f"Error: {msg}", file=sys.stderr)
        # Map known error messages to specific exit codes
        if "Blender not found" in msg:
            return 2
        if "Plugin not loaded" in msg or "Failed to import" in msg:
            return 3
        return 1
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
