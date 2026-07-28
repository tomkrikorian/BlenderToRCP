# Reality Composer Pro 3 `.import` experiment

Status: repeated clean-import/reimport corpus and runtime baseline captured. A
build-pinned, fail-closed static-mesh and sampled-translation generator is
implemented behind the experimental `RCP_IMPORT` Blender/CLI format. The
skeletal generator now produces an artifact that renders and passes the three
previously failing build-80 Truth loader paths after adding the required
skeleton-hierarchy `__asset_uuid`. RCP save/reopen persistence now passes for
the controlled candidate. It is not accepted yet: reimport, clip playback, and
public RealityKit runtime gates remain. See
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

The generator currently accepts exactly one unskinned mesh directly below the
USD default prim or inside Blender 5.2's single-mesh object Xform wrapper.
Unsupported topology, interpolation, hierarchy, or skinning fails closed and
removes the incomplete destination.

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

The bounded writer currently accepts one baked RGBA base-color image (its alpha
contains the bake pipeline's merged opacity) and, for Lit PBR, one roughness
image. Normal, metallic, occlusion, independent opacity images, unknown filename
roles, multiple base-color images, and unmeasured surface profiles fail closed.
The existing one-mesh geometry limit still applies.

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
   and named clips are implemented, but the resulting package still triggers
   three RCP internal errors. General rotation, scale, multiple animated nodes,
   and arbitrary skeletons remain outside the validated subset.
4. UUID lifetime rules now show a stable clean phase and a stable reimport
   phase, but the opaque skeletal canonicalization between them is unexplained.
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
3. **Baked texture writer (implemented, RCP acceptance pending):** all three
   bake modes pass the Blender/CLI and structural gates for one mesh. Repeat
   clean import, save/reopen, reimport, visual, and RealityKit runtime checks
   before widening the texture-role subset.
4. **Transform generator (implemented, final acceptance in progress):** the
   aggregate sampled timeline, translation/time buffers, entity component, and
   four named clip records pass RCP open/save. Reopen, Sequence Editor, and
   playback evidence remain required.
5. **Skeletal generator (rendering, not accepted):** the controlled hierarchy,
   definition, binding, sampled timeline, scene-tree buffers, and four named
   clip records are generated. Resume with the record-group differential
   procedure in `RCP_IMPORT_SKELETAL_CHECKPOINT.md`; do not widen the input
   subset until the clean-shell console gate passes.
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
