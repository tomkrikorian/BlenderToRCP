# Texture baking

This page explains what the bake pipeline does, and — more importantly —
what it decides on your behalf. Read it if a baked export does not look like
your viewport, or if you want to know when the Export button bakes at all.

*Applies to: Blender 5.2.0 LTS (`fbe6228777e7`).*

Two terms recur on this page. *Baking* renders a material's appearance into
texture images. *IBL* (image-based lighting) lights a scene with an
environment image instead of individual lamps. A *passthrough* copies a
source texture — a normal map, for example — into the export unchanged
instead of baking it.

Scope: `Plugin/export/bake_textures.py`, `Plugin/export/bake_finalize.py`,
`Plugin/bake_export_runner.py`, `Plugin/api/commands/bake_export.py`,
`Plugin/ops/bake_export_operator.py`, `Plugin/export_profile.py`, and the
bake-related settings in `Plugin/ui/panel.py`. Source references are asides
for contributors; you do not need the source code to use this page. The
*Verification* notes at the end of sections record how the stated behavior
was confirmed by running the Blender build above against purpose-built
scenes.

Related: [`CLI.md`](CLI.md) for the `bake-export` command surface,
[`ARCHITECTURE.MD`](ARCHITECTURE.MD) for where baking sits in the export
pipeline.

---

## 1. When baking happens at all

The Blender sidebar has one **Export** button. It does not say whether it
will bake. `resolve_ui_export_route` decides, from two enum settings,
whether the button runs the direct USD export or a bake
(`export_profile.py:32`).

The panel reads that route and swaps the operator behind the button
(`panel.py:623-638`): `blendertorcp.export` for `PIPELINE_DIRECT`,
`blendertorcp.bake_export_background` otherwise.

| `ui_material_type` | Secondary setting | Route | `bake_mode` | Implemented at |
|---|---|---|---|---|
| `REALITYKIT_PBR` | `ui_pbr_processing = TRANSLATE` | **No bake** — direct export | — | `export_profile.py:43` |
| `REALITYKIT_PBR` | `ui_pbr_processing = BAKE` | Bake | `LIT_ALBEDO` | `export_profile.py:42` |
| `REALITYKIT_UNLIT` | `ui_unlit_appearance = MATERIAL_COLOR` | Bake | `UNLIT_ALBEDO` | `export_profile.py:52` |
| `REALITYKIT_UNLIT` | `ui_unlit_appearance = LIGHTING_SHADOWS` | Bake | `LIT_IBL` | `export_profile.py:51` |

Three of the four combinations bake. Only *RealityKit PBR → Translate
Materials* does not. In particular, **choosing "RealityKit Unlit" always
bakes**, even for `Material Color Only`, because an Unlit material still
needs a color texture.

### The UI overwrites your `bake_mode`

`bake_mode` is a real, persisted setting with its own enum
(`panel.py:379-389`, default `LIT_IBL`). When the Export button routes to
the bake operator it sets `apply_ui_profile = True` (`panel.py:637-638`),
and the operator then **overwrites** `settings.bake_mode` with whatever the
route resolved (`bake_export_operator.py:104-117`). Whatever `bake_mode` you
last set from the CLI is discarded on the next UI export.

The CLI does the opposite: `bake-export` takes `--bake-mode` directly and
never consults `ui_material_type` (`bake_export.py:116-130`). The two front
ends reach the same code with different defaults — see §3.2.

### `bake_mode` is normalized, not validated

Any value outside `{UNLIT_ALBEDO, LIT_ALBEDO, LIT_IBL}` silently becomes
`LIT_IBL` (`bake_textures.py:127-129`).

---

## 2. The bake modes

| | `UNLIT_ALBEDO` | `LIT_ALBEDO` | `LIT_IBL` |
|---|---|---|---|
| UI label | Unlit → Material Color Only | PBR → Bake Materials | Unlit → Lighting & Shadows |
| Cycles bake type | `DIFFUSE` | `DIFFUSE` | `COMBINED` |
| `pass_filter` | `{COLOR}` | `{COLOR}` | `{DIRECT, INDIRECT, DIFFUSE, GLOSSY, TRANSMISSION, EMIT}` |
| Lighting included | none | none | scene lights + world/IBL + shadows + AO |
| Cycles samples | forced to **1** | forced to **1** | **your scene's** `cycles.samples` |
| Roughness map baked | no | yes | no |
| Normal map carried over | **no** | yes (passthrough) | **no** |
| Metallic carried over | **no** | yes (passthrough) | **no** |
| Flat materials short-circuited | yes | yes | **no** |
| Instances can share one bake | yes | yes | **no** |
| Exported material | Unlit | Lit PBR | Unlit |

Source lines: bake type and pass filter `bake_textures.py:237-243` and
`bake_textures.py:35-37`; samples `bake_textures.py:454`; roughness gate
`bake_textures.py:143`; normal/metallic passthrough only under `LIT_ALBEDO`
`bake_textures.py:1321-1330`; flat short-circuit `bake_textures.py:180-185`;
cache `bake_textures.py:256`; Unlit/Lit choice `bake_finalize.py:10-22`.

