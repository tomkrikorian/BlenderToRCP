# RCP skeletal `.import` checkpoint

Checkpoint date: 2026-07-26

Branch: `experiment/rcp-import-export`, based on `origin/dev`

RCP under test:

- Reality Composer Pro 3.0
- `CFBundleVersion` `80.0.1.500.1`
- Xcode build `27A5218g`
- observed on macOS 27.0 build `26A5388g`

This document is the restart point for the full `.import` generator
experiment. No compatibility claim is made for the skeletal lane. Static mesh
and sampled translation have their own accepted, build-pinned subsets. The
skeletal v2 output passes the three previously failing build-80 Truth loader
paths, renders in RCP, survives save/reopen and two source reimports, and loads
through the public RealityKit runtime with finite bounds and all four named
clips. The current float32-normalized v3 output separately passes clean RCP
load and the same public runtime checks; its two reimports remain to be
repeated. Sequence Editor playback and a second structurally distinct skeletal
fixture also remain open.

## Where work stopped

The generator can read the controlled `MeshyRiggedCharacter.usda` UsdSkel
source and emit:

- 32-bit skinned triangle geometry and the measured interleaved vertex format;
- four vertex-interpolated joint indices and weights per point;
- source and optimized entity variants;
- skeleton hierarchy and definition records;
- source skinning and optimized merged mesh resource records;
- sampled joint translation and quaternion buffers;
- source and optimized scene-tree name/node tables;
- source inverse-bind bone table;
- a separate armature-scale transform timeline;
- named skeletal clip records for `Agree_Gesture`, `Running`, `Walking`, and
  `walking_2`.

For this controlled source, the generated large buffers match the
RCP-authored baseline byte for byte:

| Payload | Bytes | SHA-256 |
|---|---:|---|
| Processed geometry | 72,904,500 | `409805f896546dcb7f189603d77915d71fd810e4e5776eaa76a84846ea0f0475` |
| Skeletal times | 3,064 | `4bf261e9a9b8819a7d9e4b239cf48a5c2b59d5a11ee980cf1b362d1953aaba15` |
| Joint translations | 110,304 | `ebfdf491b7ec6f964a246765058ae2f2f28567bb207a5761707768fd8ff510ea` |
| Joint rotations | 147,072 | `617f815e45636fdfed863ad58e7baa522acc9e972582fe3f395202fda352f943` |

These hashes are fixture evidence, not a general contract. Validation must
recompute them from the selected controlled source.

The decoded build-80 scene-tree layouts are:

- names: NUL-terminated UTF-8 full joint paths;
- nodes: one 56-byte little-endian `<QI11f` row per joint containing the
  MurmurHash64A path, parent index, rest translation, quaternion, scale, and a
  zero flag;
- bones: one 64-byte little-endian `<QI13f` row per joint containing the path
  hash, joint index, the first three columns of each inverse-bind matrix row,
  and a zero flag.

The original generated artifact opened and displayed the correctly skinned
character but reproducibly reported:

1. `Unexpected nil item`
2. `Trying to lookup property of NULL truth object`
3. `Trying to add NULL object to subobject set`

LLDB on the pinned RCP loader identified the first error at
`CoreRealityTools` `resolve_or_create_placeholder + 292`. Its caller,
`private__create_asset_data_from_path`, was processing
`skeletons/root.tm_skeleton_hierarchy`. The caller looked up the
MurmurHash64A key `0x28598ea17608bf3d`, which decodes to `__asset_uuid`, and
passed an all-zero UUID because the generated hierarchy record omitted that
field.

The writer now emits a deterministic `__asset_uuid` for the hierarchy. The
structural contract also requires `__asset_uuid` on every known
non-directory record and fails closed if it is absent. A newly generated
candidate then:

- loaded without reaching `resolve_or_create_placeholder + 292`;
- loaded without reaching `add_to_subobject_set + 368`, the observed
  `Trying to add NULL object to subobject set` path;
- loaded without reaching any of the 66 build-80 call sites for
  `Trying to lookup property of NULL truth object`;
- rendered the correctly skinned robot in the RCP viewport with `Ready` and
  `Tasks: None`.

The three Truth errors were therefore one causal chain, not three independent
format defects. This clears the clean-loader gate for the controlled candidate;
it does not yet clear the remaining editor and runtime gates.

Build-pinned evidence for this run is recorded in
`tests/fixtures/rcp_import/evidence/rcp3-80.0.1.500.1/generated-skeletal-v2.json`.

