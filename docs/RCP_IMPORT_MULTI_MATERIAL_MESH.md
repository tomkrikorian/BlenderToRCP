# RCP `.import` multi-material mesh contract

This page records how Reality Composer Pro represents one mesh carrying
multiple face materials inside an `.import` package, how it binds those
materials to faces, and what the experimental writer must author to match.
It describes only the controlled two-material fixtures — a skinned Robot
body mesh and a static cube — and is deliberately build-pinned. Read
[RCP_IMPORT_EXPERIMENT.md](RCP_IMPORT_EXPERIMENT.md) first for the lane
overview and for the definitions of record, buffer, reimport, and
canonicalization.

*Applies to: Reality Composer Pro 3.0, build `80.0.1.500.1`.*

Status: the writer authors the full binding contract below, and a
two-material static mesh loads in Reality Composer Pro and renders both
materials on the correct faces. Rendering is not acceptance. The remaining
Reality Composer Pro gate — save and reopen — has not been run, so writer
support is **not accepted**. Reimport is out of scope; see
[Reimport is not supported for generated packages](RCP_IMPORT_EXPERIMENT.md#reimport-is-not-supported-for-generated-packages).

## Why the previous split representation was insufficient

The earlier experiment turned each material-bound `GeomSubset` into an
independent generated mesh resource. That package:

- opens, saves, closes, and reopens in Reality Composer Pro;
- compiles with `realitytool` and loads through public RealityKit;
- preserves both materials in the generated/runtime artifact;
- completes one genuine RCP reimport without resource growth.

Reality Composer Pro's own reimport of it authored a different
multi-material mesh shape, and the package grew from 83 records/139 buffers
after the first reimport to 147 records/306 buffers after the second. RCP retains the split resources, creates duplicate source
resources, and adds its own combined mesh representation. A rendering
success is therefore not proof that the generated resource graph matches
RCP's private contract. That split path has been removed from the writer.

One schema-legal field is deliberately not written: `material_bindings`.
Its shape is pinned by the type index, but no local capture contains one —
RCP's own reimport of the Robot fixture authored only `subsets` — and
matching the measured output beats schema-legal guessing.

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
subsets. In the observed two-slot case, slot 0 omits `index`; slot 1
explicitly stores `index: 1`. This is evidence for those two slots only, not
a general default-material or arbitrary-slot rule. That `index` is the
binding key, not a label; see
[How Reality Composer Pro binds materials to faces](#how-reality-composer-pro-binds-materials-to-faces).

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

This proves that the subset payload is not an opaque buffer that must be
invented: for this controlled case it is a directly reproducible encoding of
authored USD face membership. It does not yet prove how RCP represents
unassigned, overlapping, empty, or non-partitioned subsets.

## Canonical schema (from the shipped type index)

The app's own Truth schema (`__type_index.tm_meta`, see
[RCP_IMPORT_EXPERIMENT.md](RCP_IMPORT_EXPERIMENT.md) and
`scripts/_lib/rcp_type_index.py`) settles the record shapes the observations
above were reverse-measuring, and
`tests/unit/test_rcp_contract_matches_type_index.py` pins them as the writer
specification:

- `tm_mesh_descriptor.subsets` is a **subobject_set** of
  `tm_mesh_descriptor_subset` = `{name (string), index (uint32),
  face_indices (buffer), face_count (uint32)}` — matching the measured
  records, including `index` being an ordinary defaulted uint32 (slot 0's
  omitted `index` is the serializer eliding a default-valued property, not a
  special two-slot rule).
- `tm_mesh_descriptor.material_bindings` is a **singular subobject** of
  `tm_mesh_descriptor_material_binding` = `{mesh_material_index (uint32),
  subset_to_material_index (buffer), subset_count (uint32)}` — one binding
  object per descriptor whose buffer maps subset ordinal to material index.
  Reality Composer Pro does not author it, and it is not the binding the
  renderer uses; see
  [How Reality Composer Pro binds materials to faces](#how-reality-composer-pro-binds-materials-to-faces).
- `tm_mesh_descriptor.winding_order` is a defaulted uint32 the writer has
  never needed to author.

Schema legality is necessary, not sufficient: buffer payload encodings
beyond the measured face-ordinal arrays, and RCP's behavior for the
unmeasured subset cases listed above, still require controlled fixtures and
the acceptance gates below.

## How Reality Composer Pro binds materials to faces

A multi-material mesh binds through three separate representations. All
three must agree. Authoring one or two of them correctly is not enough: the
package still loads, and every face still draws the same material.

| Layer | Where it lives | What it holds | Who reads it |
| --- | --- | --- | --- |
| Authoring truth | `tm_mesh_descriptor.subsets` | face ordinals per material | no draw path reads it |
| Slot mapping | the model component's `materials` array | one `index` per entry | binds a subset to a material |
| Render ranges | `tm_geometry.subsets` | contiguous ranges of the triangle index stream | the renderer |

### The descriptor subsets are the authoring-side truth

`tm_mesh_descriptor` is the retained pre-processing mesh, not the mesh that
draws. Its only inbound reference is the `retain_original_mesh` input on
`transform_settings`. Each `subsets` entry lists the face ordinals assigned
to one material, in source face order. The measured record shape is under
[Subset records](#subset-records) above.

### The materials array carries the slot number

Every entry of the model component's `materials` array has an `index`
property. Reality Composer Pro binds a subset to the entry whose `index`
equals the subset's `index`. **Array order alone is not the mapping.**

Slot 0 elides `index`, because the serializer omits default values. Every
later slot writes it: `index: 1`, `index: 2`, and so on. If every entry
elides `index`, all entries claim slot 0 and the last one wins.

### The geometry subsets are what the renderer draws

`tm_geometry` carries its own `subsets` array, present in both
`input_geometry` and `output_geometry`. Each entry is a contiguous range of
the triangle index stream. This is the representation the render path
consumes. It never draws from the descriptor's face ordinals.

`tm_geometry_subset` has four properties:

| Property | Type | Meaning |
| --- | --- | --- |
| `name` | string | The material display name. Not a prim path — full prim paths are the descriptor subset's convention. |
| `index` | uint32 | The material slot. Elided on slot 0. |
| `offset` | uint32 | A **byte** offset into the index buffer. Elided on slot 0. |
| `count` | uint32 | A **number of indices**. Not triangles, not bytes. |

### Index stream order

Reality Composer Pro sorts the triangle index stream by subset so that each
range is contiguous: all of subset 0's triangles, then all of subset 1's, in
slot order. Only the index buffer is permuted. Vertex and corner data stays
in original face-corner order.

Within one subset:

- faces appear in ascending source order;
- each triangle keeps its original corner order.

This holds for interleaved subsets too. A mesh whose subset 0 covers faces
0–43 and 120–339, and whose subset 1 covers faces 44–119 and 340–547, still
produces exactly two contiguous ranges.

### Index width

Reality Composer Pro uses 32-bit triangle indices whenever a geometry
carries subsets. Subset presence selects the width, not mesh size:

| Index block | Stride | `format` | Measured in RCP-authored packages |
| --- | ---: | ---: | --- |
| 32-bit | 4 | 67108896 | 8 of 8 carry subsets |
| 16-bit | 2 | 67108880 | 440 of 440 are subset-free |

The smallest subset-bearing block has 438 vertices and 1,644 indices, far
under the 16-bit limit. A small multi-material mesh still gets 32-bit
indices.

### Subset limit

One geometry carries at most 128 subsets. Past that, Reality Composer Pro
reports `Too many subsets!`.

### Vertex channel semantics

A geometry channel declares what it carries with a `semantic` value:

| Value | Semantic |
| ---: | --- |
| 0 | none |
| 1 | position |
| 2 | normal |
| 3 | tangent |
| 4 | binormal |
| 5 | texcoord |
| 6 | color |
| 7 | joint indices |
| 8 | joint weights |
| 9 | index |
| 10 | position deltas |
| 11 | vector deltas |
| 12 | cluster local-to-global index LUT |
| 13 | cluster local indices |
| 14 | skin data |

The enum has no per-vertex and no per-face material index. A subset range is
the only mechanism Reality Composer Pro has for drawing different materials
on different faces of one mesh.

Semantic 14 is packed, one uint32 per vertex:
`(influence_table_offset << 5) | influence_count`.

### Channel format words

A channel's `format` is a packed word. Its low byte is the component bit
width; its high byte is the type class.

| Value | Meaning | Stride |
| ---: | --- | ---: |
| 67108880 | uint16 index | 2 |
| 67108896 | uint32 index | 4 |
| 83886112 | uint32 primvar index array | 4 |
| 16779296 | float2 | 8 |
| 16910368 | float3 | 12 |
| 25298976 | float4 | 16 |

`tm_geometry_channel` also has a `set` property (uint32, default 0) that
distinguishes several channels sharing one semantic. Reality Composer Pro
omits it when it is zero, and the writer does not need to author it.

### Output geometry is a shape-only cache

`output_geometry` describes the post-processed shape. Its buffer entries
carry no payload reference. Reality Composer Pro records the **post-weld**
vertex count there, while the index count and every subset's `offset` and
`count` stay identical to `input_geometry`. Subset ranges are invariant
across welding and vertex-cache optimization.

`validity_hash` on `tm_geometry` is content-derived, not a constant.

### Entity hierarchy binds nothing

Reality Composer Pro preserves the USD `Xform` → `Mesh` hierarchy as two
entities: the object's Xform entity, and a child entity named after the
`Mesh` prim that carries the model component. Entity names and paths play no
part in material binding. The chain from subset to material is entirely by
UUID.

## Buffer naming

Two different rules apply, depending on where the buffer lives. Both produce
a hex suffix that follows the buffer's UUID in the filename. `murmur64a` is
the MurmurHash64A variant described under buffer filenames in
[RCP_IMPORT_EXPERIMENT.md](RCP_IMPORT_EXPERIMENT.md).

### Content-addressed buffers

Buffers under `mesh_descriptors/*.tm_buffers`, `settings.tm_buffers`, and
the texture buffer directories are named from their own payload:

```
suffix = murmur64a(payload, seed 0)
```

### Geometry buffers

Buffers under `geometry/*.tm_buffers` are **not** content-addressed
individually. Reality Composer Pro chains every non-empty slot of one
geometry, in ascending slot order, feeding each result in as the next seed.
Slot 0 takes the final chain value. Every later slot takes the hash of the
chain paired with its own slot number:

```
chain = 0
for payload in slots:          # ascending slot order
    if payload:                # empty slots do not contribute
        chain = murmur64a(payload, seed=chain)

suffix(0) = chain
suffix(i) = murmur64a(pack_le_uint64(chain, i))    # for i > 0
```

`pack_le_uint64(a, b)` is the two values written as little-endian uint64s,
16 bytes in total.

The slot number is the `index:` property on the matching entry of
`input_geometry.buffers`. An absent `index` means slot 0.

Because the chain covers the whole geometry, no geometry buffer's name can
be computed in isolation. Change any slot's payload and every slot's
filename changes.

### Suffix formatting

Reality Composer Pro formats the hash with `%llx`. The suffix is lowercase
and **not** zero-padded. A value whose leading nibble is zero has 15 hex
digits, not 16.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| The mesh loads, but every face draws one material. | The model component's `materials` entries all elide `index`, so every entry claims slot 0. |
| The descriptor subsets and the material indices are correct, but every face draws slot 0's material. | `tm_geometry` carries no `subsets` array. The renderer reads geometry ranges, not descriptor face ordinals. |
| The mesh does not render, and the console reports `Bad position chanel`, `Channel with semantic: 1 and set: 0 not found in geometry`, `<material>: Vertex buffer missing for geometry subset!`, and `Index access out of bounds`. | The geometry buffer filenames were computed with the content-hash rule instead of the chain rule, so Reality Composer Pro cannot resolve the vertex buffer. |

None of those four messages names the real cause. The geometry payloads can
be byte-identical to Reality Composer Pro's own import of the same source;
only the filenames differ. Check the geometry buffer names first. `Bad
position chanel` is Reality Composer Pro's own spelling.

## Writer representation (implemented)

Supporting this representation cleanly required coordinated changes rather
than adding a second material reference to the old split model. The writer
implements all ten:

1. Retain one in-memory mesh per USD mesh prim. Store ordered material slots
   and face subsets beside it instead of cloning topology, attributes, and
   skinning per material.
2. Parse material-binding `GeomSubset` face indices while retaining the full
   mesh topology once. Fail on out-of-range indices, overlap, unsupported
   subset families, unsupported hierarchy, or an unmeasured coverage rule.
3. Write one mesh descriptor with a `subsets` array. For every accepted
   subset, write one deterministic UUID and one content-hashed,
   little-endian 32-bit face-index buffer.
4. Write one geometry, one mesh resource model, one model component, and one
   skinning component per source mesh. Do not multiply skeleton/timeline
   resources by the material count.
5. Keep one material/texture record per actual material and emit the model
   component's material array in exactly the same slot order as the
   descriptor subsets, with each entry's slot number on its `index`
   property. Slot 0 keeps eliding the default.
6. Give subset records and buffers deterministic, namespaced identities so a
   repeat generation is byte/contract stable without borrowing captured
   UUIDs.
7. Apply the same representation to optimizer input. A source mesh must
   remain one model with material slots, not several material-partition
   models.
8. Write the triangle index stream subset-sorted for multi-slot meshes, and
   author the matching range table in both `input_geometry.subsets` and
   `output_geometry.subsets`. Single-slot meshes keep the plain face-order
   stream and no subsets block.
9. Derive the index stride from subset presence, not from the corner count:
   4 bytes whenever the geometry carries subsets. One helper feeds both the
   buffer packer and the record so the two cannot drift.
10. Name `geometry/` buffers with the cross-slot chain rule and every other
    buffer with the plain content hash. Format both with `%llx`, without
    zero padding.

The static and skinned paths should share this subset model; skinning
remains an orthogonal descriptor block.

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
payload and graph shape are measured. Compatibility is not supportable until
a new generated package passes all of these gates:

1. deterministic generation and structural inspection with no unknown fields
   or derived/unknown buffer suffixes;
2. clean import, save, close, and reopen in a fresh disposable RCP project;
3. a re-export from Blender over the imported package, with the project open
   in Reality Composer Pro, producing no record or buffer growth and equal
   canonical structure, contract, and opaque-payload multisets.

   This replaces an earlier two-reimport gate. **Editor > Reimport** cannot
   pass and is out of scope: Reality Composer Pro tracks generated records in
   a session buffer this writer does not author, so every reimport creates a
   duplicate record set. See
   [Reimport is not supported for generated packages](RCP_IMPORT_EXPERIMENT.md#reimport-is-not-supported-for-generated-packages).
   Re-export is the supported refresh path, so it is the path acceptance
   measures;
4. visual confirmation that both face materials remain assigned;
5. `realitytool` compilation and public RealityKit bounds, material,
   deformation, and animation-library checks;
6. Sequence Editor clip visibility and playback for the animated skeletal
   fixture.

The controlled static two-material fixture imports cleanly and passes gate
4: both materials render on their assigned faces. Gate 2 (save and reopen)
and gate 3 (re-export refresh) are the remaining bar.

After the two-material static and skinned lanes pass, add separate
controlled fixtures for three materials, unassigned faces, shared materials,
slot reordering, and multiple multi-material meshes. Any RCP build change
starts a new versioned corpus lane.

## Verification

The measurements come from the preserved second-reimport capture of the
disposable Robot acceptance project; see
[the skeletal checkpoint](RCP_IMPORT_SKELETAL_CHECKPOINT.md) for the
capture locations. The canonical schema is pinned by
`tests/unit/test_rcp_contract_matches_type_index.py` against the shipped
`__type_index.tm_meta`, parsed by `scripts/_lib/rcp_type_index.py`.

The binding contract, buffer-naming rules, subset limit, semantic values,
and format words come from the shipped Reality Composer Pro 3.0 (build
`80.0.1.500.1`) binaries — `libtm-geometry` and `CoreRealityTools` — and
from importing the same source USD through Reality Composer Pro and
comparing its package against the generated one. The rendering result is a
live check of a generated two-material static mesh in that build.
`tests/unit/test_rcp_import_generator.py` pins the geometry subset ranges,
the index stride and format words, and the per-entry material `index`.
`scripts/_lib/rcp_import_format.py` implements both buffer-naming rules, and
`scripts/inspect_rcp_import.py` checks generated geometry filenames against
the chain rule.
