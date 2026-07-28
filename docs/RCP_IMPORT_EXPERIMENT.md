# Reality Composer Pro 3 `.import` experiment

Status: repeated clean-import/reimport corpus and runtime baseline captured. A
build-pinned, fail-closed static-mesh and sampled-translation generator is
implemented behind the experimental `RCP_IMPORT` Blender/CLI format. The
skeletal generator now produces an artifact that renders and passes the three
previously failing build-80 Truth loader paths after adding the required
skeleton-hierarchy `__asset_uuid`. RCP save/reopen persistence now passes for
the controlled candidate. The 12-mesh/13-material Robot candidate also opens,
saves, and reopens, but its second genuine reimport is not idempotent: RCP
duplicates the generated resources and authors a different multi-material mesh
shape. It is not accepted yet: canonical face subsets, clip playback, and a
public RealityKit handoff from RCP-authored output remain. See
[the skeletal checkpoint](RCP_IMPORT_SKELETAL_CHECKPOINT.md) before resuming.

## Decision

BlenderToRCP must continue to export supported USD as the compatibility
baseline. A `.import` directory is an RCP-private generated cache beside the
source USD, not a published interchange format. The experimental generator is
therefore pinned to one exact RCP build, rejects unmeasured inputs, and is
accepted only after that build opens, saves, and reopens its output. It must not
guess an unknown buffer or silently fall back to a nearby schema.

The observed fixture build is:

- Reality Composer Pro 3.0
- `CFBundleVersion` `80.0.1.500.1`
- Xcode build `27A5218g`

Every capture and golden result is build-scoped. A different build starts a new
corpus lane; it does not silently update the existing contract.

## Observed format contract

The controlled local corpus contains:

- `RedCube.import`: minimal static mesh;
- `CubeWith4Animations.import`: transform timeline;
- `MeshyRiggedCharacter.import`: skeletal hierarchy and skeletal timeline.

The first measured capture is:

| Fixture | Text records | Opaque buffers | Text bytes | Opaque bytes |
|---|---:|---:|---:|---:|
| RedCube | 13 | 9 | 20,518 | 6,090 |
| CubeWith4Animations | 15 | 11 | 23,143 | 8,107 |
| MeshyRiggedCharacter | 21 | 21 | 89,906 | 100,836,599 |

These are one-time observations, not determinism claims. The skeletal example
also demonstrates why copying full `.import` fixtures into Git is unsuitable:
almost all of its roughly 96 MiB footprint is opaque buffer data.

Two fresh imports into independent disposable RCP 3 projects produced:

| Fixture | Text records | Opaque buffers | Text bytes | Opaque bytes | Structural SHA-256 |
|---|---:|---:|---:|---:|---|
| RedCube | 13 | 9 | 20,166 | 5,274 | `568af6d8676e7d18928121ffddeafea01999bd77d20c80b3c1d3b2602b3601a7` |
| CubeWith4Animations | 15 | 11 | 22,678 | 7,291 | `3c884b31a88bb9373b0ea99175c51ec0f11cae6602104c2e0dcde6142ca94e6f` |
| MeshyRiggedCharacter | 24 | 23 | 90,989 | 107,017,565 | `be992d32b8bf5cc9fae2557643bff5038e47c1f15cfe65fa5b7d949231fd9768` |

The structural hash matched between the two clean runs for every fixture.
Record types, normalized text records, buffer paths, and buffer byte counts
matched. Raw UUID identities changed. Exactly two same-sized opaque payloads
under `settings.tm_buffers` changed for each fixture; all other payloads were
byte-identical. The inspector therefore reports structural equality separately
from exact opaque-payload equality.

Two genuine in-place **Editor > Reimport** operations were then run for each
fixture in the first disposable project:

| Fixture | Clean structure | Reimport structure | Reimport 1 vs 2 |
|---|---|---|---|
| RedCube | `568af6d8676e7d18928121ffddeafea01999bd77d20c80b3c1d3b2602b3601a7` | same | exact contract and opaque-payload match |
| CubeWith4Animations | `3c884b31a88bb9373b0ea99175c51ec0f11cae6602104c2e0dcde6142ca94e6f` | same | exact contract and opaque-payload match |
| MeshyRiggedCharacter | `be992d32b8bf5cc9fae2557643bff5038e47c1f15cfe65fa5b7d949231fd9768` | `af958e472308e52bba3f74adee45e972ef7e57d78274eea031d531c634d0fb60` | exact contract and opaque-payload match |

