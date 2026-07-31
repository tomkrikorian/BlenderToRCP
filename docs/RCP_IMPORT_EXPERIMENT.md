# Reality Composer Pro 3 `.import` experiment

This page explains the experimental `RCP_IMPORT` export lane: what a Reality
Composer Pro `.import` package is, what the experimental generator writes,
which inputs it accepts, and how far each profile has been validated. Read it
before you use the lane or extend it.

*Applies to: Reality Composer Pro 3.0, `CFBundleVersion` `80.0.1.500.1`,
Xcode build `27A5218g`. Every capture and golden result on this page is
scoped to that build. A different build starts a new corpus lane; it does not
silently update this contract.*

The lane is experimental and fails closed by design. A `.import` directory is
a Reality Composer Pro–private generated cache beside a source USD file, not
a published Apple interchange format. No public writer API or schema exists.
Supported USD export remains the compatibility baseline; see
[APPLE_PLATFORM_CONTRACT.md](APPLE_PLATFORM_CONTRACT.md).

Terms used on this page:

- **Truth** — the data model Reality Composer Pro is built on (Our
  Machinery's "The Truth"). Everything in an `.import` package is Truth data.
- **Record** — a UTF-8 text file named `tm_*` that stores one typed Truth
  object, such as a mesh descriptor or a material.
- **Buffer** — an opaque binary file under a `*.tm_buffers` directory,
  referenced from a record. Geometry, texture, and animation payloads live in
  buffers.
- **Reimport** — Reality Composer Pro regenerating an existing `.import`
  package from its source file. Select the import asset, then choose
  **Editor > Reimport**.
- **Canonicalization** — Reality Composer Pro rewriting record formatting,
  numeric spelling, and some identities into its own preferred form on save
  or first reimport, without changing the package structure.

## Current status

Established for the pinned build:

- A repeated clean-import/reimport corpus and a supported-USD runtime
  baseline exist for three controlled fixtures.
- A build-pinned, fail-closed static-mesh and sampled-translation generator
  is implemented behind the experimental `RCP_IMPORT` Blender/CLI format.
- The skeletal generator produces an artifact that renders and passes the
  three previously failing build-80 Truth loader paths after adding the
  required skeleton-hierarchy `__asset_uuid`. Save/reopen persistence in
  Reality Composer Pro passes for the controlled candidate.
- The 12-mesh/13-material Robot candidate opens, saves, and reopens.
- The contract that binds materials to faces is established: descriptor
  face subsets, the slot `index` on each model-component material entry,
  geometry subset ranges over a subset-sorted triangle index stream, and
  Reality Composer Pro's separate naming rule for geometry buffers. The
  writer authors all of it, and a two-material static mesh loads and renders
  both materials on their assigned faces.

Not established — the lane is not accepted:

- The canonical multi-material writer has not been through save/reopen or
  two non-growing reimports. Rendering correctly is not acceptance.
- The superseded split representation — one generated mesh resource per
  material — failed the second genuine reimport of the Robot candidate.
  Reality Composer Pro duplicated the generated resources and authored a
  different multi-material mesh shape. That path has been removed from the
  writer.
- Clip playback and a public RealityKit handoff from RCP-authored output
  remain open.

See [the skeletal checkpoint](RCP_IMPORT_SKELETAL_CHECKPOINT.md) and the
[measured multi-material mesh contract](RCP_IMPORT_MULTI_MATERIAL_MESH.md)
before resuming work on the lane.

## Decision

BlenderToRCP must continue to export supported USD as the compatibility
baseline. Because a `.import` directory is an RCP-private generated cache
beside the source USD, the experimental generator:

- is pinned to one exact RCP build;
- rejects unmeasured inputs;
- is accepted only after that build opens, saves, and reopens its output;
- must not guess an unknown buffer or silently fall back to a nearby schema.

## Observed format contract

An `.import` package is a directory containing UTF-8 `tm_*` record files and
opaque buffers under `*.tm_buffers` directories. Records form a UUID graph
covering the source path, root/proxy/optimized entities, the scene optimizer,
the LOD generator, variants, sessions, geometry, mesh descriptors, materials,
and timelines. Skeletal inputs add skeleton definition and hierarchy records,
a skeletal timeline, and `tm_texture` records when sibling texture sources
are present.

The controlled local corpus contains three fixtures:

| Fixture | Contents |
|---|---|
| `RedCube.import` | minimal static mesh |
| `CubeWith4Animations.import` | transform timeline |
| `MeshyRiggedCharacter.import` | skeletal hierarchy and skeletal timeline |

The first measured capture — a one-time observation, not a determinism claim:

| Fixture | Text records | Opaque buffers | Text bytes | Opaque bytes |
|---|---:|---:|---:|---:|
| RedCube | 13 | 9 | 20,518 | 6,090 |
| CubeWith4Animations | 15 | 11 | 23,143 | 8,107 |
| MeshyRiggedCharacter | 21 | 21 | 89,906 | 100,836,599 |

The skeletal fixture also shows why full `.import` fixtures cannot be copied
into Git: almost all of its roughly 96 MiB footprint is opaque buffer data.

### Clean-import repeatability

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
byte-identical. The inspector therefore reports structural equality
separately from exact opaque-payload equality.

### Reimport repeatability

Two genuine in-place **Editor > Reimport** operations were run for each
fixture in the first disposable project:

| Fixture | Clean structure | Reimport structure | Reimport 1 vs 2 |
|---|---|---|---|
| RedCube | `568af6d8676e7d18928121ffddeafea01999bd77d20c80b3c1d3b2602b3601a7` | same | exact contract and opaque-payload match |
| CubeWith4Animations | `3c884b31a88bb9373b0ea99175c51ec0f11cae6602104c2e0dcde6142ca94e6f` | same | exact contract and opaque-payload match |
| MeshyRiggedCharacter | `be992d32b8bf5cc9fae2557643bff5038e47c1f15cfe65fa5b7d949231fd9768` | `af958e472308e52bba3f74adee45e972ef7e57d78274eea031d531c634d0fb60` | exact contract and opaque-payload match |

The skeletal importer therefore has a build-pinned, deterministic
clean-to-first-reimport canonicalization step. Its record types and buffer
layout remain constant, but normalized record fingerprints, the UUID graph,
and some opaque payloads change once. Contract evidence schema v2 pins the
clean and reimport phases separately. An unrecognized third structure fails
closed.

### Source paths

The migrated historical fixture stores an absolute source path. A project
created directly in the pinned build instead stores a project-relative path
such as `../sources/static/RedCube.usda`. Contract v1 accepts both, resolves
relative paths against the project package, and rejects paths that escape
their containing disposable workspace.

### Buffer filenames

Buffer filenames contain an ID plus a hex hash suffix. The hash is
MurmurHash64A with seed zero, multiplier `0xc6a4a7935bd1e995`, and shift 47;
the payload length is truncated to 32 bits before the initial mix. Reality
Composer Pro prints the value with `%llx`, so the suffix is lowercase and not
zero-padded — 1 to 16 digits, not always 16.

Two naming rules exist. Buffers under `mesh_descriptors`, `settings`, and the
texture directories hash their own payload. Geometry buffers do not: their
names come from a hash chained across every slot of the geometry. Getting
that rule wrong makes Reality Composer Pro fail to resolve the vertex
buffer. See
[the multi-material mesh contract](RCP_IMPORT_MULTI_MATERIAL_MESH.md) for
both rules. Reality Composer Pro rewrites the UUID portion of a buffer
filename on save. Buffer layouts remain build-private contracts; implement a
layout only where a controlled fixture and RCP acceptance establish its
semantics.

## Ground truth: the shipped Truth schema

The application itself is the primary source for the format contract. The
facts below come from the shipped binaries and schema files of the pinned
build, not from sample measurement. For the wider platform picture — the
entire Truth/`libtm` engine is RCP-only editor infrastructure, while USDZ
plus MaterialX is the shared OS-runtime contract, together with the measured
OpenUSD and MaterialX support ceilings — see
[APPLE_PLATFORM_CONTRACT.md](APPLE_PLATFORM_CONTRACT.md). The app-specific
facts:

- **The format is Our Machinery's "The Truth".** Reality Composer Pro is
  built on The Machinery engine; `CoreRealityTools.framework` embeds
  `the_truth.c` / `the_truth_migration.c` build paths and owns the text
  serializer, buffer store, and every `__`-dunder token. The `tm_*` record
  families are registered by ~100 `libtm-*.dylib` engine plugins
  (`libtm-usd.dylib` owns `tm_usd_asset` and the
  `%p{tm_uuid_t}%p{tm_str_t}.import` package naming;
  `libtm-asset_importer.dylib` owns the Reimport commands).
- **The complete schema ships in plain ASCII** at
  `Contents/Resources/rcp_app_data.bundle/Contents/Resources/data/core/__type_index.tm_meta`
  — 963 types with property names, kinds, target hashes, and defaults.
  `scripts/_lib/rcp_type_index.py` parses it and
  `tests/unit/test_rcp_contract_matches_type_index.py` holds the structural
  contract, the generator's emitted types, and the hashing rule to it. Diff
  this one file across RCP updates for the cheapest possible format-drift
  check.
- **Every cross-reference hash is `murmur64a(type_name, seed 0)`** — verified
  for all 436 referenced `type_hash` values; the single nonmember is the
  wildcard `8944e0b1cefd4756` = `murmur64a("tm_anything")`. The unpadded 1-16
  hex-digit buffer suffix is proven by the serializer's own format string
  (`%s.tm_buffers/%llx%s%s`); buffers may gain an extension suffix and can be
  LZ4-compressed on save (`tm_compress_buffers_when_saving`).
- **`members_sort_values` is a declared schema property** — a `subobject_set`
  of `tm_double` on `tm_timeline_group`. The generator's emission is legal;
  RCP's own files merely omit an optional sort-value set.
- **The canonical multi-material mesh form is fully known:**
  `tm_mesh_descriptor.subsets` is a `subobject_set` of
  `tm_mesh_descriptor_subset` (`name`, `index`, `face_indices` buffer,
  `face_count`) and `material_bindings` is a **singular** subobject of
  `tm_mesh_descriptor_material_binding` (`mesh_material_index`,
  `subset_to_material_index` buffer, `subset_count`). The
  clean-to-first-reimport canonicalization described above is RCP
  normalizing into this shape. The descriptor is one of three layers a
  multi-material mesh binds through; the model component and the geometry
  carry the other two. See
  [the multi-material mesh contract](RCP_IMPORT_MULTI_MATERIAL_MESH.md).
- **Serializer grammar tokens beyond those documented above:**
  `__instantiated` (prototype-instantiated set members, seen as a
  property-name suffix), `__removed` (prototype-removed members), `__types` /
  `__tm_types`. Some schema property names literally contain spaces
  (`"skeleton hierarchy"`, `"pose masks"`, `"joint chains"`).
- **Build pinning is forward-tolerant.** The engine has a real migration
  system: per-project `__migration_index.tm_meta` lists applied migration
  ids, types carry deprecated-name registries, and hard gates exist only for
  the binary database formats. A newer RCP build migrates old text data on
  open; the pin protects this project's writer, not RCP's reader.
- **Reimport has an automatic mode.** Beyond the manual **Editor > Reimport**,
  `libtm-asset_importer` registers USD file watchers on `source_path`
  (`tm_editor_command_reimport_automatically`), governed by a per-directory
  Import Settings hierarchy (`dcc_import_settings`). The
  `Trying to lookup property of NULL truth object` message that Import File
  triggers is one of ~15 generic Truth accessor errors, not an import-path
  diagnostic — consistent with dangling-reference lookups after a duplicate
  asset is created.

## Experimental static generator

The generator writes a complete 13-record, 7-buffer constant-material static
artifact for the pinned build:

- source, proxy, and optimized entity records;
- mesh descriptor, processed geometry, mesh resource, and material records;
- directory and USD settings records;
- descriptor buffers for topology, points, UVs, and normals;
- processed interleaved vertex data and 16-bit triangle indices.

It intentionally omits `settings.tm_buffers`, optimizer output, the variant
session, and other volatile caches. Ablation projects without those fields
opened and saved with `world Ready`; RCP did not regenerate the omitted
caches. Removing geometry processing metadata did cause RCP errors, so
`transform`, `transform_settings`, and `output_geometry` remain required.

The plugin and CLI expose the lane as `RCP_IMPORT`. To export, run:

```bash
python -m Plugin.cli \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  export References/Blender/RedCube.blend \
  --format RCP_IMPORT \
  -o /path/to/RedCube.import
```

The CLI publishes the adjacent USDA source and the `.import` directory.

### Accepted inputs

The static generator accepts one or more unskinned meshes directly below the
USD default prim or inside Blender 5.2's per-object, single-mesh Xform
wrappers. It deduplicates shared material records. A USD mesh with
`materialBind` `GeomSubset` face assignments keeps its full topology in one
mesh descriptor and authors the canonical `subsets` array RCP itself uses:
one entry per subset carrying the full GeomSubset prim path, a deterministic
UUID, and a content-hashed buffer of little-endian 32-bit face ordinals,
with the model component's materials listed in exactly descriptor-subset
order and carrying their slot `index`. The geometry gets the matching
subset ranges over a subset-sorted 32-bit triangle index stream — the
representation the renderer actually draws from (see
[RCP_IMPORT_MULTI_MATERIAL_MESH.md](RCP_IMPORT_MULTI_MATERIAL_MESH.md)).
Up to two material slots are supported — the measured corpus. Overlapping,
out-of-range, empty, or non-exhaustive subsets, materials shared across
subsets or mesh prims, more than two slots, unsupported topology,
interpolation, or hierarchy, and multi-mesh transform animation fail closed
and remove the incomplete destination.

### Skeletal extension

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

Structural results for the pinned build:

- A synthetic two-mesh/two-material fixture passes deterministic structural
  inspection with two geometry records, two descriptors, three mesh
  resources (including the optimizer resource), one skeleton
  definition/hierarchy, and zero derived or unknown hashed buffers.
- A disposable copy of RCP's 12-mesh Robot source generates the same
  measured record shape with 1- and 3-influence descriptors and zero unknown
  buffers.
- The full Blender 5.2 CLI path from `References/Blender/Robot.blend` with
  `export_animation=true`, `author_animation_library=true`, `UNLIT_ALBEDO`,
  and disposable 32-pixel bake textures baked 12 objects and produced a
  12-mesh, 12-material, 12-texture skeletal package with 78 records, 130
  content-hashed buffers, and zero derived or unknown hashed buffers.

Two independent bake/export runs of that Robot package produced the same
record-type/count shape, but not identical source paths, UUIDs, records, or
opaque texture payload hashes: the bake publisher uses a volatile staging
directory and independent baked image payloads. Running the generator twice
against one fixed staged USDA and texture set was byte-for-byte
deterministic. Generator determinism and whole-bake reproducibility are
therefore separate acceptance claims.

### Multi-material Robot results

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

Reality Composer Pro then established the current multi-material
compatibility boundary in a disposable project:

- clean open, save, close, and reopen completed with `world Ready` and
  `Tasks: None`;
- the first RCP save retained 83 records and all 140 opaque payloads, while
  canonicalizing record bytes and buffer filenames;
- the first genuine **Editor > Reimport** produced 83 records and 139
  buffers, added RCP's external `matched_skeleton_hierarchies` result, and
  removed one 12-byte settings buffer;
- the second genuine reimport was not idempotent. The package grew to 147
  records and 306 buffers, including 25 geometry records, 25 mesh
  descriptors, 26 mesh resources, and 26 materials. RCP retained the
  writer's per-material partitions, added `(1)` duplicates for the source
  meshes, and authored one combined body descriptor with two `subsets`
  entries and face-index buffers.

The two reimport phases therefore do **not** validate the superseded
strategy of representing one USD mesh with multiple face materials as
independent RCP mesh resources. RCP's canonical form keeps one mesh
descriptor and records material partitions in its nested `subsets` field.
The writer now authors that form, with deterministic UUIDs and reproduced
buffer payloads. It still must not synthesize
`matched_skeleton_hierarchies`, which the inspector recognizes only as a
measured RCP-authored field.

The preserved second-reimport capture establishes the bounded subset payload
contract. Each of the two descriptor subsets points to a content-hashed
buffer containing little-endian 32-bit face ordinals. The 5,288 entries in
each buffer exactly match the corresponding source USDA
`GeomSubset.indices`; the two arrays are disjoint and exhaust all 10,576
faces. The combined model component references one mesh resource and carries
two materials in matching slot order. See
[the multi-material mesh contract](RCP_IMPORT_MULTI_MATERIAL_MESH.md) for
record identities, hashes, the three layers that bind materials to faces,
implementation requirements, unsupported cases, and the acceptance plan.
This makes a bounded staging implementation possible, but does not change
the failed compatibility status.

Each reimport of the unmodified Blender-authored source emitted 13
`Unknown color space <private> encountered` warnings, one per baked texture.
Two controlled source-only A/B runs removed the shader ColorSpaceAPI or
mapped `srgb_rec709_display` to `srgb_texture`. Both suppressed the
warnings, but both converged to the exact same 83-record/139-buffer
first-reimport package as the unmodified source. Color-space metadata is
therefore a separate cleanup item, not the cause of the resource-duplication
failure. RCP's import preview also changed between magenta matching
visualization and the textured black/white model across phases, so preview
color alone is not accepted as a material-runtime proof.

The Robot run also established three Blender-specific compatibility rules:

- time-sampled UV index primvars are evaluated at the stage start time;
- individual single-mesh object Xform wrappers are retained below one common
  rig group;
- long staged texture names are classified from measured shader connections
  and bounded with deterministic hashes before creating filesystem records.

Explicit unsupported filename roles still fail closed even when the shader
graph is otherwise ambiguous.

### Supported-lane baseline for the same bake

The same animated 12-object Robot bake was exported through the supported
USDA, USDC, and USDZ lanes. Every stage reopened with 12 meshes, 12 material
bindings, 12 skinned meshes, one skeleton, one animation over frames 1–149
at 24 fps, the `Animation` clip contract, and 24 resolved shader texture
inputs deduplicated to nine content-addressed AVIF files. Superseded
pre-staging bake images are removed only from the bake worker's owned
temporary directory; the resulting USDZ contains the root USDC plus exactly
those nine referenced textures instead of carrying 12 additional orphan
images.

All three formats passed Apple USD Tools 0.25.11
`usdchecker --arkit --strict` and Xcode 27 `realitytool` compilation. Public
RealityKit 27 loaded source USDC, source USDZ, compiled USDC, and compiled
USDZ with one recursive model, 12 `ShaderGraphMaterial` instances,
`Animation`, `MeshDeformerComponent`, `SkeletalPosesComponent`, and matching
finite nonempty bounds with extents
`[0.14261799, 0.2738792, 0.16812176]`. Realitytool 27 exposed one false
positive: when a USDZ was nested unchanged inside a temporary `.rkassets`,
the compiler exited zero but RealityKit rejected the result with error 20.
The validator now safely expands the already-validated USDZ members before
compilation, and the resulting `.reality` passes the same runtime probe.

These are Blender, generator, and structural results only. Clean RCP
load/save/reopen, two reimports, Sequence Editor playback, and RealityKit
runtime/bounds acceptance for the multi-mesh skeletal output are still
required.

### Baked material extension

`bake-export --format RCP_IMPORT` runs the existing bake pipeline, publishes
its post-processed USDA beside the destination, then builds the private
package. The writer uses the RCP-authored `bakeTest_02.import` and Robot
material records as the build-80 contract:

- source image bytes are copied unchanged into a `tm_texture` buffer;
- the payload filename uses the same MurmurHash64A content suffix as RCP;
- the measured `tm_texture` creation-graph wrapper, color-space fields,
  shader connector hashes, and texture resource references are authored
  deterministically;
- `UNLIT_ALBEDO` and `LIT_IBL` use the measured RealityKit Unlit graph;
- `LIT_ALBEDO` uses the measured RealityKit PBR base-color graph and may add
  its baked roughness texture.

The bounded writer accepts one baked RGBA base-color image per material (its
alpha contains the bake pipeline's merged opacity) and, for Lit PBR, one
roughness image per material. Different mesh/material pairs may therefore
produce independent texture records, while meshes that genuinely share the
same USD material reuse one material record. Normal, metallic, occlusion,
and independent opacity images, unknown filename roles, multiple base-color
images within one material, and unmeasured surface profiles fail closed.

Disposable Blender/CLI multi-asset runs use a three-object corpus containing
two shared procedural materials and one object with two face materials:

- `UNLIT_ALBEDO` generated four split mesh resources, four materials, four
  textures, 30 records, and 32 content-hashed buffers;
- `LIT_ALBEDO` generated four split mesh resources, four materials, eight
  textures, 34 records, and 36 content-hashed buffers;
- direct `RCP_IMPORT` export of the equivalent compatible flat-material
  scene generated four mesh resources and two deduplicated material records;
- the Blender UI background-worker path reached terminal `done`, consumed
  its disposable scene snapshot, published the adjacent USDA, and produced
  the same 30-record/32-buffer unlit package shape;
- USDA, USDC, and USDZ bake exports retained three USD meshes, four baked
  material records, and both material subsets;
- the public RealityKit 27 smoke probe loaded both USDC and USDZ on Apple M5
  Max, recursively found three model entities and four ShaderGraph
  materials, and reported identical finite bounds (`min [-2.5, -1, -1]`,
  `max [2.5, 3.5, 1]`).

Disposable Blender/CLI runs also cover all three bake modes for a single
mesh:

| Bake mode | Records | Content-hashed buffers |
|---|---:|---:|
| textured `UNLIT_ALBEDO` | 15 | 8 |
| textured `LIT_ALBEDO` | 16 | 9 |
| `LIT_IBL` | 15 | 8 |

In every run above the structural inspector reported zero derived or unknown
hashed buffers, and the CLI returned `format: RCP_IMPORT`. RCP
open/save/reopen and visual/runtime acceptance of these generated
multi-model and textured packages is still required before the extension can
be called RCP-compatible.

### Direct plugin-output acceptance

On the pinned build, the exact CLI output for
`References/Blender/RedCube.blend` was copied into an isolated disposable
project shell with its deterministic asset identity intact. Reality Composer
Pro:

1. opened it with `world Ready` and no console error indicator;
2. completed all background tasks (`Tasks: None`);
3. saved without repair;
4. closed and reopened it with `world Ready`.

Before save the artifact contained 13 records, 7 content-hashed buffers, and
1,536 opaque bytes. After save the record and buffer counts, buffer layout,
UUID graph counts, and every opaque payload remained equal. RCP
canonicalized:

- the UUID portion of two geometry buffer filenames and their references;
- geometry record formatting and numeric spelling;
- several material float spellings;
- geometry `validity_hash` from the accepted bootstrap value
  `2cfcf0b4ccf2dcd8` to `a28884579325560a`.

This proves the measured static artifact is an accepted staging input, not
that the private schema is stable across RCP builds or arbitrary mesh
payloads.

A second isolated project tested genuinely different topology: one triangle
with three points and one face. The generator supplied the same bootstrap
validity value used by the cube. RCP opened and saved the project with
`world Ready`, `Tasks: None`, and no error indicator, then canonicalized the
triangle validity hash to `a529a77de146ba8d`. The artifact retained 13
records, 7 content-hashed buffers, and 214 opaque bytes. This establishes
that `2cfcf0b4ccf2dcd8` is an accepted build-80 bootstrap marker for the
validated static subset rather than a cube-content checksum.

## Experimental transform generator

The controlled `CubeWith4Animations` record shows that RCP stores transform
animation in three layers:

1. a sampled type-2 timeline nested inside `settings.tm_usd`;
2. little-endian float32 frame and translation buffers under
   `settings.tm_buffers`;
3. one type-1 `tm_timeline` record per named clip, each referencing the
   sampled timeline and carrying its start/end trim.

For the original 97-sample corpus, the time buffer is exactly the float32
sequence `1...97` (388 bytes), and the position buffer is 97 XYZ float32
tuples (1,164 bytes). Their MurmurHash suffixes are respectively
`31e4244ce368fb5c` and `6dfa4c9b558eb501`, matching RCP's own import byte for
byte. The other four potential rotation/scale key/time slots are declared but
have no backing buffers for a translation-only animation.

The generator reads the authored `RealityKit.AnimationLibrary` clip names
and start times, samples translation at each integer stage frame, writes the
two buffers, adds `tm_animation_library_component` to both entity variants,
and emits all named clip records. Sampled rotation, scale, multiple animated
nodes, or conflicting clip definitions fail closed.

Two disposable RCP projects accepted generated transform artifacts:

- the controlled 97-frame corpus source;
- the exact Blender 5.2 CLI export from
  `References/Blender/CubeWith4Animations.blend` with
  `export-animation=true`.

Both reached `world Ready`, saved with no error indicator, retained all four
clip records, and preserved every opaque payload. The direct plugin output
also closed and reopened with `world Ready`; it had 100 samples, 18 records,
9 content-hashed buffers, and 3,136 opaque bytes. Its clip ranges were
derived from the current Blender Actions at 24 fps:

| Clip | Start | End |
|---|---:|---:|
| GoBackward | 0 | 1.0416666666666667 |
| GoDown | 1.0416666666666667 | 2.0833333333333335 |
| GoForward | 2.0833333333333335 | 3.125 |
| GoUp | 3.125 | 4.125 |

RCP save canonicalized text and UUID details but retained the record types,
buffer layout, UUID graph counts, clip names and ranges, and opaque
animation payloads.

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

Capture the same controlled source again after an RCP reimport, then
compare:

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
identity, path, and payload fields from stable structure. A field is not
declared deterministic until at least two clean imports and two reimports of
the same source agree.

The checked-in corpus catalog is `tests/fixtures/rcp_import/corpus.json`.
Full opaque payloads stay local. Run the golden corpus test with:

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
- fixtures that do not meet the selected static, transform, or skeletal
  shape.

This is a structural contract only. Nested values are inventoried, not
decoded as a writable schema. Passing inspection does not prove that RCP can
open an asset.

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

RCP UI/runtime results need the application build, source hash, capture
hash, timestamp, and pass/fail notes. A successful USD import is the
baseline; a generated `.import` candidate must be at least as reliable.

The corpus catalog pins source size and SHA-256 so a result from a modified
USD cannot be mistaken for a repeatability measurement.

### Reimport boundary observed

Reality Composer Pro does not refresh a saved `.import` merely because a
source changes on disk. To reimport, select the import asset, then choose
**Editor > Reimport**. Each measured run completed with `Tasks: None`; the
project saved and reopened without repair or an error indicator.

Do not use **Import File** as a substitute. Importing the same path created
`RedCube (1).import` and emitted
`Trying to lookup property of NULL truth object` in the RCP console.

Import destination is selection-sensitive. Importing while another `.import`
container is active can nest the new `.import` inside it. Acceptance
automation must navigate to the project root before each clean import and
verify the on-disk top-level layout afterward.

The repeated clean-import and two-reimport requirements are satisfied for
all three profiles. The retained structural reports are under
`tests/fixtures/rcp_import/evidence/rcp3-80.0.1.500.1`.

### RealityKit and animation findings

The supported source USDs were converted losslessly to USDC and loaded
through the public RealityKit 27 runtime probe. All three exposed one model
and one `ShaderGraphMaterial`. Recursive visual bounds were finite and
non-empty:

| Fixture | Minimum | Maximum | Extents |
|---|---|---|---|
| RedCube | `[-1, -1, -1]` | `[1, 1, 1]` | `[2, 2, 2]` |
| CubeWith4Animations | `[-1, 1, -1]` | `[1, 3, 1]` | `[2, 2, 2]` |
| MeshyRiggedCharacter | `[-0.620521, 0, -0.282728]` | `[0.620521, 1.7, 0.282728]` | `[1.241043, 1.7, 0.565455]` |

The transform source retained `GoBackward`, `GoDown`, `GoForward`, and
`GoUp`. The skeletal source retained `Agree_Gesture`, `Running`, `Walking`,
and `walking_2`, plus `MeshDeformerComponent` and `SkeletalPosesComponent`.

RCP did not retain those author-facing clip sets. The transform `.import`
contains one `CubeWith4Animations_transform.tm_animation`. The skeletal
`.import` contains one transform timeline and one root skeletal timeline.
The source clip keys are absent from the generated records, so Sequence
Editor clip selection and per-clip playback acceptance fail instead of being
inferred from the source runtime result.

A staging-only package experiment copied the untouched disposable
`.realitycomposerpro` package to a `.rkassets` path. `realitytool compile`
accepted it, but the resulting `.reality` was only 4.3 KiB and public
RealityKit loading failed with `RealityKit.__RealityFileError error 4`.
RCP's **Save Project As Asset Database** instead produced a private
`.rcp_db`, which `realitytool` rejects as an input. Renaming or copying
generated packages is therefore not yet a valid runtime handoff.

To record acceptance evidence, copy
`tests/fixtures/rcp_import/acceptance.template.json` to an evidence
location, fill every gate with a retained evidence path, then run:

```bash
python scripts/validate_rcp_import_acceptance.py /path/to/acceptance.json
```

The validator fails for pending or failed gates, unknown gates, build
drift, changed source hashes, changed structural captures, or a claimed
pass without evidence. It requires exactly two `clean_import` and two
`reimport` run records per fixture. Evidence schema v2 pins one expected
structure per phase, allowing the measured skeletal canonicalization
without accepting arbitrary drift. The checked-in measured evidence
intentionally fails full acceptance because the staged runtime and RCP
animation-authoring gates are not satisfied:

```bash
python scripts/validate_rcp_import_acceptance.py \
  tests/fixtures/rcp_import/acceptance.rcp3-80.0.1.500.1.json
```

## What prevents a complete writer today

1. No public writer API or schema exists.
2. Static buffer filename hashing and the validated layouts are understood.
   RCP's canonical geometry-validity function is still private, but
   controlled cube and triangle projects establish an accepted bootstrap
   value that RCP replaces on save.
3. Translation animation buffers and clip records are implemented. The
   controlled skeletal source's joint transforms, skinning, scene-tree
   tables, and named clips open and render in RCP. General rotation, scale,
   multiple animated nodes, and arbitrary skeletons remain outside the
   validated subset.
4. UUID lifetime rules show stable clean and first-reimport phases for the
   single-mesh corpus. The superseded split writer, which partitioned one
   source mesh into multiple descriptors, made the multi-material Robot
   candidate duplicate resources on its second reimport. The writer now
   authors RCP's canonical nested `subsets` representation and the geometry
   and model-component layers that bind with it, and a two-material static
   mesh renders. No reimport evidence exists for that output yet.
5. RCP may enforce hidden version/build migrations or invariants beyond the
   text records.
6. RCP 3 demonstrably flattens the named `RealityKit.AnimationLibrary` clip
   definitions motivating this experiment; the `.import` timeline records
   show editor state, but do not prove a stable authoring contract.
7. One-USD-per-Blender-Action is a supported parallel experiment, but still
   requires RCP authoring and Sequence Editor acceptance evidence.

## Phased plan

1. **Corpus repeatability (complete for build 80):** retain the two clean
   and two reimport reports and keep clean/reimport phases separately
   pinned.
2. **Parser and static generator (complete for the bounded build-80
   subset):** typed parsing, MurmurHash buffer validation, build-pinned
   record generation, and direct static open/save/reopen acceptance are
   complete for cube topology. A different triangle topology confirms that
   the accepted bootstrap validity value generalizes inside the strict
   static subset.
3. **Baked texture writer (implemented, single-material RCP acceptance
   pending):** all three bake modes pass the Blender/CLI and structural
   gates for one mesh. Multi-mesh/single-material source shapes pass
   supported USD compilation and RealityKit runtime checks. A mesh with
   multiple face materials renders both materials with the canonical
   representation, but remains experimental-only until save/reopen and two
   non-growing reimports pass.
4. **Transform generator (implemented, final acceptance in progress):** the
   aggregate sampled timeline, translation/time buffers, entity component,
   and four named clip records pass RCP open/save. Reopen, Sequence Editor,
   and playback evidence remain required.
5. **Skeletal generator (rendering, not accepted):** the controlled
   hierarchy, definition, binding, sampled timeline, scene-tree buffers, and
   four named clip records are generated. One mesh with multiple materials
   is now written as a single descriptor with `subsets` and content-hashed
   32-bit face-index buffers, plus the geometry subset ranges and material
   slot indices that bind it, and it renders. Two idempotent reimports are
   still required before that input shape counts as compatible.
6. **Acceptance automation:** retain reproducible RCP open/reimport
   captures; extend the RealityKit probe from bounds/resource discovery to
   controlled playback duration only for clips that RCP actually exposes.
7. **Runtime handoff gate:** create an RCP-authored entity in the disposable
   world, export/compile that supported authoring output, and require
   successful public RealityKit loading. Package renaming alone is rejected
   by the current evidence.
8. **Product decision:** if build churn or remaining private invariants
   defeat repeatability, keep `.import` support as a diagnostic/corpus tool
   and invest in supported USD/action-per-file workflows instead.

## Verification

The facts on this page were established against Reality Composer Pro 3.0
(build `80.0.1.500.1`, Xcode build `27A5218g`) by controlled imports and
reimports in disposable projects and by inspecting the shipped application
bundle. Retained evidence:

- structural reports:
  `tests/fixtures/rcp_import/evidence/rcp3-80.0.1.500.1`;
- corpus catalog with pinned source sizes and SHA-256:
  `tests/fixtures/rcp_import/corpus.json`;
- pinned tests: `tests/unit/test_rcp_import_contract.py`,
  `tests/unit/test_rcp_import_generator.py`, and
  `tests/unit/test_rcp_contract_matches_type_index.py`;
- acceptance validation: `scripts/validate_rcp_import_acceptance.py` with
  `tests/fixtures/rcp_import/acceptance.rcp3-80.0.1.500.1.json`.
