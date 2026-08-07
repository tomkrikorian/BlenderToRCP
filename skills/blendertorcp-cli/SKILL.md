---
name: "blendertorcp-cli"
description: "Use when a user asks to export a Blender scene to USDA/USDC/USDZ, bake textures for RealityKit, validate materials for RealityKit compatibility, or read and change BlenderToRCP export, texture, and bake settings from the command line. Requires the `blendertorcp` CLI alias or the Plugin path (see the blendertorcp-setup skill)."
---

# BlenderToRCP CLI

Control the BlenderToRCP Blender plugin from the terminal. Every command spawns `blender --background`; successful commands return JSON to stdout, and `--json` keeps failure envelopes machine-readable on stdout.

## Prerequisites

- `blendertorcp` alias configured (see the `blendertorcp-setup` skill), or
- `BLENDERTORCP_BLENDER` environment variable set and the Plugin path known

## Commands

### Scene inspection

```bash
# Scene metadata (object count, materials, frame range, units)
blendertorcp info <file.blend>

# List objects with optional type filter (repeatable, case-insensitive)
blendertorcp list-objects <file.blend> [--type MESH] [--type LIGHT] [--selected]

# List materials
blendertorcp list-materials <file.blend> [--unused]
```

`--type` takes Blender 5.2 `Object.type` identifiers: `MESH`, `CURVE`,
`SURFACE`, `META`, `FONT`, `CURVES`, `POINTCLOUD`, `VOLUME`, `GREASEPENCIL`,
`ARMATURE`, `LATTICE`, `EMPTY`, `LIGHT`, `LIGHT_PROBE`, `CAMERA`, `SPEAKER`.
Note `GREASEPENCIL`, not the pre-4.3 `GPENCIL`. The filter is not validated — an
identifier that does not exist matches nothing and still exits 0 with `[]`.

### Validation

Check materials for RealityKit compatibility. Exit code 0 = all OK, exit code 1 = errors found.

```bash
blendertorcp validate <file.blend>
blendertorcp validate <file.blend> --material "MyMaterial"
blendertorcp validate <file.blend> --only-errors
blendertorcp validate <file.blend> --materialx-surface-profile realitykit_pbr2
```

`--materialx-surface-profile` accepts `realitykit_portable` (production default), `realitykit_pbr2`, or `openpbr_1_1`. The latter two profiles are experimental OS 27 targets.

A failing validation is not a failing command: the report is still the ordinary
result payload on stdout, with its own top-level `ok: false` and no `error`
object. A run that could not execute at all — `--material` naming a material
that is not in the file, for instance — produces the error envelope instead.
Both exit 1, so branch on whether the payload has an `error` key.

`--only-errors` removes the `warnings` arrays and the `warning_count` key
entirely rather than zeroing them.

### Export

```bash
blendertorcp export <file.blend> -o /path/to/output.usdz --format USDZ
blendertorcp export <file.blend> -o out.usda --format USDA --selected-only
blendertorcp export <file.blend> -o out.usdz --format USDZ --diagnostics
```

Export always uses Blender's native orientation conversion with `-Z` forward,
`Y` up, meters at scale `1`, relative dependencies, and mesh/UV/normal export.
`--diagnostics` and `--no-diagnostics` control successful-export sidecars;
failures always write diagnostics. If both are passed, `--no-diagnostics` wins.

**`-o` names a stem, not the final path.** The extension is rewritten to match
the effective format — `--format` if given, otherwise the `.blend`'s saved
`export_format`. `-o out.usdz` on a scene left at the `USDA` default silently
writes `out.usda`. Always pass `--format` when the format matters, and read
`export_path` back from the result rather than assuming the path you passed.
Extension replacement targets the last dot, so `-o my.scene.v2` becomes
`my.scene.usda`.

Any export setting key can be passed as a positional `key=value` override (does not modify the .blend). Hyphens and underscores in the *key* are interchangeable (`bake-resolution=1024` == `bake_resolution=1024`); values are taken literally and are case-sensitive.

**Argument order:** the blend file and the override tokens are positionals and must form one uninterrupted run. Flags may sit before or after that run, never inside it.

```bash
# OK
blendertorcp export <file.blend> export-animation=true triangulate-meshes=true -o out.usda --format USDA
blendertorcp export -o out.usda <file.blend> export-animation=true --format USDA

# FAILS: "unrecognized arguments: export-animation=true"
blendertorcp export <file.blend> -o out.usda export-animation=true
```

