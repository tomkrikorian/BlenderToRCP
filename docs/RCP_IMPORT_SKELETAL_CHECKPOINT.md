# RCP skeletal `.import` checkpoint

Checkpoint date: 2026-07-24

Branch: `experiment/rcp-import-export`, based on `origin/dev`

RCP under test:

- Reality Composer Pro 3.0
- `CFBundleVersion` `80.0.1.500.1`
- Xcode build `27A5218g`
- observed on macOS 27.0

This document is the restart point for the full `.import` generator
experiment. No compatibility claim is made for the skeletal lane. Static mesh
and sampled translation have their own accepted, build-pinned subsets; the
skeletal output presently renders in RCP but fails the clean-console gate.

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

The generated artifact opens and displays the correctly skinned character.
Nevertheless, a clean open reproducibly reports:

1. `Unexpected nil item`
2. `Trying to lookup property of NULL truth object`
3. `Trying to add NULL object to subobject set`

That is the stopping blocker. Sequence Editor visibility, clip playback,
save/reopen, reimport survival, and public RealityKit runtime exposure are not
accepted while these errors remain.

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

These are temporary paths, not durable fixtures. Before resuming, verify their
existence and copy required evidence into a new disposable experiment
directory. Never put the approximately 100 MiB opaque corpus in Git.

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
- near-one rest-scale serialization: RCP appears to decide omission after
  float32 conversion while the generator currently decides from source
  doubles;
- record ordering/format details and possible private identity invariants not
  represented by the structural inspector;
- the simplified generated material graph, although replacing the entire
  material graph did not clear the errors.

## Exact next steps

1. Recreate a clean disposable shell and enforce the single-import invariant.
   Copy the baseline and candidate outside the package before each run.
2. Extend the comparison harness to replace and retarget one complete
   **record group** at a time, not individual guessed fields. Use this order:
   settings; source/optimized entities; geometry/mesh/resources; skeleton
   hierarchy/definition; animations; material.
3. Run a binary search over those groups. For every candidate, retain the
   inspector report, the exact RCP build, a console screenshot/log, and the
   package hash. The first hybrid with zero errors identifies the group
   containing the missing invariant.
4. Subdivide only that group until the smallest responsible record or
   relationship is known. Derive a general rule from at least two independently
   generated inputs; do not copy fixture UUIDs or opaque buffers into the
   writer.
5. Correct float32-before-omission behavior for hierarchy transforms and add
   unit tests for scene-tree row packing, parent indices, inverse-bind rows,
   deterministic IDs, and unsupported UsdSkel shapes.
6. When—and only when—the candidate opens with zero console errors, run
   save/reopen and two genuine **Editor > Reimport** cycles.
7. Then verify all four names and ranges in Sequence Editor, visual playback,
   persistence after reopen/reimport, and the public RealityKit
   `AnimationLibrary`/bounds runtime probe.
8. Repeat on a second, structurally different skeletal fixture. Only after both
   pass may the supported subset be described as a staging writer.

## Restart and product boundary

The intended product remains a full `.import` generator, but implementation
must remain a set of explicit, build-pinned profiles. The current skeletal
profile must fail closed unless all measured preconditions hold: exact build,
joint ordering, four vertex influences, supported interpolation, identity
geometry bind, integer sample range, and known animation layout.

Do not enable skeletal generation as a compatibility default, claim RCP
support, fabricate an unknown binary payload, push, merge, or touch the
original checkout until the acceptance gates above pass.