`UNLIT_ALBEDO` and `LIT_ALBEDO` produce the same base color texture for the
same material; the two modes differ only in what is authored *around* that
texture. The sample-count decision is not cosmetic: `LIT_IBL` uses your
scene's sample count, so a scene saved with a high `cycles.samples` bakes
much more slowly than the other two modes.

*Verification: `UNLIT_ALBEDO` and `LIT_ALBEDO` staged a byte-identical
content-hashed file
`…_baseColor-0c3f58e9f3a02999856650c70a6af21a…avif` for the same material.
On a five-mesh test scene saved with `cycles.samples = 4096`, `LIT_ALBEDO`
completed in 0.47 s and `LIT_IBL` in 88.61 s.*

### Why `LIT_IBL` cannot share bakes between instances

A `COMBINED` bake records path-traced lighting in world space, so two copies
of the same mesh at different transforms genuinely differ. The reuse cache
is therefore disabled for `LIT_IBL` (`bake_textures.py:249-256`) and every
object bakes its own textures.

**That is not the same as every object *getting* its own textures.**
Material slots are `DATA`-linked by default, so writing the baked material
into `obj.material_slots[i].material` writes it onto the shared **mesh
datablock** — the last object processed wins for every object sharing that
mesh. The pipeline handles this correctly on the read side (it snapshots the
original slot materials before baking, `bake_textures.py:149-161`) but not
on the write side.

**Known limitation, and what to do about it:** in `LIT_IBL`, give each
object a real mesh copy (Shift+D, or
`Object ▸ Relations ▸ Make Single User ▸ Object & Data`) if the objects sit
in different lighting. Linked duplicates all inherit the last-baked
instance's lighting.

`UNLIT_ALBEDO` and `LIT_ALBEDO` bake pure material color, so sharing is
correct there and *is* the mechanism that lets the USD exporter emit
instanceable references.

*Verification: a scene with two objects sharing one mesh datablock (an
Alt+D linked duplicate), a sun light, and an opaque slab occluding only the
second object was exported with `bake-export --bake-mode LIT_IBL`. The
exported USD bound **both** `LitCube` and `DarkCube` to
`</root/_materials/Shared_Baked_1>`, whose texture
`s-DarkCube__Shared_Baked_1_baseColor-….avif` measured `R[0.0000, 0.2275]`,
mean `0.0003` — black. The fully lit cube exported black; the first object's
bake was produced, then discarded by the unreferenced-output sweep
(`bake_export.py:602-612`). Separately, three objects sharing a mesh and
material under the albedo modes produced exactly one baked texture and one
`Textured_Baked` material.*

---

## 3. Decisions made for you

Read this section if the output does not look like the viewport.

### 3.1 Scene state that is overridden and restored

| State | Overridden to | Where | Restored |
|---|---|---|---|
| `scene.render.engine` | `CYCLES` | `bake_export.py:505`, `bake_export_runner.py:664` | `bake_export.py:752-757`, `runner:808-811` |
| `cycles.samples` | `1` for every property pass; untouched for `LIT_IBL` color | `bake_textures.py:454`, `500`, `547`, `628` | `bake_textures.py:834-844` |
| `cycles.use_denoising` | `False` whenever samples are pinned | `bake_textures.py:829-831` | `bake_textures.py:840-844` |
| `scene.world` | replaced by a generated `BlenderToRCP_IBL` world — **only** when `bake_mode = LIT_IBL` **and** `bake_ibl_source = HDRI_FILE` | `bake_textures.py:713-752` | `bake_textures.py:744-752`, temp world deleted |
| Object mode | forced to `OBJECT` | `bake_export.py:504`, `bake_textures.py:1888-1889` | `bake_export.py:766-777` |
| Selection + active object | each mesh selected alone before every pass | `bake_textures.py:1918-1925` | `bake_export.py:766-771` |
| `hide_viewport` / `hide_render` of every other mesh | `True`, only when `LIT_IBL` **and** `bake_isolate_meshes_lit` | `bake_textures.py:847-873` | `bake_textures.py:867-873` |
| Material slots | replaced by `<name>_Baked` copies | `bake_textures.py:344-356` | `bake_textures.py:932-968` unless `bake_keep_materials` |
| `force_unlit_materials` | set from `bake_mode` | `bake_finalize.py:20-22` | `bake_export.py:746-751` |
| Collection-prototype scene links | temporarily linked so bake operators can reach them | `bake_export.py:510-514` | `bake_export.py:715-728`, fails closed |

**Color management is *not* touched, and does not affect the bake.**
`view_transform`, `look`, exposure, and gamma are never read or written by
any file in scope. Cycles bakes scene-referred data; the display transform
is irrelevant. If your export looks different from the viewport, the view
transform is the reason — not the bake.

**Restoration runs on both the success and the failure path.** The rollback
is explicit: `bake_materials_for_objects` wraps the implementation and
restores every slot before re-raising (`bake_textures.py:91-109`), and each
caller restoration step is independently guarded so one failure cannot skip
the rest (`bake_export.py:736-793`, `bake_export_runner.py:789-843`).

