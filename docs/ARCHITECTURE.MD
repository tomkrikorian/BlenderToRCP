# BlenderToRCP Architecture

## Overview
BlenderToRCP is a Blender extension that exports scenes to USD/USDZ and rewrites Blender materials into RealityKit-compatible MaterialX graphs for Reality Composer Pro.

Key design constraints:
- Strict mode: if we can't translate a graph deterministically, export fails with actionable errors (no silent fallbacks).
- Self-contained exports: textures/assets are staged next to the USD and all asset paths are rewritten to be relative.
- Reality Composer Pro compatibility: the exporter post-processes USD to match RCP's ShaderGraph/MaterialX expectations.
- Non-blocking bake workflow: baking is executed in a background Blender process so the UI remains responsive.

## Repository Layout
- `Plugin/` - Blender extension package (add-on code).
- `Plugin/ops/` - Operators (export, diagnostics).
- `Plugin/ui/` - UI panels for export + compatibility status.
- `Plugin/export/` - USD export pipeline and post-processing.
- `Plugin/export/materials/` - Material extraction, graph building, and authoring.
- `Plugin/export/bake_textures.py` - Texture baking helpers for Bake & Export.
- `Plugin/manifest/` - Prebuilt MaterialX nodedef manifest (runtime only; no rebuild in-plugin).
- `References/` - MaterialX definitions and Reality Composer Pro reference assets.
- `scripts/` - Developer scripts (manifest builder, nodegroup builder, validation).

## Export Pipeline (End-to-End)
The export is a multi-step pipeline:

### 0) Settings + strict validation
Entry point: `Plugin/ops/export_operator.py`
- Reads export settings from `context.scene.blender_to_rcp_export_settings`.
- Suggests a default output path based on the current `.blend` filename.
- Validates all scene materials in strict mode (`Plugin/nodes/validate.py`); unsupported nodes block export.

### 1) Blender USD export (base stage)
Wrapper: `Plugin/export/blender_usd_export.py`
- Computes the real output path:
  - For `.usda/.usdc`: export directly to the requested file.
  - For `.usdz`: export to `.blendertorcp_temp/<name>.usdc` first, then package later.