The skeletal importer therefore has a build-pinned, deterministic
clean-to-first-reimport canonicalization step. Its record types and buffer
layout remain constant, but normalized record fingerprints, UUID graph, and
some opaque payloads change once. Contract evidence schema v2 pins the clean
and reimport phases separately. An unrecognized third structure still fails
closed.

An import is a directory containing UTF-8 `tm_*` record files and opaque files
under `*.tm_buffers` directories. Records form a UUID graph covering source
path, root/proxy/optimized entities, scene optimizer, LOD generator, variants,
sessions, geometry, mesh descriptors, materials, and timelines. Skeletal inputs
add skeleton definition/hierarchy records, a skeletal timeline, and observed
`tm_texture` records when sibling texture sources are present. The
migrated historical fixture stores an absolute source path. A project
created directly in RCP 3.0 build `80.0.1.500.1` instead stores a
project-relative path such as `../sources/static/RedCube.usda`. Contract v1
accepts both, resolves relative paths against the project package, and rejects
paths that escape its containing disposable workspace.

The buffer filenames contain an ID plus a 16-hex content hash. Controlled
renaming and byte-level probes identify that suffix as MurmurHash64A with seed
zero, multiplier `0xc6a4a7935bd1e995`, and shift 47. RCP accepts content-hashed
geometry buffers and rewrites the UUID portion on save. Buffer layouts still
remain build-private contracts and must be implemented only where a controlled
fixture and RCP acceptance establish their semantics.

## Experimental static generator

The branch implements a complete 13-record, 7-buffer constant-material static
artifact for the measured build. It writes:

- source, proxy, and optimized entity records;
- mesh descriptor, processed geometry, mesh resource, and material records;
- directory and USD settings records;
- descriptor buffers for topology, points, UVs, and normals;
- processed interleaved vertex data and 16-bit triangle indices.

It intentionally omits `settings.tm_buffers`, optimizer output, variant session,
and other volatile caches. Ablation projects without those fields opened and
saved with `world Ready`; RCP did not regenerate the omitted caches. Removing
geometry processing metadata did cause RCP errors, so `transform`,
`transform_settings`, and `output_geometry` remain required.

The plugin and CLI expose the lane as `RCP_IMPORT`. The CLI publishes the
adjacent USDA source and the `.import` directory:

```bash
python -m Plugin.cli \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  export References/Blender/RedCube.blend \
  --format RCP_IMPORT \
  -o /path/to/RedCube.import
```

The static generator accepts one or more unskinned meshes directly below the
USD default prim or inside Blender 5.2's per-object, single-mesh Xform wrappers.
It deduplicates shared material records. A USD mesh with `materialBind`
`GeomSubset` face assignments is split into one generated mesh resource per
material, preserving the selected faces, UVs, normals, object transform, and
material binding without inventing a private material-index buffer.
Overlapping/out-of-range subsets, unsupported topology/interpolation/hierarchy,
and multi-mesh transform animation fail closed and remove the incomplete
destination.

The experimental skeletal extension accepts one or more skinned meshes when
every mesh belongs to the same common rig group (optionally through Blender's
single-mesh object Xform wrapper), inherited skeleton, joint/rest/bind
contract, and animation. Each mesh may have its own material and one to four
vertex-interpolated joint influences. Face-material subsets are partitioned
into one generated skinned mesh resource per material. Each partition keeps
the source vertex and skin-weight tables and selects only the faces, UVs, and
normals assigned to that material; this reuses RCP's measured multi-model
skinned optimizer contract instead of inventing a private material-index
buffer. The writer emits one measured geometry, descriptor, and source
model/skinning component per partition, plus the measured optimizer resource
containing multiple skinned models that reference those geometries and the
shared skeleton. Intermediate rig transforms are flattened relative to the
retained default prim. Mixed skinned/unskinned sets, multiple rig groups,
multiple skeletons or animations, reset transform stacks, and non-identity
geometry binds fail closed.

A synthetic two-mesh/two-material fixture passes deterministic structural
inspection with two geometry records, two descriptors, three mesh resources
(including the optimizer resource), one skeleton definition/hierarchy, and
zero derived or unknown hashed buffers. A disposable copy of RCP's 12-mesh
Robot source also generates the same measured record shape with 1- and
3-influence descriptors and zero unknown buffers.

