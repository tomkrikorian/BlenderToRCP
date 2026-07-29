# BlenderToRCP — Codebase Review Findings

**Status as of 2026-07-29, branch `experiment/rcp-import-export`.**

Everything under **Still open** was re-checked on that date and is true
now. Everything the 2026-07-29 audit found has either been fixed (see
**Fixed since the original review**) or appears below with its
measurement attached.

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

### Packaging

- **One unreferenced texture copy per generation directory.** The same image
  reaches staging through two on-disk paths - the original, and the copy
  Blender's own exporter wrote - and the two are not byte-identical because
  Blender re-encodes, so content fingerprinting cannot merge them. Only one is
  referenced by the stage. Wasted bytes in the package, not a correctness
  problem.

  **Audited 2026-07-29; pruning is not safe today.** The obvious fix is to
  delete everything in the generation directory that
  `_referenced_texture_paths` ([usd_textures.py:1328](Plugin/export/usd_textures.py:1328))
  does not report. That function walks `stage.Traverse()` and reads
  `attr.Get()` with no time code, so it misses at least three classes of live
  reference: a texture used only by a **non-selected variant** (preflight
  iterates up to `MAX_VARIANT_COMBINATIONS = 256`, so variants are real in this
  pipeline), a texture referenced only at a **time sample**, and anything under
  an **inactive prim or unloaded payload**. Deleting on that basis would drop
  textures a variant needs - trading wasted bytes for a broken asset.

  Two viable routes, in preference order: (1) stop creating the duplicate, by
  reusing the already-staged destination when the source is one of the native
  copies recorded by `staging_namespace.record_native_texture_copies`; or
  (2) harden `_referenced_texture_paths` to walk variant combinations, time
  samples and inactive prims, and only then prune.

### Verification

- **CI validates no exported artifact with Apple tooling.** The archive smoke
  is invoked only from `ci.yml`'s `blender-5-2-integration` job on
  `ubuntu-24.04`, where neither `usdchecker` nor `realitytool` exists;
  `apple-platform-validation.yml` never invokes it. Both stages have reported
  `{"available": false}` in every run to date. Since 2026-07-29 this is at
  least *declared* - the run fails unless the lane names the stages it cannot
  perform - but declaring a gap is not closing it. The fix is to invoke the
  smoke from the Apple lane, where both tools are present. This machine has the
  full toolchain (xrOS SDK 27, `realitytool`, `usdchecker`), so it can be
  proven locally before being wired into CI.

- **Workflow trust-policy tests assert against a Python reimplementation.**
  `tests/unit/test_workflow_trust_policy.py` models the shell policy in Python
  and tests the model; the tie to the real workflow is coarse substring checks.
  Turning the real ancestry check into a non-fatal warning would keep every
  test green.

- **`git diff --check` in `ci.yml` can never fail.** It runs as the first
  command against a pristine `actions/checkout` tree, so it always diffs an
  index against itself.

### Correctness

- **Two RK extraction paths disagree about normal textures.**
  `_extract_group_inputs` marks normal-named sockets `normal_texture` while
  `_build_rk_node_graph` always uses `texture`, so the same RK PBR Surface group
  gets a `normal_map_decode` on one path and a raw `color3`→`vector3` convert on
  the other. Resolving this needs the per-nodedef input semantics, not a guess
  about whether the value arrives encoded.

- **`_is_ktx_required` can silently blank a texture.** It is called but never
  satisfied - no node in `rk_nodes_manifest.json` sets `policy.requires_ktx`. If
  it ever fires, `_create_texture_connection` returns `None` with only a
  warning and `author.py` substitutes the nodedef default, so the texture is
  replaced by a flat value instead of failing the export.

- **Nested unresolved sub-expressions vanish without a warning.**
  [extract/core.py:402](Plugin/export/materials/extract/core.py:402) checks only
  the top-level `kind`, and `_expr_from_socket` returns the unresolved dict
  rather than `None`, so a surrounding node is built and the graph builder drops
  the unresolved child - the input silently falls back to a nodedef default.
  Every multi-input resolver branch has this shape.

