# BlenderToRCP Architecture

## Overview
BlenderToRCP is a Blender extension that exports scenes to USD or USDZ, then rewrites Blender-authored materials into RealityKit-compatible MaterialX graphs for Reality Composer Pro.

Core design constraints:
- Blender 5.2 is the only Blender API contract for release 2.x. Older compatibility paths are intentionally not retained.
- Strict mode first. If a material graph cannot be translated deterministically, export fails with actionable errors instead of silently falling back.
- Portable outputs. Textures and auxiliary assets are copied next to the exported USD and rewritten to relative paths.
- Reality Composer Pro compatibility. Post-processing reshapes Blender-authored USD into the subset RealityKit and RCP expect.
- Responsive baking. The single Blender Export action routes bake-backed profiles through a second Blender process so the foreground UI stays interactive.
- Built artifacts stay built. Runtime loads the prebuilt MaterialX manifest and nodegroup library; it does not regenerate them inside Blender.

## Supported platform contract

The release-2.x validation baseline is:

- Blender 5.2.x and its bundled Python runtime.
- Apple-silicon macOS 27 for Apple-specific checks.
- Xcode 27 with the version-27 SDKs selected.
- Reality Composer Pro 3.
- Version-27 deployment targets for visionOS, macOS, iOS/iPadOS, and tvOS in the reference Swift package.

The pipeline has two distinct validation boundaries:

1. Portable checks run Python tests and verify that the extension can be packaged deterministically. They do not prove RealityKit compatibility.
2. Apple checks exercise the real Blender 5.2 and Xcode 27 toolchain. `usdchecker` covers structural acceptance, `realitytool` covers compilation, and a public-API RealityKit harness loads the fresh source assets and those exact compiled outputs on macOS 27. There is no supported headless Reality Composer Pro import command in this repository.

Interactive Reality Composer Pro 3 import/save/reopen, visual inspection, Quick Look/Spatial Preview, and physical Vision Pro testing are manual release gates. Compilation alone is insufficient—the automated Apple gate also requires real macOS 27 RealityKit loading—but neither automated check proves the remaining UI, visual, or device acceptance.

The mandatory shipping material profile is `realitykit_portable`, based on the established RealityKit PBR v1 surface. The graph builder also contains explicit `realitykit_pbr2` and `openpbr_1_1` profiles, but they remain experimental. Passing an experimental compile does not promote either profile into the supported release contract or weaken package validation.

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
- `References/RealityComposerProProject/`: legacy Reality Composer Pro 2 reference material; it is not an RCP3/Apple 27 validation fixture until manually migrated.
- `References/Doc/` and `References/Blender/`: supporting reference documentation and sample Blender scenes.
- `.github/workflows/ci.yml`: portable unit, archive-smoke, and pinned Blender 5.2 integration gates.
- `.github/workflows/apple-platform-validation.yml`: protected self-hosted Apple 27 validation lane.
- `.github/workflows/build-archive.yml`: tag-gated validation, packaging, checksum, and release publication workflow.

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

Diagnostics are an export setting on `BlenderToRCPExportSettings`, not an add-on preference. Failures always write `.diagnostics.json`; `diagnostics_enabled` controls only successful-export sidecars.

## Export pipeline
The foreground export operator is `blendertorcp.export` in `Plugin/ops/export_operator.py`.

### 0. Settings restore and strict validation
- The operator restores persisted settings before export.
- It validates every material in the current scene with `Plugin/nodes/validate.py`.
- Unsupported nodes block export immediately with Blender `report()` errors.
- Fresh release-2.x settings use `-Z` forward, `Y` up, meters at scale `1.0`, and orientation conversion enabled.
- Raw lights, world-material conversion, cameras, curves, points, volumes, and hair are not configurable export types. Author cameras and lighting downstream and convert unsupported geometry to polygon meshes for the portable RealityKit asset profile.

