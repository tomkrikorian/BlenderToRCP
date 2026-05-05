---
name: "blendertorcp-cli"
description: "Use when a user asks to export a Blender scene to USD or USDZ, bake textures for RealityKit, validate materials for RealityKit compatibility, or read and change BlenderToRCP export settings from the command line. Requires the `blendertorcp` CLI alias or the Plugin path (see the blendertorcp-setup skill)."
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
```

Any export setting key can be passed as a positional `key=value` override (does not modify the .blend). Put override tokens before optional flags:

```bash
blendertorcp export <file.blend> export-animation=true triangulate-meshes=true -o out.usdz
```

### Bake & Export

Bake textures and export. Default: unlit albedo, 2048 px, AVIF format.

```bash
# Simple bake
blendertorcp bake-export <file.blend> -o /path/to/output.usdz

# High-res PNG bake
blendertorcp bake-export <file.blend> -o out.usdz --resolution 4096 --image-format PNG

# Lit IBL bake with HDRI override
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
| `--no-diagnostics` | off | Skip diagnostics generation |
| `--bake-mode` | `UNLIT_ALBEDO` | `UNLIT_ALBEDO` or `LIT_IBL` |
| `--resolution` | `2048` | `512`, `1024`, `2048`, `4096`, or any integer |
| `--image-format` | `AVIF` | `AVIF` (Blender 5.1+) or `PNG` |
| `--margin` | `8` | Bake padding in pixels |
| `--ibl-source` | `SCENE_WORLD` | `SCENE_WORLD` or `HDRI_FILE` |
| `--ibl-filepath` | — | Path to HDRI file |
| `--ibl-strength` | `1.0` | IBL strength multiplier |
| `--ibl-rotation` | `0.0` | IBL Z rotation in radians |
| `--isolate-meshes` | off | Isolate meshes during lit bake |
| `--no-base-color` | off | Skip base color channel |
| `--no-opacity` | off | Skip opacity channel |
| `--keep-materials` | off | Keep baked materials after export |
| `--timeout` | `0` | Per-step timeout in seconds |

Any export setting key can also be passed as a positional override (same as `export`), e.g. `export-animation=true`.

### Settings

```bash
# Read all settings
blendertorcp settings get <file.blend>

# Read a specific group: general, objects, geometry, rigging, bake
blendertorcp settings get <file.blend> --group bake

# Read specific keys
blendertorcp settings get <file.blend> --keys export_format bake_resolution

# Modify settings
blendertorcp settings set <file.blend> export_format=USDZ bake_resolution=4096

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
blendertorcp preferences set default_export_format=USDZ enable_diagnostics=true
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

Use this after failed exports or background bake/export jobs. For background jobs, include the job directory so `settings.json`, `status.json`, and `log.txt` are bundled:

```bash
blendertorcp support-bundle scene.blend \
  -o output.usdz \
  --job-dir output/.blendertorcp_jobs/bake_export_YYYYMMDD_HHMMSS_abcd
```

Useful options: `--bundle-output`, `--job-dir`, `--diagnostics`, `--include-output`, `--include-blend`, `--full-log`, and `--no-redact`. Bundles are redacted by default, including JSON-escaped Windows paths, and do not include the source `.blend` or exported assets unless `--include-blend` or `--include-output` is passed.

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

**Bake:** `bake_mode` (UNLIT_ALBEDO/LIT_IBL), `bake_resolution` (512/1024/2048/4096/CUSTOM), `bake_image_format` (AVIF/PNG), `bake_margin`

**Geometry:** `triangulate_meshes`, `export_normals`, `export_uvmaps`, `export_subdivision` (IGNORE/TESSELLATE/BEST_MATCH)

**Objects:** `export_meshes`, `export_lights`, `export_cameras`, `export_curves`, `export_hair`

**Rigging:** `export_armatures`, `export_shapekeys`, `only_deform_bones`

For the complete list run `blendertorcp settings list`.
