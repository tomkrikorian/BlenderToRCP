# BlenderToRCP CLI reference

This page documents the BlenderToRCP command-line interface: every command, flag, exit code, and error envelope. Use the CLI to run exports, bake textures, validate materials, and manage settings from a terminal, a script, or an automation agent.

How the CLI runs:

- Every command spawns Blender in background mode. On success, the command prints structured JSON to stdout. Human-readable status goes to stderr.
- Bake and export commands start Blender with factory startup, so unrelated user add-ons cannot affect the bake session.
- On failure, pass `--json` when automation needs the structured error envelope on stdout. Without `--json`, failures are summarized on stderr, with diagnostics and support-bundle hints when available.
- Each invocation runs in its own short-lived Blender process. Nothing carries over to the next invocation unless it was written to disk — see [`settings set --save`](#settings-set).

## Installation

The CLI ships inside the BlenderToRCP plugin. There is no separate installation: once the add-on is installed in Blender, the CLI is ready to use.

### 1. Tell the CLI where Blender is

```bash
export BLENDERTORCP_BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
```

Add this line to your shell profile (`.zshrc`, `.bashrc`), or pass `--blender` on each command instead.

### 2. Find your extension root

The CLI lives directly in the Blender extension root. Blender names an installed extension directory after its manifest ID, so the directory is `blender_to_rcp` even though the display name is BlenderToRCP. The repository directory is usually `user_default`, but it can be another configured repository module.

| Workflow | Path |
|----------|------|
| macOS installed extension | `~/Library/Application Support/Blender/<version>/extensions/<repository>/blender_to_rcp/` |
| macOS development symlink | `~/Library/Application Support/Blender/<version>/extensions/user_default/blender_to_rcp/` |
| Linux installed extension | `~/.config/blender/<version>/extensions/<repository>/blender_to_rcp/` |
| Linux development symlink | `~/.config/blender/<version>/extensions/user_default/blender_to_rcp/` |
| Windows installed extension | `%APPDATA%\Blender Foundation\Blender\<version>\extensions\<repository>\blender_to_rcp\` |
| Windows development symlink | `%APPDATA%\Blender Foundation\Blender\<version>\extensions\user_default\blender_to_rcp\` |

Look for `cli/__main__.py` and `api/runner.py` directly under that `blender_to_rcp/` directory. An older development symlink may still use the display-name directory `BlenderToRCP`; check it as a fallback when searching, but use the manifest ID for new installs and symlinks. In a repository checkout, the equivalent directory is `<repo>/Plugin/`.

### 3. Run the CLI

Run the CLI by pointing Python at the extension root:

```bash
python3 /path/to/blender_to_rcp version
```

```bash
python3 /path/to/blender_to_rcp preferences get
```

```bash
python3 /path/to/blender_to_rcp settings list
```

In a development checkout, use the `Plugin` directory instead:

```bash
python3 /path/to/repo/Plugin version
```

```bash
python3 /path/to/repo/Plugin preferences get
```

```bash
python3 /path/to/repo/Plugin settings list
```

### 4. (Optional) Create an alias for convenience

Add an alias to your shell profile:

```bash
alias blendertorcp="python3 /path/to/blender_to_rcp"
```

For a repository checkout:

```bash
alias blendertorcp="python3 /path/to/repo/Plugin"
```

Then run commands as:

```bash
blendertorcp <command> [options]
```

---

## Global options

These flags are available on every command.

| Flag | Default | Description |
|------|---------|-------------|
| `--blender <path>` | `$BLENDERTORCP_BLENDER` or `blender` | Path to the Blender executable |
| `--json` | off | JSON-only output: implies `--quiet` and puts failure envelopes on stdout |
| `--verbose` | off | Forward Blender's **stderr** to stderr. Not suppressed by `--json` or `--quiet` |
| `--quiet` | off | Suppress the CLI's own progress messages. Does **not** suppress failure messages |
| `--timeout <SEC>` | `600` | Overall Blender subprocess timeout in seconds; `0` disables the limit |

All five are top-level flags and must appear **before** the subcommand. Placing one after the subcommand is an argument error (exit 1):

```bash
blendertorcp version --timeout 30
```

```
Error: unrecognized arguments: --timeout 30
```

`--timeout` rejects negative and non-integer values with exit 1 and `INVALID_ARGUMENTS`:

```bash
blendertorcp --json --timeout -5 version
```

The envelope reports `error.message: "argument --timeout: timeout must be 0 or a positive number of seconds"`.

See [Output format](#output-format) for exactly what each of `--json`, `--verbose`, and `--quiet` does to each stream.

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
  "python": "3.13.13"
}
```

`version` is the only command that does not need the add-on to load, so it is the quickest way to check that `--blender` points at a working Blender.

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
  "object_count": 4,
  "material_count": 1
}
```

`material_count` counts materials assigned to scene objects, not every material datablock in the file. Use `list-materials --unused` to see the rest.

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
| `--type <TYPE>` | Filter by object type. Repeatable. Matched case-insensitively |
| `--selected` | Only list objects that are selected in the scene |

`--type` takes Blender's own `Object.type` identifiers. On Blender 5.2 the complete set is:

`MESH`, `CURVE`, `SURFACE`, `META`, `FONT`, `CURVES`, `POINTCLOUD`, `VOLUME`, `GREASEPENCIL`, `ARMATURE`, `LATTICE`, `EMPTY`, `LIGHT`, `LIGHT_PROBE`, `CAMERA`, `SPEAKER`.

Note `GREASEPENCIL` — the pre-4.3 spelling `GPENCIL` is not a Blender 5.2 identifier. The filter is **not** validated: an identifier that does not exist simply matches nothing, and the command still exits 0 with `[]`.

**Examples:**

List every object:

```bash
blendertorcp list-objects scene.blend
```

List one type:

```bash
blendertorcp list-objects scene.blend --type MESH
```

Repeat `--type` to combine filters:

```bash
blendertorcp list-objects scene.blend --type MESH --type LIGHT
```

Matching is case-insensitive:

```bash
blendertorcp list-objects scene.blend --type mesh
```

**Output:**

```json
[
  {
    "name": "Cube",
    "type": "MESH",
    "visible": true,
    "selected": false,
    "materials": ["SimpleMat"],
    "vertices": 8
  },
  {
    "name": "Sun",
    "type": "LIGHT",
    "visible": true,
    "selected": false,
    "materials": [],
    "light_type": "SUN"
  },
  {
    "name": "Pivot",
    "type": "EMPTY",
    "visible": true,
    "selected": true,
    "materials": []
  }
]
```

`vertices` is present only for `MESH` objects and `light_type` only for `LIGHT` objects. Every other entry carries just `name`, `type`, `visible`, `selected`, and `materials`.

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
    "name": "SimpleMat",
    "users": 1,
    "use_nodes": true,
    "node_count": 2
  },
  {
    "name": "UnusedMat",
    "users": 1,
    "use_nodes": true,
    "node_count": 2
  }
]
```

