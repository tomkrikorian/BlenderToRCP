# BlenderToRCP

Blender add-on to export USD/USDZ and rewrite Blender materials into Reality Composer Pro compatible MaterialX ShaderGraph graphs.

## Key features

- **CLI remote control**: export, bake, validate, and manage settings from the terminal — no Blender UI needed.
- Export `.usda`, `.usdc`, or `.usdz` from Blender with a Reality Composer Pro friendly pipeline.
- Strict material validation: unsupported nodes fail export with copy/pasteable errors instead of silently degrading.
- RealityKit material rewrite: supported Blender shader graphs are rewritten into MaterialX graphs that Reality Composer Pro can edit.
- Portable exports: textures and auxiliary assets are staged next to the USD and rewritten to relative paths.
- Animation compatibility: actions can be concatenated for export and authored into a Reality Composer Pro animation library.
- Background Bake Textures & Export: runs baking and export in a second Blender process, writes status/log files, and keeps the UI responsive.
- Shader authoring helpers: insert RealityKit PBR or Unlit node groups, browse a generated RealityKit node menu, and validate active materials in the Shader Editor.

## Important note
This is still a strict, compatibility-first exporter. Node coverage and graph translation are intentionally limited, and some Blender materials or scene setups will fail export until explicit support is added. When export succeeds, validate the result in Reality Composer Pro or with the repo validation scripts before relying on it in production.

This repo supports three workflows:
- Install the Blender add-on.
- Use the CLI to control exports from the terminal or an AI agent.
- Contribute to the add-on.

## Where to find it in Blender
- `3D View > Sidebar > RCP Exporter`: main export UI, advanced USD export settings, bake settings, job monitor, and diagnostics access.
- `Shader Editor > Sidebar > RCP Exporter > RealityKit Compatibility`: validate the active material and select offending nodes.
- `Shader Editor > Sidebar > RCP Exporter > RealityKit Authoring`: insert RealityKit PBR or Unlit node groups.
- `Shader Editor > Add > RealityKit Nodes`: insert generated RealityKit node groups from the bundled node catalog.

## Install the Blender add-on
1. Download the release asset `BlenderToRCP.zip` from GitHub Releases.
2. In Blender, open `Edit > Preferences > Extensions > Add-ons > Install from Disk...`.
3. Select `BlenderToRCP.zip`.
4. Enable `BlenderToRCP` in the add-ons list.

## CLI

BlenderToRCP includes a command-line interface that can export, bake, validate, and manage settings without opening the Blender UI. Every command spawns `blender --background` and returns JSON to stdout on success. For failures, use `--json` when callers need the structured error envelope on stdout; without `--json`, the CLI prints a short human-readable error and support hints to stderr.

### Quick start

```bash
# Set the Blender path (add to ~/.zshrc or ~/.bashrc)
export BLENDERTORCP_BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"

# Create an alias for convenience.
# Installed extension:
alias blendertorcp="python3 /path/to/BlenderToRCP"
# Or, for a development checkout:
# alias blendertorcp="python3 /path/to/repo/Plugin"

# Test the connection
blendertorcp version
blendertorcp preferences get
blendertorcp settings list
```

### Usage examples

```bash
# Scene inspection
blendertorcp info scene.blend
blendertorcp list-objects scene.blend --type MESH
blendertorcp list-materials scene.blend

# Validate materials for RealityKit compatibility
blendertorcp validate scene.blend --strict

# Export to USDZ
blendertorcp export scene.blend -o output.usdz --format USDZ

# Bake textures and export
blendertorcp bake-export scene.blend -o output.usdz --resolution 2048

# Read and modify settings
blendertorcp settings get scene.blend --group bake
blendertorcp settings set scene.blend export_format=USDZ --dry-run
```

For the full command reference see [`docs/CLI.md`](docs/CLI.md).

## AI agent skills