The full Blender 5.2 CLI path was also exercised from
`References/Blender/Robot.blend` with `export_animation=true`,
`author_animation_library=true`, `UNLIT_ALBEDO`, and disposable 32-pixel bake
textures. It baked 12 objects and produced a 12-mesh, 12-material, 12-texture
skeletal package with 78 records, 130 content-hashed buffers, and zero derived
or unknown hashed buffers. Two independent bake/export runs produced the same
record-type/count shape, but not identical source paths, UUIDs, records, or
opaque texture payload hashes: the bake publisher uses a volatile staging
directory and independent baked image payloads. Running the generator twice
against one fixed staged USDA and texture set was byte-for-byte deterministic.
Generator determinism and whole-bake reproducibility must therefore remain
separate acceptance claims.

A second disposable Robot run used
`tests/fixtures/rcp_import/create_skinned_multimaterial_fixture.py` to assign
two material slots to alternating faces of the skinned body mesh before the
same 32-pixel `UNLIT_ALBEDO` bake. The generated package contained 13
geometries, descriptors, materials, textures, and source model/skinning
components for the 12 Blender mesh objects, plus one 13-model optimizer mesh
resource. Structural inspection found 83 records, 140 content-hashed buffers,
and zero derived or unknown hashed buffers. Its staged USDA passed Apple USD
Tools 0.25.11 `usdchecker --arkit --strict` and Xcode 27 `realitytool`
compilation. Public RealityKit 27 loaded the compiled artifact with 13
`ShaderGraphMaterial` instances, the `Animation` library key,
`MeshDeformerComponent`, `SkeletalPosesComponent`, and the same finite,
nonempty Robot bounds as the one-material-per-source-mesh baseline.

RCP 3 build `80.0.1.500.1` then established the current multi-material
compatibility boundary in a disposable project:

- clean open, save, close, and reopen completed with `world Ready` and
  `Tasks: None`;
- the first RCP save retained 83 records and all 140 opaque payloads, while
  canonicalizing record bytes and buffer filenames;
- the first genuine **Editor > Reimport** produced 83 records and 139 buffers,
  added RCP's external `matched_skeleton_hierarchies` result, and removed one
  12-byte settings buffer;
- a second genuine reimport was not idempotent. The package grew to 147
  records and 306 buffers, including 25 geometry records, 25 mesh
  descriptors, 26 mesh resources, and 26 materials. RCP retained the
  writer's per-material partitions, added `(1)` duplicates for the source
  meshes, and authored one combined body descriptor with two `subsets`
  entries and face-index buffers.

The two reimport phases therefore do **not** validate the current strategy of
representing one USD mesh with multiple face materials as independent RCP mesh
resources. RCP's canonical form keeps one mesh descriptor and records material
partitions in its nested `subsets` field. The inspector recognizes
`matched_skeleton_hierarchies` and `subsets` only as measured RCP-authored
fields; the writer must not synthesize either until their UUID and opaque
buffer contracts have been independently reproduced.

Each reimport of the unmodified Blender-authored source emitted 13
`Unknown color space <private> encountered` warnings, one per baked texture.
Two controlled source-only A/B runs removed the shader ColorSpaceAPI or mapped
`srgb_rec709_display` to `srgb_texture`. Both suppressed the warnings, but
both converged to the exact same 83-record/139-buffer first-reimport package as
the unmodified source. Color-space metadata is therefore a separate cleanup
item, not the cause of the resource-duplication failure. RCP's import preview
also changed between magenta matching visualization and the textured
black/white model across phases, so preview color alone is not accepted as a
material-runtime proof.

The Robot run also established three Blender-specific compatibility rules:
time-sampled UV index primvars are evaluated at the stage start time; individual
single-mesh object Xform wrappers are retained below one common rig group; and
long staged texture names are classified from measured shader connections and
bounded with deterministic hashes before creating filesystem records. Explicit
unsupported filename roles still fail closed even when the shader graph is
otherwise ambiguous.

The same animated 12-object Robot bake was exported through the supported
USDA, USDC, and USDZ lanes. Every stage reopened with 12 meshes, 12 material
bindings, 12 skinned meshes, one skeleton, one animation over frames 1–149 at
24 fps, the `Animation` clip contract, and 24 resolved shader texture inputs
deduplicated to nine content-addressed AVIF files. Superseded pre-staging bake
images are now removed only from the bake worker's owned temporary directory;
the resulting USDZ contains the root USDC plus exactly those nine referenced
textures instead of carrying 12 additional orphan images.