Only materials that survived the last save are listed. Blender drops zero-user datablocks when a `.blend` is written, so an "unused" material shows up here only if it was given a fake user (the shield icon) before saving.

---

### `validate`

Check materials with the same strict compatibility policy used by direct export. The report contains errors that block export and informational warnings that do not.

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
| `--only-errors` | Suppress warnings in output |
| `--materialx-surface-profile <PROFILE>` | Validate against `realitykit_portable`, `realitykit_pbr2`, or `openpbr_1_1` for this run. Defaults to the active scene setting |
| `--normalize-unsupported-values` | Preview the explicit export-only safe normalization policy; currently limited to constant achromatic overbright Principled Specular Tint |

**Examples:**

Validate every scene material:

```bash
blendertorcp validate scene.blend
```

Validate one material:

```bash
blendertorcp validate scene.blend --material "Wood"
```

Validate against a different surface profile for this run:

```bash
blendertorcp validate scene.blend --materialx-surface-profile realitykit_pbr2
```

Preview the normalization policy:

```bash
blendertorcp validate scene.blend --normalize-unsupported-values
```

`realitykit_portable` is the production default. The PBR Surface 2 and OpenPBR profiles are experimental; select them only for a pinned, validated OS 27 toolchain.

**Output:**

```json
{
  "ok": false,
  "error_count": 1,
  "materialx_surface_profile": "realitykit_portable",
  "normalize_unsupported_values": false,
  "materials": [
    {
      "name": "SimpleMat",
      "ok": false,
      "errors": [
        {
          "node_name": "Mix Shader",
          "node_type": "MIX_SHADER",
          "message": "Node is not supported by RealityKit export."
        }
      ],
      "warnings": []
    }
  ],
  "warning_count": 0
}
```

`materialx_surface_profile` and `normalize_unsupported_values` echo the policy the run was validated under, so a captured report is self-describing. `--only-errors` drops the `warnings` arrays and the top-level `warning_count` key entirely rather than zeroing them.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | All materials are compatible |
| 1 | One or more export-blocking errors found, **or** the run itself failed |

A failing *validation* is not a failing *command*: `validate` still prints the report above on stdout and only the top-level `ok` field is `false`. There is no `error` object, and `--json` changes nothing about the shape. Distinguish the two cases by testing for the `error` key:

```bash
blendertorcp --json validate scene.blend > report.json
if jq -e 'has("error")' report.json > /dev/null; then
  echo "validate itself failed: $(jq -r .error.code report.json)"
elif jq -e '.ok' report.json > /dev/null; then
  echo "all materials compatible"
else
  echo "export-blocking errors: $(jq -r .error_count report.json)"
fi
```

`--material <name>` with a name that is not in the file *is* a command failure (exit 1). It reports the generic `VALUEERROR` code with a Python traceback in the envelope, not a dedicated error code:

```bash
blendertorcp validate scene.blend --material NoSuchMat
```

```
Error: Material not found: 'NoSuchMat'
```

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
| `--group <name>` | Return settings from a panel group: `general`, `geometry`, `rigging`, `texture`, `materials`, `bake`, `diagnostics`, or `all` (default) |

`--keys` wins if both are given — `--group` is then ignored. An unknown key or group is a hard failure (exit 1):

```bash
blendertorcp settings get scene.blend --keys export_format nope_key
```

```
Error: Unknown setting key(s): nope_key. Use 'settings list' to see valid keys.
```

```bash
blendertorcp settings get scene.blend --group bogus
```

```
Error: Unknown group: 'bogus'. Available: ['bake', 'diagnostics', 'general', 'geometry', 'materials', 'rigging', 'texture']
```

**Group breakdown:**

| Group | Settings included |
|-------|-------------------|
| `general` | `filepath`, `export_format`, `root_prim_name`, `export_animation`, `author_animation_library`, `selected_objects_only`, `export_custom_properties`, `custom_properties_namespace`, `author_blender_name`, `allow_unicode`, `xform_op_mode`, `evaluation_mode`, `use_instancing` |
| `geometry` | `merge_parent_xform`, `triangulate_meshes`, `quad_method`, `ngon_method`, `export_subdivision` |
| `rigging` | `export_armatures`, `only_deform_bones`, `export_shapekeys` |
| `texture` | `export_texture_settings_enabled`, `bake_resolution`, `bake_resolution_custom`, `bake_image_format`, `bake_margin` |
| `materials` | `materialx_surface_profile`, `normalize_unsupported_values` |
| `bake` | `bake_mode`, `bake_ibl_source`, `bake_ibl_filepath`, `bake_ibl_strength`, `bake_ibl_rotation`, `bake_isolate_meshes_lit`, `bake_base_color`, `bake_opacity`, `bake_keep_materials`, `bake_roughness_mode`, `bake_step_timeout_seconds` |
| `diagnostics` | `diagnostics_enabled` |

**Examples:**

Read every setting:

```bash
blendertorcp settings get scene.blend
```

Read one group:

```bash
blendertorcp settings get scene.blend --group bake
```

```bash
blendertorcp settings get scene.blend --group texture
```

```bash
blendertorcp settings get scene.blend --group materials
```

Read specific keys:

```bash
blendertorcp settings get scene.blend --keys export_format bake_resolution
```

**Output** (`--group materials`):

```json
{
  "materialx_surface_profile": "realitykit_portable",
  "normalize_unsupported_values": false
}
```

Values come back in their native JSON types — booleans as `true`/`false`, `bake_resolution` and the other enums as strings.

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
| `--save` | **Required to change the file.** Save the `.blend` after applying settings |
| `--dry-run` | Validate the keys and values without applying them |

> ### `--save` is required to change the file
>
> Every command runs in a short-lived `blender --background` worker. Without `--save`, the values are applied to that worker and discarded when it exits. The command still exits 0 and still lists the keys under `updated`, so `updated` alone is not evidence that anything was written — check `saved`. Without `--save`, the result carries `"saved": false` plus an explicit warning.

