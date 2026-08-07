# Export pipeline

This page explains what happens to geometry, transforms, animation, and
packaging between pressing Export and getting a file. Read it to understand
what the exporter decides on your behalf, and why re-exporting to the same
path is safe.

*Applies to: Blender 5.2.0 LTS (`fbe6228777e7`).*

This page covers the structural half of the export. Material translation and
texture baking have their own documentation; textures appear here only where
they affect staging, publication, and packaging. See
[`ARCHITECTURE.MD`](ARCHITECTURE.MD) for the module map and [`CLI.md`](CLI.md)
for the setting keys and their defaults.

Source references such as `Plugin/export/blender_usd_export.py:109` are asides
for contributors; you do not need the source code to use this page. The
*Verification* notes at the end of sections record how the stated behavior was
confirmed against real exports with the Blender build above.

## Contents

1. [The Apple spatial contract](#1-the-apple-spatial-contract)
2. [Object selection and scope](#2-object-selection-and-scope)
3. [Geometry decisions](#3-geometry-decisions)
4. [Animation](#4-animation)
5. [Staging and publication](#5-staging-and-publication)
6. [Packaging](#6-packaging)
7. [Preflight and validation gates](#7-preflight-and-validation-gates)

## Pipeline order

Every export runs the same sequence, whether you start it from the sidebar,
the CLI, or the bake lane. The three entry points are the UI operator
(`Plugin/ops/export_operator.py:210`), the CLI `export` command
(`Plugin/api/commands/export.py:250`), and the bake lane
(`Plugin/api/commands/bake_export.py:574`).

Two terms recur throughout this page. *Staging* means assembling the export in
a private temporary directory. *Publication* means installing the finished
files into your output directory in an order that can never leave it
half-written.

| Step | Implementation | Notes |
|------|----------------|-------|
| Selection closure | `Plugin/export/animation_export.py:30` | Fails closed on an empty selected-only export |
| Material validation | `Plugin/nodes/validate.py` via `Plugin/api/commands/export.py:216` | Strict; blocks before any file is written |
| Staging directory | `Plugin/export/blender_usd_export.py:109` | `.blendertorcp_temp/<output>.<attempt>/` |
| Animation preparation | `Plugin/export/animation_export.py:156` | Concatenates takes onto one NLA track and bakes |
| Native USD export | `Plugin/export/blender_usd_export.py:319` | `bpy.ops.wm.usd_export` with a fixed contract |
| Post-processing | `Plugin/export/postprocess_usd.py:22` | Localize, normalize, rewrite materials, preflight |
| Package or publish | `Plugin/export/pack_usdz.py:66` / `Plugin/export/blender_usd_export.py:359` | USDZ archive, or transactional publication |
| Staging cleanup | `Plugin/export/blender_usd_export.py:501` | Runs from `finally`, success or failure |

---

## 1. The Apple spatial contract

Every export is Y-up, faces `-Z` forward, and is scaled in meters. Four stage
properties are **not** export options: they are constants in
`Plugin/apple_contract.py` and are written into every export regardless of
your scene or settings.

| Constant | Value | `Plugin/apple_contract.py` |
|----------|-------|-----------------------------|
| `REALITYKIT_FORWARD_AXIS` | `-Z` | line 6 |
| `REALITYKIT_USD_EXPORT_FORWARD_AXIS` | `NEGATIVE_Z` | line 7 |
| `REALITYKIT_UP_AXIS` | `Y` | line 8 |
| `REALITYKIT_SCENE_UNITS` | `METERS` | line 9 |
| `REALITYKIT_METERS_PER_UNIT` | `1.0` | line 10 |

The constants reach Blender's exporter through `_build_export_kwargs`, which
hard-codes `convert_orientation=True`
(`Plugin/export/blender_usd_export.py:1146`), the forward and up axes
(`:1147`, `:1148`), `convert_scene_units` (`:1175`), and `meters_per_unit`
(`:1176`). Unlike every neighboring key, none of those five lines reads from
`settings`. Post-processing re-asserts the up axis on the composed stage
(`Plugin/export/usd_scene.py:54`). Preflight — the exporter's final validation
pass over the composed USD stage — fails the export if either the up axis or
`metersPerUnit` deviates (`Plugin/export/realitykit_preflight.py:775-812`).

The orientation conversion is applied as an authored transform on the export
root prim. Vertex data is not rewritten.

*Verification: a Z-up Blender scene exported to `.usda` produced a stage
header of `metersPerUnit = 1`, `upAxis = "Y"`, and a root prim carrying
`float3 xformOp:rotateXYZ = (-90, -0, 0)` with
`xformOpOrder = ["xformOp:rotateXYZ"]`.*

### What this means for a scene authored in other units

**One Blender unit always becomes one meter.** The pipeline never reads
`scene.unit_settings.scale_length`. Blender 5.2's `convert_scene_units` enum
can express `CENTIMETERS`, `MILLIMETERS`, `INCHES`, `FEET`, `YARDS`, or a
`CUSTOM` value — the exporter uses that enum to declare the stage's
`metersPerUnit`, not to rescale points — and BlenderToRCP pins it to
`METERS`/`1.0` (`Plugin/export/blender_usd_export.py:1175-1176`).

The practical consequence: if you set Blender's Unit Scale to `0.01` and model
something you read as "2 cm wide" in the sidebar, the exported asset is 2
meters wide in RealityKit. Nothing warns you.

**This is a deliberate decision made on your behalf.** RealityKit and Reality
Composer Pro assets are Y-up, `-Z`-forward, and meter-scaled, and an asset
that declares anything else is not portable. Authoring at a non-`1.0` unit
scale is a workflow the pipeline does not support. What to do: apply the scale
to your objects, or model at 1 unit = 1 meter.

*Verification: the same 2-Blender-unit cube was exported twice, from a scene
with `unit_settings.scale_length = 1.0` and from one with
`scale_length = 0.01`. Both outputs were byte-identical in the relevant
respects: `metersPerUnit = 1` and
`float3[] extent = [(-1, -1, -1), (1, 1, 1)]`. The scene unit scale had no
effect.*

---

## 2. Object selection and scope

### Scene vs. selection

`selected_objects_only` (default `false`, `Plugin/ui/panel.py:209-214`)
chooses between two scopes, both computed by `collect_export_objects`
(`Plugin/export/animation_export.py:30`):

- **Whole scene** — every object in `context.scene.objects` that passes the
  object-class filter (`Plugin/export/animation_export.py:48-51`).
- **Selection only** — every object in `context.selected_objects` that passes
  the same filter (`Plugin/export/animation_export.py:53-57`).

An empty selected-only scope is never silently widened to the whole scene.
`prepare_animation_export` raises
(`Plugin/export/animation_export.py:167-171`), and callers convert that to a
`NO_EXPORTABLE_OBJECTS` failure before anything is written
(`Plugin/api/commands/export.py:201-208`,
`Plugin/ops/export_operator.py:154-162`).

*Verification: exporting a scene with nothing selected and `--selected-only`
returned `{"ok": false, "error": {"code": "NO_EXPORTABLE_OBJECTS", "stage":
"validation"}}` and produced no output file.*

### Dependency closure

The exporter computes two closures, and they are deliberately different.

**Export closure** (`collect_export_objects`,
`Plugin/export/animation_export.py:30`) is what gets *selected* for Blender's
operator. It adds exactly one dependency to your selection: the deforming
armature of a selected skinned mesh, and only when `export_armatures` is on
and the Armature modifier is enabled in the active evaluation mode
(`Plugin/export/animation_export.py:77-97`). A skinned mesh with an enabled
Armature modifier whose `object` is `None` is a hard error rather than an
orphaned `SkelBinding` (`:93-96`).

Parents and collection-instance prototypes are **not** added. Blender's own
`selected_objects_only` already weak-exports parent transform chains and
expands collection instances without selecting the prototypes. Adding them
would change semantics — exporting parent geometry you did not select, or
duplicating prototype objects instead of instancing them. The docstring at
`Plugin/export/animation_export.py:32-45` records this rationale.

**Processing closure** (`collect_processing_objects`,
`Plugin/export/animation_export.py:110`) is a superset used only for
animation preparation and validation. It walks the full parent chain and
every `instance_collection` prototype transitively (`:132-147`). Animated
prototypes that are not linked into the active scene are temporarily linked
so `bpy.ops.nla.bake` can evaluate them
(`Plugin/export/animation_export.py:1211-1230`) and unlinked afterwards
(`:1233-1243`).

Both closures return objects in scene order for determinism, with any closure
member not in the scene appended afterwards (`:103-107`, `:149-153`).

### What is silently excluded

`_is_exportable_object` (`Plugin/export/animation_export.py:662`) is the
object-class filter:

| Object type | Exported | Where |
|-------------|----------|-------|
| `MESH` | if `export_meshes`, or if it carries an enabled Armature modifier and `export_armatures` is on | `:677-684` |
| `ARMATURE` | if `export_armatures` (default `true`) | `:675` |
| `EMPTY` | always — Empties are real USD Xforms and collection-instance roots | `:687-690` |
| `LIGHT`, `CAMERA` | never | `:667-668` |
| `CURVE`, `CURVES`, `POINTCLOUD`, `VOLUME` | never | `:669-674` |
| anything else | never | `:690` |

The corresponding native exporter flags are hard-disabled too —
`export_lights`, `export_cameras`, `export_curves`, `export_points`,
`export_volumes` at `Plugin/export/blender_usd_export.py:1166-1170` and
`export_hair` at `:1132`. These are policy constants with no settings lookup:
RealityKit and RCP 3 do not import those schemas, so admitting them would
produce an export that fails composed-stage preflight instead of failing
early.

Exclusion is silent. No warning is emitted for a camera, light, or curve that
was dropped.

**Visibility.** BlenderToRCP does not filter on `hide_viewport` or
`hide_render` itself. That is Blender's exporter behavior under the chosen
`evaluation_mode` (`RENDER` by default,
`Plugin/export/blender_usd_export.py:1143`).

*Verification: a probe scene containing a mesh with
`hide_viewport = hide_render = True`, a camera, and a point light exported
none of the three. The resulting `.usda` contained only the visible meshes,
their materials, and the instance prototypes.*

---

## 3. Geometry decisions

### Root prim

`root_prim_name` (default `/root`, `Plugin/ui/panel.py:184-189`) is
normalized to a leading-slash path
(`Plugin/export/blender_usd_export.py:280-281`) and passed as
`root_prim_path` (`:1153`). Post-processing guarantees the stage has a
`defaultPrim` pointing at a root-level prim, creating an `Xform` if the
exporter did not (`Plugin/export/usd_scene.py:45-50`). A nested path such as
`a/b` cannot be a `defaultPrim` token, so `_root_identifier` collapses
separators to underscores (`Plugin/export/usd_scene.py:264-270`).

Preflight rejects a missing `defaultPrim` (`DEFAULT_PRIM_MISSING`) or one
that is not at root level (`DEFAULT_PRIM_NOT_ROOT`) —
`Plugin/export/realitykit_preflight.py:760-773`.

### Triangulation

`triangulate_meshes` defaults to **`false`** (`Plugin/ui/panel.py:308-313`,
forwarded at `Plugin/export/blender_usd_export.py:1171`). N-gons are exported
as n-gons unless you turn it on.

When you enable it:

- `quad_method` (default `SHORTEST_DIAGONAL`) is passed through unchanged
  (`Plugin/export/blender_usd_export.py:1172`).
- `ngon_method` is **translated**. The UI offers `BEAUTY` and `EAR_CLIP`
  (`Plugin/ui/panel.py:332-335`), but Blender's USD operator only accepts
  `BEAUTY` and `CLIP`. `_ngon_method_for_usd_export`
  (`Plugin/export/blender_usd_export.py:67`) maps `EAR_CLIP` → `CLIP`
  (`:76-77`, `:81-82`), accepts either valid value verbatim (`:74-75`),
  upper-cases a lower-case spelling (`:78-80`), and passes anything else
  through unchanged so the operator raises a precise error rather than being
  silently defaulted (`:83`).

*Verification: a hexagonal n-gon exported with `triangulate_meshes=true
ngon_method=EAR_CLIP` produced `int[] faceVertexCounts = [3, 3, 3, 3]`. The
same mesh with default settings produced `int[] faceVertexCounts = [6]`.*

### Subdivision

`export_subdivision` defaults to `BEST_MATCH`
(`Plugin/export/blender_usd_export.py:1138`), which authors a USD subdivision
scheme when the Blender modifier maps cleanly. Preflight requires
`subdivisionScheme` to be explicitly authored — an unauthored value silently
means `catmullClark` in USD — and errors with
`SUBDIVISION_SCHEME_UNAUTHORED` otherwise
(`Plugin/export/realitykit_preflight.py:872-879`). Any scheme other than
`none` produces a `SUBDIVISION_RUNTIME_COST` warning (`:890-897`).

### Instancing

`use_instancing` defaults to **`true`** (`Plugin/ui/panel.py:372-377`,
forwarded at `Plugin/export/blender_usd_export.py:1142`). This inverts
Blender's own operator default, which is `False`.

With it on, a collection instance becomes an `instanceable = true` Xform
carrying a `references` arc to an abstract prototype class under the root
prim, rather than a duplicated mesh. For example, two `COLLECTION`-instance
Empties pointing at one prototype collection export as:

```usda
def Xform "ProtoCube_0" (
    instanceable = true
    prepend references = </root/prototypes/ProtoCube>
)
```

…twice, alongside a single `class "prototypes"` subtree holding one
`Mesh "Cube"`. The mesh data appears once.

The abstract `class "prototypes"` tree matters for post-processing: it is not
reachable through an ordinary composed-stage traversal, which is why
normalization walks raw `Sdf` specs on the output-owned layers instead
(`Plugin/export/usd_scene.py:85-96`).

*Verification: the instancing example above is the recorded output of a real
export of two collection-instance Empties sharing one prototype collection.*

### Transforms

`xform_op_mode` (default `TRS`, `Plugin/ui/panel.py:278-284`) selects between
translate/rotate/scale, translate/orient/scale, and a single matrix op; it is
forwarded at `Plugin/export/blender_usd_export.py:1152`. `merge_parent_xform`
(default `false`) folds parent transforms into geometry (`:1174`).

### Prim naming and sanitization

Blender authors prim names from object and datablock names. Post-processing
then repairs any name that is not a valid USD identifier, in
`_rename_invalid_prims` (`Plugin/export/usd_scene.py:273`).

The algorithm:

1. Collect every prim in the stage — including inactive and undefined ones,
   via `TraverseAll` — whose name fails `Sdf.Path.IsValidIdentifier`
   (`Plugin/export/usd_scene.py:296-300`, validity test at `:524-533`).
2. Process one namespace depth at a time, shallowest first (`:304-307`).
   Moving a parent first carries its whole subtree with it; the next pass
   then sees descendants at their new paths.
3. Sanitize each name with `_make_valid_identifier` (`:503`). Every character
   that is neither `_` nor alphanumeric becomes `_` (`:507-511`); an empty
   result becomes `prim` (`:512-513`); a name that does not start with a
   letter or underscore is prefixed with `prim_` (`:514-516`). With
   `allow_unicode=false` (default is `true`, `Plugin/ui/panel.py:237-242`)
   the filter is restricted to ASCII (`:511`, `:518-520`).
4. Allocate the new name against both existing siblings and destinations
   already reserved in the same batch, appending `_2`, `_3`, … on collision
   (`:494-500`, `:311-327`).
5. Apply the moves as an `Sdf.BatchNamespaceEdit` per contributing layer
   (`:350`). Unlike recreating a prim, a namespace edit preserves
   descendants, attributes, metadata, variants, relationships, and time
   samples.

Two safety properties are worth calling out. Renames are refused on layers
outside the localization allowlist (`Plugin/export/usd_scene.py:380-384`),
and a prim that exists *only* by virtue of an external composition arc cannot
be renamed at all — the export fails with "Cannot safely rename prims
authored only by external composition arcs" (`:394-400`). Because
`Sdf.Layer.Apply` does not update paths stored in *other* specs, composed
relationship targets and shader connections are captured before the edit
(`:426`) and retargeted afterwards (`:456`), and the `defaultPrim` is
re-pointed (`:336-345`).

*Verification: an object named `My Object! 1` exported as
`def Xform "My_Object__1"` — space, `!`, and space each replaced by `_`. The
original name survives as
`custom string userProperties:blender:object_name = "My Object! 1"`, authored
because `export_custom_properties` defaults to `true`
(`Plugin/export/blender_usd_export.py:1121`, `:1154-1155`).*

### Mesh repair and the double-sided contract

Two mesh-level normalizations run after renaming.

`_repair_xform_mesh_prims` (`Plugin/export/usd_scene.py:536`) re-types a prim
to `Mesh` when Blender emitted mesh schema attributes onto an `Xform`. The
signature is the presence of `faceVertexCounts`, `faceVertexIndices`, and
`points` (`:551-556`); Reality Composer Pro would not treat such a prim as
geometry otherwise.

`_normalize_owned_double_sided_mesh_specs`
(`Plugin/export/usd_scene.py:73`) authors `doubleSided = false` on every Mesh
spec in an output-owned layer. Blender 5.2 authors `doubleSided = true`,
which the portable Apple OS 27 renderer profile does not support. The pass is
a raw `Sdf` spec edit rather than a composed `UsdGeom.Mesh` set, for two
reasons stated at `:80-88`: a composed edit would create a stronger
root-layer override for geometry owned by an external reference, and it
cannot see inactive variants. Layers outside the localization allowlist are
never opened for editing, so a surviving external `true` opinion stays
visible to preflight and fails the export there (`:88-93`). A malformed
non-boolean `doubleSided` opinion is a hard error rather than a silent
replacement (`:178-186`). The pass runs twice — once after localization
(`Plugin/export/postprocess_usd.py:47-55`) and once over the authoritative
final asset set (`:88-95`) — and warns once per affected owner
(`Plugin/export/usd_scene.py:234-241`).

*Verification: every exported `Mesh` carried
`uniform bool doubleSided = 0`.*

---

## 4. Animation

Animation export is off by default (`export_animation`,
`Plugin/ui/panel.py:192-197`). When off, `prepare_animation_export` still
runs — it computes the selection closure and returns the state needed to
restore your selection transactionally after the operator finishes
(`Plugin/export/animation_export.py:176-183`).

### What counts as an animated take

`_collect_targets` (`Plugin/export/animation_export.py:445`) produces one
target per animated owner, in three kinds:

- `ARMATURE` — the armature object (`:452-464`).
- `OBJECT` — any other exportable object (`:465-477`).
- `SHAPEKEYS` — the mesh's `shape_keys` datablock, when `export_shapekeys` is
  on and the mesh has shape keys (`:479-492`, predicate at `:708-716`).

Ownership is resolved by `_action_bindings_for_owner`
(`Plugin/export/animation_export.py:497`). Blender 5.2 Actions are layered
and can hold multiple slots, and a slot is the ownership boundary — an Action
with an `OBCharacter` slot must not be broadcast to every object that happens
to have `id_type == OBJECT`. The function therefore collects only explicit
associations:

1. The owner's active Action and its `action_slot` (`:517-519`).
2. Every Action referenced by an NLA strip on the owner, with the strip's
   `action_slot` (`:520-524`).
3. Any Action slot whose `users()` include the owner (`:529-537`).

Each binding is validated (`_validate_action_binding`, `:571`): a slotless
Action is an error (`:575-578`), a slot must belong to its Action
(`:578-584`), the slot's `target_id_type` must match the owner (`:585-591`),
the slot must have F-Curves (`:593-597`), and every F-Curve `data_path` must
resolve against the owner (`:598-606`). An Action bound to two different
slots on the same owner is an error rather than an ambiguous guess
(`:542-550`). NLA tweak mode anywhere in scope fails the export (`:511-515`).

**A stashed Action is not exported.** In practice, path 3 above never fires
for a take that is neither active nor staged as an NLA strip. If you want a
take exported, assign it or put it in an NLA strip. The code comment at
`Plugin/export/animation_export.py:529-531` describes path 3 as covering
stashed takes; in Blender 5.2 it does not.

*Verification: a scene with three Actions on one object — `A_active`
assigned, `B_nla` in an NLA strip, `C_stashed` with only a fake user —
exported two takes. `C_stashed` was absent from the schedule and from the
clip list, with no warning. Probing Blender directly showed `slot.users()`
returning `['Cube']` for the first two and `[]` for the stashed one.*

### Concatenation and frame range

All collected Actions across all targets are sorted case-insensitively by
name (`Plugin/export/animation_export.py:347-353`) and laid end to end on a
single global timeline by `_build_schedule` (`:372`).

Each Action's source range comes from `_action_frame_range` (`:609`): an
explicit `use_frame_range` wins (`:610-612`); otherwise the union of the
F-Curve ranges across the Action's owner-bound slots (`:614-632`); otherwise
the Action's own `frame_range` (`:629-631`). A zero-length or negative range
is clamped to one frame with a warning (`:379-385`).

The schedule is quantized to integers. Each take gets
`bake_frame_count = ceil(source_length)` frame intervals starting at
`current`, so its final sample is at `current + bake_frame_count`, and the
next take starts on the *following* timecode (`:386-395`). This is the key
design point, stated at `:388-393`: Blender's NLA bake samples integer frames
only, so sharing one timecode between the previous take's final pose and the
next take's first pose would necessarily drop one of them. Giving each take a
distinct inclusive final sample retains both. When the source range is
fractional, NLA time-scales it onto the integer span and a warning records
the exact mapping (`:396-415`).

The scene frame range is then set to `1 .. total_frames` for the bake
(`:239-244`) and restored afterwards
(`Plugin/export/animation_export.py:285-289`).

*Verification: `A_active` (frames 1–10) and `B_nla` (frames 1–5) produced
segments `[start 1, end 10, exclusive 11]` and
`[start 11, end 15, exclusive 16]`, with a stage header of
`startTimeCode = 1`, `endTimeCode = 15`, `timeCodesPerSecond = 24`.*

### Baking

Each target is baked independently. The schedule for that target — only the
segments whose Action it is actually bound to (`_schedule_for_target`,
`Plugin/export/animation_export.py:356`) — is written as strips on a fresh,
uniquely named NLA track `__BlenderToRCP_Export__` (`:907`, name allocation
at `:1182-1188`). Assignment order matters in Blender 5.2:
`action_frame_start`/`action_frame_end` are set before
`frame_start`/`frame_end`, because changing the source range can rewrite
`frame_end` (`:939-950`). The export track is soloed and all others muted
(`:1002-1007`), then:

- Armatures: `bpy.ops.nla.bake` in Pose mode with
  `bake_types={"POSE", "OBJECT"}`, `visual_keying=True`, constraints and
  parents retained (`:1018-1057`).
- Objects: the same with `bake_types={"OBJECT"}` (`:1060-1094`).
- Shape keys: no operator. F-Curves are created per key block and sampled at
  every integer frame (`:1097-1130`). Key-block names are escaped with
  `bpy.utils.escape_identifier` — a shape key named `Eye "Blink"` would
  otherwise produce a data path that `fcurves.new()` accepts without
  validation, keyframes, and that resolves to nothing, exporting as a static
  value with no warning (`:1111-1115`).

When a target has more than one take, a warning explains that one baked USD
animation cannot represent a discontinuous hard cut without interpolation,
and recommends per-take assets (`:250-259`).

Everything is restored transactionally by `restore_animation_export`
(`Plugin/export/animation_export.py:278`): the export track is removed,
mute/solo flags are restored, the original Action *and its exact slot* are
reassigned (`:319-323`, `:882-905`), baked Actions are deleted (`:326-331`),
and animation data created for the bake is cleared (`:333-340`). Target state
is registered *before* the first NLA mutation so a mid-bake failure is still
recoverable (`Plugin/export/animation_export.py:742-744`).

### Skeletal and shape-key export

`export_armatures` (default `true`) and `only_deform_bones` (default
`false`) are forwarded at `Plugin/export/blender_usd_export.py:1139-1140`;
`export_shapekeys` (default `true`) at `:1141`. Blender authors
`SkelRoot` / `Skeleton` / `SkelAnimation` / `BlendShape` prims.

Preflight checks the result: `MULTIPLE_SKELETONS`,
`SKELETON_OUTSIDE_SKEL_ROOT`, `SKELETON_JOINTS_MISSING`,
`SKELETON_BINDING_INVALID`, `SKELETON_TARGET_INVALID`,
`SKEL_BINDING_API_MISSING`, and `SKINNING_PRIMVARS_INCOMPLETE`
(`Plugin/export/realitykit_preflight.py:1243`). Time-sampled mesh `points`
are a hard error — `VERTEX_ANIMATION_UNSUPPORTED` (`:862-870`) — so
vertex-cache style animation must be converted to shape keys or skinning.

*Verification: a UV sphere with one animated shape key exported as a
`SkelRoot` containing a `Mesh` with `SkelBindingAPI`, a
`BlendShape "Squash"`, and a `Skeleton` with a `SkelAnimation`.*

### The experimental RCP clip library

`author_animation_library` defaults to **`false`**
(`Plugin/ui/panel.py:199-207`). When you enable it together with
`export_animation`, `author_animation_library`
(`Plugin/export/usd_animation_library.py:17`) writes a minimal Reality
Composer Pro `AnimationLibrary` component under the default prim.

Structure:

- A `RealityKitComponent` prim named `AnimationLibrary` with
  `uniform token info:id = "RealityKit.AnimationLibrary"` (`:69-70`).
- One `RealityKitClipDefinition` child per source animation, named
  `Clip_<source name with spaces underscored>` (`:76-77`, naming at
  `:152-156`).
- `clipNames` — the schedule's segment names, deduplicated by appending a
  counter to repeats while the first occurrence keeps the base name (`:78`,
  `:88-100`).
- `sourceAnimationName` — always the constant
  `"default subtree animation"` (`:14`, `:126-137`). The reason: the
  component sits on the default prim, and RCP 3's *default subtree animation*
  covers that prim's own transform animation plus animation on descendants
  including UsdSkel, whereas *transform animation* is entity-local and
  compiles successfully but yields no named clips at runtime. No fallback or
  guessed source names are emitted, because RealityKit may try to compile
  every `RealityKitClipDefinition` and an orphan source can produce invalid
  `compiledanimationscene` assets (`:140-149`).
- `startTimes` — each segment's start expressed in **seconds from the stage
  start time**: `(start_frame - stage_start) / timeCodesPerSecond`
  (`:53-57`).

All attributes are authored non-custom and uniform to match RCP's own output
(`:103-111`). A previous library at the same path is removed first so
repeated exports do not accumulate clip definitions (`:62-67`), and disabling
the setting removes any existing library and warns (`:28-34`).

For example, two takes with `author_animation_library=true` produce:

```usda
def RealityKitComponent "AnimationLibrary"
{
    uniform token info:id = "RealityKit.AnimationLibrary"

    def RealityKitClipDefinition "Clip_default_subtree_animation"
    {
        uniform string[] clipNames = ["A_active", "B_nla"]
        uniform string sourceAnimationName = "default subtree animation"
        uniform double[] startTimes = [0, 0.4166666666666667]
    }
}
```

`0.41666…` is `(11 - 1) / 24`, matching the second segment's start frame at
24 fps.

**Known limitation: RCP 3 build `80.0.1.500.1` flattens this.**
[`README.md`](../README.md) (line 12) and [`CLI.md`](CLI.md) (lines 809–814)
both state that supported USD import on the pinned build recognizes the
`RealityKit.AnimationLibrary` schema but collapses the authored named clip
definitions to the aggregate animation. So the setting is editor metadata whose named clips do not survive
a round trip through RCP 3 build 80. It is opt-in for that reason. What to
do: for RealityKit runtime work, leave it off and trim or split the imported
animation resource in app code — the same guidance as
`Plugin/export/usd_animation_library.py:30-34` and
[`ARCHITECTURE.MD`](ARCHITECTURE.MD) (line 122).

*Verification: the example block above is the recorded output of a real
two-take export. The flattening was measured on Reality Composer Pro 3.0 (build
80.0.1.500.1): importing an asset whose source authored four named clips
produced a single timeline record rather than four clip definitions.*

*The same USD files loaded through public RealityKit 27 kept their clips — a
transform-animated source retained `GoBackward`, `GoDown`, `GoForward` and
`GoUp`; a skeletal source retained `Agree_Gesture`, `Running`, `Walking` and
`walking_2` along with its `MeshDeformerComponent` and `SkeletalPosesComponent`.
So the clips survive the format and the runtime; it is the editor's import that
flattens them.*

---

### Shape keys travel through the skeletal schema

Blender does not export an unrigged shape-keyed mesh as an unrigged mesh. Shape
keys reach USD through its skeletal schema, so a scene with **no armature** still
gets a `SkelRoot` wrapper and a synthesized `Skeleton`: one joint, identity bind
and rest transforms, and every vertex fully weighted to it. That skeleton deforms
nothing — it exists to carry the shapes.

Blender also names the shapes in the `SkelAnimation` when nothing animates them,
leaving the weights unauthored. Reality Composer Pro refuses such a file with
*Failed to import blend shape animation*, so the exporter clears that empty
declaration. The shapes themselves are untouched: they stay on the mesh's
`skel:blendShapes` and `skel:blendShapeTargets`, which is where Apple's own
shape-keyed assets carry them.

## 5. Staging and publication

### Exports are not byte-reproducible

Exporting the same unchanged `.blend` twice does not give you the same file.
Blender's USD exporter writes top-level prims in an order that varies between
runs: the prims and their values are identical, the order is not, so the bytes
and any checksum differ.

This matters if you put exports under version control or compare them by hash.
Diff the composed stage rather than the file — for example by opening both with
USD and walking the prims in sorted path order — or accept that every re-export
shows as changed.

*Verification: three consecutive exports of one unchanged scene of three
independent cubes produced two distinct SHA-256 values; the only difference was
the order of the top-level `Xform` prims.*


Nothing is ever written directly to the destination. This section explains
the machinery, because you will see the directories it leaves behind.

### The attempt directory

Every export allocates a private directory under the *output* directory:

```
<output dir>/.blendertorcp_temp/<portable output filename>.<32 hex chars>/
```

built by `get_export_staging_dir` (`Plugin/export/blender_usd_export.py:89`)
from the complete output filename (`:105`) and a `secrets.token_hex(16)`
attempt token (`:102`). The filename is passed through
`_portable_staging_output_name` (`:145`), which NFC-normalizes it, replaces
every non-alphanumeric character other than `-`, `_`, `.` with `_`, and
appends an 8-character SHA-256 digest when that substitution changed
anything (`:145-156`).

The rationale, recorded at `:94-100`: an earlier stem-only path let
`scene.usda` and `scene.usdc` share one directory, and a concurrent reset
could delete another process's in-flight export. Filename plus random token
makes the directory an **ownership handle** rather than global mutable state.

`create_export_staging_dir` (`:109`) creates it with a bare `mkdir()` — not
`exist_ok=True` — so a token collision or a pre-created unowned path raises
`FileExistsError` and is retried with a fresh token rather than reused or
reset (`:127-133`), up to 16 attempts (`:116`, `:140-142`).

Staging exists for a second reason too, stated at `:256-259`: it prevents
Blender's USD exporter from resolving relative texture paths against an
existing destination `textures/` directory and reusing stale sidecars from
previous exports.

**Path safety.** `_validate_export_staging_dir` (`:159`) rejects a parent
that is not literally named `.blendertorcp_temp` or a child whose name does
not match `.+\.[0-9a-f]{32}` (`:169-173`), refuses a symlinked temp root or
per-output directory (`:177-178`, `:188-189`), refuses non-directories
(`:183-184`, `:192-194`), and requires both to resolve inside the output
directory (`:185-186`, `:195-196`). Without these checks a symlink at either
level could redirect `mkdir`, `rmtree`, or the native exporter outside the
chosen output directory. `_validate_staging_matches_final` (`:204`)
additionally proves a caller-supplied directory belongs to the output it
claims (`:210-220`).

**Cleanup.** `cleanup_export_staging_dir` (`:466`) runs on the success path
from inside publish; `remove_export_staging_dir` (`:501`) is called from a
`finally` in all three entry points
(`Plugin/api/commands/export.py:337-348`,
`Plugin/ops/export_operator.py:300-312`,
`Plugin/api/commands/bake_export.py:782-791`) so the tree never lingers
after an early return or exception. It requires an exact attempt directory:
given only a final filename it refuses and warns
(`Plugin/export/blender_usd_export.py:517-525`), because several exports to
the same name may be in flight and deleting every matching child would
reintroduce the cross-process data-loss bug the attempt-scoped API prevents.
The `.blendertorcp_temp` root itself is `rmdir`'d only when empty, which is
a no-op while other exports still hold directories inside it (`:547-552`).

*Verification: a failing export left `miss/out.diagnostics.json` and nothing
else — no `.blendertorcp_temp` remained. A successful USDZ export recorded
its staging root in diagnostics as
`z1/.blendertorcp_temp/scene.usdz.d91ab901c7b1df6fdb52abf75415eca2/scene.usdc`,
matching the documented shape.*

### The bake lane exception

`export_blender_scene` takes `reset_staging` and `staging_dir`
(`Plugin/export/blender_usd_export.py:230-231`). Ordinary exports pass
neither and get a fresh private attempt (`:259-264`). The bake lane bakes
textures into `<staging>/textures` *before* calling the exporter
(`Plugin/api/commands/bake_export.py:519-520`, `:545-552`), so it allocates
the directory itself and passes `reset_staging=False` (`:579-580`) —
otherwise the freshly baked textures would be deleted
(`Plugin/export/blender_usd_export.py:239-242`).

### The generation namespace

Staged sidecars — the texture and asset files that accompany a USD file —
are not written flat into `textures/` or `assets/`. They go into a two-level
namespace produced by `output_sidecar_namespace`
(`Plugin/export/staging_namespace.py:17`):

```
textures/<portable output filename>/<32 hex generation token>/<file>
assets/<portable output filename>/<32 hex generation token>/<file>
```

(`Plugin/export/usd_textures.py:126-131`, `Plugin/export/usd_assets.py:56`.)

The generation token is deliberately **immutable and unique per attempt**,
not a stable prefix. `_generation_token`
(`Plugin/export/staging_namespace.py:31`) stores it in a marker file under
`.blendertorcp_generations/<sha256 of filename>[:24].txt` created with
`O_CREAT | O_EXCL` and fsynced (`:41-66`), so every caller within one attempt
agrees on the token while a new attempt gets a new one. The marker root lives
beside the *staged* USD, so it is destroyed with the staging directory and
never reaches your output folder.

The reason, stated at `:20-25`: because each generation's files are immutable
and uniquely named, a publisher can install every new sidecar **first** and
atomically replace the root USD **last**. A hard process exit at any point
leaves either the old root with the old generation, or the new root with a
fully installed new generation. At worst it leaks an unreferenced generation.

### The ownership manifest

Each output owns an explicit list of the sidecar files it wrote, stored at
`<output dir>/.blendertorcp_sidecars/<canonical output identity>.json`
(`Plugin/export/sidecar_manifest.py:43-50`). The identity is the complete
filename, NFC-normalized and case-folded twice (`:53-59`) to match macOS
filesystem behavior. Two sibling outputs whose names collapse to the same
identity are rejected outright (`validate_unambiguous_output_identity`,
`:62`).

Only `textures/` and `assets/` are ownable (`OWNED_SIDECAR_DIRECTORIES`,
`:19`). Manifest entries are validated strictly: string, no backslash or
NUL, relative, no `.` or `..` segments, first component in the owned set,
round-trips through `PurePosixPath` unchanged, at least two components
(`validate_sidecar_relative_path`, `:111-127`). Duplicate entries, a wrong
schema version, or a manifest naming another output all raise
(`read_output_sidecar_manifest`, `:130`).

The manifest exists so that consumers — support-bundle creation in
particular — use the recorded list instead of recursively walking shared
output directories (`:1-6`). `validate_owned_sidecar_files` (`:181`)
additionally refuses symlinked directories or files anywhere along each
entry's path, missing files, hard-linked files (`st_nlink != 1`,
`:231-234`), and any path that escapes the managed root (`:236-244`).

*Verification: exporting `scene.usda` with one packed texture produced
`t1/.blendertorcp_sidecars/scene.usda.json` containing
`{"output": "scene.usda", "schema_version": 1, "sidecars": [...]}` listing
exactly the two staged PNGs under
`textures/scene.usda/bd6f04c80cf627cb46153b7cfeed2110/`.*

### The publication lock

`publish_unpacked_export` (`Plugin/export/blender_usd_export.py:359`) takes
an exclusive advisory lock keyed on the canonical output identity before
doing anything (`_output_publication_lock`, `:582`). The lock file is
`<output dir>/.blendertorcp_publish/locks/<sha256 of identity>.lock`, opened
with `O_NOFOLLOW` where available and mode `0600` (`:604-613`), locked with
non-blocking `flock` on POSIX or `msvcrt.locking` on Windows (`:630-644`).
It **fails closed**: a second process publishing the same output gets
`"Another export is already publishing '<path>'."` rather than interleaving
(`:619-622`). The transaction root and lock root are both checked for
symlinks and for resolving inside the output directory (`:585-602`).

This lock file persists in the output directory after the export completes.
That is by design — it is a lock, not an artifact. You can ignore it.

### The publication transaction

The publication transaction is the ordered sequence of file operations that
installs a finished export. With the lock held,
`_publish_unpacked_export_locked`
(`Plugin/export/blender_usd_export.py:379`) runs:

1. **Recover debris.** Abandoned transaction directories from a previous
   hard exit are removed, identified by an owner marker naming this exact
   output with an empty sidecar list
   (`_recover_abandoned_publication_transactions`, `:812`).
2. **Collect and plan.** Staged sidecars are gathered from `textures/` and
   `assets/`, refusing symlinks at every level (`_collect_staged_sidecars`,
   `:669`). The previous generation's owned set is read from the manifest
   (`:733`), and paths owned by *other* outputs' manifests are collected
   (`_sidecars_owned_by_other_outputs`, `:1064`).
   `_plan_sidecar_publication` (`:745`) then refuses to overwrite an unowned
   collision (`:763-766`), refuses a non-file collision (`:758-759`), and —
   for a path that already exists and is owned — requires the bytes to be
   identical (`:768-772`), since content-addressed generations are immutable
   by construction. Identical files need no action and are shared across
   manifests (`:773-775`).
3. **Prepare.** Every replacement is copied into a same-filesystem
   transaction directory
   `<output dir>/.blendertorcp_publish/<output name>.<mkdtemp>/prepared/`
   first (`:404-433`), so the commit phase is only `os.replace` calls.
4. **Commit, root last** (`_execute_root_last_publication`, `:910`). The
   order is: write a *transition manifest* claiming the union of old and new
   entries (`:951-955`); install every new sidecar (`:959-968`); atomically
   replace the root USD (`:972`); write the final manifest, or delete it if
   the output now owns nothing (`:977-982`). Backups of the old root and old
   manifest are copied first (`:935-942`).
5. **Roll back on any exception**, including `TimeoutError` and cancellation
   — the handler catches `BaseException` (`:985`). The root is restored from
   backup or unlinked, the manifest likewise, and installed sidecars are
   unlinked in reverse order (`:986-1008`). If rollback itself fails, that
   is surfaced as a distinct error rather than swallowed (`:1013-1017`).
6. **Clean up.** Stale sidecars from the superseded generation are removed
   only *after* the new root and final manifest are durable
   (`_remove_stale_sidecars_after_commit`, `:1021`), and the transaction
   directory is removed (`:1033`).

### Why re-exporting to the same path is safe

Because of the four properties above acting together:

- The new export's sidecars land in a **new generation directory**, so they
  cannot collide with the ones the currently-published root still
  references.
- The **root USD is swapped last**, atomically, so a reader either sees the
  entire old asset or the entire new one.
- The **transition manifest** claims both generations before any new file is
  installed, so a retry after a hard kill can tell a partially installed
  generation apart from an unowned user collision.
- **Stale files are deleted after the commit**, so the old generation stays
  intact until the new root is durable.

The comment at `Plugin/export/blender_usd_export.py:920-927` states the
invariant directly: at every checkpoint either the old root plus old
sidecars, or the new root plus all new sidecars, form a complete artifact. A
hard exit may leak an unused immutable generation but cannot corrupt the
previously published asset. The `_publication_phase_checkpoint` no-op at
`:906` is the fault-injection point the crash-coherence tests use.

`_remove_stale_sidecars_after_commit`
(`Plugin/export/blender_usd_export.py:1066`) unlinks the superseded files, and
`_remove_emptied_sidecar_generations` then removes the directories it just
emptied. Re-exporting to the same path leaves exactly one generation
directory, however many times you run it.

*Verification: three consecutive exports of the same scene to `t1/scene.usda`
each succeeded. After each, the manifest listed exactly the current
generation and the previous generation's files were gone. Generation tokens
observed: `bd6f04c8…`, then `e506e3d1…`, then `ff53566d…`. After the three
exports, `textures/scene.usda/` held exactly one generation directory.*

---

## 6. Packaging

### Format selection

`export_format` offers `USDA`, `USDC` and `USDZ` (default `USDA`). The CLI
maps each to a mandatory extension and rewrites the output path with it
(`Plugin/api/commands/export.py:116-123`).

The staged intermediate extension is chosen at
`Plugin/export/blender_usd_export.py:270-273`:

- `USDZ` stages as **`.usdc`** — the archive root is always binary, never
  ASCII.
- `USDA` and `USDC` stage with the final extension.

### USDZ layout requirements

USDZ is not an arbitrary ZIP. `Plugin/export/pack_usdz.py:1-7` states the
three constraints the module enforces so exports stay valid even without
Apple's `usdzip`:

1. **Every member stored, never deflated** —
   `compression=zipfile.ZIP_STORED` (`:223-228`), re-asserted per member
   (`:396`), and verified (`:308-309`).
2. **Every member's payload begins on a 64-byte boundary** —
   `_USDZ_ALIGNMENT = 64` (`:44`). `_write_aligned_member` (`:373`) computes
   `-(offset + 30 + len(name) + 4) % 64` and inserts that many padding bytes
   inside a private ZIP extra field with ID `0x1986` (`:382-392`), which is
   explicitly skippable (`:45-47`).
3. **The root USD layer is the first member** — `_iter_package_files` yields
   the root before anything else (`:346-348`), and validation rejects a
   first member that is not a single-component `.usd`/`.usda`/`.usdc` path
   (`:274-280`).

Member paths are also checked: no backslash, no trailing slash, not
absolute, no empty/`.`/`..` segments (`_is_safe_archive_name`, `:648`);
extension in the allowed set — `.usd`, `.usda`, `.usdc`, `.usdz`, `.png`,
`.jpg`, `.jpeg`, `.exr`, `.avif`, `.m4a`, `.mp3`, `.wav` (`:28-43`,
`:666-667`); no directory entries (`:306-307`); not encrypted (`:310-311`);
and no case/Unicode-colliding names under NFC + casefold (`:285-293`).

### What ends up inside

Everything in the staging directory, minus exporter bookkeeping.
`_iter_package_files` (`:342`) walks the staging root, refuses any symlink
(`:353-354`), skips the root layer and the output file itself (`:357-358`),
and skips any path containing `.blendertorcp_generations` or a component
starting with `.blendertorcp_` (`_is_internal_package_member`, `:657-663`).
Validation independently rejects such members if they somehow appear
(`:295-299`).

Note the practical consequence: sidecars keep their
`textures/<output>/<generation>/…` namespace **inside** the archive.

*Verification: a USDZ export of a textured cube produced exactly three
members, all stored, all 64-aligned:*

```
scene.usdc                                                   stored=True data_offset=64   aligned64=True size=4614
textures/scene.usdc/ea4c2a…/scene-Tex-27ac5b….png            stored=True data_offset=4864 aligned64=True size=410
textures/scene.usdc/ea4c2a…/scene-Tex_703fcf…-27ac5b….png    stored=True data_offset=5504 aligned64=True size=410
```

### Packager selection and atomicity

`create_usdz` (`Plugin/export/pack_usdz.py:66`) writes to a temporary
sibling created with `mkstemp` (`:603-612`) and only `os.replace`s it into
position after validation passes (`:124`). The temporary file is unlinked in
a `finally` (`:178-182`). The destination is resolved without following a
final-component symlink — resolving first would turn
`scene.usdz -> unrelated.dat` into permission to replace the unrelated
target (`_validated_output_path`, `:615-633`).

If the `usdzip_path` preference points at an executable,
`usdzip --asset <root> --checkCompliance <out>` is used (`:92-95`,
`:189-213`); `--asset` resolves the full dependency closure while retaining
authored composition, whereas a positional member would archive only the
root file (`:191-195`). Otherwise the built-in aligned packager runs
(`:97-102`), which self-validates and deletes its output on structural
failure (`:232-236`).

External tools run in their own process group with bounded timeouts — 600 s
for the packager, 300 s for the checker (`:48-49`, `_run_external_tool`,
`:534`) — so the background-export watchdog can terminate the whole tree
rather than orphaning descendants (`:536-540`, `:578-601`).

On success the staging tree is removed (`:186`, `_cleanup_usdz_staging`,
`:670`); on packaging or validation failure it is deliberately preserved so
the support bundle has the source material (`:184-185`).

---

## 7. Preflight and validation gates

### Before anything is written

| Gate | Where | Failure |
|------|-------|---------|
| Setting override keys/values | `Plugin/api/commands/export.py:74-96` | `INVALID_SETTING_OVERRIDE`, `INVALID_SETTING_VALUE` |
| Selection closure raises | `Plugin/api/commands/export.py:189-200` | `INVALID_EXPORT_SELECTION` |
| Selected-only with nothing exportable | `Plugin/api/commands/export.py:201-208` | `NO_EXPORTABLE_OBJECTS` |
| Strict material validation | `Plugin/api/commands/export.py:216-243` | `UNSUPPORTED_MATERIAL_NODES` |
| Missing external assets (**bake lane only**) | `Plugin/api/commands/bake_export.py:387-397` | `MISSING_EXTERNAL_TEXTURES` / `MISSING_EXTERNAL_ASSETS` |

Material validation runs over the exact export closure when
`selected_objects_only` is on, and over all scene materials otherwise
(`Plugin/api/commands/export.py:211-215`).

### The asset preflight is bake-only

`Plugin/export/asset_preflight.py` walks the processing scope's reachable
datablocks and uses Blender 5.2's `BlendData.file_path_foreach(subset=…)`
for exact UDIM, sequence, and cache expansion
(`Plugin/export/asset_preflight.py:514-559`), falling back to a manual walk
when that API is unavailable (`Plugin/export/asset_preflight.py:562-591`).
It covers collection-instance prototypes, nested material and Geometry Nodes
groups, typed Geometry Nodes modifier inputs, classic `Texture.image`
modifiers, transform and mesh caches, linked libraries, and the scene World
when it contributes to the bake
(`Plugin/export/asset_preflight.py:26-38`). Object classes outside the
delivery contract are excluded so an old saved setting cannot make their
inputs release-blocking (`_object_content_enabled`,
`Plugin/export/asset_preflight.py:696-726`).

It is wired into the bake lane only —
`Plugin/api/commands/bake_export.py:387`,
`Plugin/bake_export_runner.py:551`,
`Plugin/ops/bake_export_operator.py:200`. The plain export path does not
call it. A plain export with a missing external texture still fails closed,
but later — during texture staging, after the native USD export has run —
and with the generic `EXPORT_FAILED` code rather than
`MISSING_EXTERNAL_TEXTURES`.

*Verification: exporting a scene whose only image file had been deleted
returned `{"code": "EXPORT_FAILED", "stage": "export", "message": "Texture
file not found: …/will_vanish.png"}` — raised during texture staging, after
the native USD export had already run.*

### The composed-stage preflight

`validate_stage` (`Plugin/export/realitykit_preflight.py:227`) runs against
the **composed stage** — the fully assembled USD scene after all layers are
combined — after material rewriting and asset staging but before the stage
is saved (`Plugin/export/realitykit_preflight.py:3-5`). `process_usd_stage`
treats any error as fatal for the whole shared UI/CLI/bake pipeline
(`Plugin/export/postprocess_usd.py:171-185`).

Checks, all in `_check_composed_stage`
(`Plugin/export/realitykit_preflight.py:262`): stage metadata, prim types,
meshes, material bindings, material texture transforms, skeletons, textures,
accessibility. When the stage has authored variant sets, the checks run
across variant combinations instead of the single default composition
(`Plugin/export/realitykit_preflight.py:246-255`), bounded at
`MAX_VARIANT_COMBINATIONS = 256` — above that the export fails closed rather
than becoming exponential (`Plugin/export/realitykit_preflight.py:30-36`).

Error codes:

`DEFAULT_PRIM_MISSING`, `DEFAULT_PRIM_NOT_ROOT`, `UP_AXIS_UNAUTHORED`,
`UP_AXIS_NOT_Y`, `METERS_PER_UNIT_UNAUTHORED`, `METERS_PER_UNIT_INVALID`,
`METERS_PER_UNIT_NOT_ONE`, `UNSUPPORTED_REALITYKIT_PRIM_TYPE`,
`MESH_TOPOLOGY_MISSING`, `VERTEX_ANIMATION_UNSUPPORTED`,
`SUBDIVISION_SCHEME_UNAUTHORED`, `SUBDIVISION_SCHEME_INVALID`,
`DOUBLE_SIDED_GEOMETRY`, `TOO_MANY_UV_SETS`,
`MATERIAL_BINDING_API_MISSING`, `MATERIAL_BINDING_INVALID`,
`MATERIAL_TEXTURE_TRANSFORM_CONFLICT`, `TEXTURE_TRANSFORM_UNINSPECTABLE`,
`MULTIPLE_SKELETONS`, `SKELETON_OUTSIDE_SKEL_ROOT`,
`SKELETON_JOINTS_MISSING`, `SKELETON_BINDING_INVALID`,
`SKELETON_TARGET_INVALID`, `SKEL_BINDING_API_MISSING`,
`SKINNING_PRIMVARS_INCOMPLETE`, `TEXTURE_ASSET_MISSING`,
`TEXTURE_COLOR_ROLES_CONFLICT`, `TEXTURE_COLOR_SPACE_MISMATCH`,
`TEXTURE_COLOR_SPACE_UNSUPPORTED_TOKEN`, `MATERIALX_NODEDEF_UNSUPPORTED_BY_RCP`,
`USDZ_TEXTURE_FORMAT_UNSUPPORTED`, `USDZ_TEXTURE_PATH_EXTERNAL`,
`VARIANT_SET_UNINSPECTABLE`, `VARIANT_VALIDATION_LIMIT`.

Warnings (non-fatal): `PRELIMINARY_SCHEMA`, `SUBDIVISION_RUNTIME_COST`,
`USDSKEL_SCHEMA_UNAVAILABLE`, `ACCESSIBILITY_LABEL_MISSING`,
`ACCESSIBILITY_DESCRIPTION_MISSING`, `TEXTURE_ALPHA_SOURCE_MISSING`.

`LIGHTMAP_UV_MISSING` and `LIGHTMAP_UV_EMPTY` change severity with
`require_lightmap_uv` — info/warning by default, error when it is set
(`Plugin/export/realitykit_preflight.py:924-951`).

`UNSUPPORTED_REALITYKIT_PRIM_TYPE` is raised for `BasisCurves`,
`NurbsCurves`, `NurbsPatch`, `Points`, `PointInstancer`, `ParticleField`,
`TetMesh`, `Volume`, `OpenVDBAsset`, every light type including `DomeLight`
and `PortalLight`, and `Camera` (`:50-72`). Each carries a specific
remediation string. `ParticleField` is standardized in OS 27 but has no
shipping USD-to-RealityKit Gaussian-splat import path, so schema
availability is not treated as runtime rendering support (`:46-49`).

### Operator contract validation

Before invoking Blender's exporter, `_validate_export_operator_contract`
(`Plugin/export/blender_usd_export.py:1191`) inspects the live operator's
RNA and fails if any argument the pipeline passes is unsupported, or if any
of `export_textures_mode`, `generate_preview_surface`,
`generate_materialx_network`, `root_prim_path` is missing
(`_REQUIRED_USD_EXPORT_PROPERTIES`, `:57-64`). These four define the Blender
5.2 USD boundary the add-on depends on; silently dropping one would change
the exported asset, notably the texture-copy behavior (`:53-56`).

`_invoke_usd_export` (`:1213`) then snapshots the `WindowManager` report
list before and after the call (`:1251`, `:1272-1276`) and turns any new
`ERROR*` report into an exception, forwards `WARNING` reports to
diagnostics, and requires `FINISHED` in the operator result (`:1228-1248`).

### After packaging

For USDZ, `validate_usdz_details` (`Plugin/export/pack_usdz.py:250`) runs
the structural checks above and then, if `usdchecker` is available, invokes
it. Apple-profile validation is **mandatory when advertised**:
`_usdchecker_supports_arkit` (`:452`) probes `--help`, and a launch error,
timeout, or non-zero help exit is treated as ambiguous and fails closed
rather than silently downgrading (`:456-458`, `:107-114`). Only a clean
`--help` that genuinely lacks `--arkit` permits the generic `--strict`
fallback, which is then reported as a warning (`:166-171`). No checker at
all is also a warning (`:172-176`). The checker is located next to a
configured `usdzip`, or via `xcrun --find` on macOS, or on `PATH`
(`_find_usdchecker`, `:490`).

The compliance level reached is recorded in diagnostics as
`usdchecker_arkit_strict`, `usdchecker_strict_fallback`, or
`structural_only`, alongside the exact tool paths, versions, and command
lines (`:126-165`).

*Verification: a USDZ export on macOS recorded
`"compliance": "usdchecker_arkit_strict"` with
`"checker_path": "/usr/bin/usdchecker"`,
`"checker_version": "Apple USD Tools (0.25.11)"`, and
`"checker_command": ["/usr/bin/usdchecker", "--arkit", "--strict", …]`.*

### Diagnostics

Failure diagnostics are mandatory; `diagnostics_enabled` only controls
whether a *successful* export keeps its `.diagnostics.json` sidecar
(`Plugin/api/commands/export.py:161-163`). The sidecar records the phase
timeline, the animation schedule, every generated file with its role, the
full preflight report, and the asset-dependency snapshot.