*Verification: the same scene baked twice — once saved with `AgX` +
`AgX - High Contrast`, once with `Standard` — produced textures with
identical content hashes (`…baseColor-0c3f58e9f3a029…`,
`…roughness-5615e03c28ee52…`). A snapshot of 20 state fields (engine,
samples, denoising, bake target/save-mode/split/margin, pass toggles, view
transform, look, world, datablock counts for worlds/images/materials, active
object, selection, mode, every material slot, `hide_viewport`,
`force_unlit_materials`) taken before and after an in-process `bake_export`
run showed zero differences for: `LIT_ALBEDO`, successful run; `LIT_IBL`
with `isolate_meshes`, successful run; and `LIT_ALBEDO` aborted mid-bake by
an object with no UV map — no leaked materials, images, or worlds, and every
slot back to its original material.*

### 3.2 Bake operator properties that are pinned, not inherited

`bpy.ops.object.bake` fills any property you omit from `scene.render.bake` —
whatever the `.blend` happens to have been saved with. Every property this
pipeline depends on is therefore passed explicitly
(`bake_textures.py:1890-1915`):

| Property | Pinned to | Why |
|---|---|---|
| `target` | `IMAGE_TEXTURES` | A scene saved with `VERTEX_COLORS` bakes into a color attribute, leaves the target image untouched, still returns `{'FINISHED'}`, and an all-black texture is saved and packaged (`bake_textures.py:1896-1901`) |
| `save_mode` | `INTERNAL` | `EXTERNAL` redirects the bake to files on disk; this pipeline reads pixels back off the image datablock and saves them itself (`bake_textures.py:1902-1904`) |
| `use_split_materials` | `False` | `bake_textures.py:1905` |
| `pass_filter` (COMBINED) | the full `COMBINED_PASS_FILTER` set | An omitted filter inherits the scene's `use_pass_direct`/`use_pass_indirect`/… toggles; a `.blend` with those disabled bakes pure black through `LIT_IBL` (`bake_textures.py:1907-1911`) |
| `use_clear` | `True` | `bake_textures.py:1893` |
| `use_selected_to_active` | `False` | `bake_textures.py:1894` |
| `margin` | from settings, see §3.9 | `bake_textures.py:1892` |

*Verification: a scene deliberately saved with
`render.bake.target = 'VERTEX_COLORS'`, `save_mode = 'EXTERNAL'`,
`use_split_materials = True`, all six `use_pass_*` toggles off, engine
`BLENDER_EEVEE`, and `cycles.samples = 4096` still produced correct,
non-black textures in all three modes — and every one of those scene values
was unchanged afterwards.*

### 3.3 Resolution — and the UI/CLI divergence

`_resolve_bake_resolution` (`bake_textures.py:971-990`) returns either a
fixed pixel size or `0`, meaning "key each material to its own source
textures":

| `export_texture_settings_enabled` | `bake_resolution` | Result |
|---|---|---|
| `False` | (ignored) | `0` → source-keyed |
| `True` | `ORIGINAL` | `0` → source-keyed |
| `True` | `512` / `1024` / `2048` / `4096` | that value |
| `True` | `CUSTOM` | `bake_resolution_custom` (min 32, `panel.py:476-482`) |
| `True` | unparseable | `2048` (`bake_textures.py:990`) |

Two overrides sit on top:

- **`LIT_IBL` never uses source-keyed sizing.** If the resolution resolves
  to `0` under `LIT_IBL` it is forced to `2048`
  (`bake_textures.py:132-138`): a 256 px tileable albedo says nothing about
  how much resolution a shadow gradient needs.
- **Source-keyed sizing has a 512 px floor.** `_material_source_resolution`
  (`bake_textures.py:1082-1130`) walks upstream from the Principled
  **Base Color, Roughness and Alpha** inputs only, takes the largest image
  dimension it finds, and returns `max(largest, 512)`. A small tileable
  texture repeated across a UV layout flattens its repetition into the bake,
  so keying the bake to the tile size would squeeze that repetition into a
  few texels. Images that drive channels the pipeline does *not* bake — a
  normal map, for example — are deliberately ignored. Falls back to `2048`
  when no image is found (procedural or unloaded textures).

**The UI and the CLI disagree by default.**
`export_texture_settings_enabled` defaults to `False` (`panel.py:442-447`),
but the UI bake operator forces it to `True` in the payload it sends to the
worker (`bake_export_operator.py:730-731`). So:

| Front end | Default behavior |
|---|---|
| **Sidebar Export button** | always fixed resolution — `bake_resolution`, default **2048** |
| **`blendertorcp bake-export`** with no `--resolution` | source-keyed (floor 512) |
| **`blendertorcp bake-export --resolution N`** | fixed `N` (the flag also flips `export_texture_settings_enabled` on, `bake_export.py:132-140`) |

A 256 px source texture is upscaled 8× by the UI path.

*Verification: a `LIT_IBL` bake with no resolution flag produced 2048×2048
textures; the same scene under `LIT_ALBEDO` produced 512×512. A material
with a 256 px base-color texture, a 256 px roughness texture, and a 1024 px
normal map baked at 512×512 — the floor applied and the 1024 px normal map
correctly did not raise the size. The same scene and mode with no flag
returned 512×512 and `"resolution": 0` in the response; with
`--resolution 2048` it returned 2048×2048 and `"resolution": 2048`.*