Boolean `key=value` settings accept only `true`, `1`, or `yes` and `false`, `0`, or `no` (case-insensitive, with surrounding whitespace ignored). Other spellings such as `on`, `off`, or a typo fail with `INVALID_SETTING_VALUE`; they are never silently treated as false. The same contract applies to positional setting overrides for `export` and `bake-export`.

**Examples:**

Change one setting and save:

```bash
blendertorcp settings set scene.blend export_format=USDZ --save
```

Change several settings at once:

```bash
blendertorcp settings set scene.blend export_texture_settings_enabled=true bake_resolution=4096 bake_image_format=PNG --save
```

Validate without writing:

```bash
blendertorcp settings set scene.blend triangulate_meshes=true quad_method=BEAUTY --dry-run
```

**Output** without `--save`:

```json
{
  "updated": ["export_format"],
  "saved": false,
  "warnings": [
    "Settings were applied to a temporary Blender session and NOT written to the .blend. Re-run with --save to persist them."
  ]
}
```

**Output** with `--save`:

```json
{
  "updated": ["export_format"],
  "saved": true
}
```

The `warnings` key is present only when `--save` was omitted.

With `--dry-run`:

```json
{
  "valid": true,
  "would_update": ["triangulate_meshes", "quad_method"]
}
```

`--dry-run` implies "do not write" and takes precedence over `--save`. `valid` is only ever `true`: an unknown key or a rejected value is a command *failure* (exit 1) whether or not `--dry-run` was passed, so a `--dry-run` that exits 0 is the pass signal.

```bash
blendertorcp settings set scene.blend export_format=FOO --dry-run
```

```
Error: Invalid setting value.
```

The plain-stderr message is only the summary line. The actionable part — which key, which value, which values were allowed — lives in `error.details` and is visible only with `--json`:

```bash
blendertorcp --json settings set scene.blend export_animation=on
```

The envelope reports:

```
error.details[0].reason:
  "Invalid boolean value 'on' for 'export_animation'.
   Allowed true tokens: ['true', '1', 'yes']; allowed false tokens: ['false', '0', 'no']"
```

**Error codes:** `INVALID_SETTING_FORMAT` (a token with no `=`, raised by the CLI before Blender starts), `INVALID_SETTING_OVERRIDE` (unknown or internal key), `INVALID_SETTING_VALUE` (value rejected for a known key), `SETTINGS_SAVE_FAILED` (`--save` given but the save was refused, or the `.blend` has no filepath).

---

### `settings list`

List all available setting keys with their types and allowed values.

```bash
blendertorcp settings list
```

This command takes no arguments and does not require a `.blend` file. It still spawns Blender, because the schema is read from the registered add-on. It prints one record for each of the 40 export settings.

**Output** (abridged):

```json
[
  {
    "key": "export_format",
    "type": "ENUM",
    "description": "Export format and file extension",
    "group": "general",
    "values": ["USDA", "USDC", "USDZ", "RCP_IMPORT"],
    "default": "USDA"
  },
  {
    "key": "root_prim_name",
    "type": "STRING",
    "description": "Root prim path or name (e.g. /root or Scene)",
    "group": "general",
    "default": "/root"
  },
  {
    "key": "export_animation",
    "type": "BOOLEAN",
    "description": "Include animation data in the USD export",
    "group": "general",
    "default": false
  }
]
```

`type` is one of `BOOLEAN`, `INT`, `FLOAT`, `STRING`, or `ENUM` (upper case). `values` is present only for `ENUM`. `group` matches the `--group` names used by `settings get`. This command is the authoritative list of setting keys — prefer it over any table in the docs.

---

### `export`

Export the scene to USD, USDZ, or the experimental RCP 3 `.import` directory.

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
| `--format <FORMAT>` | Override export format: `USDA`, `USDC`, `USDZ`, or experimental `RCP_IMPORT` |
| `--selected-only` | Export selected objects only |
| `--diagnostics` | Keep `<output>.diagnostics.json` after a successful export |
| `--no-diagnostics` | Do not keep success diagnostics, even if enabled by settings. Failures still write diagnostics |

If both `--diagnostics` and `--no-diagnostics` are given, `--no-diagnostics` wins.

#### The format decides the extension, not `-o`

`-o` names the output *stem*. The exporter then forces the extension that matches the effective format — `--format` if given, otherwise the `.blend`'s saved `export_format` setting. Passing an extension that disagrees does not change the format and does not warn; the extension is simply rewritten.

For example, with `export_format=USDA` saved in the scene (the default):

```bash
blendertorcp export scene.blend -o /output/scene.usdz
```

The result reports:

```
"export_path": "/output/scene.usda",
"format": "USDA",
```

Extension replacement is applied to the last dot in the name, so a versioned stem loses its suffix:

```bash
blendertorcp export scene.blend -o /output/my.scene.v2
```

```
"export_path": "/output/my.scene.usda",
```

Pass `--format` (or set `export_format`) whenever the format matters, and read `export_path` from the result rather than assuming the path you passed.

#### Positional `key=value` overrides

Any key from `settings list` can be passed as a positional `key=value` token. Overrides apply to this run only and never modify the `.blend`.

Both spellings of a key are accepted — hyphens are folded to underscores before lookup, so `bake-resolution=1024` and `bake_resolution=1024` are the same override. Values are **not** transformed: enum values keep their exact spelling and case.

**Argument order:** `<file.blend>` and the override tokens are positionals, and argparse needs them as one uninterrupted run. Flags may come before or after that run, but never inside it.

Blend file, then overrides, with flags afterwards:

```bash
blendertorcp export scene.blend export-animation=true triangulate_meshes=true \
  -o out.usda --format USDA
```

Flags first, then the positional run:

```bash
blendertorcp export --selected-only scene.blend export-animation=true -o out.usda
```

```bash
blendertorcp export -o out.usda scene.blend export-animation=true
```

A flag inside the positional run fails:

```bash
blendertorcp export scene.blend -o out.usda export-animation=true
```

```
Error: unrecognized arguments: export-animation=true
```

A token with no `=` is rejected by the CLI before Blender starts, with `INVALID_OVERRIDE`. An unknown key is rejected by Blender with `INVALID_SETTING_OVERRIDE`, and a bad value with `INVALID_SETTING_VALUE` — both list the offending key in `error.details` when `--json` is used:

```bash
blendertorcp --json export scene.blend bake-resolution=true -o out.usda
```

The envelope reports:

```
error.code:    "INVALID_SETTING_VALUE"
error.details[0].reason:
  "Invalid value 'true' for 'bake_resolution'.
   Allowed: ['1024', '2048', '4096', '512', 'CUSTOM', 'ORIGINAL']"
```

A worked example that runs as written:

```bash
blendertorcp export scene.blend \
  export-animation=true \
  triangulate_meshes=true \
  root-prim-name=/MyRoot \
  export-texture-settings-enabled=true \
  bake-resolution=1024 \
  bake-image-format=PNG \
  -o /output/scene.usda \
  --format USDA
```

**Examples:**

Simple USDZ export:

```bash
blendertorcp export scene.blend -o /output/scene.usdz --format USDZ
```

Export with overrides:

```bash
blendertorcp export scene.blend \
  export-animation=true \
  -o /output/scene.usda \
  --format USDA \
  --selected-only
```

Experimental RCP 3 private package plus its adjacent USDA source:

```bash
blendertorcp export scene.blend \
  -o /output/scene.import \
  --format RCP_IMPORT
```

Every export uses the non-configurable Apple spatial contract: Blender's native orientation conversion, `-Z` forward, `Y` up, meters at `metersPerUnit=1`, relative dependencies, and mesh/UV/normal export.

**Output:**

```json
{
  "ok": true,
  "export_path": "/output/scene.usdz",
  "format": "USDZ",
  "duration_seconds": 0.3,
  "diagnostics_path": null,
  "support_bundle_hint": "blendertorcp support-bundle scene.blend -o /output/scene.usdz"
}
```

`diagnostics_path` is `null` unless success diagnostics were retained. For `RCP_IMPORT`, `export_path` is the `.import` directory and the post-processed `.usda` is published beside it.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Export completed successfully |
| 1 | Export failed (unsupported materials, bad overrides, file errors, timeout) |
| 2 | Blender not found or failed to start |
| 3 | Addon failed to load inside Blender |
| 130 | Interrupted with Ctrl-C |

**Error codes** `export` can emit:

| Code | Raised by | Meaning |
|------|-----------|---------|
| `INVALID_OVERRIDE` | CLI | An override token has no `=` |
| `INVALID_SETTING_OVERRIDE` | Blender | Override names an unknown or internal setting |
| `INVALID_SETTING_VALUE` | Blender | Override value rejected for that setting |
| `RCP_IMPORT_EXISTS` | Blender | `--format RCP_IMPORT` and the `.import` directory already exists; nothing is overwritten |
| `INVALID_EXPORT_SELECTION` | Blender | The selected object set could not be resolved |
| `NO_EXPORTABLE_OBJECTS` | Blender | `--selected-only` with nothing selected |
| `UNSUPPORTED_MATERIAL_NODES` | Blender | Strict material-graph validation failed |
| `BLENDER_USD_EXPORT_FAILED` | Blender | Blender's own USD exporter failed |
| `POSTPROCESS_FAILED` | Blender | USD post-processing failed |
| `EXPORT_FAILED` | Blender | Catch-all for anything else in the export stage |

`RCP_IMPORT_EXISTS` is a deliberate refusal, not a crash — remove or rename the existing directory and rerun:

```bash
blendertorcp --json export scene.blend -o /output/pkg.import --format RCP_IMPORT
```

The envelope reports:

```
error.code:    "RCP_IMPORT_EXISTS"
error.message: "Refusing to overwrite existing .import directory: /output/pkg.import"
```

---

### `bake-export`

Bake textures and export the scene. The Blender UI reaches this command through its single Export button whenever the selected material type and profile options require baking.

Choose a bake mode by goal:

| Goal | Use |
|------|-----|
| Translate compatible RealityKit PBR materials | `blendertorcp export` / `RealityKit PBR` → `Translate Materials` |
| Bake materials and keep dynamic RealityKit lighting | `bake-export --bake-mode LIT_ALBEDO` / `RealityKit PBR` → `Bake Materials` |
| Export unlit material color | `bake-export --bake-mode UNLIT_ALBEDO` / `RealityKit Unlit` → `Material Color Only` |
| Preserve Blender lighting and shadows | `bake-export --bake-mode LIT_IBL` / `RealityKit Unlit` → `Lighting & Shadows` |

All three bake modes bake material color or lighting into the texture. `UNLIT_ALBEDO` and `LIT_IBL` export the final result as RealityKit Unlit materials. `LIT_ALBEDO` exports Lit PBR materials, so Reality Composer Pro or RealityKit lights the baked color.

Before baking, the command preflights the external dependencies used by the dependency-closed export scope: collection prototypes, material and Geometry Nodes images, classic modifier textures, linked libraries, caches, Scene World lighting when active, and an explicit bake HDRI. Missing unpacked images fail with `MISSING_EXTERNAL_TEXTURES`; any missing non-image dependency fails with `MISSING_EXTERNAL_ASSETS`. Pack or relink textures, and relink libraries or caches, before retrying.

`bake-export` intentionally skips source material-graph validation, because baking is what resolves unsupported Blender node groups. Strict graph validation remains part of `blendertorcp export` and `blendertorcp validate`.

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
| `--format <FORMAT>` | from settings | Export format: `USDA`, `USDC`, `USDZ`, or experimental `RCP_IMPORT` |
| `--bake-mode <MODE>` | from settings (`LIT_IBL` for fresh scenes) | `UNLIT_ALBEDO` for Material Color Only - Unlit, `LIT_ALBEDO` for Material Color Only - Lit PBR, `LIT_IBL` for Lighting & Shadows |
| `--resolution <RES>` | setting (`ORIGINAL`) | Enables texture overrides for this run and sets bake/export texture resolution: `ORIGINAL`, `512`, `1024`, `2048`, `4096`, or any integer for custom. `ORIGINAL` sizes each material from its own source textures, floored at 512 |
| `--image-format <FMT>` | `AVIF` | Enables texture overrides for this run and sets baked/exported texture format: `ORIGINAL`, `AVIF`, or `PNG`. AVIF is encoded natively by Blender; no external tools required |
| `--margin <PX>` | `8` | Enables texture overrides for this run and sets bake padding in pixels |
| `--selected-only` | off | Only bake and export selected objects |
| `--diagnostics` | off | Keep `<output>.diagnostics.json` after success |
| `--no-diagnostics` | off | Suppress success diagnostics; failures still write diagnostics |

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
| `--step-timeout <SEC>` | `0` (disabled) | Per-step worker timeout. Each bake, USD export, post-process, package, and cleanup step gets this budget independently. The CLI always emits a structured timeout error and failure diagnostics; UI background jobs also persist terminal status. For the whole Blender process, use the global `--timeout` |

