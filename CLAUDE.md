# Working in this repository

Instructions for coding agents. `docs/` is public documentation for artists and
integrators; this file is not. Keep it short and keep it true.

## Never treat `realitytool` as evidence that a material is correct

`xcrun realitytool compile` succeeding proves **nothing** about whether Reality
Composer Pro or RealityKit can render the asset. Do not cite it as validation of
fidelity, correctness, or compatibility. The same goes for
`usdchecker --arkit --strict`.

This is measured, not cautious. A rigged-character export (`Robot.usda`, since
removed from this repository along with its 27 MB source) contained a material
Reality Composer Pro 3 refused with

```text
GEN RESOURCE: tm_material object id: ... - Resource generation failed.
Error: Couldn't find compiled shader graph buffer!
```

On that exact file, measured before it was removed:

| Check | Verdict |
|---|---|
| `realitytool compile --platform xros` | exit 0, **emits `shadergraph_<material>`**, zero PBR fallbacks |
| `usdchecker --arkit --strict` | `Success!` |
| `scripts/check_shader_implementations.py` | passes — every nodedef in it resolves to a symbol |
| Reality Composer Pro 3 | refuses the material |

`realitytool` does not merely stay quiet. It reports a *successful* shader graph
for a material the app cannot build.

**The cause of this refusal is not known.** It was attributed to the material's
`ND_swizzle_color3_float`, on the belief that no `ND_swizzle_*` had a Metal
implementation. Both halves of that are now measured false:

- Every one of the 61 declared swizzle nodedefs has a Metal symbol, under a
  rewritten name (see below).
- A generated package whose roughness reads through `ND_swizzle_color3_float`
  **imports into Reality Composer Pro 3 with no console error and renders** —
  with and without an authored `channels` value. Measured on build
  `80.0.1.500.1`.

So the swizzle node is not what that material tripped over. Do not restate that
explanation. What survives is the observation that matters: Reality Composer Pro
refused a material that `realitytool`, `usdchecker`, and this repository's own
checker all passed. Only an import tells you what the editor will build.

The asset is gone, so this is no longer reproducible here. Treat it as a
recorded measurement rather than a fixture you can re-run - and if you meet the
`Couldn't find compiled shader graph buffer` refusal again, keep that asset:
it is the only way this gets explained.

**Why they disagree.** Reality Composer Pro compiles through
`ShaderGraph.framework` and the `libtm-*` libraries. `realitytool` links neither.
They are different compilers reading the same file, and only one of them ships in
the app the user runs.

**A second measured instance.** A USDZ nested unchanged inside a temporary
`.rkassets` compiled with exit 0, and RealityKit then rejected the result with
error 20. The validator now expands already-validated USDZ members before
compilation rather than nesting them.

**Importing into Reality Composer Pro has its own trap.** When an import fails
part way, the editor leaves a `.import` cache beside the source containing
records but no geometry buffers, and importing the corrected file *under the same
name does not rebuild it*. It keeps reporting

```text
Failed reading file `.../geometry/….tm_buffers/…`
Geometry still has buffers being streamed, object_to_geometry() shouldn't be
called before receive all the buffers!
```

against buffers that were never written, which reads exactly like a fresh defect
in the file you just fixed. Delete that cache, or import under a new name, before
concluding anything about a change. This applies to plain `.usda`/`.usdz` imports
too - the editor builds the same cache for them - so it outlives any one export
format.

**What `realitytool` is still good for:** proving a file parses, packages, and
survives crate conversion. Treat it as a syntax check.

## Use these instead

```bash
# Names the materials RealityKit cannot build a shader for.
python3 scripts/check_shader_implementations.py <file-or-.rkassets-directory>
```

It reads Apple's shipped Metal libraries directly, so it catches the failure
class above. Two traps it exists to handle:

- A nodedef can **resolve** in RealityKit's nodedef store and still have **no
  implementation** — no Metal symbol and no nodegraph expansion. Resolution is
  not implementation.