- **Stashed Actions are dropped silently, and the comment says otherwise.**
  [animation_export.py:529](Plugin/export/animation_export.py:529) documents its
  `slot.users()` scan as covering "logical takes that are not the active Action
  and are not currently staged as NLA strips", but in Blender 5.2 `users()`
  returns only *live* users, so it is empty for exactly that case.
  *Measured:* three Actions on one object (active / NLA strip / stashed with
  fake user) exported two takes; the stashed one was absent from both the
  schedule and the clip list, with no warning.

- **Validator/exporter drift, both directions.** `validate` says OK and export
  dies for sRGB-tagged data textures, `COMBINE_COLOR` in HSV/HSL, `VALTORGB`
  with <2 stops, `TEX_ENVIRONMENT` with no image, and materials with no active
  surface shader. Conversely `CURVE_RGB` is in `BAKE_TYPES`
  ([validate.py:91](Plugin/nodes/validate.py:91)) despite a complete resolver
  implementation, making that code unreachable.

- **The extractor's warning table is 11 node types behind the validator**
  ([extract/core.py:575](Plugin/export/materials/extract/core.py:575)) - 15
  supported types vs the validator's 29, so `TEX_NOISE`, `CLAMP`, `MAP_RANGE`
  and others export correctly while emitting "is unrecognized".

- **Packed ORM textures get two samplers.** `_texture_cache_key` includes
  `channel` ([textures.py:40](Plugin/export/materials/textures.py:40)), so one
  ORM file read for roughness (G) and metallic (B) authors two
  `ND_image_vector4` prims. Doubles sampler cost for the standard packing
  workflow.

- **UDIM is unsupported with a misleading error** - a tile set fails with
  `Texture file not found: .../tile.<UDIM>.png`. It does fail closed.

### Surprising but loud

- **`-o` extension is silently rewritten and the format comes from the
  `.blend`.** [export.py:117](Plugin/api/commands/export.py:117). `-o out.usdz`
  on a scene whose saved `export_format` is `USDA` writes `out.usda` and exits 0.
  `with_suffix` also mangles dotted stems: `-o /tmp/my.scene.v2` becomes
  `/tmp/my.scene.usda`.
- **User-facing conditions raised as bare `ValueError`** in `validate.py:67`,
  `settings_get.py:19`/`:26`, `preferences_set.py:26`/`:32` - bypassing
  `CommandError`, so `error.code` is `VALUEERROR` and a traceback is attached,
  defeating the policy in `runner.py`.
- **Actionable error detail is invisible without `--json`.**
  [cli/__main__.py:633](Plugin/cli/__main__.py:633) prints only `str(exc)`;
  which key, which value and which tokens were allowed all live in
  `error.details` and are dropped.
- **`preferences set` writes global user preferences with no `--save` and no
  `--dry-run`** ([preferences_set.py:36](Plugin/api/commands/preferences_set.py:36))
  - the opposite of `settings set`'s contract, in a sibling subcommand.
- **`bake_keep_materials` is a no-op from the UI** (the bake runs in a
  subprocess against a scene copy) **and leaves dangling paths from the CLI** -
  retained images' `filepath_raw` point into a staging directory that has been
  deleted.
- **`--quiet` does not suppress failure output.** Three lines still go to
  stderr, contradicting the flag's own help text.

### Hygiene

- **Job directories are never pruned.** Every bake leaves a
  `.blendertorcp_jobs/...` directory next to the export.
- **`load_post` silently orphans running jobs** - opening a file clears job
  state without terminating or mentioning the still-running process.
- **Modal watcher / timers are not stopped on unregister.**
- **Release archive is built from the working tree** and does not exclude
  `*.blend1`, so a stray Blender backup under `Plugin/` would ship and break the
  byte-for-byte determinism `--check` exists to prove.
- **Duplicated helpers** remain: `_safe_filename_stem`,
  `_unique_destination_name`, `_get_active_material`, and the several near-copies
  of the settings skip-key set. `_pid_is_running` is still duplicated between
  `panel.py` and `bake_export_operator.py`; only the operator's copy is
  zombie-safe, which is enough for the terminal-state path but leaves the
  panel's own liveness check able to report a zombie as alive.
