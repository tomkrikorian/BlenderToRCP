# BlenderToRCP — Codebase Review Findings

**Status as of 2026-07-29, branch `experiment/rcp-import-export`.**

This file began as a snapshot of a 2026-07-22 review of `dev`, taken before the
Blender 5.2 modernization. It had drifted badly: it listed as "still open"
several things that were already fixed, and cited version numbers and line
references that no longer exist. That made it actively misleading — the worst
state for a findings document, because it is read as current.

Every claim below was re-checked against the code on the date above. Items are
grouped by **what is true now**, not by what the original review said. Where a
claim was checked by running something rather than reading code, the
measurement is included, because several findings in the original list turned
out to be wrong in exactly the cases where nobody had measured.

A second pass on 2026-07-29 — a documentation audit that produced
`docs/MATERIAL_TRANSLATION.md`, `docs/BAKING.md`, `docs/EXPORT_PIPELINE.md` and
`docs/SETTINGS.md` — added the "silently wrong output" and "surprising but
loud" sections below. Those findings came out of writing down what the exporter
actually does, which is a more effective way to find defects than looking for
them directly: the worst ones are all cases where the code does something
reasonable-looking that nobody had ever stated in prose.

---

## Still open

### Silently wrong output (found by the 2026-07-29 documentation audit)

These produce a plausible-looking asset that is wrong. Every one was measured,
and the measurement is quoted so it can be re-run.

- **`LIT_IBL` gives every mesh-sharing instance the last instance's lighting.**
  `LIT_IBL` disables the bake reuse cache so each instance bakes its own texture
  ([bake_textures.py:256](Plugin/export/bake_textures.py:256)), but the baked
  material is assigned to a `DATA`-linked slot
  ([bake_textures.py:355](Plugin/export/bake_textures.py:355)) — i.e. onto the
  shared *mesh datablock*. Last write wins. The comment at
  [bake_textures.py:149](Plugin/export/bake_textures.py:149) documents this exact
  hazard and guards the read side; the write side is unguarded and `slot.link`
  is never set to `'OBJECT'` anywhere.
  *Measured:* two objects sharing one mesh (Alt+D), sun light, a slab occluding
  only the second. Both export bound to `</root/_materials/Shared_Baked_1>`,
  whose texture measures `R[0.0000, 0.2275]`, mean `0.0003`. **The fully lit
  cube exports black.** Three `COMBINED` bakes run and two outputs are discarded.
  `LIT_IBL` is the default bake mode and linked duplicates are the standard
  Blender instancing idiom.

- **Invalid MaterialX ships for a textbook graph.** The nodedef selector falls
  back signature → input/output → output-only → *any nodedef of that name*
  ([materialx_nodes.py:91](Plugin/manifest/materialx_nodes.py:91)).
  `luminance→float` returns a `color3`-output nodedef, and the resulting
  `color3→float` convert resolves to **`ND_convert_boolean_float`**. Because that
  is truthy, the `missing_mappings` diagnostic at
  [conversions.py:265](Plugin/export/materials/conversions.py:265) never fires.
  *Measured:* `Image Texture → RGB to BW → Roughness` exports `"ok": true` with
  no diagnostics, and the USD contains a `ND_convert_boolean_float` shader whose
  `in` is declared `color3f`, wired to `inputs:roughness`. RealityKit cannot
  bind that.

- **Blender's scene unit scale is ignored.**
  [blender_usd_export.py:1175](Plugin/export/blender_usd_export.py:1175) pins
  `convert_scene_units='METERS'` / `meters_per_unit=1.0`. Nothing in the export
  path reads `scene.unit_settings.scale_length` — it is read only for reporting
  (`scene_info.py`, `support_bundle.py`). Blender's enum *declares*
  `metersPerUnit` rather than rescaling points, so the declared unit and the
  authored geometry diverge whenever the scene is not at 1.0.
  *Measured:* an identical 2-unit cube exported from `scale_length=1.0` and
  `scale_length=0.01` produced byte-identical `metersPerUnit = 1` and
  `extent = [(-1,-1,-1),(1,1,1)]`. A user modelling in centimetres reads "2 cm"
  in the sidebar and gets a 2 m object, 100x oversized, with no warning. Pinning
  `metersPerUnit=1` is correct for the Apple contract; the gap is that a
  non-1.0 `scale_length` should be compensated or refused.

