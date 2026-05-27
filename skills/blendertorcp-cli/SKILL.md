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
blendertorcp validate <file.blend> --material "MyMaterial" --strict
blendertorcp validate <file.blend> --only-errors
```

### Export

```bash
blendertorcp export <file.blend> -o /path/to/output.usdz --format USDZ
blendertorcp export <file.blend> -o out.usda --selected-only
blendertorcp export <file.blend> -o out.usdz --diagnostics
```

Export supports `--format`, `--selected-only`, `--diagnostics`, and `--no-diagnostics`.

Any export setting key can be passed as a positional `key=value` override (does not modify the .blend). Put override tokens before optional flags:

```bash
blendertorcp export <file.blend> export-animation=true triangulate-meshes=true -o out.usdz

# Resize textures but keep each source image format.
blendertorcp export <file.blend> \
  export-texture-settings-enabled=true \
  bake-image-format=ORIGINAL \
  bake-resolution=1024 \
  -o out.usda

# Keep original texture formats and dimensions.
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

# Material Color Only bake
blendertorcp bake-export <file.blend> -o out.usdz --bake-mode UNLIT_ALBEDO

# High-res PNG bake
blendertorcp bake-export <file.blend> -o out.usdz --resolution 4096 --image-format PNG

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
| `--format` | from settings | `USDA`, `USDC`, or `USDZ` |
| `--selected-only` | off | Only bake/export selected objects |
| `--diagnostics` | off | Write `<output>.diagnostics.json` |
| `--no-diagnostics` | off | Do not write diagnostics, even if enabled by settings |
| `--bake-mode` | from settings (`LIT_IBL` for fresh scenes) | `UNLIT_ALBEDO` = Material Color Only, `LIT_IBL` = Lighting & Shadows |
| `--resolution` | `2048` | `ORIGINAL`, `512`, `1024`, `2048`, `4096`, or any integer |
| `--image-format` | `AVIF` | `ORIGINAL`, `AVIF`, or `PNG`; AVIF staging uses external `avifenc` when available and falls back to PNG |
| `--margin` | `8` | Bake padding in pixels |
| `--ibl-source` | `SCENE_WORLD` | Lighting source: `SCENE_WORLD` or `HDRI_FILE` |
| `--ibl-filepath` | — | Path to HDRI file |
| `--ibl-strength` | `1.0` | Lighting strength multiplier |
| `--ibl-rotation` | `0.0` | Lighting-source Z rotation in radians |
| `--isolate-meshes` | off | Isolate meshes during Lighting & Shadows bake |
| `--no-base-color` | off | Skip base color channel |
| `--no-opacity` | off | Skip opacity channel |
| `--keep-materials` | off | Keep baked materials after export |
| `--timeout` | `0` | Per-step timeout in seconds |

Missing, unpacked external images fail before baking with `MISSING_EXTERNAL_TEXTURES`; pack or relink textures in Blender and rerun. `ORIGINAL` texture format/resolution is meaningful for existing texture staging: Export Scene can keep each source texture's format and/or dimensions. Bake Textures & Export creates new baked images, so `ORIGINAL` falls back to PNG/2048 for bake output where there is no source image to preserve.

Any export setting key can also be passed as a positional override (same as `export`), e.g. `export-animation=true`.

### Settings

```bash
# Read all settings
blendertorcp settings get <file.blend>

# Read a specific group: general, objects, geometry, rigging, texture, bake, diagnostics, or all
blendertorcp settings get <file.blend> --group texture
blendertorcp settings get <file.blend> --group bake

# Read specific keys
blendertorcp settings get <file.blend> --keys export_format bake_resolution

# Modify settings
blendertorcp settings set <file.blend> export_format=USDZ
blendertorcp settings set <file.blend> export_texture_settings_enabled=true bake_resolution=4096
blendertorcp settings set <file.blend> diagnostics_enabled=true

# Modify and save the .blend
blendertorcp settings set <file.blend> export_format=USDZ --save

# Validate without applying
blendertorcp settings set <file.blend> export_format=FOO --dry-run

# List all setting keys with types and allowed values
blendertorcp settings list
```

### Preferences (addon-level)

```bash
blendertorcp preferences get
blendertorcp preferences set default_export_format=USDZ
```

### Version

```bash
blendertorcp version
```

On this branch, the add-on manifest and `bl_info` report version `1.1.0`.

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
if blendertorcp validate scene.blend --strict; then
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

**Export:** `export_format` (USDA/USDC/USDZ), `root_prim_name`, `export_animation`, `selected_objects_only`

**Texture:** `export_texture_settings_enabled`, `bake_resolution` (ORIGINAL/512/1024/2048/4096/CUSTOM), `bake_image_format` (ORIGINAL/AVIF/PNG), `bake_margin`

**Bake:** `bake_mode` (`UNLIT_ALBEDO` = Material Color Only, `LIT_IBL` = Lighting & Shadows), `bake_ibl_source`, `bake_ibl_filepath`, `bake_ibl_strength`, `bake_ibl_rotation`, `bake_isolate_meshes_lit`, `bake_base_color`, `bake_opacity`, `bake_keep_materials`

**Geometry:** `triangulate_meshes`, `export_normals`, `export_uvmaps`, `export_subdivision` (IGNORE/TESSELLATE/BEST_MATCH)

**Objects:** `export_meshes`, `export_lights`, `export_cameras`, `export_curves`, `export_hair`

**Rigging:** `export_armatures`, `export_shapekeys`, `only_deform_bones`

For the complete list run `blendertorcp settings list`.
