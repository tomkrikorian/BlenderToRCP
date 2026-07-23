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

The CLI lives directly in the Blender extension root. Blender names an installed
extension directory from its manifest ID, so the canonical directory is
`blender_to_rcp` even though the display name is `BlenderToRCP`. The repository
directory is usually `user_default`, but it can be another configured repository
module.

| Workflow | Path |
|----------|------|
| macOS installed extension | `~/Library/Application Support/Blender/<version>/extensions/<repository>/blender_to_rcp/` |
| macOS development symlink | `~/Library/Application Support/Blender/<version>/extensions/user_default/blender_to_rcp/` |
| Linux installed extension | `~/.config/blender/<version>/extensions/<repository>/blender_to_rcp/` |
| Linux development symlink | `~/.config/blender/<version>/extensions/user_default/blender_to_rcp/` |
| Windows installed extension | `%APPDATA%\Blender Foundation\Blender\<version>\extensions\<repository>\blender_to_rcp\` |
| Windows development symlink | `%APPDATA%\Blender Foundation\Blender\<version>\extensions\user_default\blender_to_rcp\` |

Look for `cli/__main__.py` and `api/runner.py` directly under that
`blender_to_rcp/` directory. An older development symlink may still use the
display-name directory `BlenderToRCP`; it remains a useful fallback when
searching, but new installs and symlinks should use the manifest ID. In a
repository checkout, the equivalent directory is `<repo>/Plugin/`.

### 3. Run the CLI

```bash
# Installed extension root
python3 /path/to/blender_to_rcp version
python3 /path/to/blender_to_rcp preferences get
python3 /path/to/blender_to_rcp settings list

# Development checkout
python3 /path/to/repo/Plugin version
python3 /path/to/repo/Plugin preferences get
python3 /path/to/repo/Plugin settings list
```

### 4. (Optional) Create an alias for convenience

```bash
# Add to your shell profile for easy access
alias blendertorcp="python3 /path/to/blender_to_rcp"
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
| `--timeout <SEC>` | `600` | Overall Blender subprocess timeout in seconds; `0` disables the limit. Place before the subcommand |

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
  "plugin": "2.0.0",
  "blender": "5.2.0",
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

Check materials for RealityKit compatibility. Reports errors (nodes that block export) and warnings (nodes that require baking, unsupported Principled inputs such as Transmission/Sheen/Subsurface/Thin Wall, and DirectX-convention normal maps).

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
| `--materialx-surface-profile <PROFILE>` | Validate against `realitykit_portable`, `realitykit_pbr2`, or `openpbr_1_1` for this run. Defaults to the active scene setting |

**Examples:**

```bash
blendertorcp validate scene.blend
blendertorcp validate scene.blend --material "Wood"
blendertorcp validate scene.blend --strict
blendertorcp validate scene.blend --materialx-surface-profile realitykit_pbr2
```

`realitykit_portable` is the production default. The PBR Surface 2 and OpenPBR profiles are experimental and should be selected only for a pinned, validated OS 27 toolchain.

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
| `--group <name>` | Return settings from a panel group: `general`, `objects`, `geometry`, `rigging`, `texture`, `materials`, `bake`, `diagnostics`, or `all` (default) |

**Group breakdown:**

