# BlenderToRCP Architecture

## Overview
BlenderToRCP is a Blender extension that exports scenes to USD or USDZ, then rewrites Blender-authored materials into RealityKit-compatible MaterialX graphs for Reality Composer Pro.

Core design constraints:
- Strict mode first. If a material graph cannot be translated deterministically, export fails with actionable errors instead of silently falling back.
- Portable outputs. Textures and auxiliary assets are copied next to the exported USD and rewritten to relative paths.
- Reality Composer Pro compatibility. Post-processing reshapes Blender-authored USD into the subset RealityKit and RCP expect.
- Responsive baking. Bake Textures & Export runs inside a second Blender process so the foreground UI stays interactive.
- Built artifacts stay built. Runtime loads the prebuilt MaterialX manifest and nodegroup library; it does not regenerate them inside Blender.

## Repository layout
- `Plugin/`: Blender add-on package.
- `Plugin/ui/`: 3D View and Shader Editor panels, menus, and the scene property group that stores export settings.
- `Plugin/ops/`: user-invoked operators for export, background bake/export, diagnostics, node insertion, and material validation.
- `Plugin/export/`: USD export pipeline, post-processing, texture and asset staging, animation clip authoring, diagnostics, and USDZ packaging.
- `Plugin/export/materials/`: Blender material extraction, MaterialX graph construction, and USD material authoring.
- `Plugin/nodes/`: RealityKit compatibility rules, node metadata, generated nodegroup builders, and preview builders.
- `Plugin/manifest/`: bundled `rk_nodes_manifest.json` plus selectors for MaterialX nodedef lookup.
- `Plugin/assets/nodegroups.blend`: generated nodegroup library used by the authoring tools.
- `Plugin/core/paths.py`: shared path resolution for manifests, assets, and bundled resources.
- `Plugin/core/version.py`: runtime access to `blender_manifest.toml` (single source of version metadata).
- `Plugin/export/usd_hook.py`: scoped USDHook that captures the exporter's prim map during export.
- `scripts/`: developer tooling for packaging, manifest generation, nodegroup generation, and validation.
- `References/MaterialX-definitions/`: Apple MaterialX definition sources used to build the runtime manifest.
- `References/RealityComposerProProject/`: reference assets and Reality Composer Pro project material.
- `References/Doc/` and `References/Blender/`: supporting reference documentation and sample Blender scenes.
- `.github/workflows/build-archive.yml`: CI packaging workflow for the installable archive.

## Blender UX surface
BlenderToRCP appears in multiple editors, not just one export panel.

### 3D View sidebar
Defined in `Plugin/ui/panel.py`.
- Category: `RCP Exporter`
- Main panel: output path, export format, actions, background job monitor, diagnostics access.
- Child panels:
  - `USD Export: General`
  - `USD Export: Object Types`
  - `USD Export: Geometry`
  - `USD Export: Rigging`
  - `Bake Settings`

### Shader Editor sidebar
Defined in `Plugin/ui/shader_panel.py` and `Plugin/ui/shader_authoring_panel.py`.
- `RealityKit Compatibility`: validates the active material and exposes the offending-node workflow.
- `RealityKit Authoring`: inserts bundled RealityKit PBR or Unlit node groups.

### Shader Editor add menu
Defined in `Plugin/ui/shader_menu.py`.
- `Add > RealityKit Nodes` exposes the generated node catalog for inserting supported RealityKit nodegroups into the active material.

## Scene settings and preferences
The main scene property group lives in `Plugin/ui/panel.py` as `BlenderToRCPExportSettings`.

Important behaviors:
- Export settings are stored on the scene.
- The add-on persists most last-used settings into Blender preferences and restores them on the next session.
- Export paths are remembered per `.blend` file through add-on preferences.

Preferences live in `Plugin/prefs.py`:
- `usdzip_path`
- `materialx_library_path`

Diagnostics are an export setting on `BlenderToRCPExportSettings`, not an always-on add-on preference. `diagnostics_enabled` gates whether `.diagnostics.json` files are written and whether the UI exposes the diagnostics viewer/support-bundle actions.

## Export pipeline
The foreground export operator is `blendertorcp.export` in `Plugin/ops/export_operator.py`.

### 0. Settings restore and strict validation
- The operator restores persisted settings before export.
- It validates every material in the current scene with `Plugin/nodes/validate.py`.
- Unsupported nodes block export immediately with Blender `report()` errors.

### 1. Base USD export
Wrapper: `Plugin/export/blender_usd_export.py`
- Computes the real output path.
- Exports all formats to `.blendertorcp_temp/<name>/` first so Blender cannot reuse stale sidecar textures from the destination `textures/` directory.
- For `.usda` or `.usdc`, publishes the processed staged USD plus fresh `textures/` and `assets/` sidecars to the requested destination.
- For `.usdz`, exports to a staged `.usdc` first and packages the staged contents later.
- Calls Blender's USD exporter with the add-on scene settings rather than a hard-coded configuration.
- Registers a scoped USDHook during the export call to capture the exact prim map (`export_context.get_prim_map()`), so the material rewrite resolves material prims exactly instead of by name.