### 3.4 Image format

`_resolve_bake_image_format` (`bake_textures.py:1148-1178`):

- When `export_texture_settings_enabled` is `False`, `bake_image_format` is
  **ignored** and the format is `AVIF` (`bake_textures.py:1149-1152`,
  `_DEFAULT_BAKE_IMAGE_FORMAT` at `bake_textures.py:43`).
- `ORIGINAL` is meaningless for a freshly baked image. Baking silently
  substitutes **PNG** and records a warning: *"Original texture format is
  only available for existing texture staging; baked textures are saved as
  PNG."* (`bake_textures.py:1156-1167`). The Optimization panel says so too
  (`panel.py:831-835`).
- A format this Blender build cannot write falls back to PNG with a warning
  (`bake_textures.py:1169-1177`).
- If assigning the format to the image datablock fails at all,
  `_create_bake_image` rewrites the path to `.png` and uses PNG
  (`bake_textures.py:1938-1942`).

AVIF is encoded natively by Blender — no external tools involved.

### 3.5 Color space assigned to baked images

Chosen at creation time, not inferred (`bake_textures.py:1928-1947`):

| Baked image | Color space | Line |
|---|---|---|
| Base color | `sRGB` | `bake_textures.py:429` |
| Roughness (texture or averaging target) | `Non-Color` | `bake_textures.py:492`, `539` |
| Opacity | `Non-Color` | `bake_textures.py:619` |
| Flat-slot throwaway | `sRGB` | `bake_textures.py:409` |
| Opaque-slot opacity throwaway | `Non-Color` | `bake_textures.py:599` |

Source images carried through untouched (normal, metallic) keep their
**authored** color space. The pipeline deliberately does not rewrite it,
because the image datablock is shared with every other user of that texture
and the change would not be restored (`bake_textures.py:1761-1764`, `1774`).

*Verification: the choice survives into the USD —
`inputs:sourceColorSpace = "sRGB"` on the baked base-color reader and
`"raw"` on the baked roughness reader.*

### 3.6 Which channels are baked, and which are copied

| Channel | `UNLIT_ALBEDO` | `LIT_ALBEDO` | `LIT_IBL` |
|---|---|---|---|
| Base color | baked (`DIFFUSE`/`COLOR`) | baked (`DIFFUSE`/`COLOR`) | baked (`COMBINED`) |
| Roughness | not authored | baked (`ROUGHNESS` pass) or averaged | not authored |
| Alpha | baked (`EMIT` pass) | baked (`EMIT` pass) | baked (`EMIT` pass) |
| Normal | **dropped** | source image passed through | **dropped** |
| Metallic | **dropped** | source image or constant passed through | **dropped** |
| Emission | **dropped, silently** | **rejected** — export fails | folded into the lit color |

Normal and metallic passthrough are only computed when
`bake_mode == "LIT_ALBEDO"` (`bake_textures.py:1321-1330`), which is correct
for Unlit output but means a `LIT_IBL` export carries no normal map either.

Passthrough is strict and fails closed rather than guessing
(`bake_textures.py:1411-1543`). Normal passthrough requires exactly
`Image Texture ▸ Color → Normal Map ▸ Normal → Principled`, OpenGL
convention, tangent space, unlinked Strength, and a default
`Vector`/projection/extension/interpolation on the image node. Metallic
passthrough accepts a directly wired Image Texture `Color` output or a
non-zero constant; a packed channel, a `Math`/`Separate Color` chain, or
anything procedural raises rather than silently becoming zero.

**Known limitation: emission is treated inconsistently across modes.**
`LIT_ALBEDO` validates the Principled inputs it cannot reproduce and fails
(`bake_textures.py:1333-1377`) — non-neutral `Weight`,
`Specular IOR Level`, `Coat Weight`, `Coat Roughness`, `Coat Normal`, and
any non-zero `Emission Strength`. `UNLIT_ALBEDO` and `LIT_IBL` run no such
validation, and `UNLIT_ALBEDO` drops emission without a warning. What to do:
if a material's emission matters, use `LIT_IBL` (which folds it into the lit
color) or remove the emission before an `UNLIT_ALBEDO` bake.

*Verification: the `LIT_ALBEDO` export of a material with a normal map
staged the original 1024 px normal PNG, wired it through
`ND_normal_map_decode`, and preserved `inputs:metallic = 0.7`. The
`UNLIT_ALBEDO` and `LIT_IBL` exports of the same scene staged no normal map
at all. A material with `Emission Strength = 2.0` and an orange emission
color failed under `LIT_ALBEDO` with "Bake Textures cannot preserve Material
Color Only shading for material 'M': Principled 'Emission Strength' is not
preserved by Material Color Only bake. Use Lighting & Shadows bake to
flatten the full lit appearance instead. …". Under `UNLIT_ALBEDO` the same
file exported `ok: true`, and its baked texture was byte-identical (hash
`88ea4353c7d5607c567e8467e4cde577…`) to the same material with the emission
removed.*

### 3.7 Opacity: straight alpha, merged into base color