- **Averaged roughness is a function of bake margin, not of the material.**
  `_average_image_value`
  ([bake_textures.py:1674](Plugin/export/bake_textures.py:1674)) means over the
  whole buffer including texels no UV island covers, which are `0`.
  *Measured:* one material at `Roughness = 0.5` → margin `0`: **0.3373**;
  margin `8` (the default): **0.4074**; margin `32`: **0.5011**. At the shipped
  default the exported constant is 18.5% low. A UV-coverage mask would fix it.

- **Transparent materials export roughness `0` and darker RGB.** Cycles'
  `ROUGHNESS` pass returns `0` on alpha-blended surfaces and nothing detects or
  compensates.
  *Measured:* two materials identical but for `Alpha`, both `Roughness = 0.5` →
  opaque `R[0.0000, 0.5020]`, `Alpha=0.4` `R[0.0000, 0.0000]`. Isolated from the
  opacity pass. Any glass or foliage material baked with `LIT_ALBEDO` gets a
  mirror finish. Separately, the same material's RGB bakes darker (opaque peak
  `R = 0.4941` vs `0.3176`), and RealityKit then applies alpha again on top.

- **Nested unresolved sub-expressions vanish without a warning.**
  [extract/core.py:402](Plugin/export/materials/extract/core.py:402) checks only
  the top-level `kind`, and `_expr_from_socket` returns the unresolved dict
  rather than `None`, so a surrounding node is built and the graph builder drops
  the unresolved child — the input silently falls back to a nodedef default.
  Every multi-input resolver branch has this shape.

- **Stashed Actions are dropped silently, and the comment says otherwise.**
  [animation_export.py:529](Plugin/export/animation_export.py:529) documents its
  `slot.users()` scan as covering "logical takes that are not the active Action
  and are not currently staged as NLA strips", but in Blender 5.2 `users()`
  returns only *live* users, so it is empty for exactly that case.
  *Measured:* three Actions on one object (active / NLA strip / stashed with
  fake user) exported two takes; the stashed one was absent from both the
  schedule and the clip list, with no warning.

- **`LIT_IBL` with no world and no lights exports black and reports success.**
  `_temporary_ibl_world` returns early for `SCENE_WORLD`
  ([bake_textures.py:718](Plugin/export/bake_textures.py:718)) and nothing checks
  that any light exists. *Measured:* `scene.world = None`, no lights → `ok: true`,
  one 2048x2048 texture, mean `0.0000`, no warning anywhere.

- **Emission is rejected in `LIT_ALBEDO` but silently dropped in
  `UNLIT_ALBEDO`.** The validator is gated on `bake_mode == "LIT_ALBEDO"`
  ([bake_textures.py:1321](Plugin/export/bake_textures.py:1321)).
  *Measured:* a material with `Emission Strength = 2.0` fails under
  `LIT_ALBEDO` with a precise message and exports `ok: true` under
  `UNLIT_ALBEDO` with a baked texture byte-identical to the same material with
  emission removed.

- **A legal material cannot be exported at all.** A Non-Color image on Base
  Color fails with `TEXTURE_COLOR_SPACE_MISMATCH`. The MaterialX graph is
  correct (`lin_rec709`); the failure comes from the retained native
  `UsdPreviewSurface` network, which Blender's own exporter tags
  `colorSpace:name = "data"`. `_remove_stale_preview_network`
  ([rewrite.py:681](Plugin/export/materials/rewrite.py:681)) only runs when a
  texture came from dirty or generated pixels, and `validate` reports OK first.
  *Measured:* export fails on `/root/_materials/M/Image_Texture`.

### Surprising but loud

- **`-o` extension is silently rewritten and the format comes from the
  `.blend`.** [export.py:117](Plugin/api/commands/export.py:117). `-o out.usdz`
  on a scene whose saved `export_format` is `USDA` writes `out.usda` and exits 0.
  `with_suffix` also mangles dotted stems: `-o /tmp/my.scene.v2` becomes
  `/tmp/my.scene.usda`.