Boolean setting values accept only `true`, `1`, or `yes` and `false`, `0`, or `no` (case-insensitive and whitespace-trimmed). Other spellings, including `on` and `off`, fail with `INVALID_SETTING_VALUE` instead of being guessed. Enum values must match a `settings list` value exactly — `bake-resolution=true` is not a boolean setting and fails with `INVALID_SETTING_VALUE`.

```bash
blendertorcp export <file.blend> export-animation=true triangulate-meshes=true -o out.usdz --format USDZ

# Resize eligible LDR textures while keeping their Apple-compatible encoding.
blendertorcp export <file.blend> \
  export-texture-settings-enabled=true \
  bake-image-format=ORIGINAL \
  bake-resolution=1024 \
  -o out.usda --format USDA

# Keep Apple-compatible encodings and original dimensions.
blendertorcp export <file.blend> \
  export-texture-settings-enabled=true \
  bake-image-format=ORIGINAL \
  bake-resolution=ORIGINAL \
  -o out.usda --format USDA
```

### Bake Textures & Export

Bake textures and export. Fresh scenes default to Lighting & Shadows (`LIT_IBL`). Texture overrides are off by default; passing `--resolution`, `--image-format`, or `--margin` enables them for the run. Override setting defaults are 2048 px, AVIF, and 8 px margin. Bake/export skips source material graph validation; use `validate` or `export` when checking direct RealityKit graph compatibility.

```bash
# Lighting & Shadows bake at default settings
blendertorcp bake-export <file.blend> -o /path/to/output.usdz --format USDZ

# Material Color Only - Unlit bake
blendertorcp bake-export <file.blend> -o out.usdz --format USDZ --bake-mode UNLIT_ALBEDO

# Material Color Only - Lit PBR bake (RealityKit lights the baked color)
blendertorcp bake-export <file.blend> -o out.usdz --format USDZ --bake-mode LIT_ALBEDO --roughness-mode AVERAGE

# High-res PNG bake
blendertorcp bake-export <file.blend> -o out.usdz --format USDZ --resolution 4096 --image-format PNG --margin 4

# Keep original texture override semantics where source textures are staged.
# For newly baked images, ORIGINAL falls back to concrete bake outputs.
blendertorcp bake-export <file.blend> -o out.usdz --format USDZ --resolution ORIGINAL --image-format ORIGINAL

# Lighting & Shadows bake with HDRI override
blendertorcp bake-export <file.blend> -o out.usdz --format USDZ \
  --bake-mode LIT_IBL \
  --ibl-source HDRI_FILE \
  --ibl-filepath /path/to/env.hdr \
  --ibl-strength 1.5 \
  --isolate-meshes

# Quick preview of selected objects
blendertorcp bake-export <file.blend> -o /tmp/preview.usdz --format USDZ --resolution 512 --selected-only
```

Bake-export flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | from settings | `USDA`, `USDC`, or `USDZ` |
| `--selected-only` | off | Only bake/export selected objects |
| `--diagnostics` | off | Keep `<output>.diagnostics.json` after success |
| `--no-diagnostics` | off | Suppress success diagnostics; failures still write diagnostics |
| `--bake-mode` | from settings (`LIT_IBL` for fresh scenes) | `UNLIT_ALBEDO` = Material Color Only - Unlit, `LIT_ALBEDO` = Material Color Only - Lit PBR, `LIT_IBL` = Lighting & Shadows |
| `--resolution` | `2048` | `ORIGINAL`, `512`, `1024`, `2048`, `4096`, or any integer |
| `--image-format` | `AVIF` | `ORIGINAL`, `AVIF`, or `PNG`; AVIF is encoded natively by Blender — no external tools required |
| `--margin` | `8` | Bake padding in pixels |
| `--ibl-source` | `SCENE_WORLD` | Lighting source: `SCENE_WORLD` or `HDRI_FILE` |
| `--ibl-filepath` | — | Path to HDRI file |
| `--ibl-strength` | `1.0` | Lighting strength multiplier |
| `--ibl-rotation` | `0.0` | Lighting-source Z rotation in radians |
| `--isolate-meshes` | off | Isolate meshes during Lighting & Shadows bake |
| `--no-base-color` | off | Skip base color channel |
| `--no-opacity` | off | Skip opacity channel |
| `--keep-materials` | off | Keep baked materials after export |
| `--step-timeout` | `0` | Per-step worker timeout; always emits a structured error and failure diagnostics, and persists status for UI jobs |
| `--roughness-mode` | `TEXTURE` | LIT_ALBEDO roughness output: `TEXTURE` or `AVERAGE` |