### 1. Base USD export
Wrapper: `Plugin/export/blender_usd_export.py`
- Computes the real output path.
- Exports all formats to a unique `.blendertorcp_temp/<full-output-name>.<attempt-id>/` directory first, so Blender cannot reuse stale destination sidecars and concurrent exports cannot delete each other's in-flight work.
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
- Uses configured `usdzip` through its dependency-resolving `--asset` and compliance-check path.
- Otherwise uses the built-in uncompressed packager, which writes the root layer first and aligns every payload to the USDZ-required 64-byte boundary.
- Packages the staged dependency tree, validates archive safety/alignment/CRC before publication, and additionally runs strict `usdchecker` when that tool is available.
- Publishes atomically. A failed package or validation does not replace the requested output, and its staging tree is retained for diagnostics.

### 5. Diagnostics
Collector: `Plugin/export/diagnostics.py`
- Captures warnings, errors, animation segments, texture work, and material conversion results.
- Writes `<output>.diagnostics.json` for every failed export.
- Successful exports retain the sidecar only when diagnostics are enabled for that command.
- Diagnostics include export context, runtime environment, phase timings, validation issues, material graph issues, asset dependency preflights, generated files, artifacts, warnings, errors, and captured exceptions.
- The diagnostics viewer in `Plugin/ops/export_operator.py` renders a summary dialog in Blender.
- `Plugin/export/support_bundle.py` creates redacted ZIPs containing environment, scene/settings, asset dependencies, diagnostics, and background job files when a job directory is supplied. Material validation snapshots are included only for non-baked exports. Redaction covers plain absolute paths and JSON-escaped Windows path strings.

## Profile-driven background baking

The Blender UI exposes two artist-facing material types with one Export action:

- `RealityKit PBR` + `Translate Materials` routes to the direct export operator.
- `RealityKit PBR` + `Bake Materials` routes to `LIT_ALBEDO`.
- `RealityKit Unlit` + `Material Color Only` routes to `UNLIT_ALBEDO`.
- `RealityKit Unlit` + `Lighting & Shadows` routes to `LIT_IBL`.

The CLI retains the explicit `export` and `bake-export` commands and their
low-level settings. The UI-only routing fields are not part of the CLI schema.
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
- The CLI and persisted plugin settings expose an optional per-step timeout that the foreground watcher can use to terminate the background Blender process when a single step stalls. The Blender panel intentionally omits this operational control.

## Material rewrite flow
Material rewriting is orchestrated in `Plugin/export/materials/rewrite.py`.

### Runtime inputs
- Blender material bindings already authored by the base USD export (mesh prims and GeomSubset children — multi-material meshes bind per subset).
- The prim map captured by the export-time USDHook, mapping material prim paths to Blender material names exactly.
- Blender material data resolved from `context.blend_data.materials`.
- The prebuilt MaterialX manifest loaded through `Plugin/manifest/materialx_nodes.py`.
- The surface profile, defaulting to the shipping `realitykit_portable` PBR v1 contract. `realitykit_pbr2` and `openpbr_1_1` are explicit experimental alternatives.

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
- Accepts a USD/USDZ file, `.rkassets` bundle, or directory.
- Runs `usdchecker --strict` when enabled; `--arkit` adds the legacy ARKit profile.
- Lints nodedef IDs and asset paths.
- Optionally compiles bundles with `xcrun realitytool`.
- With `--compiled-output-dir`, preserves a deterministic, collision-safe `.reality` artifact for subsequent runtime loading and records its exact path in the JSON report.

### RealityKit runtime acceptance
`scripts/run_realitykit_runtime_smoke.sh`
- Compiles `scripts/realitykit_runtime_smoke.swift` against the macOS 27 SDK.
- Loads fresh USDC and USDZ assets plus the exact macOS `.reality` files retained by export validation.
- Recursively requires `ModelComponent` and, for the material fixture, `ShaderGraphMaterial`.
- Inspects public animation resources, `AnimationLibraryComponent` keys, and required component types such as `MeshDeformerComponent` and `SkeletalPosesComponent` for the animated and rigged fixtures.
- Emits machine-readable JSON and fails closed on load or expectation failures.