- **Inert preferences**: `materialx_library_path` is drawn in the preferences UI
  and settable through `preferences set` but never read by the export pipeline;
  `enforcement_mode` is read by nothing at all.
- **Five phantom settings** - `incremental_frames`, `export_mesh_colors`,
  `accessibility_label`, `accessibility_description`, `export_meshes` - are read
  through `getattr` fallbacks but never declared on the PropertyGroup. Harmless
  today; declaring a property with any of those names would silently make it
  live.

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

**Silently wrong output**

- **`LIT_IBL` gave every mesh-sharing instance the last instance's lighting.**
  Baked materials went into DATA-linked slots, i.e. onto the shared mesh
  datablock, so with a linked duplicate (Alt+D) the last bake overwrote every
  earlier one. Measured: both cubes bound to one material, the cube in full sun
  exporting black. Slots are now switched to OBJECT for shared meshes and
  restored afterwards. `LIT_IBL` is the default bake mode.
- **Bake inherited `scene.render.bake.target` and the COMBINED `pass_filter`**,
  so a `.blend` saved with a vertex-colour target, or with lighting passes
  disabled, produced all-black textures and reported success.
- **Invalid MaterialX shipped for a textbook graph.** The nodedef selector fell
  through to looser indexes and returned `ND_convert_boolean_float` for a
  `color3`→`float` convert. Constraints now filter candidates instead.
- **Averaged roughness tracked the bake margin, not the material** - 0.118 /
  0.212 / 0.438 at margins 0 / 8 / 32 for a 0.5 material. Now 0.502 / 0.492 /
  0.501, by masking on coverage.
- **Transparent materials exported roughness 0.** Cycles' ROUGHNESS pass returns
  0 on alpha-blended surfaces; roughness is now carried through from the source
  the way normal and metallic already were.
- **Muted nodes and links were evaluated as if live**, so an export could
  silently disagree with the viewport. Now rejected in strict mode.
- **Blender's scene unit scale was ignored**, so a centimetre-scale scene landed
  100x oversized. Now refused with the magnitude and the remedy. Blender cannot
  compensate: measured, `convert_scene_units` only declares `metersPerUnit` and
  never moves the points.

**Blocked legitimate work**

- **A Non-Color image on Base Color could not be exported at all.** The retained
  preview network and the MaterialX graph disagreed about the same image, and
  preflight rejected the network the user has no control over. The retained
  network is now normalised to the same decision.
- **`LIT_IBL` with no world and no lights exported black and reported success.**
  Now warns, naming what was detected. A warning rather than a refusal, because
  emissive materials are a legitimate sole light source.
- **Re-exporting to a path after a texture changed failed permanently** with
  "Immutable sidecar collision has different bytes".
- **`settings set` silently discarded the first key** on a pristine `.blend`
  and reported success; the `--save`-less form was a no-op that the docs taught
  as canonical.
- **`build_unlit_material` and the OpenPBR rename table** authored inputs their
  nodedefs do not declare.

**Consistency and safety**

- **The UI and CLI disagreed on bake resolution** - 2048x2048 from the sidebar
  versus 512x512 from the CLI for the same 256px source. `bake_resolution` now
  defaults to source-keyed sizing, which both paths honour.
- **Zombie children defeated crash detection**, leaving the panel greyed out
  indefinitely when a runner died without writing a terminal status. The Popen
  handle is now retained and polled, which also reaps.
- **Foreground export had no running-job guard**, so it could delete the staging
  tree a background bake was writing into.
- **Baked textures were never bound to a UV map**, so they could be sampled
  through a different layout than they were baked into.
- **RK node-group textures carried no colour-space role**, so an sRGB-tagged
  normal map was silently decoded.
- **Mapping nodes in TEXTURE mode exported the rotation with the wrong sign.**
- **Shape-key names containing `"` silently dropped that key's animation.**
- **`--json` error envelopes leaked `$HOME`** and attached tracebacks to
  ordinary user errors. The `--verbose` stderr forward leaked too, and was
  fixed separately after the first pass missed it.
- **A bake-export of any transparent material failed** with
  "StructRNA of type Image has been removed".
- **The Shader Editor authoring panel and node menu were never registered**,
  so two documented features did not exist in Blender.

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