| Group | Settings included |
|-------|-------------------|
| `general` | `filepath`, `export_format`, `root_prim_name`, `export_animation`, `author_animation_library`, `selected_objects_only`, `export_custom_properties`, `custom_properties_namespace`, `author_blender_name`, `allow_unicode`, `relative_paths`, `convert_orientation`, `forward_axis`, `up_axis`, `convert_scene_units`, `meters_per_unit`, `xform_op_mode`, `evaluation_mode`, `use_instancing` |
| `objects` | `export_meshes` |
| `geometry` | `export_uvmaps`, `rename_uvmaps`, `export_normals`, `merge_parent_xform`, `triangulate_meshes`, `quad_method`, `ngon_method`, `export_subdivision` |
| `rigging` | `export_armatures`, `only_deform_bones`, `export_shapekeys` |
| `texture` | `export_texture_settings_enabled`, `bake_resolution`, `bake_resolution_custom`, `bake_image_format`, `bake_margin` |
| `materials` | `materialx_surface_profile` |
| `bake` | `bake_mode`, `bake_ibl_source`, `bake_ibl_filepath`, `bake_ibl_strength`, `bake_ibl_rotation`, `bake_isolate_meshes_lit`, `bake_base_color`, `bake_opacity`, `bake_keep_materials`, `bake_roughness_mode`, `apply_yup_geometry`, `bake_step_timeout_seconds` |
| `diagnostics` | `diagnostics_enabled` |

**Examples:**

```bash
blendertorcp settings get scene.blend
blendertorcp settings get scene.blend --group bake
blendertorcp settings get scene.blend --group texture
blendertorcp settings get scene.blend --group materials
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

Boolean `key=value` settings accept only `true`, `1`, or `yes` and `false`,
`0`, or `no` (case-insensitive, with surrounding whitespace ignored). Other
spellings such as `on`, `off`, or a typo fail with `INVALID_SETTING_VALUE`;
they are never silently treated as false. The same contract applies to
positional setting overrides for `export` and `bake-export`.

**Examples:**

```bash
blendertorcp settings set scene.blend export_format=USDZ
blendertorcp settings set scene.blend export_texture_settings_enabled=true bake_resolution=4096 bake_image_format=PNG --save
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
  "would_update": ["export_texture_settings_enabled", "bake_resolution", "bake_image_format"]
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
    "type": "ENUM",
    "values": ["ORIGINAL", "512", "1024", "2048", "4096", "CUSTOM"],
    "default": "2048",
    "group": "texture",
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
| `--diagnostics` | Write `<output>.diagnostics.json` |
| `--no-diagnostics` | Do not write diagnostics, even if enabled by settings |
| `--apply-yup` | Enforce `-Z` forward / `Y` up and bake a Y-up rotation into safe mesh data; unsafe animated, constrained, or skinned transforms fall back to root conversion |

Any export setting key can also be passed as a positional `key=value` override. These overrides apply for this export only and do not modify the `.blend` file:

