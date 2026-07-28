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

# List objects with optional type filter
blendertorcp list-objects <file.blend> [--type MESH] [--type LIGHT] [--selected]

# List materials
blendertorcp list-materials <file.blend> [--unused]
```

### Validation

Check materials for RealityKit compatibility. Exit code 0 = all OK, exit code 1 = errors found.

```bash
blendertorcp validate <file.blend>
blendertorcp validate <file.blend> --material "MyMaterial"
blendertorcp validate <file.blend> --only-errors
blendertorcp validate <file.blend> --materialx-surface-profile realitykit_pbr2
```

`--materialx-surface-profile` accepts `realitykit_portable` (production default), `realitykit_pbr2`, or `openpbr_1_1`. The latter two profiles are experimental OS 27 targets.

### Export

```bash
blendertorcp export <file.blend> -o /path/to/output.usdz --format USDZ
blendertorcp export <file.blend> -o out.usda --selected-only
blendertorcp export <file.blend> -o out.usdz --diagnostics
```

Export always uses Blender's native orientation conversion with `-Z` forward,
`Y` up, meters at scale `1`, relative dependencies, and mesh/UV/normal export.
`--diagnostics` and `--no-diagnostics` control successful-export sidecars;
failures always write diagnostics.

Any export setting key can be passed as a positional `key=value` override (does not modify the .blend). Put override tokens before optional flags:

Boolean setting values accept only `true`, `1`, or `yes` and `false`, `0`, or `no` (case-insensitive and whitespace-trimmed). Other spellings, including `on` and `off`, fail with `INVALID_SETTING_VALUE` instead of being guessed.

```bash
blendertorcp export <file.blend> export-animation=true triangulate-meshes=true -o out.usdz

# Resize eligible LDR textures while keeping their Apple-compatible encoding.
blendertorcp export <file.blend> \
  export-texture-settings-enabled=true \
  bake-image-format=ORIGINAL \
  bake-resolution=1024 \
  -o out.usda

# Keep Apple-compatible encodings and original dimensions.
blendertorcp export <file.blend> \
  export-texture-settings-enabled=true \
  bake-image-format=ORIGINAL \
  bake-resolution=ORIGINAL \
  -o out.usda
```

### Bake Textures & Export

Bake textures and export. Fresh scenes default to Lighting & Shadows (`LIT_IBL`). Texture overrides are off by default; passing `--resolution`, `--image-format`, or `--margin` enables them for the run. Override setting defaults are 2048 px, AVIF, and 8 px margin. Bake/export skips source material graph validation; use `validate` or `export` when checking direct RealityKit graph compatibility.

```bash
# Lighting & Shadows bake at default settings
blendertorcp bake-export <file.blend> -o /path/to/output.usdz

# Material Color Only - Unlit bake
blendertorcp bake-export <file.blend> -o out.usdz --bake-mode UNLIT_ALBEDO

# Material Color Only - Lit PBR bake (RealityKit lights the baked color)
blendertorcp bake-export <file.blend> -o out.usdz --bake-mode LIT_ALBEDO

# High-res PNG bake
blendertorcp bake-export <file.blend> -o out.usdz --resolution 4096 --image-format PNG

# Experimental RCP3 private package plus adjacent USDA source
blendertorcp bake-export <file.blend> -o out.import \
  --format RCP_IMPORT --bake-mode LIT_IBL

# Keep original texture override semantics where source textures are staged.
# For newly baked images, ORIGINAL falls back to concrete bake outputs.
blendertorcp bake-export <file.blend> -o out.usdz --resolution ORIGINAL --image-format ORIGINAL

# Lighting & Shadows bake with HDRI override
blendertorcp bake-export <file.blend> -o out.usdz \
  --bake-mode LIT_IBL \
  --ibl-source HDRI_FILE \
  --ibl-filepath /path/to/env.hdr \
  --ibl-strength 1.5 \
  --isolate-meshes

