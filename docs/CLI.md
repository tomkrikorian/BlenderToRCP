# BlenderToRCP CLI Reference

Command-line interface for BlenderToRCP. Run exports, bake textures, validate materials, and manage settings — all from your terminal, scripts, or AI agents.

Every command spawns Blender in background mode and prints structured JSON to stdout on success. Human-readable status goes to stderr. Bake/export uses Blender factory-startup mode to avoid unrelated user add-ons polluting the bake session. On failure, use `--json` when automation needs the structured error envelope on stdout; without `--json`, failures are summarized on stderr with diagnostics and support-bundle hints when available.

## Installation

The CLI ships inside the BlenderToRCP plugin — no separate installation needed. Once the addon is installed in Blender, the CLI is ready to use.

### 1. Tell the CLI where Blender is

```bash
# Add to your shell profile (.zshrc, .bashrc), or pass --blender each time
export BLENDERTORCP_BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
```

### 2. Find your extension root

The CLI lives directly in the Blender extension root. Common locations:

| Workflow | Path |
|----------|------|
| macOS installed extension | `~/Library/Application Support/Blender/<version>/extensions/.local/BlenderToRCP/` |
| macOS development symlink | `~/Library/Application Support/Blender/<version>/extensions/user_default/BlenderToRCP/` |
| Linux installed extension | `~/.config/blender/<version>/extensions/.local/BlenderToRCP/` |
| Linux development symlink | `~/.config/blender/<version>/extensions/user_default/BlenderToRCP/` |
| Windows installed extension | `%APPDATA%\Blender Foundation\Blender\<version>\extensions\.local\BlenderToRCP\` |
| Windows development symlink | `%APPDATA%\Blender Foundation\Blender\<version>\extensions\user_default\BlenderToRCP\` |

Look for `cli/__main__.py` and `api/runner.py` directly under that `BlenderToRCP/` directory. In a repository checkout, the equivalent directory is `<repo>/Plugin/`.

### 3. Run the CLI

```bash
# Installed extension root
python3 /path/to/BlenderToRCP version
python3 /path/to/BlenderToRCP preferences get
python3 /path/to/BlenderToRCP settings list

# Development checkout
python3 /path/to/repo/Plugin version
python3 /path/to/repo/Plugin preferences get
python3 /path/to/repo/Plugin settings list
```

### 4. (Optional) Create an alias for convenience

```bash
# Add to your shell profile for easy access
alias blendertorcp="python3 /path/to/BlenderToRCP"
# Or for a repository checkout:
# alias blendertorcp="python3 /path/to/repo/Plugin"
```

Then use it as:

```bash
blendertorcp <command> [options]
```


---

## Global Options

These flags are available on every command.

| Flag | Default | Description |
|------|---------|-------------|
| `--blender <path>` | `$BLENDERTORCP_BLENDER` or `blender` | Path to the Blender executable |
| `--json` | off | JSON-only output (suppress all stderr messages) |
| `--verbose` | off | Print Blender startup output to stderr |
| `--quiet` | off | Suppress all stderr output |

---

## Commands

### `version`

Print plugin, Blender, and Python version information.

```bash
blendertorcp version
```

**Output:**

```json
{
  "plugin": "1.1.0",
  "blender": "5.1.0",
  "python": "3.12.0"
}
```

---

### `info`

Get scene metadata from a `.blend` file.

```bash
blendertorcp info <file.blend>
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `file.blend` | yes | Path to the Blender file |

**Output:**

```json
{
  "file": "/path/to/scene.blend",
  "scene": "Scene",
  "frame_range": [1, 250],
  "fps": 24,
  "unit_system": "METRIC",
  "unit_scale": 1.0,
  "object_count": 12,
  "material_count": 5
}
```

---

### `list-objects`

List all objects in the scene.