```bash
blendertorcp export scene.blend \
  export-texture-settings-enabled=true \
  bake-image-format=AVIF \
  bake-resolution=1024 \
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
  "diagnostics_path": null,
  "support_bundle_hint": "blendertorcp support-bundle scene.blend -o /output/scene.usdz"
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
| Reusable baked textures that Reality Composer Pro or RealityKit can light | `bake-export --bake-mode UNLIT_ALBEDO` / `Material Color Only - Unlit`, or `--bake-mode LIT_ALBEDO` / `Material Color Only - Lit PBR` |
| Export that preserves Blender-looking lighting and shadows | `bake-export` default / `Lighting & Shadows` |

All three bake modes bake material color or lighting into the texture. `UNLIT_ALBEDO` and `LIT_IBL` export the final result as RealityKit Unlit materials; `LIT_ALBEDO` exports Lit PBR materials so Reality Composer Pro or RealityKit lights the baked color.

Bake/export preflights external dependencies used by the dependency-closed export scope, including collection prototypes, material and Geometry Nodes images, classic modifier textures, linked libraries, caches, Scene World lighting when active, and an explicit bake HDRI. Missing unpacked images fail with `MISSING_EXTERNAL_TEXTURES`; any missing non-image dependency fails with `MISSING_EXTERNAL_ASSETS`. Pack or relink textures, and relink libraries or caches, before retrying. Bake/export intentionally skips source material graph validation because unsupported Blender node groups are resolved by baking. Strict graph validation remains part of `blendertorcp export` and `blendertorcp validate`.

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
| `--bake-mode <MODE>` | from settings (`LIT_IBL` for fresh scenes) | `UNLIT_ALBEDO` for Material Color Only - Unlit, `LIT_ALBEDO` for Material Color Only - Lit PBR, `LIT_IBL` for Lighting & Shadows |
| `--resolution <RES>` | `2048` | Enables texture overrides for this run and sets bake/export texture resolution: `ORIGINAL`, `512`, `1024`, `2048`, `4096`, or any integer for custom |
| `--image-format <FMT>` | `AVIF` | Enables texture overrides for this run and sets baked/exported texture format: `ORIGINAL`, `AVIF`, or `PNG`. AVIF is encoded natively by Blender; no external tools required |
| `--margin <PX>` | `8` | Enables texture overrides for this run and sets bake padding in pixels |
| `--selected-only` | off | Only bake and export selected objects |
| `--diagnostics` | off | Write `<output>.diagnostics.json` |
| `--no-diagnostics` | off | Do not write diagnostics, even if enabled by settings |

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
| `--roughness-mode <MODE>` | `TEXTURE` | LIT_ALBEDO roughness output: `TEXTURE` (full map) or `AVERAGE` (constant) |
| `--apply-yup` | off | Enforce `-Z` forward / `Y` up and bake a Y-up rotation into safe mesh data; unsafe animated, constrained, or armature-deformed transforms fall back to root conversion |
| `--step-timeout <SEC>` | `0` (disabled) | Per-step worker timeout. Each bake, USD export, post-process, package, and cleanup step gets this budget independently. The CLI always emits a structured timeout error; diagnostics are written when enabled, and UI background jobs also persist terminal status. For the whole Blender process use global `--timeout` |

**Examples:**

```bash
# Lighting & Shadows bake at default settings
blendertorcp bake-export scene.blend -o /output/scene.usdz

# Material Color Only - Unlit bake
blendertorcp bake-export scene.blend -o /output/scene.usdz \
  --bake-mode UNLIT_ALBEDO

# Material Color Only - Lit PBR bake (RealityKit lights the baked color)
blendertorcp bake-export scene.blend -o /output/scene.usdz \
  --bake-mode LIT_ALBEDO

# High-res bake with PNG textures
blendertorcp bake-export scene.blend -o /output/scene.usdz \
  --resolution 4096 \
  --image-format PNG

# Lighting & Shadows bake with custom HDRI
blendertorcp bake-export scene.blend -o /output/scene.usdz \
  --ibl-source HDRI_FILE \
  --ibl-filepath /hdris/studio.hdr \
  --ibl-strength 1.5 \
  --isolate-meshes

# Bake only selected objects at low resolution for preview
blendertorcp bake-export scene.blend -o /tmp/preview.usdz \
  --resolution 512 \
  --selected-only

# Allow up to 15 minutes overall, but stop an individual stalled step after 5 minutes
blendertorcp --timeout 900 bake-export scene.blend -o /output/scene.usdz \
  --step-timeout 300
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
  "diagnostics_path": null,
  "support_bundle_hint": "blendertorcp support-bundle scene.blend -o /output/scene.usdz"
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
  "materialx_library_path": ""
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

**Examples:**

```bash
blendertorcp preferences set usdzip_path=/opt/usd/bin/usdzip
```

**Output:**