- **`--json --verbose` leaks unredacted absolute paths to stderr.**
  [bridge.py:374](Plugin/cli/bridge.py:374) forwards `proc.stderr` raw; only the
  copy *inside* the envelope is `$HOME`-redacted. `--verbose` is what the docs
  tell users to pass when capturing output for a support issue.
- **User-facing conditions raised as bare `ValueError`** in `validate.py:67`,
  `settings_get.py:19`/`:26`, `preferences_set.py:26`/`:32` — bypassing
  `CommandError`, so `error.code` is `VALUEERROR` and a traceback is attached,
  defeating the policy in `runner.py`.
- **Actionable error detail is invisible without `--json`.**
  [cli/__main__.py:633](Plugin/cli/__main__.py:633) prints only `str(exc)`;
  which key, which value and which tokens were allowed all live in
  `error.details` and are dropped.
- **`preferences set` writes global user preferences with no `--save` and no
  `--dry-run`** ([preferences_set.py:36](Plugin/api/commands/preferences_set.py:36))
  — the opposite of `settings set`'s contract, in a sibling subcommand.
- **UI and CLI disagree on default bake resolution.** The operator forces
  `export_texture_settings_enabled = True` into the worker payload
  ([bake_export_operator.py:730](Plugin/ops/bake_export_operator.py:730)); the
  CLI leaves it `False`. *Measured:* same scene, 256 px source → sidebar bakes
  2048x2048, CLI bakes 512x512.
- **Packed ORM textures get two samplers.** `_texture_cache_key` includes
  `channel` ([textures.py:40](Plugin/export/materials/textures.py:40)), so one
  ORM file read for roughness (G) and metallic (B) authors two
  `ND_image_vector4` prims. Doubles sampler cost for the standard packing
  workflow.
- **UDIM is unsupported with a misleading error** — a tile set fails with
  `Texture file not found: .../tile.<UDIM>.png`. It does fail closed.
- **Validator/exporter drift, both directions.** `validate` says OK and export
  dies for sRGB-tagged data textures, `COMBINE_COLOR` in HSV/HSL, `VALTORGB`
  with <2 stops, `TEX_ENVIRONMENT` with no image, and materials with no active
  surface shader. Conversely `CURVE_RGB` is in `BAKE_TYPES`
  ([validate.py:91](Plugin/nodes/validate.py:91)) despite a complete resolver
  implementation, making that code unreachable.
- **The extractor's warning table is 11 node types behind the validator**
  ([extract/core.py:575](Plugin/export/materials/extract/core.py:575)) — 15
  supported types vs the validator's 29, so `TEX_NOISE`, `CLAMP`, `MAP_RANGE`
  and others export correctly while emitting "is unrecognized".
- **`bake_keep_materials` is a no-op from the UI** (the bake runs in a
  subprocess against a scene copy) **and leaves dangling paths from the CLI** —
  retained images' `filepath_raw` point into a staging directory that has been
  deleted.

### Correctness

- **Zombie children defeat crash detection.**
  [bake_export_operator.py:305](Plugin/ops/bake_export_operator.py:305) assigns
  `subprocess.Popen(...)` to a local and drops it; it is never `poll()`ed or
  `wait()`ed. `_pid_is_running`
  ([bake_export_operator.py:569](Plugin/ops/bake_export_operator.py:569),
  duplicated at [panel.py:1135](Plugin/ui/panel.py:1135)) uses
  `os.kill(pid, 0)`, which succeeds for a zombie. If the runner dies without
  writing a terminal status, the panel stays greyed out indefinitely. Keep the
  `Popen` object and use `proc.poll()`.

- **Foreground export lacks the running-job guard.**
  `Plugin/ops/export_operator.py` has no `background_job_pid` check (grep: zero
  hits), so invoking `blendertorcp.export` via F3 while a background job runs
  can delete the staging tree the runner is baking into.
  `bake_export_operator.py` has the guard; this path does not.

- **Muted nodes are treated as active.** No `node.mute` / `link.is_muted`
  handling anywhere under `Plugin/export/materials/` (grep: zero hits). A muted
  operation is still extracted, so it is baked back in or flagged as an error.