`bake-export` also takes positional `key=value` overrides on the same terms as
`export`, and rewrites the `-o` extension to match the effective format in the
same way.

The global `--timeout <sec>` flag (place before the subcommand, default 600, `0` = unlimited) bounds the whole Blender subprocess — raise it for long bakes. It is a different budget from `--step-timeout` and produces a different error: `--step-timeout` terminates the Blender worker (which exits 124) and returns a structured `BAKE_STEP_TIMEOUT` naming the stalled step with failure diagnostics, while `--timeout` kills Blender outright and returns a bare `BLENDER_TIMEOUT` with no stage and no sidecar. Both exit 1 — 124 appears only as `context.returncode`.

Missing, unpacked external images fail before baking with `MISSING_EXTERNAL_TEXTURES`; missing linked libraries, caches, HDRIs, or other non-image dependencies fail with `MISSING_EXTERNAL_ASSETS`. Pack or relink textures, relink the other dependency, and rerun. The scan is limited to the dependency-closed export scope, including collection prototypes and active Geometry Nodes/modifier/Scene World inputs. For existing texture staging, `ORIGINAL` preserves Apple-compatible AVIF, PNG, JPEG, and OpenEXR encodings and/or source dimensions; unsupported LDR inputs are normalized to PNG. OpenEXR always remains byte-for-byte unchanged and ignores overrides. Radiance HDR (`.hdr`) fails with guidance to convert it to OpenEXR. Bake Textures & Export creates new baked images, so `ORIGINAL` falls back to PNG/2048 for bake output where there is no source image to preserve.

Any export setting key can also be passed as a positional override (same as `export`), e.g. `export-animation=true`.

`author-animation-library=true` is experimental editor metadata. RCP 3 build
`80.0.1.500.1` recognizes the schema but flattens authored named clip
definitions to the aggregate animation during supported USD import. Leave it
off for ordinary RealityKit runtime exports and do not promise that it
preserves Blender Action names in RCP.

### Settings

```bash
# Read all settings
blendertorcp settings get <file.blend>

# Read a specific group: general, geometry, rigging, texture, materials, bake, diagnostics, or all
blendertorcp settings get <file.blend> --group texture
blendertorcp settings get <file.blend> --group bake
blendertorcp settings get <file.blend> --group materials

# Read specific keys (--keys wins over --group if both are given)
blendertorcp settings get <file.blend> --keys export_format bake_resolution

# Modify settings. --save is REQUIRED to change the file: without it the
# values are applied to the short-lived background Blender worker and are
# discarded when it exits (the result reports "saved": false and warns).
blendertorcp settings set <file.blend> export_format=USDZ --save
blendertorcp settings set <file.blend> export_texture_settings_enabled=true bake_resolution=4096 --save
blendertorcp settings set <file.blend> diagnostics_enabled=true --save

# Validate without applying. --dry-run also overrides --save.
blendertorcp settings set <file.blend> triangulate_meshes=true quad_method=BEAUTY --dry-run

# List all setting keys with types and allowed values (40 keys, no .blend needed)
blendertorcp settings list
```

`--save` is the whole contract: without it the command still exits 0 and still
lists the keys under `updated`, so `updated` is not evidence that anything
reached the file — check `saved`. Never tell a user a setting was changed on the
basis of a run without `--save`.

`--dry-run` returns `{"valid": true, "would_update": [...]}` and is only ever
`true`: an unknown key or a rejected value is a hard failure (exit 1) whether or
not `--dry-run` was passed. A `--dry-run` that exits 0 is the pass signal.

Unknown keys and groups on `settings get`, and unknown keys on
`preferences set`, currently surface as the generic `VALUEERROR` code with a
Python traceback rather than a dedicated error code. Read `error.message`, not
`error.code`, for those.

Without `--json`, a rejected value prints only the summary line
(`Error: Invalid setting value.`). The actionable part — which key, which value,
which values were allowed — is in `error.details` and needs `--json`.

### Preferences (addon-level)

```bash
blendertorcp preferences get
blendertorcp preferences set usdzip_path=/opt/usd/bin/usdzip

# Clear a preference with an empty value
blendertorcp preferences set usdzip_path=
```

**`preferences set` persists immediately — there is no `--save` and no
`--dry-run`.** Unlike `settings set`, it calls Blender's *Save Preferences* on
the user's real preferences file before returning, so the change is global to
their Blender install. Confirm before running it on a user's behalf.