`bake-export` also accepts positional `key=value` overrides on exactly the same terms as [`export`](#positional-keyvalue-overrides), and `-o` names a stem whose extension is rewritten to match the effective format in exactly the same way. `--roughness-mode` is shorthand for the `bake_roughness_mode` override.

`--resolution` is not constrained by argparse — anything that is not `ORIGINAL` (or its alias `KEEP_ORIGINAL`) or one of `512`/`1024`/`2048`/`4096` is parsed as a custom integer. A non-numeric value therefore fails inside Blender with `INVALID_SETTING_OVERRIDE`, not `INVALID_SETTING_VALUE`:

```bash
blendertorcp --json bake-export scene.blend -o out.usdz --format USDZ --resolution abc
```

The envelope reports:

```
error.code:              "INVALID_SETTING_OVERRIDE"
error.details[0].reason: "invalid literal for int() with base 10: 'abc'"
```

`--step-timeout` and the global `--timeout` are different budgets and produce different errors. A step timeout terminates the Blender worker (which exits `124`) and surfaces as a structured `BAKE_STEP_TIMEOUT` error naming the step; the CLI process still exits `1`:

```bash
blendertorcp --json bake-export scene.blend -o /output/scene.usdz \
    --resolution 4096 --step-timeout 1
```

The envelope reports:

```
error.code:    "BAKE_STEP_TIMEOUT"
error.stage:   "Step 1/1 - Baking lighting and shadows [1/1] - Cube"
error.details: {"timeout_seconds": 1, "elapsed_seconds": 1.02}
context.returncode: 124        <- Blender's exit code, not the CLI's
```

A global `--timeout` expiry kills Blender before it can report anything, so there is no diagnostics sidecar and no stage — only `BLENDER_TIMEOUT`, also exit `1`.

**Examples:**

Pass `--format` in every example below that names a `.usdz` output: without it, the format comes from the `.blend`'s `export_format` setting, and a scene left at the `USDA` default silently writes `scene.usda` instead.

Lighting & Shadows bake at default settings:

```bash
blendertorcp bake-export scene.blend -o /output/scene.usdz --format USDZ
```

Material Color Only - Unlit bake:

```bash
blendertorcp bake-export scene.blend -o /output/scene.usdz --format USDZ \
  --bake-mode UNLIT_ALBEDO
```

Material Color Only - Lit PBR bake (RealityKit lights the baked color):

```bash
blendertorcp bake-export scene.blend -o /output/scene.usdz --format USDZ \
  --bake-mode LIT_ALBEDO \
  --roughness-mode AVERAGE
```

High-resolution bake with PNG textures:

```bash
blendertorcp bake-export scene.blend -o /output/scene.usdz --format USDZ \
  --resolution 4096 \
  --image-format PNG \
  --margin 4
```

Experimental RCP 3 private package plus its adjacent USDA source:

```bash
blendertorcp bake-export scene.blend -o /output/scene.import \
  --format RCP_IMPORT \
  --bake-mode LIT_IBL
```

Lighting & Shadows bake with a custom HDRI:

```bash
blendertorcp bake-export scene.blend -o /output/scene.usdz --format USDZ \
  --ibl-source HDRI_FILE \
  --ibl-filepath /hdris/studio.hdr \
  --ibl-strength 1.5 \
  --ibl-rotation 0.785 \
  --isolate-meshes
```

Skip the opacity channel and keep the baked materials in the session:

```bash
blendertorcp bake-export scene.blend -o /output/scene.usdz --format USDZ \
  --resolution 512 \
  --no-opacity \
  --keep-materials
```

Bake only selected objects at low resolution for preview:

```bash
blendertorcp bake-export scene.blend -o /tmp/preview.usdz --format USDZ \
  --resolution 512 \
  --selected-only
```

Allow up to 15 minutes overall, but stop an individual stalled step after 5 minutes:

```bash
blendertorcp --timeout 900 bake-export scene.blend -o /output/scene.usdz --format USDZ \
  --step-timeout 300
```

**Output:**

For `RCP_IMPORT`, the output path is a directory and the command also publishes the post-processed `.usda` source beside it. This lane is pinned to RCP 3.0 build `80.0.1.500.1`. Its current limits:

- Static scenes may contain multiple mesh objects and shared materials.
- Single- or multi-mesh skeletal inputs are structurally generated only when every mesh shares the same rig, skeleton, and animation contract. The multi-mesh skeletal lane has not yet been verified through Reality Composer Pro reimport and Sequence Editor playback.
- A USD mesh with multiple face materials is currently split into one generated RCP mesh resource per material. That representation preserves faces, UVs, normals, skin weights, and material appearance; opens and renders in Reality Composer Pro; and passes public RealityKit source-runtime checks. It is not RCP-compatible yet: a second genuine reimport duplicates resources, because Reality Composer Pro itself authors a different combined descriptor with nested `subsets`. The single-descriptor subset representation the writer needs to adopt is documented in [`RCP_IMPORT_MULTI_MATERIAL_MESH.md`](RCP_IMPORT_MULTI_MATERIAL_MESH.md); the acceptance bar is two reimports that do not grow the project.
- Baked RGBA base color (including merged opacity) is supported per material for all three bake modes; `LIT_ALBEDO` also supports each material's baked roughness map. Normal, metallic, occlusion, and independent opacity texture records remain unsupported.
- Multi-mesh transform animation and mixed rig or skeleton contracts fail closed.

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

`bake_stats` is present only on `bake-export` results. `resolution` is reported as an integer even though `--resolution` accepts the `ORIGINAL`/`512`/… enum spellings.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Bake and export completed successfully |
| 1 | Bake or export failed, including `--step-timeout` and `--timeout` expiry |
| 2 | Blender not found or failed to start |
| 3 | Addon failed to load inside Blender |
| 130 | Interrupted with Ctrl-C |

**Error codes** `bake-export` can emit:

| Code | Meaning |
|------|---------|
| `INVALID_OVERRIDE` | An override token has no `=` (raised by the CLI) |
| `INVALID_SETTING_OVERRIDE` | Override names an unknown or internal setting |
| `INVALID_SETTING_VALUE` | Override value rejected for that setting |
| `RCP_IMPORT_EXISTS` | `--format RCP_IMPORT` and the `.import` directory already exists |
| `NO_EXPORTABLE_OBJECTS` | `--selected-only` with nothing selected |
| `MISSING_EXTERNAL_TEXTURES` | Unpacked source images are missing (preflight) |
| `MISSING_EXTERNAL_ASSETS` | A non-image dependency is missing (preflight) |
| `BAKE_STEP_TIMEOUT` | `--step-timeout` expired; the worker was terminated |
| `BLENDER_USD_EXPORT_FAILED` | Blender's own USD exporter failed |
| `POSTPROCESS_FAILED` | USD post-processing failed |
| `BAKE_EXPORT_FAILED` | Catch-all for anything else in the bake/export stage |

Unlike `export`, `bake-export` never emits `UNSUPPORTED_MATERIAL_NODES` — it skips strict material-graph validation on purpose, because baking is what resolves unsupported node groups.

---

### `support-bundle`

Create a redacted ZIP with the files support needs to diagnose an export or bake failure.

```bash
blendertorcp support-bundle <file.blend> [options]
```

Support bundles include `diagnostics/assets.json` for missing external image dependencies. `diagnostics/validate.json` is included for `Export Scene` failures, but omitted for Bake Textures & Export jobs, because baking does not require the source material graph to be RealityKit-compatible.

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

The `.blend` file is the only required argument; every other input is optional, and the command succeeds with whatever it was given.

By default, bundles redact absolute paths, including JSON-escaped Windows path strings, and do not include the source `.blend` or exported assets. The default ZIP name is `BlenderToRCP-support-<blend-stem>-<YYYYMMDD-HHMMSS>.zip`, written next to `--output` when given.

**Output:**

```json
{
  "support_bundle_path": "/output/BlenderToRCP-support-scene-20260729-142644.zip",
  "file_count": 7,
  "redacted": true,
  "included_output": false,
  "included_blend": false
}
```

Without `--json` or `--quiet`, the resolved ZIP path is also echoed to stderr.

Note that `--diagnostics` here **takes a path**, unlike the boolean `--diagnostics` switch on `export` and `bake-export`:

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

Read add-on-level preferences.

```bash
blendertorcp preferences get
```

**Output:**

```json
{
  "usdzip_path": ""
}
```

---

### `preferences set`

Modify add-on-level preferences.

```bash
blendertorcp preferences set <key>=<value> [...]
```

**Available keys:**

| Key | Type | Description |
|-----|------|-------------|
| `usdzip_path` | string | Path to the usdzip tool (leave empty for Python fallback) |

**Examples:**

Set a preference:

```bash
blendertorcp preferences set usdzip_path=/opt/usd/bin/usdzip
```

Clear a preference by assigning an empty value:

```bash
blendertorcp preferences set usdzip_path=
```

**Output:**

```json
{
  "updated": ["usdzip_path"]
}
```

> **`preferences set` writes immediately — there is no `--save` and no `--dry-run`.** Unlike `settings set`, which needs `--save` to touch the `.blend`, this command calls Blender's *Save Preferences* on your real user preferences file before returning. The change is global to your Blender install and survives the process. Re-read with `preferences get` to confirm, and re-run with the previous value to undo.

An unknown key aborts the whole call before anything is saved, and reports the generic `VALUEERROR` code:

```bash
blendertorcp preferences set bogus_key=1
```

```
Error: Unknown preference key: 'bogus_key'. Available: ['usdzip_path']
```

---

## Setting keys

Every export setting can be read with `settings get`, written with `settings set`, or applied to a single run as a positional `key=value` override on `export` and `bake-export`.

**`settings list` is the authoritative reference.** It prints the live schema — key, type, allowed values, default, and group — straight out of the registered add-on, so it can never drift from the build you are running:

```bash
blendertorcp settings list | jq '.[] | select(.group == "bake")'
```

For prose describing what each setting *means*, see [`SETTINGS.md`](SETTINGS.md). This page covers only how settings reach the command line.

### Value syntax on the command line

Everything on the command line arrives as a string and is coerced by the setting's declared type.

| Type | Accepted spelling |
|------|-------------------|
| `BOOLEAN` | `true`, `1`, `yes` / `false`, `0`, `no` — case-insensitive, surrounding whitespace ignored. Nothing else, including `on` and `off` |
| `ENUM` | Exactly one of the `values` from `settings list`, case-sensitive |
| `INT`, `FLOAT` | A plain number |
| `STRING` | Taken literally; quote it if it contains spaces |

A rejected value is a hard failure (exit 1, `INVALID_SETTING_VALUE`) — a booleanish typo is never silently read as `false`. Key names accept hyphens or underscores interchangeably; values never do.

### Groups

`settings get --group <name>` accepts `all` (the default) plus the seven groups below. They match the panel layout in the Blender UI.

| Group | Settings |
|-------|----------|
| `general` | `filepath`, `export_format`, `root_prim_name`, `export_animation`, `author_animation_library`, `selected_objects_only`, `export_custom_properties`, `custom_properties_namespace`, `author_blender_name`, `allow_unicode`, `xform_op_mode`, `evaluation_mode`, `use_instancing` |
| `geometry` | `merge_parent_xform`, `triangulate_meshes`, `quad_method`, `ngon_method`, `export_subdivision` |
| `rigging` | `export_armatures`, `only_deform_bones`, `export_shapekeys` |
| `texture` | `export_texture_settings_enabled`, `bake_resolution`, `bake_resolution_custom`, `bake_image_format`, `bake_margin` |
| `materials` | `materialx_surface_profile`, `normalize_unsupported_values` |
| `bake` | `bake_mode`, `bake_ibl_source`, `bake_ibl_filepath`, `bake_ibl_strength`, `bake_ibl_rotation`, `bake_isolate_meshes_lit`, `bake_step_timeout_seconds`, `bake_base_color`, `bake_opacity`, `bake_keep_materials`, `bake_roughness_mode` |
| `diagnostics` | `diagnostics_enabled` |

### Settings with a dedicated flag

Some settings have a flag on `export` or `bake-export`. The flag and the override are two routes to the same value; use whichever reads better.

| Flag | Equivalent setting |
|------|--------------------|
| `--format` | `export_format` |
| `--selected-only` | `selected_objects_only` |
| `--diagnostics` / `--no-diagnostics` | `diagnostics_enabled` (success sidecars only) |
| `--bake-mode` | `bake_mode` |
| `--resolution` | `bake_resolution` (+ `bake_resolution_custom`) |
| `--image-format` | `bake_image_format` |
| `--margin` | `bake_margin` |
| `--ibl-source`, `--ibl-filepath`, `--ibl-strength`, `--ibl-rotation` | `bake_ibl_*` |
| `--isolate-meshes` | `bake_isolate_meshes_lit` |
| `--no-base-color`, `--no-opacity` | `bake_base_color`, `bake_opacity` (inverted) |
| `--keep-materials` | `bake_keep_materials` |
| `--roughness-mode` | `bake_roughness_mode` |
| `--step-timeout` | `bake_step_timeout_seconds` |
| `--materialx-surface-profile` (`validate`) | `materialx_surface_profile` |
| `--normalize-unsupported-values` (`validate`) | `normalize_unsupported_values` |

`--resolution`, `--image-format`, and `--margin` also switch `export_texture_settings_enabled` on for the run — that is why they work on a scene where texture overrides are off.

`validate` has no flag for the rest; use overrides on `export` instead:

```bash
blendertorcp export scene.blend normalize-unsupported-values=true -o scene.usdc --diagnostics
```

### Diagnostics sidecars

Failures **always** write `<output>.diagnostics.json`, including failures rejected before any geometry is touched (a bad override, `RCP_IMPORT_EXISTS`). `diagnostics_enabled`, `--diagnostics`, and `--no-diagnostics` only decide whether a *successful* run keeps its sidecar, and `--no-diagnostics` wins if both flags are passed.

### Bake mode names

The `--bake-mode` / `bake_mode` identifiers map to these Blender UI labels:

| Identifier | Blender UI |
|------------|------------|
| `UNLIT_ALBEDO` | Material Color Only - Unlit |
| `LIT_ALBEDO` | Material Color Only - Lit PBR |
| `LIT_IBL` | Lighting & Shadows |

`bake_roughness_mode` applies to `LIT_ALBEDO` only: `TEXTURE` bakes a per-texel roughness map, `AVERAGE` uses one averaged constant and exports no roughness texture.

### Materials profiles

`realitykit_portable` is the verified default for current RealityKit and Reality Composer Pro workflows. `realitykit_pbr2` (PBR Surface 2) and `openpbr_1_1` (OpenPBR 1.1 / MaterialX 1.39) are experimental OS 27 profiles; opt into them only when the target Apple toolchain and runtime have been validated for the asset. The exporter does not weaken USDZ validation for experimental profiles.

`normalize_unsupported_values=false` preserves the fail-closed default. When enabled, the exporter may clamp only an unlinked constant achromatic Principled `Specular Tint` above `1` to `[1, 1, 1]` in temporary export data. It emits a prominent warning and does not assign to the Blender node or save the `.blend`. Colored, linked, negative, non-finite, and other unsupported values remain errors.

---

## Exit codes

These four codes plus `0` are the complete set the CLI can return. There is no `124` and no `4`+.

| Code | Meaning | Reached by |
|------|---------|-----------|
| 0 | Success | The command ran and its result did not carry `ok: false` |
| 1 | Command failed | Any Blender-side error, any invalid argument or override, a `--timeout` or `--step-timeout` expiry, and a `validate` run that found export-blocking errors |
| 2 | Blender not found or failed to start | `BLENDER_NOT_FOUND`, `BLENDER_START_FAILED` |
| 3 | Addon failed to load in Blender | `ADDON_LOAD_FAILED` |
| 130 | Interrupted by the user | `SIGINT` / Ctrl-C, reported as `INTERRUPTED` |

`--help` exits `0`, like any other successful command.

Three things are **not** distinguished by exit code:

- A timeout is exit `1`, not `124`. When `--step-timeout` fires, the *Blender worker* exits `124`; that value surfaces only as `context.returncode` inside the envelope. The CLI process itself still returns `1`.
- A `validate` run that finds material errors is exit `1`, the same as a `validate` run that could not execute at all. Test for the `error` key to tell them apart — see [`validate`](#validate).
- Bad arguments are exit `1`, not the conventional argparse `2`. `2` is reserved for "Blender did not start".

Exit code 130 is produced for a Ctrl-C at any point, including while Blender is mid-bake. For example, interrupting this command:

```bash
blendertorcp --json bake-export scene.blend -o out.usdz --format USDZ
```

prints this envelope on stdout:

```json
{
  "ok": false,
  "schema_version": "1.0",
  "command": "bake_export",
  "error": {
    "code": "INTERRUPTED",
    "type": "KeyboardInterrupt",
    "message": "Command interrupted by user."
  },
  "context": {},
  "artifacts": {}
}
```

Without `--json`, the same interrupt prints `Aborted.` to stderr and nothing to stdout.

---

## Error codes

`error.code` is the stable machine-readable identifier; `error.message` is not. Branch on the code.

**Raised by the CLI, before Blender starts** (no `context`, no `artifacts`):

| Code | Meaning |
|------|---------|
| `INVALID_ARGUMENTS` | argparse rejected the command line |
| `INVALID_OVERRIDE` | An `export`/`bake-export` override token has no `=` |
| `INVALID_SETTING_FORMAT` | A `settings set` token has no `=` |
| `INVALID_PREFERENCE_FORMAT` | A `preferences set` token has no `=` |
| `BLENDER_NOT_FOUND` | The executable does not exist (exit 2) |
| `BLENDER_START_FAILED` | The path exists but could not be executed (exit 2) |
| `BLENDER_TIMEOUT` | The global `--timeout` expired |
| `BLENDER_PROCESS_FAILED` | Blender produced no parsable result, or exited non-zero after reporting success |
| `BLENDER_BRIDGE_FAILED` | Default bridge failure code |
| `CLI_RUNTIME_ERROR` | An unclassified `RuntimeError` in the CLI |
| `INTERRUPTED` | Ctrl-C (exit 130) |

**Raised inside Blender:**

| Code | Commands |
|------|----------|
| `ADDON_LOAD_FAILED` | all except `version` (exit 3) |
| `INVALID_SETTING_OVERRIDE` | `settings set`, `export`, `bake-export` |
| `INVALID_SETTING_VALUE` | `settings set`, `export`, `bake-export` |
| `SETTINGS_SAVE_FAILED` | `settings set --save` |
| `RCP_IMPORT_EXISTS` | `export`, `bake-export` (with `--format RCP_IMPORT`) |
| `INVALID_EXPORT_SELECTION` | `export` |
| `NO_EXPORTABLE_OBJECTS` | `export`, `bake-export` |
| `UNSUPPORTED_MATERIAL_NODES` | `export` |
| `MISSING_EXTERNAL_TEXTURES` | `bake-export` |
| `MISSING_EXTERNAL_ASSETS` | `bake-export` |
| `BAKE_STEP_TIMEOUT` | `bake-export --step-timeout` |
| `BLENDER_USD_EXPORT_FAILED` | `export`, `bake-export` |
| `POSTPROCESS_FAILED` | `export`, `bake-export` |
| `EXPORT_FAILED` | `export` |
| `BAKE_EXPORT_FAILED` | `bake-export` |

`COMMAND_FAILED` is the fallback code for a structured error raised without an explicit one. No current call site relies on it, so treat it as reserved rather than expected.

**Unclassified failures.** A command that raises a plain Python exception instead of a structured error reports the exception class name upper-cased — `VALUEERROR`, `RUNTIMEERROR`, and so on — plus a `traceback` field. Treat these as internal faults rather than a stable contract. They currently show up for `validate --material <unknown name>`, `settings get` with an unknown key or group, and `preferences set` with an unknown key.

`INVALID_EXPORT_SETTINGS`, `ASSET_PREFLIGHT_FAILED`, `SCENE_SNAPSHOT_FAILED`, `JOB_SETTINGS_WRITE_FAILED`, `BACKGROUND_RUNNER_MISSING`, and `BACKGROUND_LAUNCH_FAILED` belong to the Blender UI's background job operator. They never appear as CLI exit envelopes, but they do appear in job `status.json` and in support bundles.

---

## Output format

The two streams have distinct jobs and are never interleaved:

- **stdout** — JSON only. The command's result on success; with `--json`, the error envelope on failure. Safe to redirect straight into `jq`.
- **stderr** — human-readable progress, failure summaries, and (with `--verbose`) whatever Blender wrote to *its* stderr.

### What each flag actually does

Write `E` for the `Error:` summary plus its optional `Diagnostics:` and `Support bundle:` lines, and `P` for the CLI's own progress lines.

| | stdout on success | stderr on success | stdout on failure | stderr on failure |
|---|---|---|---|---|
| *(no flags)* | result JSON | `P` | *(nothing)* | `P` + `E` |
| `--quiet` | result JSON | *(nothing)* | *(nothing)* | `E` |
| `--json` | result JSON | *(nothing)* | error envelope | *(nothing)* |
| `--verbose` | result JSON | `P` + Blender's stderr | *(nothing)* | `P` + Blender's stderr + `E` |
| `--json --verbose` | result JSON | Blender's stderr | error envelope | Blender's stderr |

Three consequences are easy to get wrong:

1. **`--json` implies `--quiet`, but neither silences `--verbose`.** The Blender-stderr forward is unconditional, so `--json --verbose` still writes to stderr — and, unlike the `process_output` fields inside the envelope, that forwarded text is *not* `$HOME`-redacted. Do not combine them when capturing output for a public issue.
2. **`--quiet` does not silence failures.** It suppresses the CLI's own progress lines only; the `Error:`, `Diagnostics:`, and `Support bundle:` lines still go to stderr. Redirect with `2>/dev/null` if you truly want silence, and rely on the exit code.
3. **`--verbose` shows nothing on a clean run.** It forwards Blender's *stderr*, and Blender's startup banner goes to its *stdout*, which the bridge consumes to find the result. In practice `--verbose` surfaces Blender tracebacks and warnings, not a startup log.

### Failure envelope

Without `--json`, a failure prints a short summary to stderr and nothing to stdout:

```
Error: Unsupported nodes in material 'SimpleMat'.
Diagnostics: /output/scene.diagnostics.json
Support bundle: blendertorcp support-bundle scene.blend -o /output/scene.usda --diagnostics /output/scene.diagnostics.json
```

The `Diagnostics:` and `Support bundle:` lines appear only when the Blender runner returned them.

With `--json`, the failure goes to stdout as a structured envelope:

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
    "stdout_tail": "...",
    "stderr_tail": "..."
  }
}
```

Field notes:

| Field | Always present | Notes |
|-------|----------------|-------|
| `ok` | yes | Always `false` in an error envelope |
| `schema_version` | yes | Currently `"1.0"` |
| `command` | yes | May be `null` when the command could not be identified, e.g. an argparse failure with no recognizable subcommand. CLI-side errors report the top-level subcommand token (`"settings"`); Blender-side errors report the API command name (`"settings_set"`) |
| `error.code` | yes | The stable identifier — branch on this |
| `error.type` | yes | Python exception class name |
| `error.message` | yes | Human-readable; not a contract |
| `error.stage` | no | Present when the failure is attributed to a pipeline stage |
| `error.details` | no | The actionable part for setting/override errors — which key, which value, which values were allowed |
| `error.traceback` | no | Present only for unclassified internal faults, `$HOME`-redacted |
| `context` | yes | `{}` for CLI-side errors; otherwise carries `blend_file`, `blender_path`, `returncode` |
| `artifacts` | yes | `{}` for CLI-side errors; otherwise may carry `diagnostics_path` and `support_bundle_hint` |
| `process_output` | no | `stdout_tail` / `stderr_tail`, last 500 characters each, `$HOME`-redacted |

**The success envelope is a different shape.** A successful command prints its result payload directly, with no `ok`, `schema_version`, or `context` wrapper. The one nuance is `validate`, whose result payload has its own `ok` field — see [`validate`](#validate).

### Capturing output for support

```bash
blendertorcp --verbose export scene.blend -o output.usdz --format USDZ \
  > blendertorcp-result.json \
  2> blendertorcp-stderr.log
```

If the command returns a `diagnostics_path`, attach that file. If the failure happened in a Blender UI background bake/export, attach the job `settings.json`, `status.json`, and `log.txt`, or create a redacted ZIP with `support-bundle`.

### Pipe-friendly

Parse output with `jq`:

```bash
blendertorcp info scene.blend | jq '.object_count'
```

Chain commands:

```bash
FORMAT=$(blendertorcp settings get scene.blend --keys export_format | jq -r '.export_format')
echo "Current format: $FORMAT"
```

Use exit codes in scripts:

```bash
if blendertorcp validate scene.blend; then
  blendertorcp export scene.blend -o output.usdz
else
  echo "Validation failed" >&2
fi
```

Read the real output path rather than assuming `-o` was honored verbatim:

```bash
OUT=$(blendertorcp --json export scene.blend -o /output/scene --format USDZ | jq -r '.export_path')
echo "Wrote $OUT"
```