All three formats passed Apple USD Tools 0.25.11 `usdchecker --arkit --strict`
and Xcode 27 `realitytool` compilation. Public RealityKit 27 loaded source
USDC, source USDZ, compiled USDC, and compiled USDZ with one recursive model,
12 `ShaderGraphMaterial` instances, `Animation`, `MeshDeformerComponent`,
`SkeletalPosesComponent`, and matching finite nonempty bounds with extents
`[0.14261799, 0.2738792, 0.16812176]`. Realitytool 27 initially exposed a
false-positive when a USDZ was nested unchanged inside temporary `.rkassets`:
the compiler exited zero but RealityKit rejected the result with error 20.
The validator now safely expands the already-validated USDZ members before
compilation, and the resulting `.reality` passes the same runtime probe.

These are Blender, generator, and structural results only. Clean RCP
load/save/reopen, two reimports, Sequence Editor playback, and RealityKit
runtime/bounds acceptance for the multi-mesh skeletal output are still
required.

### Baked material extension

`bake-export --format RCP_IMPORT` now runs the existing bake pipeline, publishes
its post-processed USDA beside the destination, then builds the private package.
The writer uses the RCP-authored `bakeTest_02.import` and Robot material records
as the build-80 contract:

- source image bytes are copied unchanged into a `tm_texture` buffer;
- the payload filename uses the same MurmurHash64A content suffix as RCP;
- the measured `tm_texture` creation-graph wrapper, color-space fields, shader
  connector hashes, and texture resource references are authored
  deterministically;
- `UNLIT_ALBEDO` and `LIT_IBL` use the measured RealityKit Unlit graph;
- `LIT_ALBEDO` uses the measured RealityKit PBR base-color graph and may add its
  baked roughness texture.