Only materials with genuine transparency get an opacity pass. Transparency
is read from the active surface's real `Alpha` input — a linked socket, or a
constant below `0.999` — not from `surface_render_method`
(`bake_textures.py:1546-1550`, `materials/extract/core.py:60-94`). An opaque
material's alpha is a constant `1.0`, so baking it would produce a
flat-white texture that is never wired in (`bake_textures.py:568-579`).

The alpha bake is an `EMIT` pass: the material's surface link is replaced by
an Emission node fed from the Principled `Alpha` value or chain
(`bake_textures.py:1638-1671`). Because `EMIT` bakes the whole object, every
non-flat slot that is *not* getting an opacity map is temporarily pointed at
a 4×4 throwaway target so the pass cannot overwrite the base color already
baked into the opaque slots (`bake_textures.py:588-605`).

The opacity map is then merged into the base image's alpha channel as
**straight (unassociated) alpha**: only `A` is written, RGB is left exactly
as the color bake produced it (`bake_textures.py:1821-1875`, the assignment
at line 1856). `alpha_mode` is set to `STRAIGHT` and the separate opacity
file is deleted (`bake_textures.py:1860`, `1865-1874`). RealityKit/MaterialX
applies alpha once; premultiplying here would apply it twice.

The *RGB* of a transparent material is nevertheless darker than the source.
The attenuation happens inside the Cycles `DIFFUSE`/`COLOR` pass, not in the
merge — the merge writes only the alpha channel. RealityKit then applies the
alpha on top.

If the merge cannot run (size mismatch, missing NumPy, read failure) it
returns `False` and the separate opacity texture is kept and wired through a
`Separate Color ▸ Red` chain instead (`bake_textures.py:1808-1816`).

With `--no-opacity` (`bake_opacity = False`) no opacity pass runs, but a
transparent material still gets alpha — from the base image's own alpha
channel, which the `DIFFUSE` bake fills with coverage
(`bake_textures.py:1801-1806`).

*Verification: a material with base color `0.5` gray and `Alpha = 0.4`
baked to a texture whose maximum `R` where `A < 0.5` is `0.3176` — non-zero,
so RGB was not multiplied by alpha — with `alpha_mode=STRAIGHT`. The
exported USD wires opacity from the base texture's own alpha output
(`inputs:opacity.connect = …/Image_Texture_001.outputs:a`); there is no
separate opacity texture in the package. Two cubes with an identical gray
`0.5` base-color texture and identical UVs, differing only in `Alpha`: the
opaque one baked a peak `R` of `0.4941` (approximately the source), the
`Alpha = 0.4` one baked `0.3176`. The `--no-opacity` run produced a
byte-identical base texture (same content hash) to the merged run.*

### 3.8 UV map selection and binding

The bake follows `mesh.uv_layers.active`, falling back to `uv_layers[0]` if
no layer is flagged active (`bake_textures.py:1202-1211`). You are not asked
which UV map to bake into, and a mesh with several UV maps will use
whichever one is active in the mesh data.

The bake *target* image node is deliberately left unbound
(`bake_textures.py:1610-1619`) — the layout the bake writes comes from the
mesh, not from that node. Binding happens on the final baked material: every
image node gets an explicit `ShaderNodeUVMap` wired into its `Vector` input
(`bake_textures.py:1569-1607`). `ShaderNodeTexImage` has no `uv_map`
property, so without this an image node with an unconnected `Vector` samples
whatever UV map the renderer picks by default — on a multi-UV mesh,
potentially the wrong one. One UV node is created per layer per material and
reused.

Normal and metallic passthrough textures are bound to the UV map named on
their own `Normal Map`/`Image Texture` node when it has one, otherwise to
the bake's UV layer (`bake_textures.py:1758`, `1776`).

### 3.9 Margin (dilation)

`_resolve_bake_margin` (`bake_textures.py:1181-1187`) returns `bake_margin`
(default **8** px, `panel.py:484-490`) when
`export_texture_settings_enabled` is `True`, and the same default `8`
otherwise (`bake_textures.py:44`). The value is passed as an operator
argument and never written to `scene.render.bake.margin`.

Margin has one non-obvious side effect: it feeds into the *averaged*
roughness value. See §3.10.

*Verification: `scene.render.bake.margin` was unchanged after a run.*

### 3.10 Roughness: texture or a single averaged value

Only `LIT_ALBEDO` authors roughness (`bake_textures.py:143`).
`bake_roughness_mode` (`panel.py:513-522`, default `TEXTURE`) chooses
between:

- **`TEXTURE`** — a full `ROUGHNESS` bake at the material's resolution,
  saved as a `Non-Color` texture (`bake_textures.py:522-565`).
- **`AVERAGE`** — a throwaway bake capped at **64×64**
  (`bake_textures.py:479-482`), whose mean red channel becomes a single
  constant; the throwaway image is force-removed and no roughness texture is
  exported (`bake_textures.py:508-521`).

**Known limitation: the averaged constant depends on UV coverage and
margin.** `_average_image_value` (`bake_textures.py:1674-1683`) averages
**every texel in the buffer**, including texels no UV island covers, which
are `0`. The resulting constant is therefore a function of UV coverage and
bake margin, not only of the material. What to do: prefer
`--roughness-mode TEXTURE`, or unwrap with high UV coverage before
averaging.