### 2. Optional animation preparation
Implementation: `Plugin/export/animation_export.py`
- Collects actions from `bpy.data.actions`.
- Concatenates them into a temporary export timeline.
- Records clip boundaries into diagnostics.
- Restores original scene state after export, including tracks, active actions, selection, and active object.

### 3. USD post-processing
Pipeline entry point: `Plugin/export/postprocess_usd.py`

Sub-steps:
- `normalize_scene(stage, settings)` from `Plugin/export/usd_scene.py`
- `rewrite_materials(stage, settings, context, diagnostics)` from `Plugin/export/materials/rewrite.py`
- `author_animation_library(stage, settings, diagnostics)` from `Plugin/export/usd_animation_library.py`; this is opt-in via `author_animation_library=true` because RealityKit runtime exports should usually play or trim imported animation resources directly.
- `prepare_textures(stage, usd_path, settings, diagnostics)` from `Plugin/export/usd_textures.py`
- `prepare_assets(stage, usd_path, diagnostics)` from `Plugin/export/usd_assets.py`

This stage is where Blender-authored USD is converted into the RealityKit and Reality Composer Pro contract the rest of the toolchain expects.
Texture staging prefixes generated texture filenames with the export output stem, for example `badge-streak-7-extracted_image_0.avif`, before applying hash suffixes for any remaining same-name collisions.

### 4. USDZ packaging
Packager: `Plugin/export/pack_usdz.py`
- Uses `usdzip` when configured in preferences.
- Falls back to the Python zip-based packager when `usdzip_path` is empty.
- Packages the main USD together with staged `textures/` and `assets/`.

### 5. Diagnostics
Collector: `Plugin/export/diagnostics.py`
- Captures warnings, errors, animation segments, texture work, and material conversion results.
- If diagnostics are enabled for the export, writes `<output>.diagnostics.json`.
- Failure paths write `<output>.diagnostics.json` only when diagnostics are enabled for that command.
- Diagnostics include export context, runtime environment, phase timings, validation issues, material graph issues, asset dependency preflights, generated files, artifacts, warnings, errors, and captured exceptions.
- The diagnostics viewer in `Plugin/ops/export_operator.py` renders a summary dialog in Blender.
- `Plugin/export/support_bundle.py` creates redacted ZIPs containing environment, scene/settings, asset dependencies, diagnostics, and background job files when a job directory is supplied. Material validation snapshots are included only for non-baked exports. Redaction covers plain absolute paths and JSON-escaped Windows path strings.

## Background Bake Textures & Export
The background bake operator is `blendertorcp.bake_export_background` in `Plugin/ops/bake_export_operator.py`.

### Control-plane behavior
- Requires the `.blend` file to be saved before launch.
- Allows only one background job at a time.
- Serializes settings into `<export_dir>/.blendertorcp_jobs/<job_id>/settings.json`.
- Writes live status to `status.json` and process output to `log.txt`.
- Writes the log and diagnostics paths into `status.json` when available, including progress heartbeats, so the UI can expose `Open Log`, `Open Diagnostics`, and `Create Support Bundle` even after a failed or timed-out job.
- Stores the job directory and process ID on the scene settings.
- Uses a modal watcher to refresh the UI, detect process death, and enforce per-step timeouts.

### Runner behavior
Runner script: `Plugin/bake_export_runner.py`
- Launches Blender in background factory-startup mode with the current `.blend` so unrelated user add-ons do not pollute the bake session.
- Ensures the add-on is enabled inside the background session.
- Applies serialized scene settings.
- Fails early if exported objects reference missing, unpacked external image files, checking every UDIM tile and image-sequence frame individually.
- Restores selection when `Selection Only` is active.
- Switches the render engine to `CYCLES` for baking.
- Uses a heartbeat thread to keep `status.json` fresh while long bake steps run.
- Restores render engine, selection, active object, and mode after completion or failure.
- Arms an `exit_pre` crash guard so an unexpected Blender shutdown still writes a terminal error status, preventing the UI from waiting on a stale "running" job.

### Bake semantics
Baking is implemented in `Plugin/export/bake_textures.py`.

User-visible contracts:
- `Bake Textures & Export` authors RealityKit Unlit materials for `UNLIT_ALBEDO` and `LIT_IBL`, and Lit PBR materials for `LIT_ALBEDO`.
- Bake/export skips source material graph validation because baking is the compatibility boundary. Strict graph validation remains part of `Export Scene`.
- `Material Color Only - Unlit` (`UNLIT_ALBEDO`) bakes light-independent material color.
- `Material Color Only - Lit PBR` (`LIT_ALBEDO`) bakes light-independent material color and exports Lit PBR materials (roughness as a texture or averaged constant via `bake_roughness_mode`).
- `Lighting & Shadows` (`LIT_IBL`) bakes appearance under the chosen lighting source, then still exports Unlit materials whose textures already include that lighting and shadowing.
- `Isolate Meshes for Shadows` hides non-target meshes during each lighting-and-shadows bake pass to avoid cross-mesh shadows.
- `Step Timeout (sec)` is enforced by the foreground watcher and can terminate the background Blender process when a single step stalls.