This repo ships two [OpenAI-format skills](https://skills.sh) that let AI agents (Claude, ChatGPT, Copilot, etc.) drive BlenderToRCP from natural language.

### Install skills

```bash
npx skills add tomkrikorian/BlenderToRCP
```

Browse and discover skills at [skills.sh](https://skills.sh).

### Available skills

| Skill | Description |
|-------|-------------|
| `blendertorcp-cli` | Export scenes, bake textures, validate materials, and manage settings via the CLI. |
| `blendertorcp-setup` | Set up the CLI — locate Blender, verify the plugin, configure the shell alias. Also covers troubleshooting. |

Once installed, an agent can respond to prompts like "export my Blender scene to USDZ" or "bake and export Robot.blend at 4K resolution" by invoking the CLI commands automatically.

## Contribute to the Blender add-on

### Requirements
- Blender 5.0 or newer.
- Python 3.
- Git LFS. This repo stores `.png` and `.usda` via LFS.
- OpenUSD Python bindings (`pxr`) in Blender for material rewriting and validation helpers.
- Reality Composer Pro for end-to-end validation.
- Optional command-line tools for validation:
  - `usdchecker`
  - `usdcat`
  - `xcrun realitytool`

### Local setup
1. Clone the repo and pull LFS assets:

```bash
git lfs install
git lfs pull
```

2. Ensure Blender's user extension repository exists on macOS.
Replace `<version>` with your installed Blender major.minor version, for example `5.1`:

```bash
mkdir -p ~/Library/Application\ Support/Blender/<version>/extensions/user_default
```

3. Symlink the add-on into Blender's extension repository:

```bash
ln -s "<path-to-this-repo>/Plugin" \
  "$HOME/Library/Application Support/Blender/<version>/extensions/user_default/BlenderToRCP"
```

4. Enable the add-on in Blender.

5. Verify the CLI against the checkout:

```bash
python3 "<path-to-this-repo>/Plugin" --blender /Applications/Blender.app/Contents/MacOS/Blender version
python3 "<path-to-this-repo>/Plugin" --blender /Applications/Blender.app/Contents/MacOS/Blender preferences get
python3 "<path-to-this-repo>/Plugin" --blender /Applications/Blender.app/Contents/MacOS/Blender settings list
```

### Contributor quick start
Run these when you change the corresponding subsystem:

```bash
bash scripts/build_archive.sh
python3 scripts/build_materialx_manifest.py
blender --background --python scripts/build_nodegroups.py
python3 scripts/validate_nodes.py --platform xros
python3 scripts/validate_exports.py --input <export-dir-or-usd> --platform xros --deployment-target 1.0
```

Notes:
- `scripts/build_archive.sh` builds the installable archive at `dist/BlenderToRCP.zip`.
- `scripts/build_materialx_manifest.py` rebuilds `Plugin/manifest/rk_nodes_manifest.json` from `References/MaterialX-definitions`.
- `scripts/build_nodegroups.py` regenerates `Plugin/assets/nodegroups.blend`.
- `scripts/validate_nodes.py` writes generated bundles and reports under `tests/node_validation` by default and can compile each fixture with `realitytool`.
- `scripts/validate_exports.py` validates exported USD or `.rkassets` with `usdchecker`, nodedef/path lint, and optional `realitytool` compilation.

## Add-on preferences and persisted state
The add-on preferences expose:
- `USDZ Packager Path`: optional path to `usdzip`. If empty, the add-on uses the built-in Python packager.
- `MaterialX Library Path`: optional override for MaterialX definitions. If empty, the add-on uses the bundled references.
- `Default Export Format`
- `Enable Diagnostics`

The add-on also persists the last-used export settings and remembers export paths per `.blend` file. That state lives in Blender preferences, not in the repository.

## Export workflow
The main export operator validates every scene material in strict mode before writing USD. Export settings are stored on the scene and expose a large subset of Blender USD export controls, including:
- Root prim naming, selection-only export, animation export, and custom property authoring.
- Name, path, Unicode, orientation, units, and transform-op controls.
- Object-type toggles for meshes, lights, cameras, curves, points, volumes, hair, and world dome light conversion.
- Geometry and rigging controls such as UV export, `st` renaming, normals, triangulation, subdivision, armatures, deform bones, and shape keys.

Exports write support-oriented diagnostics as `<output>.diagnostics.json` when diagnostics are enabled. Failure paths also try to persist that file so users can share validation, asset dependencies, traceback, environment, timing, and artifact context. The main panel exposes `Show Diagnostics` and `Create Support Bundle` actions.

## Background Bake Textures & Export
`Bake Textures & Export` is a background-only workflow. The add-on launches a second Blender process, bakes textures, runs the same USD export pipeline, and updates live job status in the panel.

Which option should I choose?

| Goal | Use |
|------|-----|
| Quick USDZ export without baking textures | `Export Scene` |
| Reusable baked textures that Reality Composer Pro or RealityKit can light | `Bake Textures & Export` with `Material Color Only` |
| Export that preserves Blender-looking lighting and shadows | `Bake Textures & Export` with `Lighting & Shadows` (default) |

Operational details:
- The `.blend` file must be saved before starting a background bake.
- Only one background bake/export job can run at a time.
- Job state lives under `<export_dir>/.blendertorcp_jobs/<job_id>/`.
- Each job writes `settings.json`, `status.json`, and `log.txt`; status also records the diagnostics path when available.
- The panel shows progress, output path, log path, diagnostics path, and the current step, and supports cancel, clear, log open, diagnostics open, and support bundle actions.
- `Step Timeout (sec)` terminates the background process if a single step exceeds the configured duration.
- Bake/export preflights external image files used by exported objects. Missing, unpacked textures fail early with an actionable pack-or-relink error.
- Bake/export does not validate the source material graph. Unsupported Blender node groups are expected to be resolved by baking; strict graph validation only applies to `Export Scene`.

Bake modes:
- `Material Color Only` (`UNLIT_ALBEDO`): bakes light-independent material color and rewrites the exported materials as RealityKit Unlit materials. Use this when Reality Composer Pro or RealityKit should light the scene.
- `Lighting & Shadows` (`LIT_IBL`, default): bakes the appearance under the selected lighting source, then still exports the final materials as RealityKit Unlit materials with lighting and shadows encoded into textures. Use this when the USDZ should match the Blender preview.
- `Isolate Meshes for Shadows`: hides non-target meshes during lighting-and-shadows bakes to avoid cross-mesh shadow contribution.
- `Image Format`: baked textures can be written as `.png` or `.avif`; AVIF support requires Blender 5.1+, and older builds warn and fall back to PNG.

## Material authoring and diagnostics
BlenderToRCP is not export-only. The Shader Editor integration also supports:
- Validating the active material against the current RealityKit compatibility rules.
- Selecting offending nodes after validation.
- Inserting bundled RealityKit PBR and Unlit node groups.
- Browsing the generated RealityKit node catalog through `Add > RealityKit Nodes`.

Diagnostics workflow:
- Export-time diagnostics are gated by the `Enable Diagnostics` preference.
- The diagnostics dialog summarizes converted and failed materials, copied and converted textures, fallback nodes, KTX-required nodes, omitted nodes, and truncated warning/error lists.
- Diagnostics JSON can be inspected directly or opened in Blender's Text Editor for troubleshooting.
- Support bundles are redacted ZIP files created from the Blender UI or with `blendertorcp support-bundle scene.blend -o output.usdz --diagnostics output.diagnostics.json`.
- Support bundles include environment, scene/settings, asset dependency diagnostics, and export diagnostics. They include material validation only for non-baked exports. Background job files are included by the UI action for the active job or by passing `--job-dir` to the CLI. Source `.blend` files and exported assets are opt-in.
- Redaction covers absolute paths in plain text and JSON-escaped Windows path strings; `--no-redact` disables that protection.

## Troubleshooting and support capture
For CLI failures, capture stdout and stderr separately:

```bash
blendertorcp --verbose export scene.blend -o output.usdz --format USDZ \
  > blendertorcp-result.json \
  2> blendertorcp-stderr.log
```

Attach `blendertorcp-result.json`, `blendertorcp-stderr.log`, the exact command, `blendertorcp version`, `blendertorcp preferences get`, the returned `.diagnostics.json`, and a redacted support bundle. For background bake/export, also include `<export_dir>/.blendertorcp_jobs/<job_id>/settings.json`, `status.json`, and `log.txt` or use the support bundle action.
Use `--json` for automated support capture so load failures, validation failures, diagnostics paths, support-bundle hints, and process-output tails stay in a machine-readable JSON envelope.

## Release and packaging flow
- Local packaging is script-driven through `bash scripts/build_archive.sh`.
- CI packaging is defined in `.github/workflows/build-archive.yml` and runs on manual dispatch and published releases.
- Both local and CI paths build the same archive: `dist/BlenderToRCP.zip`.

Before publishing a release, verify add-on metadata:
- `Plugin/blender_manifest.toml` still contains placeholder maintainer metadata and should be updated.
- `Plugin/__init__.py` still leaves `doc_url` empty.

## Architecture
See `docs/ARCHITECTURE.MD`.