```bash
blendertorcp list-objects <file.blend> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `file.blend` | yes | Path to the Blender file |

**Options:**

| Flag | Description |
|------|-------------|
| `--type <TYPE>` | Filter by object type. Repeatable. Values: `MESH`, `LIGHT`, `CAMERA`, `CURVE`, `EMPTY`, `ARMATURE`, `FONT`, `SPEAKER`, `VOLUME`, `GPENCIL`, `LATTICE`, `SURFACE` |
| `--selected` | Only list objects that are selected in the scene |

**Examples:**

```bash
blendertorcp list-objects scene.blend
blendertorcp list-objects scene.blend --type MESH
blendertorcp list-objects scene.blend --type MESH --type LIGHT
```

**Output:**

```json
[
  {
    "name": "Cube",
    "type": "MESH",
    "vertices": 8,
    "materials": ["Material.001"],
    "visible": true,
    "selected": false
  },
  {
    "name": "Sun",
    "type": "LIGHT",
    "light_type": "SUN",
    "materials": [],
    "visible": true,
    "selected": false
  }
]
```

---

### `list-materials`

List all materials in the file.

```bash
blendertorcp list-materials <file.blend> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `file.blend` | yes | Path to the Blender file |

**Options:**

| Flag | Description |
|------|-------------|
| `--unused` | Include materials not assigned to any scene object |

**Output:**

```json
[
  {
    "name": "Material.001",
    "users": 2,
    "use_nodes": true,
    "node_count": 5
  }
]
```

---

### `validate`

Check materials for RealityKit compatibility. Reports errors (nodes that block export) and warnings (nodes that require baking).

```bash
blendertorcp validate <file.blend> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `file.blend` | yes | Path to the Blender file |

**Options:**

| Flag | Description |
|------|-------------|
| `--material <name>` | Validate a single material by name. Validates all scene materials if omitted |
| `--strict` | Treat warnings as errors (matches the plugin's strict enforcement mode) |
| `--only-errors` | Suppress warnings in output |

**Examples:**

```bash
blendertorcp validate scene.blend
blendertorcp validate scene.blend --material "Wood"
blendertorcp validate scene.blend --strict
```

**Output:**

```json
{
  "ok": false,
  "error_count": 1,
  "warning_count": 2,
  "materials": [
    {
      "name": "Material.001",
      "ok": false,
      "errors": [
        {
          "node_name": "Mix Shader",
          "node_type": "MIX_SHADER",
          "message": "Node is not supported by RealityKit export."
        }
      ],
      "warnings": [
        {
          "node_name": "Bump",
          "node_type": "BUMP",
          "message": "Node requires baking for RealityKit."
        }
      ]
    }
  ]
}
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | All materials are compatible |
| 1 | One or more errors found (or warnings in `--strict` mode) |

---

### `settings get`

Read current export settings from a `.blend` file.