These scripts provide structural, compiler, and macOS RealityKit runtime acceptance. They do not automate Reality Composer Pro 3's graphical import/save/reopen workflow or device-side visual validation.

## Developer scripts
- `scripts/check_release.sh`: validate release metadata, build the extension twice, and verify deterministic archive contents plus checksum.
- `scripts/build_archive.sh`: packaging entry point; `--check` delegates to the full release check.
- `scripts/smoke_extension_archive.py`: install a built archive into isolated Blender user resources, prove clean packaged node-group loading, run successful installed-CLI USDC/USDZ exports, inspect geometry/material/portable ShaderGraph semantics with Blender's bundled USD runtime, enforce the packaged USDZ contract, use strict `usdchecker` and Xcode 27 `realitytool` when available, and exercise the bake-runner entry point.
- `scripts/check_apple27_toolchain.sh`: fail-closed preflight for the labelled Apple 27 runner.
- `scripts/run_realitykit_runtime_smoke.sh`: compile and run the macOS 27 RealityKit source/compiled-asset acceptance probe.
- `scripts/realitykit_runtime_smoke.swift`: public-API recursive entity, material, and animation inspector used by that probe.
- `scripts/build_materialx_manifest.py`: rebuild the runtime nodedef manifest from MaterialX sources.
- `scripts/build_nodegroups.py`: regenerate `Plugin/assets/nodegroups.blend`.
- `scripts/check_nodegroup_parity.py`: rebuild the nodegroup library in a temporary Blender 5.2 session and compare catalog, interfaces, metadata, preview nodes, and links against the shipped binary.
- `scripts/validate_nodes.py`: generate and optionally compile per-node compatibility fixtures.
- `scripts/validate_exports.py`: validate exported USD, USDZ, or `.rkassets` bundles.

## Release path
Release-facing metadata lives in `Plugin/blender_manifest.toml` and is read at runtime through `Plugin/core/version.py`. The same version determines these outputs:

```text
dist/BlenderToRCP-<version>.zip
dist/BlenderToRCP-<version>.zip.sha256
```

The local release check is non-mutating with respect to Git and GitHub:

```bash
bash scripts/check_release.sh
bash scripts/check_release.sh --expected-tag <version>
```

The second form is the tag-release check. It requires a bare-semver tag that exactly matches the manifest version. It does not create or push that tag.

### Workflow gates

`.github/workflows/ci.yml` is reusable and also runs for pull requests and pushes to `dev` or `main`. Its jobs are:

- `unit-tests`: Python 3.13 compile check and unit tests on Ubuntu.
- `archive-smoke`: build and inspect the installable extension archive on Ubuntu.
- `blender-5-2-integration`: download the pinned official Blender 5.2.0 Linux archive, verify its SHA-256, run the Blender integration suite, validate the built extension archive, and run the installed-archive smoke gate.

The installed-archive gate uses isolated `BLENDER_USER_RESOURCES`; it does not import the development checkout as the add-on. It requires the canonical `bl_ext.user_default.blender_to_rcp` module, registered `Scene.blender_to_rcp_export_settings`, no `Plugin`/`Plugin.*` aliases, and clean on-demand `rk_pbr` loading with provenance inside the installed archive. It runs the installed CLI's `version` and `settings list` commands, then exports a tiny default-material scene to both USDC and USDZ through that installed CLI. Standard-library package checks enforce the installed packager's immutable USDZ member contract and 64-byte alignment, while Blender's bundled USD runtime requires mesh geometry, material binding, a connected MaterialX surface, and `ND_realitykit_pbr_surfaceshader`. Available Apple tooling adds `usdchecker --arkit --strict`; an Xcode 27 host also compiles both assets for `xros` 27 with Metal via `realitytool`. Finally, the installed background bake runner must reach the controlled empty-scene `No exportable objects found` preflight.

