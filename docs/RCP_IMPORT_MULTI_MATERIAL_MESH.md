# RCP `.import` multi-material mesh contract

Status: measured on Reality Composer Pro 3.0 build `80.0.1.500.1`; writer
support is not accepted yet.

This note records what is required to replace the experiment's current
per-material mesh splitting with the representation authored by RCP for one
mesh carrying multiple face materials. It is deliberately build-pinned and
describes only the controlled two-material skinned Robot fixture.

## Why the current writer is insufficient

The current experiment can load a USD mesh with multiple material-bound
`GeomSubset` children, but it turns each subset into an independent generated
mesh resource. That package:

- opens, saves, closes, and reopens in RCP;
- compiles with `realitytool` and loads through public RealityKit;
- preserves both materials in the generated/runtime artifact;
- completes one genuine RCP reimport without resource growth.

It does not pass the second-reimport gate. The package grows from 83
records/139 buffers after reimport 1 to 147 records/306 buffers after reimport
2. RCP retains the split resources, creates duplicate source resources, and
adds its own combined mesh representation. A rendering success is therefore
not proof that the generated resource graph matches RCP's private contract.

## Measured RCP-authored representation

The second RCP reimport authored one combined body mesh with these links:

| Role | Observed record/UUID |
| --- | --- |
| mesh descriptor | `robot_mesh_mesh_export_body_PLY.tm_mesh_descriptor` / `8c6a3e73-8069-56c8-e1d8-5174490f930b` |
| geometry | `robot_mesh_mesh_export_body_PLY.tm_geometry` / `f21f2875-b518-ac84-32fb-0b28e9f880ed` |
| mesh resource | `robot_mesh_mesh_export_body_PLY.tm_mesh_resource` / `1486cf5f-23c5-6b53-986a-39139fa8c834` |
| descriptor asset UUID | `3b37ca8e-1335-d446-6ca7-413ff72c983c` |

The descriptor keeps the source mesh whole:

- 6,207 vertices;
- 10,576 faces;
- 31,728 face-vertex indices;
- one set of points, normals, UVs, topology, and skinning data;
- a `subsets` array with one entry per material assignment.

The model entity likewise keeps one model component and one mesh-resource
reference. Its `materials` array is ordered consistently with the descriptor
subsets. In the observed two-slot case, slot 0 omits `index`; slot 1 explicitly
stores `index: 1`. This is evidence for those two slots only, not a general
default-material or arbitrary-slot rule.

### Subset records

RCP authored:

| Slot | Descriptor subset name | Faces | Index field |
| --- | --- | ---: | --- |
| 0 | full USD path ending in `rig_skin_robot_mesh_mesh_export_pxrusdpreviewsurface5sg1_Baked` | 5,288 | omitted |
| 1 | full USD path ending in `RobotBodyAccent_Baked` | 5,288 | `1` |

The subset name is the full USD `GeomSubset` prim path, not merely the
material display name. The model component uses the material names and the
same observed slot ordering.

### Face-index buffers

Each subset has one file in the descriptor's `.tm_buffers` directory. The
payload is a packed little-endian array of 32-bit unsigned face ordinals:

| Slot | Buffer UUID | Bytes | Content-hash suffix | SHA-256 |
| --- | --- | ---: | --- | --- |
| 0 | `f2d68fb8-8acc-66be-f7d3-874f241a1ee5` | 21,152 | `4a8de932ee2a86de` | `ced46dbe2402e54882bf5aa88c183498ca03344a500a472900470c47fe0bfe76` |
| 1 | `b0ebc681-dfb7-988b-4fdc-cac2df64c71f` | 21,152 | `4e7733cf5da2e75a` | `933e6f863c1419a766d7fdb119403640944aebca12345305954f9fbe38ffebcd` |

The first payload decodes to `[0, 2, 4, ... 10574]`; the second decodes to
`[1, 3, 5, ... 10575]`. Both arrays exactly match their source USDA
`GeomSubset.indices` values. They are disjoint, in range, and their union is
exactly every face ordinal from 0 through 10,575. Each filename suffix also
equals the existing build-80 `buffer_content_hash(payload)` result.

This proves that the subset payload is not an opaque buffer we need to invent:
for this controlled case it is a directly reproducible encoding of authored
USD face membership. It does not yet prove how RCP represents unassigned,
overlapping, empty, or non-partitioned subsets.

## Required writer changes

Supporting this representation cleanly requires coordinated changes rather
than adding a second material reference to the current split model:

1. Retain one in-memory mesh per USD mesh prim. Store ordered material slots
   and face subsets beside it instead of cloning topology, attributes, and
   skinning per material.
2. Parse material-binding `GeomSubset` face indices while retaining the full
   mesh topology once. Fail on out-of-range indices, overlap, unsupported
   subset families, unsupported hierarchy, or an unmeasured coverage rule.
3. Write one mesh descriptor with a `subsets` array. For every accepted
   subset, write one deterministic UUID and one content-hashed, little-endian
   32-bit face-index buffer.
4. Write one geometry, one mesh resource model, one model component, and one
   skinning component per source mesh. Do not multiply skeleton/timeline
   resources by the material count.
5. Keep one material/texture record per actual material and emit the model
   component's material array in exactly the same slot order as the descriptor
   subsets.
6. Give subset records and buffers deterministic, namespaced identities so a
   repeat generation is byte/contract stable without borrowing captured UUIDs.
7. Apply the same representation to optimizer input. A source mesh must remain
   one model with material slots, not several material-partition models.

The static and skinned paths should share this subset model; skinning remains
an orthogonal descriptor block.

## Fail-closed boundary

The writer must continue rejecting cases not established by the corpus:

- unassigned faces or a default material outside a `GeomSubset`;
- non-exhaustive or overlapping subsets;
- empty subsets;
- three or more material slots;
- reordered/sparse material slots;
- multiple subsets bound to one shared material;
- shared materials across multiple mesh prims;
- large face counts that may change index width or limits;
- different subset families or interpolation semantics;
- any RCP build other than `80.0.1.500.1`.

These are research lanes, not reasons to silently approximate the package.

## Acceptance plan

Implementation is supportable as a staging experiment now that the two-slot
payload and graph shape are measured. Compatibility is not supportable until a
new generated package passes all of these gates:

1. deterministic generation and structural inspection with no unknown fields
   or derived/unknown buffer suffixes;
2. clean import, save, close, and reopen in a fresh disposable RCP project;
3. two genuine **Editor > Reimport** cycles with no record/buffer growth and
   equal canonical structure, contract, and opaque-payload multisets;
4. visual confirmation that both face materials remain assigned;
5. `realitytool` compilation and public RealityKit bounds, material,
   deformation, and animation-library checks;
6. Sequence Editor clip visibility and playback for the animated skeletal
   fixture.

After the two-material static and skinned lanes pass, add separate controlled
fixtures for three materials, unassigned faces, shared materials, slot
reordering, and multiple multi-material meshes. Any RCP build change starts a
new versioned corpus lane.
