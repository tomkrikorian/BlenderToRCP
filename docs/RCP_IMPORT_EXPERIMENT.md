# Reality Composer Pro 3 `.import` experiment

Status: repeated clean-import/reimport corpus and runtime baseline captured. No
`.import` writer is implemented or claimed.

## Decision

BlenderToRCP must continue to export supported USD as the production ingestion
path. A `.import` directory is an RCP-private generated cache beside the source
USD, not a published interchange format. The experiment therefore starts with
capture, inspection, and acceptance evidence. It must not fabricate opaque
buffers or advertise compatibility until the exact RCP build opens and
reimports the output successfully.

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

The buffer filenames contain an ID plus a short hash, but their encoding and
all semantic invariants are unpublished. They are treated as opaque bytes.

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

## What prevents a good writer today

1. No public writer API or schema exists.
2. Buffer encodings and the relationship between filename hashes, data IDs, and
   record validity hashes are unknown.
3. UUID lifetime rules now show a stable clean phase and a stable reimport
   phase, but the opaque skeletal canonicalization between them is unexplained.
4. RCP may enforce hidden version/build migrations or invariants beyond the text
   records.
5. RCP 3 demonstrably flattens the named
   `RealityKit.AnimationLibrary` clip definitions motivating this experiment;
   the `.import` timeline records show editor state, but do not prove a stable
   authoring contract.
6. One-USD-per-Blender-Action is a supported parallel experiment, but still
   requires RCP authoring and Sequence Editor acceptance evidence.

## Phased plan

1. **Corpus repeatability (complete for build 80):** retain the two clean and
   two reimport reports and keep clean/reimport phases separately pinned.
2. **Parser depth:** add typed, read-only parsing only for fields whose behavior
   is demonstrated by controlled diffs. Keep unknown nested fields fatal for any
   future writer lane.
3. **Acceptance automation:** retain reproducible RCP open/reimport captures;
   extend the RealityKit probe from bounds/resource discovery to controlled
   playback duration only for clips that RCP actually exposes.
4. **Staging feasibility gate:** create an RCP-authored entity in the disposable
   world, export/compile that supported authoring output, and require successful
   public RealityKit loading. Package renaming alone is rejected by the current
   evidence.
5. **Writer feasibility gate:** proceed only if RCP-generated records can be
   reproduced without guessing buffer encodings. The first candidate must reuse
   RCP-generated opaque payloads for an unchanged source and make no semantic
   edits.
6. **Bounded writer:** if the feasibility gate passes, write to a staging
   directory, declare the exact build contract, reject all unsupported fields,
   and require RCP open/reimport/runtime/Sequence Editor evidence before use.
7. **Product decision:** if build churn or opaque buffers defeat repeatability,
   keep `.import` support as a diagnostic/corpus tool and invest in supported
   USD/action-per-file workflows instead.