# Quick preview of selected objects
blendertorcp bake-export <file.blend> -o /tmp/preview.usdz --resolution 512 --selected-only
```

Bake-export flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | from settings | `USDA`, `USDC`, `USDZ`, or experimental `RCP_IMPORT` |
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

The global `--timeout <sec>` flag (place before the subcommand, default 600, `0` = unlimited) bounds the whole Blender subprocess — raise it for long bakes.

Missing, unpacked external images fail before baking with `MISSING_EXTERNAL_TEXTURES`; missing linked libraries, caches, HDRIs, or other non-image dependencies fail with `MISSING_EXTERNAL_ASSETS`. Pack or relink textures, relink the other dependency, and rerun. The scan is limited to the dependency-closed export scope, including collection prototypes and active Geometry Nodes/modifier/Scene World inputs. For existing texture staging, `ORIGINAL` preserves Apple-compatible AVIF, PNG, JPEG, and OpenEXR encodings and/or source dimensions; unsupported LDR inputs are normalized to PNG. OpenEXR always remains byte-for-byte unchanged and ignores overrides. Radiance HDR (`.hdr`) fails with guidance to convert it to OpenEXR. Bake Textures & Export creates new baked images, so `ORIGINAL` falls back to PNG/2048 for bake output where there is no source image to preserve.

`RCP_IMPORT` publishes the post-processed USDA beside the generated `.import`
directory. The writer is pinned to RCP 3.0 build `80.0.1.500.1`, currently
supports static multi-mesh scenes and shared materials, and structurally
generates single- or multi-mesh skeletal inputs that share the measured rig,
skeleton, and animation contract. Multi-mesh skeletal RCP reimport and Sequence
Editor acceptance remain pending.

Meshes with multiple face materials currently use one generated mesh resource
per material. The split representation preserves geometry, skin weights, and
appearance and passes source-runtime checks, but it is not RCP-compatible: a
second genuine reimport duplicates resources and RCP authors a different
combined descriptor with nested `subsets`. Do not claim multi-material
compatibility until the measured one-descriptor subset writer passes two
non-growing reimports. Baked RGBA base-color/opacity works per material in all
three bake modes, and `LIT_ALBEDO` supports roughness maps. Multi-mesh transform
animation, mixed rig/skeleton contracts, and unmeasured texture roles such as
normal, metallic, occlusion, or a separate opacity image fail closed.

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

# Read specific keys
blendertorcp settings get <file.blend> --keys export_format bake_resolution

# Modify settings. --save is REQUIRED to change the file: without it the
# values are applied to the short-lived background Blender worker and are
# discarded when it exits (the result reports "saved": false and warns).
blendertorcp settings set <file.blend> export_format=USDZ --save
blendertorcp settings set <file.blend> export_texture_settings_enabled=true bake_resolution=4096 --save
blendertorcp settings set <file.blend> diagnostics_enabled=true --save

# Validate without applying
blendertorcp settings set <file.blend> export_format=FOO --dry-run

# List all setting keys with types and allowed values
blendertorcp settings list
```

### Preferences (addon-level)

```bash
blendertorcp preferences get
blendertorcp preferences set usdzip_path=/opt/usd/bin/usdzip
```

### Version

```bash
blendertorcp version
```

The extension manifest (`Plugin/blender_manifest.toml`) is the single source of version metadata; `version` reports it (currently `2.0.0`).

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

Useful options: `--bundle-output`, `--job-dir`, `--diagnostics`, `--include-output`, `--include-blend`, `--full-log`, and `--no-redact`. Bundles are redacted by default, including JSON-escaped Windows paths, and do not include the source `.blend` or exported assets unless `--include-blend` or `--include-output` is passed. Bundles include `diagnostics/assets.json`; `diagnostics/validate.json` is omitted for bake-export bundles because baking does not require source material graph validation.

## Global flags

| Flag | Default | Description |
|------|---------|-------------|
| `--blender <path>` | `$BLENDERTORCP_BLENDER` or `blender` | Path to Blender executable |
| `--json` | off | JSON-only output, suppress stderr |
| `--verbose` | off | Include Blender startup log on stderr |
| `--quiet` | off | Suppress all stderr messages |
| `--timeout <seconds>` | `600` | Overall Blender subprocess timeout; `0` disables it. Place before the subcommand |

## Output format

Successful commands return JSON to stdout. Parse with `jq` or read directly:

```bash
blendertorcp info scene.blend | jq '.object_count'
```

For support captures, run with `--verbose` and save stdout/stderr separately:

```bash
blendertorcp --verbose export scene.blend -o output.usdz \
  > blendertorcp-result.json \
  2> blendertorcp-stderr.log
```

For automation, use `--json`; failures then return a structured JSON envelope with `ok`, `schema_version`, `command`, `error`, `context`, `artifacts`, and optional `process_output`.

Chain commands conditionally:

```bash
if blendertorcp validate scene.blend; then
  blendertorcp export scene.blend -o output.usdz
else
  echo "Fix material issues first"
fi
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Command failed (export error, validation error, bad args) |
| 2 | Blender not found or failed to start |
| 3 | Plugin not installed or failed to load in Blender |

## Common setting keys

**Export:** `export_format` (USDA/USDC/USDZ/RCP_IMPORT), `root_prim_name`, `export_animation`, `selected_objects_only`

**Texture:** `export_texture_settings_enabled`, `bake_resolution` (ORIGINAL/512/1024/2048/4096/CUSTOM), `bake_image_format` (ORIGINAL/AVIF/PNG), `bake_margin`

**Materials:** `materialx_surface_profile` (`realitykit_portable` default; `realitykit_pbr2` and `openpbr_1_1` experimental OS 27 profiles)

**Bake:** `bake_mode` (`UNLIT_ALBEDO` = Material Color Only - Unlit, `LIT_ALBEDO` = Material Color Only - Lit PBR, `LIT_IBL` = Lighting & Shadows), `bake_roughness_mode` (`TEXTURE`/`AVERAGE`, `LIT_ALBEDO` only), `bake_ibl_source`, `bake_ibl_filepath`, `bake_ibl_strength`, `bake_ibl_rotation`, `bake_isolate_meshes_lit`, `bake_base_color`, `bake_opacity`, `bake_keep_materials`, `bake_step_timeout_seconds`

**Geometry:** `triangulate_meshes`, `export_subdivision` (IGNORE/TESSELLATE/BEST_MATCH)

Raw Blender cameras, lights, World dome lights, curves, point clouds, volumes,
and hair are intentionally not settings in the portable RealityKit/RCP3 export
contract. Author cameras and lighting downstream, and convert unsupported
geometry to polygon meshes.

**Rigging:** `export_armatures`, `export_shapekeys`, `only_deform_bones`

For the complete list run `blendertorcp settings list`.