- **Two RK extraction paths disagree about normal textures.**
  `_extract_group_inputs` marks normal-named sockets `normal_texture` while
  `_build_rk_node_graph` always uses `texture`, so the same RK PBR Surface group
  gets a `normal_map_decode` on one path and a raw `color3`→`vector3` convert on
  the other. Resolving this needs the per-nodedef input semantics, not a guess
  about whether the value arrives encoded.

- **`_is_ktx_required` can silently blank a texture.** It is called but never
  satisfied — no node in `rk_nodes_manifest.json` sets `policy.requires_ktx`. If
  it ever fires, `_create_texture_connection` returns `None` with only a
  warning and `author.py` substitutes the nodedef default, so the texture is
  replaced by a flat value instead of failing the export.

### Packaging

- **One unreferenced texture copy per generation directory.** The same image
  reaches staging through two different asset paths, so a second
  content-addressed copy is written and packaged although the stage references
  only one. Wasted bytes, not a correctness problem. Pruning it means trusting
  `_referenced_texture_paths` for a much wider deletion than it is used for
  today, which deserves an audit first.

### Verification

- **CI validates no exported artifact with Apple tooling.** The archive smoke is
  invoked only from `ci.yml`'s `blender-5-2-integration` job on `ubuntu-24.04`,
  where neither `usdchecker` nor `realitytool` exists;
  `apple-platform-validation.yml` never invokes it. Both stages have reported
  `{"available": false}` in every run to date. Since 2026-07-29 this is at least
  *declared* — the run now fails unless the lane names the stages it cannot
  perform — but declaring a gap is not closing it. The fix is to invoke the
  smoke from the Apple lane, where both tools are present.

- **Workflow trust-policy tests assert against a Python reimplementation.**
  `tests/unit/test_workflow_trust_policy.py` models the shell policy in Python
  and tests the model; the tie to the real workflow is coarse substring checks.
  Turning the real ancestry check into a non-fatal warning would keep every test
  green.

- **`git diff --check` in `ci.yml` can never fail.** It runs as the first
  command against a pristine `actions/checkout` tree, so it always diffs an
  index against itself.

### Hygiene

- **Job directories are never pruned.** Every bake leaves a
  `.blendertorcp_jobs/...` directory next to the export (grep for pruning:
  zero hits).
- **`load_post` silently orphans running jobs** — opening a file clears job
  state without terminating or mentioning the still-running process.
- **Modal watcher / timers are not stopped on unregister.**
- **Release archive is built from the working tree** and does not exclude
  `*.blend1`, so a stray Blender backup under `Plugin/` would ship and break the
  byte-for-byte determinism `--check` exists to prove.
- **`.DS_Store` is tracked** despite being in `.gitignore` (the rule has no
  effect on an already-tracked path).
- **Duplicated helpers** remain: `_pid_is_running`, `_safe_filename_stem`,
  `_unique_destination_name`, `_get_active_material`, and the several near-copies
  of the settings skip-key set.
- **Inert preferences**: `default_export_format` and `enable_diagnostics` are
  shown in the prefs UI but never affect UI exports.

---

## Fixed since the original review

Verified fixed on 2026-07-29 unless noted.

| Original finding | Evidence |
|---|---|
| Mapping-node UV transforms silently dropped | reads input sockets via `constant_vector("Scale", ...)` |
| RGB Curves channel order wrong | `curves[0]`→red, `curves[3]`→combined |
| Multi-material meshes never rewritten | `rewrite.py` handles `GeomSubset` |
| Clearcoat extraction dead | `Coat` rename handled |
| `usdzip` invoked without dependency localization | uses `usdzip --asset` |
| USDZ missing 64-byte alignment | `_USDZ_ALIGNMENT = 64` |
| `preferences set` doesn't persist | `save_userpref()` called |
| Vacuous nodedef lint in `validate_exports.py` | regex is a correct raw string |
| `--timeout` never reaches the subprocess | fixed in the modernization pass |
| Exit code 3 unreachable | dispatches on `exc.error_code == "ADDON_LOAD_FAILED"` |
| Version mismatch (1.2.0 vs 1.3.0) | single source: manifest `2.0.0`, asserted in CI |
| No test or lint CI | `ci.yml` runs unit tests, archive smoke, Blender 5.2 integration |
| Shader authoring UI is dead code | registered 2026-07-29; a structural test now requires every `Plugin/ui` module defining `register()` to be wired |
| `TEX_MUSGRAVE` handling | removed (zero references) |
| Dead code: `_write_output_sidecar_manifest`, `_remove_tracked_output_sidecars`, `_write_manifest_payload`, `get_usdz_staging_dir`, `_apply_srgb_to_linear`, `get_export_settings`, `_find_rk_group_node` | removed 2026-07-29 |
| Bake failure leaks baked materials | wrapper restores slots and removes partial datablocks on failure |