## Material rewrite flow
Material rewriting is orchestrated in `Plugin/export/materials/rewrite.py`.

### Runtime inputs
- Blender material bindings already authored by the base USD export (mesh prims and GeomSubset children — multi-material meshes bind per subset).
- The prim map captured by the export-time USDHook, mapping material prim paths to Blender material names exactly.
- Blender material data resolved from `context.blend_data.materials`.
- The prebuilt MaterialX manifest loaded through `Plugin/manifest/materialx_nodes.py`.

### Extraction
`Plugin/export/materials/extract/core.py`
- Traverses Blender node graphs.
- Emits normalized `material_data` payloads and input graph fragments.
- Flags unresolved patterns for diagnostics.

### Graph construction
`Plugin/export/materials/graph.py`
- Converts extracted material data into a MaterialX graph payload.
- Handles graph fragments, typed values, and conversion nodes.

### Authoring
`Plugin/export/materials/author.py`
- Creates USD Shade nodes.
- Connects shader inputs, textures, constants, and internal graph nodes.
- Binds the rewritten material back onto mesh prims.

### Material kinds
`rewrite_materials()` currently branches between:
- `principled`
- `emission`
- `simple`
- `rk_graph`
- `rk_group`

`force_unlit_materials` is used by Bake Textures & Export so that the final stage is always authored as RealityKit Unlit even when the source graph started as a lit graph.

## MaterialX manifest and node catalog
Runtime manifest loading lives in `Plugin/manifest/materialx_nodes.py`.

Important contracts:
- The manifest path is resolved through `Plugin/core/paths.py`.
- Runtime only loads the JSON manifest; it never rebuilds it.
- Missing or invalid manifests produce startup warnings or manifest errors.

Build path:
- `scripts/build_materialx_manifest.py` parses `.mtlx` files under `References/MaterialX-definitions`.
- It emits `Plugin/manifest/rk_nodes_manifest.json`.
- The manifest includes nodedef metadata, multiple lookup indexes, and policy flags such as:
  - omitted geometry modifier nodes
  - KTX-required nodes
  - fallback nodes
  - half-type variants

## RealityKit nodegroup authoring path
This repo also ships authoring helpers, not just export logic.

### Node metadata
`Plugin/nodes/metadata.py`
- Builds a user-facing node catalog from the bundled manifest.
- Applies label overrides and section grouping.
- Keeps preferred non-half variants when multiple nodedefs exist.

### Nodegroup generation
`Plugin/nodes/nodegroups/builder.py`
- Builds or refreshes NodeGroups from the catalog.
- Stores version metadata on each generated group.
- Saves the group library through `save_nodegroup_library()`.

### Bundled nodegroup asset
Generated by `scripts/build_nodegroups.py`
- Output: `Plugin/assets/nodegroups.blend`
- This file is what the insertion operators load at runtime if a nodegroup is not already present in the current Blender session.

### User-facing operators
Defined in `Plugin/ops/nodegroup_operators.py`
- Insert RealityKit PBR group
- Insert RealityKit Unlit group
- Insert arbitrary catalog nodes from the add menu

## Validation surface
Validation exists at three layers.

### In-editor material validation
`Plugin/nodes/validate.py` plus `Plugin/ops/validation_operators.py`
- Validates the active material.
- Selects offending nodes.
- Removes offending nodes when requested.

### Per-node compatibility harness
`scripts/validate_nodes.py`
- Wrapper around `scripts/_lib/node_validation.py`.
- Generates minimal `.rkassets` bundles for supported nodes.
- Optionally compiles them with `xcrun realitytool`.
- Defaults output to `tests/node_validation`.

### Export validation
`scripts/validate_exports.py`
- Accepts a USD file, `.rkassets` bundle, or directory.
- Runs `usdchecker` when enabled.
- Lints nodedef IDs and asset paths.
- Optionally compiles bundles with `xcrun realitytool`.

These scripts are the closest thing this repo has to an automated compatibility test suite.

## Developer scripts
- `scripts/build_archive.sh`: package `Plugin/` into `dist/BlenderToRCP.zip`.
- `scripts/build_materialx_manifest.py`: rebuild the runtime nodedef manifest from MaterialX sources.
- `scripts/build_nodegroups.py`: regenerate `Plugin/assets/nodegroups.blend`.
- `scripts/validate_nodes.py`: generate and optionally compile per-node compatibility fixtures.
- `scripts/validate_exports.py`: validate exported USD or `.rkassets` bundles.

## Release path
Packaging is intentionally deterministic:
- Local build: `bash scripts/build_archive.sh`
- CI build: `.github/workflows/build-archive.yml`
- Output artifact: `dist/BlenderToRCP.zip`

Release-facing metadata lives in `Plugin/blender_manifest.toml` (read at runtime via `Plugin/core/version.py`).

If packaging changes or release automation is touched, keep those metadata surfaces aligned with the built archive and published release asset.