```bash
blendertorcp settings get <file.blend> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `file.blend` | yes | Path to the Blender file |

**Options:**

| Flag | Description |
|------|-------------|
| `--keys <key> [<key> ...]` | Return only these specific setting keys |
| `--group <name>` | Return settings from a panel group: `general`, `objects`, `geometry`, `rigging`, `bake`, or `all` (default) |

**Group breakdown:**

| Group | Settings included |
|-------|-------------------|
| `general` | `filepath`, `export_format`, `root_prim_name`, `export_animation`, `selected_objects_only`, `export_custom_properties`, `custom_properties_namespace`, `author_blender_name`, `allow_unicode`, `relative_paths`, `convert_orientation`, `forward_axis`, `up_axis`, `convert_scene_units`, `meters_per_unit`, `xform_op_mode`, `evaluation_mode`, `use_instancing` |
| `objects` | `export_meshes`, `export_lights`, `convert_world_material`, `export_cameras`, `export_curves`, `export_points`, `export_volumes`, `export_hair` |
| `geometry` | `export_uvmaps`, `rename_uvmaps`, `export_normals`, `merge_parent_xform`, `triangulate_meshes`, `quad_method`, `ngon_method`, `export_subdivision` |
| `rigging` | `export_armatures`, `only_deform_bones`, `export_shapekeys` |
| `bake` | `bake_mode`, `bake_ibl_source`, `bake_ibl_filepath`, `bake_ibl_strength`, `bake_ibl_rotation`, `bake_isolate_meshes_lit`, `bake_resolution`, `bake_resolution_custom`, `bake_image_format`, `bake_margin`, `bake_base_color`, `bake_opacity`, `bake_keep_materials`, `bake_step_timeout_seconds` |

**Examples:**

```bash
blendertorcp settings get scene.blend
blendertorcp settings get scene.blend --group bake
blendertorcp settings get scene.blend --keys export_format bake_resolution
```

**Output:**

```json
{
  "export_format": "USDA",
  "root_prim_name": "/root",
  "bake_resolution": "2048"
}
```

---

### `settings set`

Modify export settings in a `.blend` file.

```bash
blendertorcp settings set <file.blend> <key>=<value> [...] [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `file.blend` | yes | Path to the Blender file |
| `key=value` | yes | One or more settings to change (space-separated) |

**Options:**

| Flag | Description |
|------|-------------|
| `--save` | Save the `.blend` file after applying settings |
| `--dry-run` | Validate the keys and values without applying them |

**Examples:**

```bash
blendertorcp settings set scene.blend export_format=USDZ
blendertorcp settings set scene.blend bake_resolution=4096 bake_image_format=PNG --save
blendertorcp settings set scene.blend triangulate_meshes=true quad_method=BEAUTY --dry-run
```

**Output:**

```json
{
  "updated": ["export_format"],
  "saved": false
}
```

With `--dry-run`:

```json
{
  "valid": true,
  "would_update": ["bake_resolution", "bake_image_format"]
}
```

---

### `settings list`

List all available setting keys with their types and allowed values.

```bash
blendertorcp settings list
```

This command does not require a `.blend` file. It prints the schema for all export settings.

**Output:**

```json
[
  {
    "key": "export_format",
    "type": "enum",
    "values": ["USDA", "USDC", "USDZ"],
    "default": "USDA",
    "group": "general",
    "description": "Export format and file extension"
  },
  {
    "key": "bake_resolution",
    "type": "enum",
    "values": ["512", "1024", "2048", "4096", "CUSTOM"],
    "default": "2048",
    "group": "bake",
    "description": "Resolution for baked textures"
  }
]
```

---

### `export`

Export the scene to USD or USDZ.

```bash
blendertorcp export <file.blend> [setting=value ...] -o <output_path> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `file.blend` | yes | Path to the Blender file |
| `-o, --output` | yes | Output file path |

**Options:**

| Flag | Description |
|------|-------------|
| `--format <FORMAT>` | Override export format: `USDA`, `USDC`, `USDZ` |
| `--selected-only` | Export selected objects only |
| `--no-diagnostics` | Skip diagnostics generation |

Any export setting key can also be passed as a positional `key=value` override. These overrides apply for this export only and do not modify the `.blend` file:

```bash
blendertorcp export scene.blend \
  export-animation=true \
  triangulate-meshes=true \
  root-prim-name="/MyRoot" \
  -o out.usdz
```

Note: setting keys use hyphens in CLI overrides (`bake_resolution` becomes `bake-resolution=true`). Place override tokens before optional flags such as `-o` or `--format`.

**Examples:**

```bash
# Simple USDZ export
blendertorcp export scene.blend -o /output/scene.usdz --format USDZ

# Export with overrides
blendertorcp export scene.blend \
  export-animation=true \
  convert-scene-units=CENTIMETERS \
  -o /output/scene.usda \
  --selected-only
```

**Output:**

```json
{
  "ok": true,
  "export_path": "/output/scene.usdz",
  "format": "USDZ",
  "duration_seconds": 4.2,
  "diagnostics_path": "/output/scene.diagnostics.json",
  "support_bundle_hint": "blendertorcp support-bundle scene.blend -o /output/scene.usdz --diagnostics /output/scene.diagnostics.json"
}
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Export completed successfully |
| 1 | Export failed (unsupported materials, file errors, etc.) |

---

### `bake-export`

Bake textures and export the scene. This is the CLI equivalent of the "Bake Textures & Export" button in the plugin UI.

Which option should I choose?

| Goal | Use |
|------|-----|
| Quick USDZ export without baking textures | `blendertorcp export` / `Export Scene` |
| Reusable baked textures that Reality Composer Pro or RealityKit can light | `bake-export --bake-mode UNLIT_ALBEDO` / `Material Color Only` |
| Export that preserves Blender-looking lighting and shadows | `bake-export --bake-mode LIT_IBL` / `Lighting & Shadows` |

Both bake modes export the final baked result as RealityKit Unlit materials. The difference is what gets written into the texture: material color only, or lighting and shadows baked in.

Bake/export preflights external image files used by exported objects. Missing, unpacked textures fail before baking with `MISSING_EXTERNAL_TEXTURES`; pack or relink those files in Blender before retrying. Bake/export intentionally skips source material graph validation because unsupported Blender node groups are resolved by baking. Strict graph validation remains part of `blendertorcp export` and `blendertorcp validate`.

```bash
blendertorcp bake-export <file.blend> -o <output_path> [options]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `file.blend` | yes | Path to the Blender file |
| `-o, --output` | yes | Output file path |

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--format <FORMAT>` | from settings | Export format: `USDA`, `USDC`, `USDZ` |
| `--bake-mode <MODE>` | `UNLIT_ALBEDO` | `UNLIT_ALBEDO` for Material Color Only, `LIT_IBL` for Lighting & Shadows |
| `--resolution <RES>` | `2048` | Bake resolution: `512`, `1024`, `2048`, `4096`, or any integer for custom |
| `--image-format <FMT>` | `AVIF` | Baked texture format: `AVIF` (requires Blender 5.1+) or `PNG` |
| `--margin <PX>` | `8` | Bake padding in pixels |
| `--selected-only` | off | Only bake and export selected objects |
| `--no-diagnostics` | off | Skip diagnostics generation |

**Lighting source options** (only apply when `--bake-mode LIT_IBL` / Lighting & Shadows):

| Flag | Default | Description |
|------|---------|-------------|
| `--ibl-source <SRC>` | `SCENE_WORLD` | `SCENE_WORLD` to use the scene's world, or `HDRI_FILE` to override |
| `--ibl-filepath <PATH>` | none | Path to HDRI file (required when `--ibl-source HDRI_FILE`) |
| `--ibl-strength <FLOAT>` | `1.0` | Lighting strength multiplier |
| `--ibl-rotation <RAD>` | `0.0` | Lighting-source Z-axis rotation in radians |
| `--isolate-meshes` | off | Hide other meshes while baking each object (avoids cross-mesh shadows) |

**Texture channel options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--no-base-color` | off | Skip base color bake |
| `--no-opacity` | off | Skip opacity bake |

**Advanced options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--keep-materials` | off | Keep baked materials assigned after export |
| `--timeout <SEC>` | `0` (disabled) | Abort if a single bake step exceeds this duration in seconds |

**Examples:**

```bash
# Material Color Only bake at default settings
blendertorcp bake-export scene.blend -o /output/scene.usdz

# High-res bake with PNG textures
blendertorcp bake-export scene.blend -o /output/scene.usdz \
  --resolution 4096 \
  --image-format PNG

# Lighting & Shadows bake with custom HDRI
blendertorcp bake-export scene.blend -o /output/scene.usdz \
  --bake-mode LIT_IBL \
  --ibl-source HDRI_FILE \
  --ibl-filepath /hdris/studio.hdr \
  --ibl-strength 1.5 \
  --isolate-meshes

# Bake only selected objects at low resolution for preview
blendertorcp bake-export scene.blend -o /tmp/preview.usdz \
  --resolution 512 \
  --selected-only
```

**Output:**

```json
{
  "ok": true,
  "export_path": "/output/scene.usdz",
  "format": "USDZ",
  "duration_seconds": 45.3,
  "bake_stats": {
    "objects_baked": 8,
    "resolution": 2048,
    "image_format": "AVIF"
  },
  "diagnostics_path": "/output/scene.diagnostics.json",
  "support_bundle_hint": "blendertorcp support-bundle scene.blend -o /output/scene.usdz --diagnostics /output/scene.diagnostics.json"
}
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Bake and export completed successfully |
| 1 | Bake or export failed |

---

### `support-bundle`

Create a redacted ZIP with the files support needs to diagnose an export or bake failure.

```bash
blendertorcp support-bundle <file.blend> [options]
```

Support bundles include `diagnostics/assets.json` for missing external image dependencies. `diagnostics/validate.json` is included for `Export Scene` failures, but omitted for Bake Textures & Export jobs because baking does not require the source material graph to be RealityKit-compatible.

**Options:**

| Flag | Description |
|------|-------------|
| `-o, --output <path>` | Existing exported `.usda`, `.usdc`, or `.usdz` path |
| `--bundle-output <path>` | Destination ZIP path |
| `--job-dir <path>` | Include a background bake/export job directory |
| `--diagnostics <path>` | Include a specific `.diagnostics.json` file |
| `--include-output` | Include exported USD/USDZ and sidecar assets |
| `--include-blend` | Include the source `.blend` file |
| `--full-log` | Include full redacted logs instead of the last 2000 lines |
| `--no-redact` | Disable redaction |

By default, bundles redact absolute paths, including JSON-escaped Windows path strings, and do not include the source `.blend` or exported assets. The default ZIP name is `BlenderToRCP-support-<blend-stem>-<timestamp>.zip`.

```bash
blendertorcp support-bundle scene.blend \
  -o /output/scene.usdz \
  --diagnostics /output/scene.diagnostics.json
```

For Blender UI background bake/export jobs, pass the job directory shown under `<export_dir>/.blendertorcp_jobs/<job_id>/`:

```bash
blendertorcp support-bundle scene.blend \
  -o /output/scene.usdz \
  --job-dir /output/.blendertorcp_jobs/bake_export_20260504_143012_abcd
```

---

### `preferences get`

Read addon-level preferences.

```bash
blendertorcp preferences get
```

**Output:**

```json
{
  "usdzip_path": "",
  "materialx_library_path": "",
  "default_export_format": "USDA",
  "enable_diagnostics": true
}
```

---

### `preferences set`

Modify addon-level preferences.

```bash
blendertorcp preferences set <key>=<value> [...]
```

**Available keys:**

| Key | Type | Description |
|-----|------|-------------|
| `usdzip_path` | string | Path to the usdzip tool (leave empty for Python fallback) |
| `materialx_library_path` | string | Path to MaterialX library directory (leave empty for bundled) |
| `default_export_format` | enum | `USDA`, `USDC`, or `USDZ` |
| `enable_diagnostics` | bool | Generate diagnostics JSON on export |

**Examples:**

```bash
blendertorcp preferences set default_export_format=USDZ enable_diagnostics=false
```

**Output:**

```json
{
  "updated": ["default_export_format", "enable_diagnostics"]
}
```

---

## Setting Keys Reference

Complete list of every export setting that can be read with `settings get`, written with `settings set`, or overridden as a flag on `export` and `bake-export`.

### Format & Output

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `filepath` | string | file path | `""` |
| `export_format` | enum | `USDA`, `USDC`, `USDZ` | `USDA` |
| `root_prim_name` | string | USD prim path | `/root` |

### General

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `export_animation` | bool | `true`, `false` | `false` |
| `selected_objects_only` | bool | `true`, `false` | `false` |
| `export_custom_properties` | bool | `true`, `false` | `true` |
| `custom_properties_namespace` | string | any | `userProperties` |
| `author_blender_name` | bool | `true`, `false` | `true` |
| `allow_unicode` | bool | `true`, `false` | `true` |
| `relative_paths` | bool | `true`, `false` | `true` |

### Orientation & Units

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `convert_orientation` | bool | `true`, `false` | `false` |
| `forward_axis` | enum | `X`, `Y`, `Z`, `-X`, `-Y`, `-Z` | `-Z` |
| `up_axis` | enum | `X`, `Y`, `Z`, `-X`, `-Y`, `-Z` | `Y` |
| `convert_scene_units` | enum | `METERS`, `KILOMETERS`, `CENTIMETERS`, `MILLIMETERS`, `INCHES`, `FEET`, `YARDS`, `CUSTOM` | `METERS` |
| `meters_per_unit` | float | 0.0001 – 1000.0 | `1.0` |

### Transform

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `xform_op_mode` | enum | `TRS`, `TOS`, `MAT` | `TRS` |
| `evaluation_mode` | enum | `RENDER`, `VIEWPORT` | `RENDER` |
| `use_instancing` | bool | `true`, `false` | `true` |
| `merge_parent_xform` | bool | `true`, `false` | `false` |

### Object Types

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `export_meshes` | bool | `true`, `false` | `true` |
| `export_lights` | bool | `true`, `false` | `true` |
| `convert_world_material` | bool | `true`, `false` | `true` |
| `export_cameras` | bool | `true`, `false` | `true` |
| `export_curves` | bool | `true`, `false` | `true` |
| `export_points` | bool | `true`, `false` | `true` |
| `export_volumes` | bool | `true`, `false` | `true` |
| `export_hair` | bool | `true`, `false` | `false` |

### Geometry

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `export_uvmaps` | bool | `true`, `false` | `true` |
| `rename_uvmaps` | bool | `true`, `false` | `true` |
| `export_normals` | bool | `true`, `false` | `true` |
| `triangulate_meshes` | bool | `true`, `false` | `false` |
| `quad_method` | enum | `SHORTEST_DIAGONAL`, `BEAUTY`, `FIXED`, `FIXED_ALTERNATE` | `SHORTEST_DIAGONAL` |
| `ngon_method` | enum | `BEAUTY`, `EAR_CLIP` | `BEAUTY` |
| `export_subdivision` | enum | `IGNORE`, `TESSELLATE`, `BEST_MATCH` | `BEST_MATCH` |

### Rigging

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `export_armatures` | bool | `true`, `false` | `true` |
| `only_deform_bones` | bool | `true`, `false` | `false` |
| `export_shapekeys` | bool | `true`, `false` | `true` |

### Bake

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `bake_mode` | enum | `UNLIT_ALBEDO`, `LIT_IBL` | `UNLIT_ALBEDO` |
| `bake_ibl_source` | enum | `SCENE_WORLD`, `HDRI_FILE` | `SCENE_WORLD` |
| `bake_ibl_filepath` | string | file path | `""` |
| `bake_ibl_strength` | float | 0.0+ | `1.0` |
| `bake_ibl_rotation` | float | radians | `0.0` |
| `bake_isolate_meshes_lit` | bool | `true`, `false` | `false` |
| `bake_resolution` | enum | `512`, `1024`, `2048`, `4096`, `CUSTOM` | `2048` |
| `bake_resolution_custom` | int | 32+ | `2048` |
| `bake_image_format` | enum | `AVIF`, `PNG` | `AVIF` |
| `bake_margin` | int | 0+ | `8` |
| `bake_base_color` | bool | `true`, `false` | `true` |
| `bake_opacity` | bool | `true`, `false` | `true` |
| `bake_keep_materials` | bool | `true`, `false` | `false` |
| `bake_step_timeout_seconds` | int | 0+ (0 = disabled) | `0` |

User-facing bake mode names in the Blender UI:
- `UNLIT_ALBEDO` appears as `Material Color Only`.
- `LIT_IBL` appears as `Lighting & Shadows`.

---

## Exit Codes

All commands use consistent exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Command failed (export error, validation error, invalid arguments) |
| 2 | Blender not found or failed to start |
| 3 | Plugin not installed or failed to load in Blender |

---

## Output Format

On success, commands print:
- **JSON** to **stdout** — machine-readable result
- **Status messages** to **stderr** — human-readable progress

Use `--json` to suppress all stderr output. Use `--quiet` to suppress stderr without affecting stdout. Use `--verbose` to include Blender's startup log on stderr.

On failure without `--json`, the CLI prints a short `Error: ...` message to stderr and includes diagnostics/support-bundle hints when the Blender runner returned them. With `--json`, failures are emitted to stdout as a structured envelope:

```json
{
  "ok": false,
  "schema_version": "1.0",
  "command": "export",
  "error": {
    "code": "POSTPROCESS_FAILED",
    "type": "CommandError",
    "message": "Postprocess failed",
    "stage": "postprocess_usd"
  },
  "context": {
    "blend_file": "scene.blend",
    "blender_path": "/Applications/Blender.app/Contents/MacOS/Blender",
    "returncode": 1
  },
  "artifacts": {
    "diagnostics_path": "/output/scene.diagnostics.json",
    "support_bundle_hint": "blendertorcp support-bundle scene.blend -o /output/scene.usdz --diagnostics /output/scene.diagnostics.json"
  },
  "process_output": {
    "stderr_tail": "..."
  }
}
```

For support captures, prefer saving stdout and stderr separately:

```bash
blendertorcp --verbose export scene.blend -o output.usdz --format USDZ \
  > blendertorcp-result.json \
  2> blendertorcp-stderr.log
```

If the command returns a `diagnostics_path`, attach that file. If the failure happened in Blender UI background bake/export, attach the job `settings.json`, `status.json`, and `log.txt`, or create a redacted ZIP with `support-bundle`.

Pipe-friendly:

```bash
# Parse output with jq
blendertorcp info scene.blend | jq '.object_count'

# Chain commands
FORMAT=$(blendertorcp settings get scene.blend --keys export_format | jq -r '.export_format')
echo "Current format: $FORMAT"

# Use in scripts
if blendertorcp validate scene.blend --strict; then
  blendertorcp export scene.blend -o output.usdz
else
  echo "Validation failed" >&2
fi
```