### Version

```bash
blendertorcp version
```

The extension manifest (`Plugin/blender_manifest.toml`) is the single source of version metadata; `version` reports it (currently `2.0.0`) alongside the Blender and Python versions of the resolved executable. It is the only command that does not need the addon to load, so it is the quickest check that `--blender` points somewhere usable.

### Support bundle

```bash
blendertorcp support-bundle scene.blend \
  -o output.usdz \
  --diagnostics output.diagnostics.json
```

Use this after failed exports or background bake/export jobs. For background jobs, include the job directory so redacted job status, settings, and logs are bundled:

```bash
blendertorcp support-bundle scene.blend \
  -o output.usdz \
  --job-dir output/.blendertorcp_jobs/bake_export_YYYYMMDD_HHMMSS_abcd
```

Only the `.blend` is required; every other input is optional. Useful options: `--bundle-output`, `--job-dir`, `--diagnostics`, `--include-output`, `--include-blend`, `--full-log`, and `--no-redact`. Note that `--diagnostics` here takes a **path**, unlike the boolean `--diagnostics` switch on `export` and `bake-export`. Bundles are redacted by default, including JSON-escaped Windows paths, and do not include the source `.blend` or exported assets unless `--include-blend` or `--include-output` is passed. Bundles include `diagnostics/assets.json`; `diagnostics/validate.json` is omitted for bake-export bundles because baking does not require source material graph validation. The default ZIP name is `BlenderToRCP-support-<blend-stem>-<YYYYMMDD-HHMMSS>.zip`; the result reports `support_bundle_path`, `file_count`, `redacted`, `included_output`, and `included_blend`.

## Global flags

All five are top-level flags and must appear **before** the subcommand;
`blendertorcp version --timeout 30` is an argument error.

| Flag | Default | Description |
|------|---------|-------------|
| `--blender <path>` | `$BLENDERTORCP_BLENDER` or `blender` | Path to Blender executable |
| `--json` | off | JSON-only output: implies `--quiet`, puts failure envelopes on stdout |
| `--verbose` | off | Forward Blender's **stderr** to stderr. Not suppressed by `--json` or `--quiet` |
| `--quiet` | off | Suppress the CLI's own progress lines. Does **not** suppress failure messages |
| `--timeout <seconds>` | `600` | Overall Blender subprocess timeout; `0` disables it |

## Output format

Successful commands return JSON to stdout. Parse with `jq` or read directly:

```bash
blendertorcp info scene.blend | jq '.object_count'
```

For automation, use `--json`; failures then return a structured JSON envelope with `ok`, `schema_version`, `command`, `error`, `context`, `artifacts`, and optional `process_output`. `error.code` is the stable identifier — branch on it, not on `error.message`. Success payloads have no envelope at all: the command's result is printed directly, with no `ok`/`schema_version`/`context` wrapper (`validate` is the exception — its result carries its own `ok`).

Three stream behaviours are easy to get wrong:

- **`--json` implies `--quiet`, but neither silences `--verbose`.** The
  Blender-stderr forward is unconditional, so `--json --verbose` still writes to
  stderr — and that forwarded text is *not* `$HOME`-redacted, unlike the
  `process_output` fields inside the envelope. Do not combine them when
  capturing output for a public issue.
- **`--quiet` does not silence failures.** It suppresses progress lines only;
  the `Error:`, `Diagnostics:`, and `Support bundle:` lines still go to stderr.
  Use `2>/dev/null` and the exit code if you need real silence.
- **`--verbose` prints nothing on a clean run.** It forwards Blender's *stderr*;
  the startup banner goes to Blender's *stdout*, which the bridge consumes. In
  practice `--verbose` surfaces Blender tracebacks and warnings, not a log.

For support captures, save stdout/stderr separately:

```bash
blendertorcp --verbose export scene.blend -o output.usdz --format USDZ \
  > blendertorcp-result.json \
  2> blendertorcp-stderr.log
```

Chain commands conditionally:

```bash
if blendertorcp validate scene.blend; then
  blendertorcp export scene.blend -o output.usdz --format USDZ
else
  echo "Fix material issues first"
fi
```

Read the real output path back rather than assuming `-o` was honoured verbatim:

```bash
OUT=$(blendertorcp --json export scene.blend -o /output/scene --format USDZ | jq -r '.export_path')
```

## Exit codes

