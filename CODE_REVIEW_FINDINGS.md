# BlenderToRCP — Codebase Review Findings

> **Historical snapshot (2026-07-22, pre-modernization).** Several findings were
> fixed by the Blender 5.2 modernization pass that followed: clearcoat/Coat
> extraction, TEX_MUSGRAVE removal, the stale 1.2.0 version, `preferences set`
> persistence, the CLI `--timeout` wiring, GeomSubset material rewrite, and the
> avifenc pipeline (now native imbuf; the "robust avifenc subprocess" note below
> refers to deleted code). Remaining items are still open.

*Full-codebase review (branch `dev`, 2026-07-22). Four parallel deep reviews covering the core export pipeline, the material/MaterialX translation subsystem, the add-on shell/UI/ops layer, and the CLI/API/scripts/tests — plus a cross-cutting hygiene pass. Key high-severity claims were independently re-verified against the source.*

---

## High severity (fix first)

### Material translation correctness

1. **Mapping-node UV transforms are silently dropped.**
   [core.py:2321](Plugin/export/materials/extract/core.py:2321) — `_extract_mapping_from_node` reads `node.translation/rotation/scale` via `getattr(..., default)`, but `ShaderNodeMapping` hasn't had those attributes since Blender 2.81 (they are input sockets). Every Mapping node yields an identity `place2d`, so tiling/offset/rotation exports untransformed with no warning. *Verified in source.*

2. **Modern Mix node (`ShaderNodeMix`) color/vector mixing can never resolve.**
   [core.py:2238](Plugin/export/materials/extract/core.py:2238) and [validate.py:391](Plugin/nodes/validate.py:391) — `node.inputs.get('A')` returns the *float* A socket (index 2); the RGBA sockets are at indices 6/7. Color mixes built with the default Mix node (default since Blender 3.4) always fall through to "unresolved / requires baking"; only legacy MixRGB works. Select sockets by `data_type`.

3. **RGB Curves channel order is wrong.** [core.py:1631](Plugin/export/materials/extract/core.py:1631) — `mapping.curves` is `[R, G, B, Combined]`, the code assumes `[Combined, R, G, B]`. Any non-trivial curve exports visibly wrong colors while passing validation.

4. **Multi-material meshes are never rewritten.** [rewrite.py:27](Plugin/export/materials/rewrite.py:27) — only `UsdGeom.Mesh` prims with direct bindings are visited; Blender binds materials to `GeomSubset` children when a mesh has 2+ slots, so those materials silently keep the UsdPreviewSurface output.

5. **Clearcoat extraction is dead on all supported Blender versions.** [core.py:191](Plugin/export/materials/extract/core.py:191) — Blender 4.0 renamed `Clearcoat*` → `Coat *`; with a 5.1 minimum, `inputs.get('Clearcoat')` is always `None`. Coat never exports and no diagnostic fires (the `Specular IOR Level` / `Emission Color` renames *are* handled nearby).

### Export pipeline

6. **A bake failure mid-loop leaks baked materials into the scene with no restore.**
   [bake_textures.py:187](Plugin/export/bake_textures.py:187) — `bake_materials_for_objects` mutates slots incrementally but only *returns* the `BakeResult` on success; both callers ([bake_export_runner.py:411](Plugin/bake_export_runner.py:411), [bake_export.py:202](Plugin/api/commands/bake_export.py:202)) restore from that return value in `finally`. If object N fails (e.g. missing UVs), objects 1..N-1 keep baked materials and images/materials leak into `bpy.data`. Validate all objects up front and/or attach the partial result to the exception.

7. **Both USDZ packaging paths are broken in different ways.**
   - [pack_usdz.py:44](Plugin/export/pack_usdz.py:44) — external `usdzip` is invoked in file-list mode (`usdzip out.usdz scene.usd`), which does **not** localize dependencies; users who configure `usdzip_path` get USDZs with dangling `textures/` and `assets/` references. Needs `usdzip --asset` / `-r`.
   - [pack_usdz.py:62](Plugin/export/pack_usdz.py:62) — the Python fallback uses plain `zipfile` with no 64-byte alignment, which the USDZ spec requires; strict readers (AR QuickLook, mmap-based loaders) can reject the archive.

### Add-on shell