**Known limitation: transparent materials bake a roughness of zero.**
Cycles' `ROUGHNESS` pass returns `0` on an alpha-blended surface, and the
pipeline neither detects nor compensates for that. A transparent material
therefore exports a black roughness map — a mirror finish in RealityKit —
or, under `AVERAGE`, `inputs:roughness = 0`. This is independent of the
opacity pass. What to do: set the roughness on the exported material by
hand, or avoid `LIT_ALBEDO` roughness for alpha-blended materials.

*Verification: one material with constant `Roughness = 0.5` on one cube
under `--roughness-mode AVERAGE` exported `inputs:roughness = 0.3372549` at
`--margin 0`, `0.4074238` at the default margin `8`, and `0.50109625` at
`--margin 32` — at the default margin the exported constant is 18.5 % below
the material's actual roughness. Two materials identical except for `Alpha`,
both with `Roughness = 0.5`: the opaque one baked `R[0.0000, 0.5020]`, the
`Alpha = 0.4` one baked `R[0.0000, 0.0000]`; under `--roughness-mode
AVERAGE` the same material exported `inputs:roughness = 0`, and the
`--no-opacity` run measured the same zeros.*

### 3.11 Flat materials are never baked

`_flat_material_constants` (`bake_textures.py:1214-1284`) classifies a
material as *flat* when nothing texture-varying feeds its surface: no
`TEX_IMAGE` node anywhere in the tree, and an unlinked Principled
`Base Color`. A non-node material is always flat and reads its legacy
`diffuse_color`.

Flat materials skip the bake entirely. Their constants — base color,
roughness, metallic, alpha — are authored directly onto the rebuilt material
(`bake_textures.py:1719-1745`), which both avoids burning a constant into a
full-resolution texture and avoids the all-black texture a flat-colored mesh
with no real UV unwrap would otherwise produce. A 4×4 throwaway bake target
is still attached, because `bpy.ops.object.bake` errors on any slot without
an active image node (`bake_textures.py:393-414`).

Disqualifiers, so variation is never collapsed to a Principled default:

- a **linked `Alpha`** always forces a real bake (procedural transparency);
- under `LIT_ALBEDO` only, a linked **`Roughness`** or **`Metallic`** also
  forces a real bake (`bake_textures.py:1266-1273`).

**`LIT_IBL` never short-circuits flat materials**
(`bake_textures.py:180-185`) — it must record lighting and shadows on
flat-colored surfaces too.

*Verification: a `(0, 0.25, 0.75)` flat material produced no texture under
`LIT_ALBEDO`/`UNLIT_ALBEDO` and exported
`inputs:diffuseColor = (0, 0.25, 0.75)`, `inputs:roughness = 0.33`,
`inputs:metallic = 0`. The same material under `LIT_IBL` produced a full
2048×2048 baked texture.*

### 3.12 Material rebuild, naming, and render method

Each source material is **copied** and the copy is renamed
`<source>_Baked`, uniquified against `bpy.data.materials`
(`bake_textures.py:344-355`). Any existing trailing `_Baked(_N)` run is
stripped first so a re-bake of a baked material yields `<base>_Baked` rather
than `Marble_Baked_Baked_Baked` (`bake_textures.py:1982-1997`).

The copy's node tree is then **cleared and rebuilt from scratch**
(`bake_textures.py:1713`) as one `Principled BSDF` → `Material Output`.
Nothing in the source graph survives except what §3.6 lists as baked or
passed through. This is why §3.6's validation matters: anything not on that
list is gone.

Non-node source materials get a minimal node tree seeded from
`diffuse_color` (`bake_textures.py:1622-1635`).

`surface_render_method` is decided, not copied
(`bake_textures.py:1553-1566`): an opaque baked material is always
`DITHERED` with alpha fixed to one; a transparent one preserves the source's
`DITHERED` vs `BLENDED` choice. Any other value raises — this release
targets Blender 5.2 only.

### 3.13 Cache key for shared bakes

Two slots that hash to the same key reuse one baked material with no copy
and no re-bake, which is what lets the USD exporter emit instanceable
references. The key is (`bake_textures.py:1041-1079`):

`(source_material.name_full, mesh_datablock_id, resolution, uv_layer, bake_mode, bake_base, use_opacity, bake_roughness_map, roughness_single, is_flat)`

Notes:

- `name_full` includes the library suffix, so a local and a linked material
  with the same short name cannot collide.
- The **mesh datablock identity** is part of the key, via `session_uid` (or
  `as_pointer()`), never `id()` — `obj.data` returns a transient wrapper
  whose address is reused (`bake_textures.py:274-284`). A baked texture is
  tied to a UV layout, so two objects sharing a material but not a mesh must
  not share a bake.
- A cache hit requires **every** slot on the object to be already baked
  (`bake_textures.py:315-316`).
- The cache is disabled entirely under `LIT_IBL` (`bake_textures.py:256`) —
  see §2.
- The cache lives for one bake run only. There is no on-disk cache; every
  export re-bakes.

### 3.14 Output file naming and pruning