These are the complete set. There is no `124` and no `4`+.

| Code | Meaning |
|------|---------|
| 0 | Success (`--help` also exits 0) |
| 1 | Command failed: export error, validation errors found, bad args or overrides, `--timeout` or `--step-timeout` expiry |
| 2 | Blender not found or failed to start (`BLENDER_NOT_FOUND`, `BLENDER_START_FAILED`) |
| 3 | Plugin not installed or failed to load in Blender (`ADDON_LOAD_FAILED`) |
| 130 | Interrupted with Ctrl-C (`INTERRUPTED`) |

Note that bad arguments are exit `1`, not the conventional argparse `2` — `2`
means "Blender did not start". A timeout is also exit `1`; the worker's `124`
appears only as `context.returncode`.

## Error codes

Raised by the CLI before Blender starts: `INVALID_ARGUMENTS`,
`INVALID_OVERRIDE`, `INVALID_SETTING_FORMAT`, `INVALID_PREFERENCE_FORMAT`,
`BLENDER_NOT_FOUND`, `BLENDER_START_FAILED`, `BLENDER_TIMEOUT`,
`BLENDER_PROCESS_FAILED`, `BLENDER_BRIDGE_FAILED`, `CLI_RUNTIME_ERROR`,
`INTERRUPTED`.

Raised inside Blender: `ADDON_LOAD_FAILED`, `INVALID_SETTING_OVERRIDE`,
`INVALID_SETTING_VALUE`, `SETTINGS_SAVE_FAILED`,
`INVALID_EXPORT_SELECTION`, `NO_EXPORTABLE_OBJECTS`,
`UNSUPPORTED_MATERIAL_NODES` (`export` only), `MISSING_EXTERNAL_TEXTURES`,
`MISSING_EXTERNAL_ASSETS`, `BAKE_STEP_TIMEOUT`, `BLENDER_USD_EXPORT_FAILED`,
`POSTPROCESS_FAILED`, `EXPORT_FAILED`, `BAKE_EXPORT_FAILED`, `COMMAND_FAILED`.

A command that raises a plain Python exception reports the class name
upper-cased (`VALUEERROR`, …) plus a `traceback` field. Treat those as internal
faults, not a stable contract.

`INVALID_EXPORT_SETTINGS`, `ASSET_PREFLIGHT_FAILED`, `SCENE_SNAPSHOT_FAILED`,
`JOB_SETTINGS_WRITE_FAILED`, `BACKGROUND_RUNNER_MISSING`, and
`BACKGROUND_LAUNCH_FAILED` belong to the Blender UI's background job operator —
they appear in job `status.json` and support bundles, never as CLI envelopes.

## Common setting keys

**Export:** `export_format` (USDA/USDC/USDZ, default USDA), `root_prim_name`, `export_animation`, `selected_objects_only`

**Texture:** `export_texture_settings_enabled`, `bake_resolution` (ORIGINAL/512/1024/2048/4096/CUSTOM), `bake_image_format` (ORIGINAL/AVIF/PNG), `bake_margin`

**Materials:** `materialx_surface_profile` (`realitykit_portable` default; `realitykit_pbr2` and `openpbr_1_1` experimental OS 27 profiles)

**Bake:** `bake_mode` (`UNLIT_ALBEDO` = Material Color Only - Unlit, `LIT_ALBEDO` = Material Color Only - Lit PBR, `LIT_IBL` = Lighting & Shadows), `bake_roughness_mode` (`TEXTURE`/`AVERAGE`, `LIT_ALBEDO` only), `bake_ibl_source`, `bake_ibl_filepath`, `bake_ibl_strength`, `bake_ibl_rotation`, `bake_isolate_meshes_lit`, `bake_base_color`, `bake_opacity`, `bake_keep_materials`, `bake_step_timeout_seconds`

**Geometry:** `triangulate_meshes`, `export_subdivision` (IGNORE/TESSELLATE/BEST_MATCH)

Raw Blender cameras, lights, World dome lights, curves, point clouds, volumes,
and hair are intentionally not settings in the portable RealityKit/RCP3 export
contract. Author cameras and lighting downstream, and convert unsupported
geometry to polygon meshes.

**Rigging:** `export_armatures`, `export_shapekeys`, `only_deform_bones`

For the complete list — 40 keys with type, allowed values, default, and group —
run `blendertorcp settings list`. It reads the live schema out of the registered
addon, so it can never drift from the installed build; prefer it over any table
here or in the docs.