8. **Zombie children defeat crash detection — the UI can stay locked in "running" forever.**
   [bake_export_operator.py:139](Plugin/ops/bake_export_operator.py:139) — the `Popen` handle is dropped and never `poll()`ed/`wait()`ed; on macOS/Linux a dead child becomes a zombie, `os.kill(pid, 0)` succeeds for zombies, so `_pid_is_running` reports the crashed runner alive. If the runner dies without writing a terminal status, the panel stays greyed out ("Settings are locked…") indefinitely. Keep the `Popen` object and use `proc.poll()`.

9. **The shader authoring UI is dead code — advertised features don't appear.**
   [ui/__init__.py](Plugin/ui/__init__.py) imports only `panel` and `shader_panel`; nothing imports `shader_menu.py` or `shader_authoring_panel.py`. The "RealityKit Authoring" N-panel and the `Add > RealityKit Nodes` menu promised in the README never register; their operators are reachable only via F3 search. *Verified in source.*

### CLI

10. **`--timeout` never reaches the subprocess — every CLI command is hard-killed at 600 s.**
    [cli/__main__.py:44](Plugin/cli/__main__.py:44) passes `getattr(parsed, "timeout", 600)`, but the only `--timeout` flag uses `dest="timeout_step"` (in-Blender per-step bake timeout). Long bakes get killed at 10 min with no way to raise the limit, skipping in-Blender cleanup and discarding partial output. *Verified in source.*

11. **`preferences set` doesn't persist.** [preferences_set.py:36](Plugin/api/commands/preferences_set.py:36) — `setattr` succeeds but `bpy.ops.wm.save_userpref()` is never called anywhere in the codebase (*verified by grep*); background Blender doesn't auto-save prefs, and each CLI call is a fresh process. The command reports success and is a no-op.

12. **The nodedef lint in `validate_exports.py` is vacuous.** [validate_exports.py:25](scripts/validate_exports.py:25) — `r'info:id\\s*=\\s*"..."'` uses `\\s` inside a raw string (literal backslash), so the regex never matches real usda text; "Unknown nodedef" errors are never produced and the manifest lint always passes. *Verified in source.*

---

## Medium severity

### Correctness / behavior

- **Every action applied to every animated target** — [animation_export.py:374](Plugin/export/animation_export.py:374): `_apply_schedule` strips *all* of `bpy.data.actions` onto each target's NLA track; object A physically plays object B's motion during B's clip segment. Filter the schedule per target (by `id_root` and original assignment).
- **Prim rename destroys subtrees** — [usd_scene.py:29](Plugin/export/usd_scene.py:29): the invalid-identifier repair copies only attribute defaults to a new prim, then `RemovePrim` deletes the original *including children, relationships, kind, and time samples*. Use `Sdf.BatchNamespaceEdit`.
- **Re-pack can permanently replace packed image data** — [blender_usd_export.py:20](Plugin/export/blender_usd_export.py:20): `unpack(USE_ORIGINAL)` + `pack()` swaps the .blend's packed pixels for whatever is currently on disk if the disk file changed since packing.
- **Failed texture copies still rewrite asset paths** — [usd_textures.py:193](Plugin/export/usd_textures.py:193), [usd_assets.py:73](Plugin/export/usd_assets.py:73): after a failed copy/convert the attribute is still rewritten to a nonexistent relative path, replacing a possibly still-working absolute one.
- **Muted nodes treated as active** — no `node.mute`/`link.is_muted` handling anywhere in the materials subsystem; muted operations get baked back in or flagged as errors.
- **Diamond-shaped graphs fail to resolve** — [core.py:1093](Plugin/export/materials/extract/core.py:1093): the `visited` set never unwinds and is shared across sibling branches, so two branches sharing one image node make the whole expression "unresolved".
- **Color Ramp exports only first/last stops** — [core.py:1579](Plugin/export/materials/extract/core.py:1579): middle stops, positions, and interpolation are discarded with no warning while `VALTORGB` is listed as fully supported.
- **`force_unlit` wires PBR-named graphs to the unlit shader** — [graph.py:85](Plugin/export/materials/graph.py:85): `baseColor` etc. don't exist on `realitykit_unlit_surfaceshader`; graph-driven color is lost and a dangling input is authored.
- **USD helper-prim name collisions** — [textures.py:253,403,446,489,847](Plugin/export/materials/textures.py:253): NormalMap/place2d/srgb/scale/swizzle prims are named from the input name only (`in1`, `fg`…); collisions silently rewire earlier nodes. Route through `_unique_shader_name`.
- **Silent drops on partial resolution** — [graph.py:189](Plugin/export/materials/graph.py:189) (unresolved sub-expressions fall back to nodedef defaults, no diagnostic) and [rewrite.py:72](Plugin/export/materials/rewrite.py:72) (`type == 'unknown'` materials skipped with neither converted nor failed recorded) — both violate the strict-validation promise.
- **Strict validation gaps** — [validate.py](Plugin/nodes/validate.py): node-type-only checks let Transmission/Sheen/Subsurface-heavy Principled setups export as plain opaque PBR with zero warnings (M11); the mix-identity check ignores `blend_type` and rejects supported multiply-mixes while passing unsupported ones (M4).
- **Foreground export lacks the running-job guard** — [export_operator.py:66](Plugin/ops/export_operator.py:66): invoking `blendertorcp.export` via F3 while a background job runs deletes the staging tree the runner is baking into. Mirror the check from [bake_export_operator.py:87](Plugin/ops/bake_export_operator.py:87).
- **`load_post` silently orphans running jobs** — [panel.py:1141](Plugin/ui/panel.py:1141): opening any file clears job state without terminating or mentioning the still-running process; there's then no way to cancel it from the UI.
- **Exit code 3 unreachable** — [cli/__main__.py:445](Plugin/cli/__main__.py:445): the "plugin not installed" substring match doesn't match the actual error text from [addon_loader.py:72](Plugin/api/addon_loader.py:72); a missing addon exits 1, not the documented 3. The existing test mocks a fabricated message, masking this.
- **Version mismatch** — [Plugin/__init__.py:38](Plugin/__init__.py) says `(1, 2, 0)`; [blender_manifest.toml](Plugin/blender_manifest.toml) says `1.3.0`; the CLI `version` command reports the stale one.
- **`realitytool` check spuriously fails for `.usdc`** — [validate_exports.py:212](scripts/validate_exports.py:212): crate files are renamed to `scene.usda`, which the text parser can't open.
- **Non-executable `BLENDERTORCP_BLENDER` crashes with a raw traceback** — [bridge.py:139](Plugin/cli/bridge.py:139): only `FileNotFoundError`/`TimeoutExpired` caught; pointing at `/Applications/Blender.app` (the bundle dir) raises an uncaught `PermissionError`, breaking the JSON envelope.
- **Runner `--` edge case** — [runner.py:107](Plugin/api/runner.py:107): the payload read happens *before* the try whose except claims to catch `IndexError`; bare `--` yields an unhandled traceback and "No output from Blender".