Baked files are written to the export's private staging directory — the
temporary directory where the export is assembled — as
`<object>__<material>_<suffix><ext>`, with unsafe characters replaced and a
numeric suffix on collision (`bake_textures.py:1950-1970`). They are then
staged into the published `textures/` tree under content-addressed names,
and any baked file the final USD does not reference is deleted
(`bake_export.py:602-612`, `usd_textures.py:271-283`).

Two consequences: identical bakes deduplicate to one file, and a bake whose
material never reaches the USD leaves nothing behind.

---

## 4. Failure modes and what you see

| Situation | Behavior | Where |
|---|---|---|
| A mesh has **no UV map** | Hard failure before that mesh is baked; every already-baked slot rolled back | `bake_textures.py:263-266` |
| Active surface is **not one directly connected Principled BSDF** | Hard failure *before* any material is touched | `bake_textures.py:1287-1319` |
| **Emission / coat / specular-IOR** active under `LIT_ALBEDO` | Hard failure | `bake_textures.py:1333-1377` |
| Normal or metallic chain the passthrough cannot reproduce | Hard failure | `bake_textures.py:1380-1385` |
| **No exportable objects** | `NO_EXPORTABLE_OBJECTS`; diagnostics written | `bake_export.py:374-381` |
| **Missing external images** | `MISSING_EXTERNAL_TEXTURES` / `MISSING_EXTERNAL_ASSETS` before any baking | `bake_export.py:387-400` |
| An object with **no material slots** | Silently skipped; exports unmaterialed | `bake_textures.py:203-205` |
| `LIT_IBL` with **`HDRI_FILE` and no path** | Hard failure: *"Bake mode is 'Lighting & Shadows' but no HDRI file is set."* | `bake_textures.py:766-768` |
| `LIT_IBL` with a `//`-relative HDRI in a **never-saved** `.blend` | Hard failure with an actionable message | `bake_textures.py:778-783` |
| `LIT_IBL` with **`SCENE_WORLD` and no world/lights** | **Succeeds**, exports a fully black texture, no warning | `bake_textures.py:718-723` |
| Step exceeds `--step-timeout` | `BAKE_STEP_TIMEOUT`, worker terminated, exit 124 | `bake_export.py:435-499` |
| Background worker dies | Watcher writes `state: error`, *"Background job exited unexpectedly."* | `bake_export_operator.py:490-504` |
| Blender exits mid-job | Exit handler writes *"Blender exited before the bake/export job finished."* | `bake_export_runner.py:126-149` |
| User cancels a background job | `SIGTERM`, then `SIGKILL` after 2 s; `state: canceled` | `bake_export_operator.py:583-598`, `400-406` |

Representative messages from real runs:

```
Bake failed: 'NoUV_D' has no UV map.
```

```
Bake Textures cannot preserve material 'M' because its active surface is
MIX_SHADER, not one directly connected Principled BSDF. Shader mixes (including
Transparent BSDF fallbacks) require an explicit opacity bake that this pipeline
does not provide. Use Export Scene or simplify the active surface before baking.
```

```
Bake/export step 'Step 1/6 - Baking lighting and shadows [1/5] - Textured_A'
timed out after 5s; the Blender worker was terminated.
```

Every failure writes `<output>.diagnostics.json` regardless of the
`diagnostics_enabled` preference; that preference only controls whether a
*successful* run keeps its sidecar (`bake_export.py:344-351`).

*Verification: the messages above were produced by real runs. The
black-world case: a scene with `scene.world = None`, no lights, and
`--bake-mode LIT_IBL` returned `ok: true` and staged one 2048×2048 texture
measuring `R[0.0000, 0.0000]`, mean `0.0000` — entirely black, with no
warning in the response or diagnostics.*

---

## 5. Foreground vs background execution

There are two execution paths and they are not interchangeable.

| | CLI `bake-export` | Sidebar Export button |
|---|---|---|
| Entry point | `Plugin/api/commands/bake_export.py` | `Plugin/ops/bake_export_operator.py` → `Plugin/bake_export_runner.py` |
| Runs in | the Blender process the CLI spawned | a **second** Blender process |
| Scene | the `.blend` you named | a disposable copy of your in-memory scene |
| Blocks | yes | no — the sidebar stays interactive |
| Result | JSON envelope on stdout | `status.json` polled by a modal watcher |

### The background job

The operator snapshots the live scene with
`wm.save_as_mainfile(copy=True, relative_remap=True)` into a private job
directory (`bake_export_operator.py:761-815`), verifies the active file and
dirty state were not disturbed, then launches:

```
blender --background --factory-startup <snapshot>.blend \
        --python bake_export_runner.py -- <settings.json>
```

(`bake_export_operator.py:303-318`). `--factory-startup` keeps unrelated
user add-ons out of the bake session.

Two preflights fail *before* a worker is launched, so a missing source
cannot turn into a successful-but-incomplete bake: unsaved (dirty) image
buffers, which `Save Copy` does not serialize
(`bake_export_operator.py:775-784`), and missing external image dependencies
across the whole processing closure (`bake_export_operator.py:199-224`).

The worker deletes the snapshot as soon as Blender has loaded it, after
verifying the loaded path is exactly the expected `scene_snapshot.blend`
(`bake_export_runner.py:68-123`).

### Status protocol

`<export dir>/.blendertorcp_jobs/bake_export_<YYYYmmdd_HHMMSS>_<random>/`
(`bake_export_operator.py:750-755`) holds:

| File | Contents |
|---|---|
| `settings.json` | the serialized payload handed to the worker |
| `status.json` | the live state, rewritten atomically via a temp file + `os.replace` |
| `log.txt` | the worker's combined stdout and stderr |
| `scene_snapshot.blend` | deleted by the worker on load |

`status.json` carries `state` ∈
`{queued, running, done, error, canceled}`, `progress` (0.0–1.0),
`message`, `pid`, `time`, `log_path`, `export_path`, `diagnostics_path`, and
on a timeout also `step_elapsed_seconds`, `error_code`, `stage`,
`timeout_seconds` (`bake_export_runner.py:151-202`).

A heartbeat thread rewrites `running` status once a second, appending an
elapsed counter and animated dots to the current step label
(`bake_export_runner.py:279-311`). Progress is banded: 0.02 loading settings
(`bake_export_runner.py:385-393`), then 0.10 preparing, 0.15–0.50 baking,
0.50 exporting USD, 0.70 rewriting materials, 0.85 packaging, 0.95
diagnostics, 0.98 restoring (`bake_export_runner.py:646`, `682-790`).

The panel's job monitor renders that file: a progress bar labeled with the
worker's step message, **Open Log** and **Open Diagnostics** buttons, and —
while `state` is `queued` or `running` — every other setting in the sidebar
is disabled (`panel.py:645-707`, `panel.py:616`, `728`, `805`).

### Canceling

The **✕** button in the job monitor runs
`blendertorcp.cancel_bake_export` (`panel.py:657`): `SIGTERM`, then
`SIGKILL` after a 2 s grace period (`bake_export_operator.py:583-598`), then
it writes `state: canceled` and clears the job state. A job whose recorded
PID no longer matches, or is no longer running, is cleared as stale rather
than signaled (`bake_export_operator.py:383-398`). Because the bake runs on
a *copy*, canceling cannot leave your scene half-baked.

A modal watcher polls every 0.5 s (`bake_export_operator.py:450-457`). If
the worker's PID disappears without a terminal status it writes one itself
(`bake_export_operator.py:490-504`). If `bake_step_timeout_seconds` is set
and the worker has not exited within a 15 s grace period past its own
deadline, the watcher terminates it — after re-reading `status.json` so a
terminal worker status wins the race (`bake_export_operator.py:506-538`).

### Settings that do not cross the process boundary

`_serialize_settings` (`bake_export_operator.py:714-747`) copies every RNA
property except `_SERIALIZED_SETTINGS_SKIP_KEYS`
(`bake_export_operator.py:31-43`), which excludes the three `ui_*` routing
enums — the route is already collapsed into `bake_mode` — plus `filepath`
and the job bookkeeping fields. It forces
`export_texture_settings_enabled = True` (§3.3) and resolves a
`//`-relative bake HDRI to an absolute path **while your original `.blend`
is still active**, because the worker loads its copy from the job directory
(`bake_export_operator.py:733-746`).

Consequences worth knowing:

- **`bake_keep_materials` does nothing from the sidebar.** The bake happens
  in a separate process against a scene copy; that process exits. Your
  session's materials are never touched. The setting is still drawn in the
  Advanced panel (`panel.py:782`).
- **`bake_step_timeout_seconds` has no UI control.** It is a real setting
  (`panel.py:434-440`) but is never drawn, so from the sidebar it is
  whatever the CLI or preferences last persisted — by default `0`, meaning
  no per-step timeout.

For the in-process CLI path, `bake_keep_materials` *does* keep the baked
materials assigned (`bake_export.py:758-765`). **Known limitation:** each
retained image's `filepath_raw` points into the staging directory, which is
deleted during cleanup, so the pixels survive only in memory. What to do:
pack the images (`File ▸ External Data ▸ Pack Resources`) before saving.

*Verification: after a CLI run with `keep_materials`, `bpy.data` held 3
extra materials and 4 extra images and every slot pointed at a `*_Baked`
material — but `os.path.exists()` on all four retained images' paths
returned `False`, because they pointed into the deleted staging directory.*

---

## 6. Diagnostics

The `bake` block of `<output>.diagnostics.json` records the resolved
decisions (`bake_export.py:522-534`):

```json
{
  "mode": "LIT_ALBEDO",
  "resolution": 0,
  "image_format": "AVIF",
  "margin": 8,
  "base_color": true,
  "opacity": true,
  "isolate_meshes_lit": false,
  "texture_settings_enabled": false,
  "object_count": 5,
  "native_export_object_count": 5,
  "texture_dir": "…/.blendertorcp_temp/s.usda.<id>/textures"
}
```

`"resolution": 0` is the source-keyed sentinel (§3.3). Every baked file is
also listed under `generated_files` with the role `baked_base_color`,
`baked_roughness`, or `baked_opacity` plus its object and **source**
material name (`bake_textures.py:467-473`, `559-565`, `640-646`).

Source material graph validation is deliberately skipped for bake/export and
the reason is recorded in the report (`bake_export.py:362-366`): baking
resolves node groups that strict translation would reject. Strict validation
remains part of `blendertorcp export` and `blendertorcp validate`.