The bounded writer accepts one baked RGBA base-color image per material (its
alpha contains the bake pipeline's merged opacity) and, for Lit PBR, one
roughness image per material. Different mesh/material pairs may therefore
produce independent texture records, while meshes that genuinely share the
same USD material reuse one material record. Normal, metallic, occlusion,
independent opacity images, unknown filename roles, multiple base-color images
within one material, and unmeasured surface profiles fail closed.

Disposable Blender/CLI multi-asset runs use a three-object corpus containing
two shared procedural materials and one object with two face materials:

- `UNLIT_ALBEDO` generated four split mesh resources, four materials, four
  textures, 30 records, and 32 content-hashed buffers;
- `LIT_ALBEDO` generated four split mesh resources, four materials, eight
  textures, 34 records, and 36 content-hashed buffers;
- direct `RCP_IMPORT` export of the equivalent compatible flat-material scene
  generated four mesh resources and two deduplicated material records;
- the Blender UI background-worker path reached terminal `done`, consumed its
  disposable scene snapshot, published the adjacent USDA, and produced the same
  30-record/32-buffer unlit package shape;
- USDA, USDC, and USDZ bake exports retained three USD meshes, four baked
  material records, and both material subsets.
- the public RealityKit 27 smoke probe loaded both USDC and USDZ on Apple M5
  Max, recursively found three model entities and four ShaderGraph materials,
  and reported identical finite bounds (`min [-2.5, -1, -1]`,
  `max [2.5, 3.5, 1]`).

Every structural inspection reported zero derived or unknown hashed buffers.
RCP open/save/reopen and visual/runtime acceptance of the generated multi-model
packages is still required before this extension can be called RCP-compatible.

Disposable Blender/CLI runs cover all three bake modes: textured
`UNLIT_ALBEDO` generated 15 records/8 buffers, textured `LIT_ALBEDO` generated
16 records/9 buffers, and `LIT_IBL` generated 15 records/8 buffers. In each
case the structural inspector reported zero derived/unknown hashed buffers and
the CLI returned `format: RCP_IMPORT`. RCP open/save/reopen and visual/runtime
acceptance of these newly generated textured packages is still required before
this extension can be called RCP-compatible.

### Direct plugin-output acceptance

On RCP 3.0 build `80.0.1.500.1`, the exact CLI output for
`References/Blender/RedCube.blend` was copied into an isolated disposable
project shell with its deterministic asset identity intact. RCP:

1. opened it with `world Ready` and no console error indicator;
2. completed all background tasks (`Tasks: None`);
3. saved without repair;
4. closed and reopened it with `world Ready`.

Before save the artifact contained 13 records, 7 content-hashed buffers, and
1,536 opaque bytes. After save the record and buffer counts, buffer layout,
UUID graph counts, and every opaque payload remained equal. RCP canonicalized:

- the UUID portion of two geometry buffer filenames and their references;
- geometry record formatting and numeric spelling;
- several material float spellings;
- geometry `validity_hash` from the accepted bootstrap value
  `2cfcf0b4ccf2dcd8` to `a28884579325560a`.

This proves the measured static artifact is an accepted staging input, not that
the private schema is stable across RCP builds or arbitrary mesh payloads.

A second isolated project tested genuinely different topology: one triangle
with three points and one face. The generator supplied the same bootstrap
validity value used by the cube. RCP opened and saved the project with
`world Ready`, `Tasks: None`, and no error indicator, then canonicalized the
triangle validity hash to `a529a77de146ba8d`. The artifact retained 13 records,
7 content-hashed buffers, and 214 opaque bytes. This establishes that
`2cfcf0b4ccf2dcd8` is an accepted build-80 bootstrap marker for the validated
static subset rather than a cube-content checksum.

## Experimental transform generator

The controlled `CubeWith4Animations` record shows that RCP stores transform
animation in three layers:

1. a sampled type-2 timeline nested inside `settings.tm_usd`;
2. little-endian float32 frame and translation buffers under
   `settings.tm_buffers`;
3. one type-1 `tm_timeline` record per named clip, each referencing the sampled
   timeline and carrying its start/end trim.

For the original 97-sample corpus, the time buffer is exactly the float32
sequence `1...97` (388 bytes), and the position buffer is 97 XYZ float32 tuples
(1,164 bytes). Their MurmurHash suffixes are respectively
`31e4244ce368fb5c` and `6dfa4c9b558eb501`, matching RCP's own import byte for
byte. The other four potential rotation/scale key/time slots are declared but
have no backing buffers for a translation-only animation.

The generator reads the authored `RealityKit.AnimationLibrary` clip names and
start times, samples translation at each integer stage frame, writes the two
buffers, adds `tm_animation_library_component` to both entity variants, and
emits all named clip records. Sampled rotation, scale, multiple animated nodes,
or conflicting clip definitions fail closed.

Two disposable RCP projects accepted generated transform artifacts:

- the controlled 97-frame corpus source;
- the exact Blender 5.2 CLI export from
  `References/Blender/CubeWith4Animations.blend` with
  `export-animation=true`.

Both reached `world Ready`, saved with no error indicator, retained all four
clip records, and preserved every opaque payload. The direct plugin output also
closed and reopened with `world Ready`; it had 100 samples, 18 records, 9
content-hashed buffers, and 3,136 opaque bytes.
Its clip ranges were derived from the current Blender Actions at 24 fps:

| Clip | Start | End |
|---|---:|---:|
| GoBackward | 0 | 1.0416666666666667 |
| GoDown | 1.0416666666666667 | 2.0833333333333335 |
| GoForward | 2.0833333333333335 | 3.125 |
| GoUp | 3.125 | 4.125 |

RCP save canonicalized text/UUID details but retained the record types, buffer
layout, UUID graph counts, clip names/ranges, and opaque animation payloads.

## Harness

Run the inspector against an RCP-generated fixture:

```bash
python scripts/inspect_rcp_import.py \
  /path/to/RedCube.import \
  --profile static \
  --rcp-version 3.0 \
  --rcp-build 80.0.1.500.1 \
  --output red-cube.capture.json
```

Capture the same controlled source again after an RCP reimport, then compare:

```bash
python scripts/inspect_rcp_import.py \
  /path/to/reimported/RedCube.import \
  --profile static \
  --rcp-version 3.0 \
  --rcp-build 80.0.1.500.1 \
  --compare red-cube.capture.json
```

The report retains exact content hashes while canonical comparison replaces
UUIDs, UUID-derived filenames, short payload-name hashes, and the absolute
source path. Structural comparison retains buffer paths and byte counts but
reports opaque-payload equality separately. This separates volatile
identity/path/payload fields from stable structure. A field is not declared
deterministic until at least two clean imports and two reimports of the same
source agree.

The checked-in corpus catalog is
`tests/fixtures/rcp_import/corpus.json`. Full opaque payloads stay local. Run the
golden corpus test with:

```bash
BLENDERTORCP_RCP3_FIXTURE_ROOT=/path/to/Export pytest \
  tests/unit/test_rcp_import_contract.py
```

## Fail-closed boundary

The inspector rejects:

- a root that is not a `.import` directory;
- symlinks and unexpected directory layouts;
- unknown record suffixes or record types;
- a known record type with an unknown top-level field;
- invalid record headers, duplicate UUID definitions, or unbalanced text;
- unexpected buffer filenames;
- a missing or unsafe source path;
- fixtures that do not meet the selected static, transform, or skeletal shape.

This is a structural contract only. Nested values are inventoried, not decoded
as a writable schema. Passing inspection does not prove that RCP can open an
asset.

## Acceptance matrix

Each fixture/build pair needs retained evidence for all of these gates:

| Gate | Static | Transform | Skeletal | Automation |
|---|---:|---:|---:|---|
| Structural golden capture | required | required | required | implemented |
| Two independent clean imports | required | required | required | observed |
| RCP opens without repair | required | required | required | observed for clean imports and reimports |
| Source change triggers reimport | required | required | required | passed |
| Supported-USD RealityKit baseline | required | required | required | passed |
| Staged RCP runtime artifact loads | required | required | required | failed |
| Entity/material bounds match source | required | required | required | passed for source baseline |
| Sequence editor exposes intended clip | n/a | required | required | failed |
| Animation duration and playback match | n/a | required | required | blocked by missing clips |

RCP UI/runtime results need the application build, source hash, capture hash,
timestamp, and pass/fail notes. A successful USD import is the baseline; a
generated `.import` candidate must be at least as reliable.

The corpus catalog pins source size and SHA-256 so a result from a modified USD
cannot be mistaken for a repeatability measurement.

### Reimport boundary observed

RCP does not refresh a saved `.import` merely because a source changes on disk.
The genuine build-80 command is **Editor > Reimport** on the selected import
asset. Each measured run completed with `Tasks: None`; the project saved and
reopened without repair or an error indicator. **Import File** is not a
substitute: importing the same path created `RedCube (1).import` and emitted
`Trying to lookup property of NULL truth object` in the RCP console.

Import destination is selection-sensitive. Importing while another `.import`
container is active can nest the new `.import` inside it. Acceptance automation
must navigate to the project root before each clean import and verify the
on-disk top-level layout afterward.

The repeated clean-import and two-reimport requirements are satisfied for all
three profiles. The retained structural reports are under
`tests/fixtures/rcp_import/evidence/rcp3-80.0.1.500.1`.

### RealityKit and animation findings

The supported source USDs were converted losslessly to USDC and loaded through
the public RealityKit 27 runtime probe. All three exposed one model and one
`ShaderGraphMaterial`. Recursive visual bounds were finite and non-empty:

| Fixture | Minimum | Maximum | Extents |
|---|---|---|---|
| RedCube | `[-1, -1, -1]` | `[1, 1, 1]` | `[2, 2, 2]` |
| CubeWith4Animations | `[-1, 1, -1]` | `[1, 3, 1]` | `[2, 2, 2]` |
| MeshyRiggedCharacter | `[-0.620521, 0, -0.282728]` | `[0.620521, 1.7, 0.282728]` | `[1.241043, 1.7, 0.565455]` |

The transform source retained `GoBackward`, `GoDown`, `GoForward`, and `GoUp`.
The skeletal source retained `Agree_Gesture`, `Running`, `Walking`, and
`walking_2`, plus `MeshDeformerComponent` and `SkeletalPosesComponent`.

RCP did not retain those author-facing clip sets. The transform `.import`
contains one `CubeWith4Animations_transform.tm_animation`. The skeletal
`.import` contains one transform timeline and one root skeletal timeline. The
source clip keys are absent from the generated records, so Sequence Editor
clip selection and per-clip playback acceptance fail instead of being inferred
from the source runtime result.

A staging-only package experiment copied the untouched disposable
`.realitycomposerpro` package to a `.rkassets` path. `realitytool compile`
accepted it, but the resulting `.reality` was only 4.3 KiB and public
RealityKit loading failed with `RealityKit.__RealityFileError error 4`. RCP's
**Save Project As Asset Database** instead produced a private `.rcp_db`, which
`realitytool` rejects as an input. Renaming or copying generated packages is
therefore not yet a valid runtime handoff.

Copy `tests/fixtures/rcp_import/acceptance.template.json` to an evidence
location, fill every gate with a retained evidence path, then run:

```bash
python scripts/validate_rcp_import_acceptance.py /path/to/acceptance.json
```

The validator fails for pending/failed gates, unknown gates, build drift,
changed source hashes, changed structural captures, or a claimed pass without
evidence. It requires exactly two `clean_import` and two `reimport` run records
per fixture. Evidence schema v2 pins one expected structure per phase, allowing
the measured skeletal canonicalization without accepting arbitrary drift. The
checked-in measured evidence intentionally fails full acceptance because the
staged runtime and RCP animation-authoring gates are not satisfied:

```bash
python scripts/validate_rcp_import_acceptance.py \
  tests/fixtures/rcp_import/acceptance.rcp3-80.0.1.500.1.json
```

## What prevents a complete writer today

1. No public writer API or schema exists.
2. Static buffer filename hashing and the validated layouts are understood.
   RCP's canonical geometry-validity function is still private, but controlled
   cube and triangle projects establish an accepted bootstrap value that RCP
   replaces on save.
3. Translation animation buffers and clip records are implemented. The
   controlled skeletal source's joint transforms, skinning, scene-tree tables,
   and named clips open and render in RCP. General rotation, scale, multiple
   animated nodes, and arbitrary skeletons remain outside the validated subset.
4. UUID lifetime rules show stable clean and first-reimport phases for the
   single-mesh corpus. The multi-material Robot candidate instead duplicates
   resources on its second reimport because the writer partitions one source
   mesh into multiple descriptors rather than authoring RCP's canonical nested
   `subsets` representation.
5. RCP may enforce hidden version/build migrations or invariants beyond the text
   records.
6. RCP 3 demonstrably flattens the named
   `RealityKit.AnimationLibrary` clip definitions motivating this experiment;
   the `.import` timeline records show editor state, but do not prove a stable
   authoring contract.
7. One-USD-per-Blender-Action is a supported parallel experiment, but still
   requires RCP authoring and Sequence Editor acceptance evidence.

## Phased plan

1. **Corpus repeatability (complete for build 80):** retain the two clean and
   two reimport reports and keep clean/reimport phases separately pinned.
2. **Parser and static generator (complete for the bounded build-80 subset):**
   typed parsing, MurmurHash
   buffer validation, build-pinned record generation, and direct static
   open/save/reopen acceptance are complete for cube topology. A different
   triangle topology confirms that the accepted bootstrap validity value
   generalizes inside the strict static subset.
3. **Baked texture writer (implemented, single-material RCP acceptance
   pending):** all three bake modes pass the Blender/CLI and structural gates
   for one mesh. Multi-mesh/single-material source shapes pass supported USD
   compilation and RealityKit runtime checks. A mesh with multiple face
   materials remains experimental-only because the second RCP reimport
   duplicates resources.
4. **Transform generator (implemented, final acceptance in progress):** the
   aggregate sampled timeline, translation/time buffers, entity component, and
   four named clip records pass RCP open/save. Reopen, Sequence Editor, and
   playback evidence remain required.
5. **Skeletal generator (rendering, not accepted):** the controlled hierarchy,
   definition, binding, sampled timeline, scene-tree buffers, and four named
   clip records are generated. Next, model one mesh with multiple materials as
   a single descriptor with RCP-authored `subsets`, prove its face-index buffer
   layout from controlled fixtures, and require two idempotent reimports before
   enabling that input shape as compatible.
6. **Acceptance automation:** retain reproducible RCP open/reimport captures;
   extend the RealityKit probe from bounds/resource discovery to controlled
   playback duration only for clips that RCP actually exposes.
7. **Runtime handoff gate:** create an RCP-authored entity in the disposable
   world, export/compile that supported authoring output, and require successful
   public RealityKit loading. Package renaming alone is rejected by the current
   evidence.
8. **Product decision:** if build churn or remaining private invariants defeat
   repeatability,
   keep `.import` support as a diagnostic/corpus tool and invest in supported
   USD/action-per-file workflows instead.