### Performance

- **Per-tick add-on rescan** — [prefs.py:16](Plugin/prefs.py:16) → `addon_utils.modules(refresh=True)` runs on *every* property update callback, including each mouse-move tick while dragging a slider. Cache the module name.
- **Repeated SHA1 of large textures** — [usd_textures.py:112](Plugin/export/usd_textures.py:112): full-file hash recomputed per referencing attribute (50 materials → 50 hashes of the same 4K texture). Cache per resolved path.
- **Python-list pixel processing** — [bake_textures.py:1451](Plugin/export/bake_textures.py:1451): opacity merge uses `list(image.pixels)` + per-pixel loop (~16.7M floats twice at 2048²); use `foreach_get/foreach_set`.
- Double graph traversal per material (warnings + extraction each walk the graph); trivially cacheable catalog lookups in `metadata.py`/`validate.py`.

### Process / hygiene

- **No test or lint CI.** 279 tests exist but the only workflow ([build-archive.yml](.github/workflows/build-archive.yml)) just zips releases. Add a pytest + ruff job on push/PR — several findings above (exit codes, prefs persistence, regex) would have been caught by cheap tests.
- **282 `except Exception` handlers, ~113 silently `pass`** — heaviest in bake_textures.py (46), extract/core.py (34), animation_export.py (27). Disk-full and permission errors currently make jobs look frozen with nothing in the log ([bake_export_runner.py:100](Plugin/bake_export_runner.py:100)).
- **Job directories never pruned** — every bake leaves a `.blendertorcp_jobs/...` dir next to the export ([bake_export_operator.py:506](Plugin/ops/bake_export_operator.py:506)).
- **Modal watcher / timers not stopped on unregister** — [bake_export_operator.py:574](Plugin/ops/bake_export_operator.py:574), [panel.py:1075](Plugin/ui/panel.py:1075): reload/disable while a job runs leaves the modal handler and a one-shot timer referencing unregistered classes.

---

## Duplication & decomposition (maintainability)