```json
{
  "updated": ["usdzip_path"]
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
| `author_animation_library` | bool | `true`, `false` | `false` |
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

Raw Blender cameras, lights, World dome lights, curves, point clouds, volumes,
and hair are not configurable export types in the portable RealityKit/RCP3
profile. Author cameras and lighting downstream, and convert unsupported
geometry to polygon meshes.

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

### Texture

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `export_texture_settings_enabled` | bool | `true`, `false` | `false` |
| `bake_resolution` | enum | `ORIGINAL`, `512`, `1024`, `2048`, `4096`, `CUSTOM` | `2048` |
| `bake_resolution_custom` | int | 32+ | `2048` |
| `bake_image_format` | enum | `ORIGINAL`, `AVIF`, `PNG` | `AVIF` |
| `bake_margin` | int | 0+ | `8` |

When `export_texture_settings_enabled` is `false`, `Export Scene` preserves Apple-compatible AVIF, PNG, JPEG, and OpenEXR encodings and normalizes other supported LDR inputs to PNG; `Bake Textures & Export` uses its internal defaults. When the setting is `true`, `Export Scene` can transcode eligible LDR textures to AVIF/PNG, resize them to the configured maximum resolution, or keep original dimensions. OpenEXR always remains byte-for-byte unchanged and ignores format/resize overrides to protect float/HDR data. Radiance HDR (`.hdr`) fails with remediation to convert it to OpenEXR instead of silently losing dynamic range. `Bake Textures & Export` uses concrete bake outputs; `ORIGINAL` format/resolution falls back to PNG/2048 for newly baked images because there is no source image to preserve.

### Materials

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `materialx_surface_profile` | enum | `realitykit_portable`, `realitykit_pbr2`, `openpbr_1_1` | `realitykit_portable` |

`realitykit_portable` is the verified default for current RealityKit, Reality Composer Pro, Quick Look, and USDKit workflows. `realitykit_pbr2` (PBR Surface 2) and `openpbr_1_1` (OpenPBR 1.1 / MaterialX 1.39) are experimental OS 27 profiles; opt into them only when the target Apple toolchain and runtime have been validated for the asset. PBR Surface 2 is currently intended for USDC-to-RCP3 experiments: Quick Look and USDKit are incompatible, and strict USD/USDZ validation can reject its nodedef. The exporter does not weaken USDZ validation for this profile.

### Diagnostics

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `diagnostics_enabled` | bool | `true`, `false` | `false` |

When `diagnostics_enabled` is `false`, exports do not write `<output>.diagnostics.json`. Use `--diagnostics` or `diagnostics-enabled=true` to enable the sidecar for a run.

### Bake

| Key | Type | Values | Default |
|-----|------|--------|---------|
| `bake_mode` | enum | `UNLIT_ALBEDO`, `LIT_ALBEDO`, `LIT_IBL` | `LIT_IBL` |
| `bake_ibl_source` | enum | `SCENE_WORLD`, `HDRI_FILE` | `SCENE_WORLD` |
| `bake_ibl_filepath` | string | file path | `""` |
| `bake_ibl_strength` | float | 0.0+ | `1.0` |
| `bake_ibl_rotation` | float | radians | `0.0` |
| `bake_isolate_meshes_lit` | bool | `true`, `false` | `false` |
| `bake_base_color` | bool | `true`, `false` | `true` |
| `bake_opacity` | bool | `true`, `false` | `true` |
| `bake_keep_materials` | bool | `true`, `false` | `false` |
| `bake_step_timeout_seconds` | int | 0+ (0 = disabled) | `0` |
| `bake_roughness_mode` | enum | `TEXTURE`, `AVERAGE` | `TEXTURE` |
| `apply_yup_geometry` | bool | `true`, `false` | `false` |

`apply_yup_geometry` bakes a -90° X rotation into mesh data so the export is natively Y-up, but only when `convert_orientation` is also enabled. The CLI convenience flag `--apply-yup` enables both settings. Geometry baking is auto-skipped for animated, constrained, or armature-deformed transforms, leaving root orientation conversion enabled as the safe fallback.

`bake_roughness_mode` only applies to `LIT_ALBEDO`: `TEXTURE` bakes a per-texel roughness map, `AVERAGE` uses one averaged roughness constant (no roughness texture exported).

User-facing bake mode names in the Blender UI:
- `UNLIT_ALBEDO` appears as `Material Color Only - Unlit`.
- `LIT_ALBEDO` appears as `Material Color Only - Lit PBR`.
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