Also fixed on 2026-07-29, found after the original review:

- Bake inherited `scene.render.bake.target` and the COMBINED `pass_filter`, so a
  `.blend` saved with a vertex-colour target or with lighting passes disabled
  produced **all-black textures** and reported success.
- `settings set` silently discarded the first key on a pristine `.blend` and
  reported `"saved": true`; the `--save`-less form was a no-op that docs taught
  as canonical.
- Re-exporting to a path after a texture changed failed permanently with
  "Immutable sidecar collision has different bytes".
- `build_unlit_material` and the OpenPBR rename table authored inputs their
  nodedefs do not declare.
- RK node-group textures carried no colour-space role, so an sRGB-tagged normal
  map was silently decoded.
- Mapping nodes in TEXTURE mode exported the rotation with the wrong sign.
- Shape-key names containing `"` silently dropped that key's animation.
- `--json` error envelopes leaked `$HOME` and attached tracebacks to ordinary
  user errors.
- Baked textures were never bound to a UV map.

---

## Findings that did not hold

Recorded so they are not "re-discovered" and acted on.

- **"Modern Mix node color mixing can never resolve."** The claim was that
  `inputs.get('A')` returns the float socket at index 2 while the RGBA sockets
  are at 6/7. Measured on Blender 5.2: a `ShaderNodeMix` with
  `data_type='RGBA'` has ten input sockets, and `inputs.get('A')` returns the
  **RGBA** socket at index 6 — Blender resolves the name to the enabled socket.
  Name-based lookup is correct here.

- **"`_get_active_uv` reads the wrong UV layer."** The claim was that it reads
  `uv_layers.active` while the bake renders through `active_render`. Measured
  both directions on a two-UV mesh: the bake follows `uv_layers.active` — full
  coverage through the UI-active layer and 64/1024 texels through a
  quarter-scale one, regardless of where `active_render` points. The helper
  matches the bake.

- **"`bakeTest_02.import` is malformed."** The contract checker was wrong, not
  the fixture. The buffer suffix is a 64-bit hash rendered as hex with leading
  zeros stripped: across every RCP-authored asset, 390 suffixes are 16 chars, 21
  are 15 (~1/16) and 1 is 14 (~1/256) — the distribution of an unpadded
  rendering. The `{15,16}` bound rejected RCP's own output.

- **Cross-record UUID validation should be added to the contract checker.**
  Considered and rejected after measuring: three of the seven RCP-authored
  assets contain `resource`/`resource__type` pairs pointing at UUIDs no record
  defines, and every asset dangles `__asset_uuid` and `mesh_creation_graph`.
  Enforcing this would fail closed on Apple's own files. The reverse direction
  *is* measured clean and is now enforced: a buffer payload no record can name
  is rejected.

---

## Not re-verified

The original review's remaining medium-severity items were not re-checked on
2026-07-29 and may be fixed, stale, or still true. Treat them as leads, not
facts: prim-rename subtree loss, re-pack replacing packed image data, failed
texture copies still rewriting asset paths, diamond-shaped graph resolution,
Color Ramp middle stops, USD helper-prim name collisions, silent drops on
partial resolution, strict-validation gaps, non-executable
`BLENDERTORCP_BLENDER` handling, the runner `--` edge case, and the performance
items (repeated SHA1, double graph traversal).

The duplication/decomposition section of the original review (module splits,
capability triplication) was a design opinion rather than a defect list and has
not been re-assessed.