- Calls `bpy.ops.wm.usd_export(...)` with:
  - `export_textures = False` (Blender won't pack/copy textures; we stage them ourselves)
  - `export_materials = True` (we need the authored bindings as a starting point, even though we rewrite)
  - `convert_orientation/forward_axis/up_axis` from our panel settings

### 1b) Bake & Export (background workflow)
Entry point: `Plugin/ops/bake_export_operator.py` (`blendertorcp.bake_export_background`)
- Spawns a second Blender process to keep the UI responsive.
- Writes job state to `<export_dir>/.blendertorcp_jobs/<job_id>/status.json`.
- Streams output to `log.txt` in the same job directory.
- The job runner lives inside the add-on: `Plugin/bake_export_runner.py`.

Runner behavior (`Plugin/bake_export_runner.py`):
- Ensures the add-on is enabled.
- Applies serialized settings from `settings.json`.
- Bakes textures to `<export_dir>/textures` using `Plugin/export/bake_textures.py`.
- Forces an Unlit rewrite for exported materials.
- Runs the normal USD export + postprocess pipeline.

### 2) Animation preparation (optional)
When `export_animation=True`, we temporarily restructure animation so Reality Composer Pro can clip it reliably.

Implementation: `Plugin/export/animation_export.py`
- Targets:
  - Armatures (skel animation)
  - Non-armature objects with transform animation (meshes, empties, cameras, etc.)
  - Shape keys (mesh shapekeys are handled separately; NLA baking doesn't support them directly)
- Sources:
  - All `bpy.data.actions` (alphabetical order)
- Strategy:
  - For each target, build a single continuous timeline by placing each action back-to-back.
  - Bake to a temporary action for export.
  - Record clip segments (name + start/end frames) into diagnostics.
  - Always restore the `.blend` scene state (tracks, actions, selection, active object) on success/failure.

### 3) USD post-processing (RealityKit/RCP compatibility)
Pipeline: `Plugin/export/postprocess_usd.py`
- Opens the stage with pxr (`Usd.Stage.Open(..., LoadAll)`).
- Runs:
  - `normalize_scene(stage, settings)` (`Plugin/export/usd_scene.py`)
    - Repairs common invalid patterns for downstream tools (example: re-type prims authored as `Xform` but carrying `Mesh` attributes).
  - `rewrite_materials(stage, settings, context, diagnostics)` (`Plugin/export/materials/...`)
    - Replaces Blender-authored materials with RealityKit ShaderGraph MaterialX graphs.
  - `author_animation_library(stage, settings, diagnostics)` (`Plugin/export/usd_animation_library.py`)
    - Authors a minimal `RealityKitComponent "AnimationLibrary"` with clip boundaries for RCP.
  - `prepare_textures(stage, usd_path, settings, diagnostics)` (`Plugin/export/usd_textures.py`)
    - Copies textures into `<usd_dir>/textures`
    - Rewrites all texture asset paths to be relative (so the export is portable)
  - `prepare_assets(stage, usd_path, diagnostics)` (`Plugin/export/usd_assets.py`)
    - Same staging/relativizing pattern for non-texture assets
- Saves the stage.

### 4) USDZ packaging (optional)
Packager: `Plugin/export/pack_usdz.py`
- Uses `usdzip` if configured in add-on preferences; otherwise creates a stored (uncompressed) zip.
- Includes the main USD plus `textures/` and `assets/` folders.

### 5) Diagnostics
Diagnostics collector: `Plugin/export/diagnostics.py`
- Captures warnings/errors, animation segment timings, and export metadata.
- The repo ignores `*.diagnostics.json` (intended as local debug output, not committed).

## Material Rewrite Flow
1. **Manifest** (`Plugin/manifest/rk_nodes_manifest.json`)
   - Prebuilt catalog of MaterialX nodedefs.
   - Loaded by `Plugin/manifest/materialx_nodes.py`.
   - Typed variants are selected by IO signature.

2. **Extraction** (`Plugin/export/materials/extract/core.py`)
   - Traverses Blender nodes and emits `material_data`.
   - Produces `input_graphs` for non-trivial chains.
   - Emits unresolved warnings for unsupported patterns.

3. **Graph Build** (`Plugin/export/materials/graph.py`)
   - Constructs a MaterialX node graph payload.
   - Injects expression graphs into shader inputs.

4. **Authoring** (`Plugin/export/materials/author.py`)
   - Creates USD Shade nodes from the graph payload.
   - Connects textures, constants, and graph nodes.
   - Applies conversion nodes when types differ.

5. **Texture Nodes** (`Plugin/export/materials/textures.py`)
   - Picks image nodedefs by output type.
   - Adds separate/combine only when needed (e.g., alpha usage).
   - Applies swizzle for channel extraction.
   - Normal maps use ShaderGraph's `Normal Map` (`ND_normalmap`) so tangent-space normals are transformed correctly.

## Texture and Asset Staging
- Image paths are resolved in `extract/core.py`. Packed or temp images are staged to a stable temp cache so they can be copied.
- `prepare_textures()` copies textures into `<usd_dir>/textures` and rewrites asset paths to relative.
- `prepare_assets()` handles non-texture assets similarly.

## Validation and Strict Mode
- `Plugin/nodes/validate.py` defines supported, partial, bake-required, and unsupported nodes.
- Export is strict: unsupported nodes block export with clear errors.
- The Shader Editor panel shows compatibility status and last diagnostics.

## UI and Settings
- Main export panel: `Plugin/ui/panel.py`.
- Shader compatibility panel: `Plugin/ui/shader_panel.py`.
- Add-on preferences: `Plugin/prefs.py`.
- Export settings are stored on the scene and applied per export.
- Bake & Export background status is shown inline under the Bake & Export button, sourced from the job's `status.json`.
- Bake & Export runs exclusively as a background job (no blocking UI operator).

## Developer Scripts
- `scripts/build_materialx_manifest.py` - rebuild `rk_nodes_manifest.json` from `.mtlx` sources.
- `scripts/build_nodegroups.py` - generate `Plugin/assets/nodegroups.blend` for authoring previews.
- `scripts/validate_nodes.py` - systematic validation tooling.

## Animation Export & RCP Clips
- Animation concatenation/bake is implemented in `Plugin/export/animation_export.py`.
  - Source: all `bpy.data.actions` (alphabetical).
  - Output: per-target baked actions used only for export, then scene state is restored.
- RCP clips are authored in `Plugin/export/usd_animation_library.py` by writing a
  `RealityKitComponent` named `AnimationLibrary` under the stage default prim.
  - Minimal fields: `clipNames`, `startTimes`, and `sourceAnimationName`.
  - `sourceAnimationName` varies based on how animation is authored in USD and how Reality Composer Pro labels it.
    To avoid missing clips, we author clip definitions for multiple likely sources:
    - `"default subtree animation"` (common for skeletal/UsdSkel pipelines)
    - `"transform animation"` (common for transform-only timelines)
  - Clip timing is currently authored from the integer frame boundaries of the baked
    export timeline (converted to seconds using `timeCodesPerSecond`). Reality Composer Pro
    behavior for sub-frame clip boundaries is not fully characterized yet.