- **Symbols are not always spelled like their nodedef.** ShaderGraph rewrites a
  `swizzle` node to `ND_appleinternal_swizzle_<from><to>`: separator dropped,
  MaterialX's `vectorN` spelled `floatN`. So `ND_swizzle_color3_float` compiles
  to `ND_appleinternal_swizzle_color3float`, and `ND_swizzle_color4_vector3` to
  `ND_appleinternal_swizzle_color4float3`. **Nothing in the shipped MaterialX
  XML records this mapping** — the string `appleinternal` does not appear in
  that tree at all. Matching nodedef names against the symbol table therefore
  reported all 61 declared swizzle nodedefs as unimplemented; every one of them
  has a symbol. The checker now applies the rewrite. Assume other families may
  hide behind renames too: a missing symbol is a hypothesis, not a verdict.
  **Second measured instance:** `ND_realitykit_pbr_surfaceshader_2_0` is
  implemented by `ND_realitykit_pbr_surfaceshader_v2`, declared in an
  `<implementation function="...">` element the checker used to ignore on
  principle. It reported PBR Surface 2 as unbuildable while Reality Composer
  Pro built, rendered, and recorded it. The checker now reads the element and
  honours it only when the named function is actually in the metallib - a
  claim is verified, not trusted, and not discarded.
- The converse trap: ~470 nodedefs are expanded from a `<nodegraph>` at compile
  time and never get a Metal symbol — `ND_normal_map_decode` and
  `ND_separate4_color4` among them. Judging on the metallib alone calls every one
  of those broken. An `<implementation>` element is *not* good enough either; it
  names a Metal function that may be missing.
- RealityKit keeps **one nodedef store per declared MaterialX version**. A node
  or input present at 1.39 may be absent at 1.38, which is what every export
  declares. `Plugin/manifest/rcp_nodedef_input_gaps.json` records
  both gaps; regenerate it with `scripts/dump_rcp_nodedef_inputs.py`.

Either mistake makes RealityKit discard the material's **entire** shader graph —
every texture binding included — and substitute default PBR, silently.

The only complete verification is a human importing the asset into Reality
Composer Pro and looking at it. Say so plainly rather than implying a green tool
run means the asset is right.

## Measuring against the platform

When you need to know what RealityKit actually accepts, ask the shipping
software, not the specification and not this repo's manifest — both have been
wrong here.

- **RealityKit's own resolver**: `dlopen` ShaderGraph.framework, then
  `[SGNodeDefStore storeWithMaterialXVersion:error:]` and
  `[SGNode nodeWithNodeDefName:name:nodeDefStore:error:]`. This is the code
  Reality Composer Pro runs. `scripts/dump_rcp_nodedef_inputs.py` has a working
  copy.
- **Shipped MaterialX libraries**:
  `/Applications/RealityComposerPro.app/Contents/SystemFrameworks/CoreRealityIO.framework/Versions/A/Resources/libraries`
  — a `<nodedef>` existing there is not proof it can be compiled.
- **Metal implementations**: the `MaterialX-*.metallib` files under
  `ShaderGraph.framework/Versions/A/Resources/`. Symbols carry codegen suffixes,
  so match by prefix.
- **What Apple authors**: `find / -name '*.tm_material'` finds Reality Composer
  Pro's own materials. What they do beats what the spec permits.

The generated manifest at `Plugin/manifest/rk_nodes_manifest.json` is built from
a vendored vanilla-upstream MaterialX copy. Where it disagrees with the library
RealityKit loads, the library wins.

## Repository conventions

- Target **Blender 5.2 LTS only**. Delete legacy fallbacks rather than branching
  on version.
- Do not modify vendored material under `References/`. Writing export output
  under `References/RealityComposerProProject/Export/` is expected — that is
  where `.usda`/`.usdc`/`.usdz` for manual evaluation go.
- `RealityComposerProProject.realitycomposerpro` is the Reality Composer Pro 3
  project. It holds `.import` packages only, never source assets; its `Export/`
  and `core.lib/` are RCP's own regenerated content and are gitignored.
- **Never delete or move anything under that project while Reality Composer Pro
  is open.** It watches the tree and drops its imported packages in response.
  `pgrep -x RealityComposerPro` first — the process name has no spaces.
- Manual-evaluation scenes live in `References/Blender` and are tracked;
  regenerate them with `scripts/build_test_scenes.py` and export them with
  `scripts/export_test_scenes.sh`. Their exports under the RCP project's
  `Export/` are gitignored. Expectations are in
  `References/Blender/TEST_SCENES.md`.
- Documentation under `docs/` follows `docs/STYLE_GUIDE.md`.

## Writing tests

A test that reads our own output back from the same table that produced it
proves only that we agree with ourselves. This repo has shipped two of those,
and both hid real defects for months. Assert against something independent: the
shipped nodedef, the platform's own library, or arithmetic transcribed from
Blender's source.

Prefer asserting on *values* over node names. `assert "ND_dotproduct_vector3" in
authored` survives a wrong channel mask; reading the mask back and checking the
arithmetic does not.