- **Capability knowledge is triplicated and has drifted**: the supported-node sets in [validate.py](Plugin/nodes/validate.py), the warning sets in [core.py:368](Plugin/export/materials/extract/core.py:368), and the actual resolver disagree — the validator says `CURVE_RGB`/`INVERT`/`CLAMP` etc. are supported while export-time warnings call them "requires baking"/"unrecognized". Hoist one shared `capabilities` module; converting the resolver's giant if-chain to a dispatch table gives validation a single source of truth.
- **`extract/core.py` (2,624 lines)** has clean seams: principled extraction, socket resolver, warnings, RK-group extraction, image staging → 5 modules.
- **Six drifting copies of the settings skip-key set** ([panel.py:66](Plugin/ui/panel.py:66), [panel.py:1044](Plugin/ui/panel.py:1044), [export_operator.py:484,515](Plugin/ops/export_operator.py:484), [bake_export_operator.py:30](Plugin/ops/bake_export_operator.py:30), [bake_export_runner.py:55](Plugin/bake_export_runner.py:55)) — one copy has already drifted (missing `persist_suspended`).
- **Verbatim duplicate helpers**: `_pid_is_running` (panel.py / bake_export_operator.py), `_safe_filename_stem` (blender_usd_export.py / usd_textures.py), `_unique_destination_name` (usd_textures.py / usd_assets.py), staging-cleanup logic (pack_usdz.py / blender_usd_export.py), settings persistence (3 near-copies), `_get_active_material` (2 copies), the `validate_material(strict=True)`/`TypeError` shim (5 copies).
- **Dead code to delete**: `get_export_settings` ([blender_usd_export.py:464](Plugin/export/blender_usd_export.py:464)), `validate_usdz` + `get_usdz_staging_dir` (pack_usdz.py), `_apply_srgb_to_linear` ([textures.py:429](Plugin/export/materials/textures.py:429)), `_find_rk_group_node` + duplicate `_get_manifest` (core.py), all `TEX_MUSGRAVE` handling (node removed in Blender 4.1; min is 5.1), the unreachable `usd_export` availability check ([blender_usd_export.py:270](Plugin/export/blender_usd_export.py:270)), `ExportHelper` inheritance that never opens a file browser, duplicated `_set_selection` merge-artifact block ([bake_export_operator.py:465](Plugin/ops/bake_export_operator.py:465)).
- **Inert preferences**: `default_export_format` and `enable_diagnostics` in [prefs.py](Plugin/prefs.py) are shown in the prefs UI but never affect UI exports — wire them in or remove them.
- **`panel.py` split**: ~530 lines are the PropertyGroup, ~200 are job-status plumbing shared with the operator — extract `properties.py` and `job_status.py`.

---

## Test coverage gaps (highest value first)

1. `Plugin/bake_export_runner.py` — the UI background-job runner and its status-file protocol: zero tests.
2. The core USD pipeline: `postprocess_usd.py`, `pack_usdz.py`, `usd_materials.py`, `usd_scene.py`, `materialx_builder/graph/extract`, and `bake_textures.py` beyond the cache key — the largest untested surface.
3. Real addon-failure exit-code path (current test mocks a message that production code never emits).
4. `export.py`/`bake_export.py` command handlers: override application, invalid-override errors, diagnostics-on-failure, restore paths.
5. `preferences get/set` round trip across two CLI invocations (would catch the persistence no-op).
6. `runner.py` edge cases (missing payload, bad JSON) and the `parsed`→bridge-args mapping (would catch the `--timeout` bug).
7. `scripts/` — a one-line fixture test on `NODEDEF_RE` would catch the vacuous regex.

## Docs drift (docs/CLI.md)

- Exit-code table: argparse usage errors exit 2, which the table defines as "Blender not found"; exit 3 is currently unreachable (see above).
- Bake settings table omits `bake_roughness_mode` and `apply_yup_geometry`; `settings list` example shows lowercase `"enum"` vs actual `"ENUM"`; AVIF note says "Blender 5.1+" while the manifest pins 5.2.0 minimum.
- Override metavar `--key=value` documents a syntax argparse rejects (only dash-less `key=value` works); malformed override tokens are silently dropped rather than erroring.

---

## What's in good shape

Y-up bake finalize (snapshot + `finally` restore, per-object guards), temporary IBL/samples/isolation context managers, symmetric animation prepare/restore, staging-dir deletion fenced to `.blendertorcp_temp`, robust `avifenc` subprocess use, atomic write-then-rename status IPC, `SKIP_SAVE` on job PID properties, no shell/code-injection paths in the CLI bridge (list-argv, JSON payload, no eval/exec), clean `.gitignore`, zero TODO/FIXME debt.
