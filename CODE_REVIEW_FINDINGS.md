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

---

## Still open

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