`.github/workflows/apple-platform-validation.yml` is reusable and runs directly for relevant `Plugin`, `References`, `scripts`, `tests`, or workflow changes pushed to `dev`. It intentionally has no direct manual or pull-request entry point: trusted manual dry runs enter through `.github/workflows/build-archive.yml` on `dev`, and a GitHub-hosted authorization job resolves and approves the immutable revision before the self-hosted Apple runner is allocated. Its `apple-27` job uses this exact protected runner label set:

```text
self-hosted, macOS, ARM64, macos-27, xcode-27,
reality-composer-pro-3, blender-5.2
```

That job preflights the installed tools and runs the Blender integration suite. It then creates these fresh portable-profile assets from source `.blend` fixtures:

- `RedCube.usdc` and `RedCube.usdz`
- `CubeWith4Animations.usdc`
- `Robot.usdc`, the positive skinned/skeletal portable-material fixture

`MeshyRiggedCharacter.blend` is retained as an expected-rejection fixture: its active Blender 5.2 `Specular Tint` value cannot be represented by the portable PBR v1 profile, so the workflow requires `UNSUPPORTED_MATERIAL_NODES`, a `Specular Tint` detail, diagnostics, and no output asset. It will not enter a PBR2-only success lane until that profile has independent authored-`specularColor`, Reality Composer Pro 3 compile, and RealityKit runtime proof.

Each successfully exported asset receives strict and legacy-ARKit `usdchecker` checks. Xcode 27's `realitytool` then compiles the three USDC fixtures with Metal enabled at deployment target `27.0` for `xros`, `xrsimulator`, `macosx`, `iphoneos`, `iphonesimulator`, `appletvos`, and `appletvsimulator`, retaining every tested `.reality` output as evidence.

On the macOS 27 host, the runtime harness loads RedCube's fresh USDC, USDZ, and compiled `.reality`; it loads both the fresh USDC and compiled `.reality` for CubeWith4Animations and Robot. Every input must expose a `ModelComponent` and `ShaderGraphMaterial`. The animated cube must also expose animation evidence and the exact keys `GoBackward`, `GoDown`, `GoForward`, and `GoUp`. Both Robot forms must expose animation key and resource name `Animation` plus `MeshDeformerComponent` and `SkeletalPosesComponent`, so the positive gate covers real skinning/skeletal runtime state rather than animation metadata alone. The runtime JSON/log, fresh exports, the Meshy expected-rejection evidence, and all compiled outputs are uploaded as evidence. The job additionally validates ShaderGraph nodes for `xros` and `macosx` and compiles the reference Swift package with an external scratch path.

The Apple job intentionally does not install PyPI `usd-core`; validation resolves the Apple 27 USD tools selected by `xcrun`. It does not drive the Reality Composer Pro 3 UI.

`.github/workflows/build-archive.yml` runs for bare-semver tags and trusted manual dry runs selected from `dev` (or the exact release tag). For a pushed tag, metadata validation first requires the tagged commit to be reachable from `origin/dev`. It then calls both reusable validation workflows, rejects a tag that differs from the manifest version, and only then builds the versioned ZIP and SHA-256 sidecar. The publish job has `contents: write`; all validation jobs remain read-only, and its third-party release action is pinned to a reviewed immutable commit. Tag pushes publish the two files to GitHub Releases, while manual dispatch uploads artifacts without publishing a release.

### Manual release boundary

Before a tag is pushed, the intended release commit must also be imported, saved, reopened, and inspected in Reality Composer Pro 3, checked visually in the relevant Preview/Quick Look paths, then tested on the supported Apple devices. These checks are deliberately manual because this repository has no supported headless Reality Composer Pro UI, visual-acceptance, or device-control path. Workflow success proves structural, compilation, and macOS 27 runtime-load acceptance—not the remaining UI, visual, or physical-device acceptance.