The corrected candidate was also saved normally in the disposable project,
closed, and reopened without repair. RCP's save canonicalized only
`geometry/char1.tm_geometry`: two geometry buffer UUID prefixes/references,
numeric formatting, and `validity_hash` changed. All 24 records, 19 opaque
buffers, opaque payload bytes, and four timeline records remained present.
The post-save and post-reopen packages were byte-identical with tree SHA-256
`1e5c1440ea0deee79bd2d4f882c94f1f28cf6269331442d3f733baa5d444fa6d`
and canonical contract SHA-256
`30916d7bc699bc8aa19ca9204d991ca77f9e8719563d60b1dadefe63c89552ee`.
This clears save/reopen persistence only. The stored project-relative source
was absent at capture time, so this result is not reimport evidence.

## Reimport and public runtime acceptance

A fresh, single-import disposable project was created at:

`~/.codex/rcp-import-experiment/build-80.0.1.500.1/runs/accept-generated-v2-reimport.realitycomposerpro`

`Editor > Reimport From...` bound the controlled source without changing any
byte in the generated package. The source is not self-contained without its
two referenced PNG sidecars: omitting them produced two explicit image-import
errors; restoring the exact payloads cleared the console and rendered the
textured robot with `Ready` and `Tasks: None`.

Two subsequent ordinary `Editor > Reimport` cycles completed without errors.
The pre-reimport package and both results were byte-identical:

- tree SHA-256
  `1e5c1440ea0deee79bd2d4f882c94f1f28cf6269331442d3f733baa5d444fa6d`;
- canonical contract SHA-256
  `30916d7bc699bc8aa19ca9204d991ca77f9e8719563d60b1dadefe63c89552ee`;
- 24 records, 19 opaque buffers, and 100,830,500 opaque bytes;
- 5 `tm_timeline` records (aggregate plus four named clips);
- unchanged normalized structure, record fingerprints, UUID identity, buffer
  layout, and opaque payload hashes.

The saved disposable project compiled with Apple's `realitytool` into a
16 MiB `.reality` artifact with SHA-256
`ffbe893a20d2be2af75e3a5ca59d842ad7e5a755dc22152a4bc9a895a1b5fc83`.
The public RealityKit smoke probe passed on Apple M5 Max:

- five entities and one model entity;
- `AnimationLibraryComponent`, `MeshDeformerComponent`,
  `SkeletalPosesComponent`, and `ModelComponent`;
- `Agree_Gesture`, `Running`, `Walking`, and `walking_2` animation keys;
- finite nonempty bounds with extents
  `[1.2410427, 1.6999997, 0.56545544]`.

This corrects the earlier 4.3 KiB runtime artifact failure. That failure was
caused by compiling an incomplete project staging, not by the generated
skeletal package.

The subsequent float32-normalized v3 candidate changes only
`skeletons/root.tm_skeleton_hierarchy`, whose SHA-256 is
`400de6f1d71977d28294c1f268242d014c0def7f4f7022561a6b6161fe047879`.
It opens as `Ready` in a fresh disposable RCP project and compiles to a
16 MiB `.reality` artifact with SHA-256
`7733a0c5a40b3813ac90cc1ab55f6f0a0b40496f9901dff42e2be5a568c86bd7`.
The public runtime again reports five entities, one model, all four named
clips, the required skeletal components, and identical finite bounds. This is
clean-load and runtime evidence for the current code; the two source reimports
above were captured from v2 and must not be attributed to v3 until repeated.

RCP also created a disposable Sequence, but the imported asset is read-only
and the Sequence's Root Entity remained `(none)`. The custom hierarchy control
could not bind an imported root without first authoring a project-owned
Prototype/root entity. Therefore the four timeline records and public runtime
keys are proven, but Sequence Editor range display and visual playback are not.

## Clean-control evidence

Acceptance probes used only disposable projects under `/private/tmp`; the
user's saved RCP project was not opened or modified.

A genuinely blank project shell was created at:

`/private/tmp/blendertorcp-blank-project.HjlzP5/SkeletalBlank.realitycomposerpro`

The RCP-authored baseline used for comparison was:

`/private/tmp/blendertorcp-rcp3-acceptance.PvjVsn/clean-1/AcceptanceClean1.realitycomposerpro/MeshyRiggedCharacter.import`

The controlled source was:

`/private/tmp/blendertorcp-rcp3-acceptance.PvjVsn/clean-2/sources/skeletal/MeshyRiggedCharacter.usda`

The last four-clip generated candidate was:

`/private/tmp/blendertorcp-skeletal-transform-timeline.y0mRgD/MeshyRiggedCharacter.import`

Those paths were temporary. Required read-only copies now live outside Git
under:

`~/.codex/rcp-import-experiment/build-80.0.1.500.1`

This contains the RCP-authored baseline, controlled USDA source, generated
candidates, disposable project clones, and immutable removed-package
snapshots. Never put the approximately 100 MiB opaque corpus in Git. The
stored `shell/Package.realitycomposerpro` is not a genuinely blank shell: its
project metadata retains paths from the disposable source project. Treat it as
a copied project template and assert the exact import contents on every run.

The baseline package alone in a clone of the blank shell opens with no console
errors. The generated package alone in the same kind of clean shell reports the
three errors above. This isolates the failure to the generated package rather
than the project shell.

Important harness correction: RCP recognizes an import package from its
contents, not from the `.import` suffix. Renaming an old package inside a
`.realitycomposerpro` directory does not remove it from consideration.
Immutable before/after snapshots must be moved completely outside the project
package, and every probe must assert that exactly one import package is present.

## Hypotheses already tested

Each of the following was tested in a clean, single-import disposable project
and did **not** remove the three console errors:

- adding the decoded scene-tree buffers;
- reducing the skeletal animation to one aggregate clip;
- matching the RCP source and optimized entity shapes;
- adding the semantic-14 material-index Primvars reference;
- adding the separate armature transform timeline;
- substituting the baseline skeletal geometry validity hash;
- substituting the complete RCP-authored material graph;
- substituting the exact RCP-authored scene-tree and inverse-bind buffers;
- substituting baseline output/session caches separately and together.

Do not repeat those as isolated experiments unless new evidence changes another
variable. None of the substitutions belongs in production code: opaque
baseline data was used only for disposable differential probes.

At the stopping point, normalized non-UUID scalar shapes match the baseline for
settings, source and optimized entities, geometry, mesh descriptor, merged
resource, skeleton definition, and most hierarchy fields. Both UUID graphs
have only the expected unresolved system graph ID
`feefd623-b26a-6155-97b0-2dd807e0e1c3`.

Known residual differences include:

- generated UUID identity and reference assignment;
- the generated bootstrap geometry validity hash;
- record ordering/format details and possible private identity invariants not
  represented by the structural inspector;
- the simplified generated material graph, although replacing the entire
  material graph did not clear the errors.

## Differential harness

`scripts/hybridize_rcp_import.py` now creates disposable record-group hybrids
from the RCP-authored baseline and a generated candidate. It:

- partitions directories, settings, entities, geometry, skeleton, animations,
  and materials;
- maps generated record identities to structurally corresponding baseline
  `__uuid` and `__asset_uuid` values;
- maps content-identical buffers by parent path, byte count, and SHA-256;
- rewrites mapped references and buffer prefixes;
- rejects unknown paths, symlinks, overwrite attempts, ambiguous mappings, and
  newly introduced dangling UUID references;
- writes its manifest beside, never inside, the `.import` directory.

On the controlled corpus it found 516 identity mappings and 15
content-identical buffers. An animations-only substitution correctly failed
closed on a new dangling reference; settings and animations form a coupled
group for that candidate. This harness remains a reverse-engineering tool, not
an exporter.

## Exact next steps

1. Complete two `Editor > Reimport` cycles on the float32-normalized v3
   candidate and require the same structural, opaque-payload, UUID, and
   runtime invariants recorded for v2.
2. In a disposable project, create a project-owned Prototype/root entity from
   the generated asset, bind it as the Sequence Root Entity, then capture the
   displayed ranges and playback evidence for `Agree_Gesture`, `Running`,
   `Walking`, and `walking_2`.
3. Add a second controlled skeletal fixture with materially different joint
   hierarchy, topology, animation length, and clip partitioning while retaining
   the explicit build-80 profile. The local `Robot` and `RobotUnlit` candidates
   each contain 12 meshes and correctly fail closed because the current profile
   requires exactly one.
4. Repeat clean load, save/reopen, two reimports, Sequence Editor, `realitytool`,
   and public RealityKit bounds/component/animation checks for that fixture.
5. Only after both fixtures pass may the skeletal subset be described as a
   staging writer. Multi-mesh support requires a separately measured RCP
   contract; it must not be inferred from the single-mesh corpus.

## Restart and product boundary

The intended product remains a full `.import` generator, but implementation
must remain a set of explicit, build-pinned profiles. The current skeletal
profile must fail closed unless all measured preconditions hold: exact build,
joint ordering, four vertex influences, supported interpolation, identity
geometry bind, integer sample range, and known animation layout.

Hierarchy rest transforms and inverse-bind matrices are now quantized to
float32 before deciding whether identity fields may be omitted. A targeted
unit fixture proves that near-zero and near-one source doubles follow the same
serialization decision as the build-80 records.

Do not enable skeletal generation as a compatibility default, claim RCP
support, fabricate an unknown binary payload, push, merge, or touch the
original checkout until the acceptance gates above pass.
