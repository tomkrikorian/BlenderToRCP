# Material Translation

How a Blender 5.2 material becomes a RealityKit MaterialX ShaderGraph.

This document describes what the exporter actually does, including the places where it
substitutes, infers, or drops something on your behalf. Every behavioural claim cites the
line that implements it. Where a claim was confirmed by running Blender 5.2, the
observation is quoted.

Audience: technical artists who need to predict the output, and to know which Blender
controls survive the trip.

Related: [ARCHITECTURE.MD](ARCHITECTURE.MD) for the export pipeline as a whole,
[CLI.md](CLI.md) for the commands referenced here.

## Contents

1. [The pipeline](#1-the-pipeline)
2. [Surface profiles](#2-surface-profiles)
3. [Decisions the exporter makes for you](#3-decisions-the-exporter-makes-for-you)
4. [Node coverage](#4-node-coverage)
5. [The texture pipeline](#5-the-texture-pipeline)
6. [Diagnostic and error reference](#6-diagnostic-and-error-reference)

---

## 1. The pipeline

A material crosses five gates. Each can stop the export; each stops it in a different way
and with a different error shape.

| # | Stage | Code | Runs on | Failure mode |
|---|-------|------|---------|--------------|
| 1 | Validate | `Plugin/nodes/validate.py` | Blender node tree | `UNSUPPORTED_MATERIAL_NODES`, before any USD is written |
| 2 | Extract | `Plugin/export/materials/extract/core.py` | Blender node tree | recorded per material, batched into one `RuntimeError` |
| 3 | Build graph | `Plugin/export/materials/graph.py` | extracted payload | recorded per material, batched |
| 4 | Author USD | `Plugin/export/materials/author.py`, `textures.py` | USD stage | recorded per material, batched, stage rolled back |
| 5 | Preflight | `Plugin/export/realitykit_preflight.py` | composed USD stage | `RuntimeError` listing preflight issue codes |

Stages 2-4 run inside `rewrite_materials`
(`Plugin/export/materials/rewrite.py:20`), which is step 4 of `process_usd_stage`
(`Plugin/export/postprocess_usd.py:68`). Preflight is the last step before
`stage.Save()` (`Plugin/export/postprocess_usd.py:96-108`).

### 1.1 Validate

`validate_material` (`Plugin/nodes/validate.py:448`) walks the nodes that actually
contribute to the active Material Output and classifies each one. It also checks
Principled inputs against the selected surface profile
(`Plugin/nodes/validate.py:220`) and enforces RealityKit's one-texture-transform-per-material
rule (`Plugin/nodes/validate.py:484-511`).

**Every production caller passes `strict=True`.** The export gate
(`Plugin/api/commands/export.py:216-222`), the `validate` CLI command
(`Plugin/api/commands/validate.py:76-81`), the Shader Editor panel
(`Plugin/ui/shader_panel.py:67`), the validation operators
(`Plugin/ops/validation_operators.py:57`, `:86`, `:112`), the support bundle
(`Plugin/export/support_bundle.py:219`), and the background bake runner
(`Plugin/bake_export_runner.py:701`, `:800`) all use it. Under `strict=True` most
warnings are promoted to errors, so `blendertorcp validate` is a faithful preview of the
export gate rather than a softer check. The `strict=False` default in the function
signature is not reachable from any shipped surface.

On failure the CLI returns:

```json
{"ok": false, "error": {"code": "UNSUPPORTED_MATERIAL_NODES",
 "stage": "validation", "details": [{"node_name": "...", "node_type": "...", "message": "..."}]}}
```

### 1.2 Extract

`extract_blender_material_data` (`Plugin/export/materials/extract/core.py:132`)
reduces the node tree to a flat dictionary plus an `input_graphs` map of expression trees
for anything that could not be flattened to a constant or a single texture.

It classifies the material into one of five `type` values, which decide the graph built in
stage 3 (`Plugin/export/materials/rewrite.py:263-282`):

| `type` | Trigger | Graph built |
|--------|---------|-------------|
| `simple` | `use_nodes == False` | **Unlit** |
| `principled` | active output drives a Principled BSDF | PBR, per profile |
| `emission` | active output drives an Emission node | **Unlit** |
| `rk_group` | active output drives an `RK_*` nodegroup | that RealityKit nodedef |
| `rk_graph` | a pre-built RealityKit node graph | passed through |

Only the shader wired to the **active** Material Output contributes
(`Plugin/export/materials/extract/core.py:83-85`, `:450-456`). A disconnected Principled
node cannot make an opaque material transparent, and an orphan Emission node never
replaces an unsupported active shader.

`collect_material_warnings` (`Plugin/export/materials/extract/core.py:559`) runs
alongside and emits advisory strings into diagnostics
(`Plugin/export/materials/rewrite.py:105-108`). These are *not* fatal. See
[section 4.4](#44-the-three-lists-disagree) — this table has drifted from the validator's.

A material whose `input_graphs` contain anything the resolver could not translate exactly
is rejected: `unresolved_warnings` become a per-material failure
(`Plugin/export/materials/rewrite.py:136-149`) with the message
`Material graph contains unresolved input(s): ...`.

### 1.3 Build graph

`MaterialXGraphBuilder` (`Plugin/export/materials/graph.py:61`) selects the surface
nodedef, maps Blender parameter names onto MaterialX input names, and filters out
everything the chosen surface cannot carry. It emits a nested `{nodes, connections,
output, surface_profile, materialx_version}` structure — still no USD.

`require_realitykit_mapping_contract` (`Plugin/export/materials/mapping.py:232`) then
rejects graphs needing more than one distinct 2D texture transform.

### 1.4 Author USD

`create_materialx_material` (`Plugin/export/materials/author.py:34`) turns the graph
into `UsdShade.Shader` prims under the existing `Material` prim, inserting `convert`,
`swizzle`, `separate4`, `combine3`, `place2d`, and normal-decode nodes as needed.

Authoring is transactional. Every material is resolved, validated, extracted, and built
**before** the stage receives its first MaterialX opinion
(`Plugin/export/materials/rewrite.py:84-91`); the edit layer is backed up
(`:203-206`) and restored if any authoring call fails (`:241-249`). A partially converted
stage is never saved.

The original `material:binding` is deliberately left alone
(`Plugin/export/materials/rewrite.py:257-261`): the MaterialX surface is authored at the
same prim path, so rebinding would author a stronger relationship outside the variant edit
context and override inactive variant selections.

Colour-space failures surface here, not earlier. Verified by running Blender 5.2 on a cube
whose Principled `Roughness` was driven by an image tagged `sRGB`:

```
"code": "EXPORT_FAILED",
"message": "MaterialX rewrite failed for 1 used material(s):
 - MatSRGBData (/root/_materials/MatSRGBData): MaterialX authoring failed:
   Data texture 'roughness' must use Blender Non-Color/raw, not 'srgb'"
```

`blendertorcp validate` on the same file reported `"ok": true, "error_count": 0,
"warning_count": 0`.

### 1.5 Preflight

`validate_stage` (`Plugin/export/realitykit_preflight.py:227`) inspects the **composed
USD stage**, not the Blender graph. It never imports `bpy`. It re-runs its whole check set
once per reachable variant combination, up to `MAX_VARIANT_COMBINATIONS = 256`
(`Plugin/export/realitykit_preflight.py:36`, walk at `:319-388`).

It returns a report; the caller decides. `_require_realitykit_preflight`
(`Plugin/export/postprocess_usd.py:171-185`) raises whenever `report.errors` is non-empty,
previewing the first five issues. Severity semantics:

- `error` — hard abort, stage never saved.
- `warning` — forwarded to `diagnostics.data["warnings"]` (`:1697-1700`).
- `info` — **only** in the `realitykit_preflight` diagnostics payload. `_record_diagnostics`
  forwards errors and warnings only (`:1693-1700`), so info findings never reach the UI
  report or the CLI message.

**There is no suppression, allowlist, or lenient mode.** The two strictness flags
`require_lightmap_uv` (`:844`) and `require_accessibility_metadata` (`:1619`) are read with
`getattr(..., False)` and are defined nowhere else in the codebase — no property, no
settings key, no CLI flag. They are permanently `False`, and they would *increase*
strictness, not bypass it.

Preflight is **profile-blind**. `materialx_surface_profile` is never read in that module.
The `"profile"` field in its report is the constant `TARGET_PROFILE = "RealityKit-AppleOS27"`
(`:28`, `:176`) — an Apple OS target label, not the MaterialX surface profile.

Material-relevant preflight codes:

| Code | Severity | Meaning |
|------|----------|---------|
| `TEXTURE_COLOR_SPACE_MISMATCH` | error | perceptual-colour texture not sRGB/lin_rec709 (`:1394-1407`), or data texture not raw (`:1408-1418`) |
| `TEXTURE_COLOR_ROLES_CONFLICT` | error | one texture feeds both a colour and a data input (`:1386-1393`) |
| `TEXTURE_COLOR_ROLE_UNRESOLVED` | info | role could not be inferred (`:1419-1426`) |
| `TEXTURE_ASSET_MISSING` | error | dependency does not resolve after staging (`:1374-1381`) |
| `USDZ_TEXTURE_FORMAT_UNSUPPORTED` | error | not JPEG/PNG/EXR/AVIF (`:1356-1364`) |
| `USDZ_TEXTURE_PATH_EXTERNAL` | error | texture path not localized and relative (`:1365-1372`) |
| `MATERIAL_TEXTURE_TRANSFORM_CONFLICT` | error | more than one distinct 2D transform (`:1082-1102`) |
| `TEXTURE_TRANSFORM_UNINSPECTABLE` | error | connected or time-sampled transform inputs (`:1063-1078`) |
| `MATERIAL_BINDING_API_MISSING` | error | binding authored without `MaterialBindingAPI` (`:997-1001`) |
| `MATERIAL_BINDING_INVALID` | error | binding does not resolve to a Material (`:1003-1010`) |

The full preflight code set also covers stage metadata, prim types, meshes, and skeletons;
those are outside material translation.

---

## 2. Surface profiles

The profile picks which MaterialX surface nodedef the graph terminates in, and therefore
which Blender controls can survive at all.

| Profile | Nodedef | MaterialX | Status |
|---------|---------|-----------|--------|
| `realitykit_portable` | `ND_realitykit_pbr_surfaceshader` | 1.38 | **Shipping default** |
| `realitykit_pbr2` | `ND_realitykit_pbr_surfaceshader_2_0` | 1.38 | Experimental |
| `openpbr_1_1` | `ND_open_pbr_surface_surfaceshader` | 1.39 | Experimental |
| *(unlit)* | `realitykit_unlit_surfaceshader` | 1.38 | Not selectable directly — see 2.2 |

Constants at `Plugin/export/materials/graph.py:12-18`; selection at
`_select_surface_profile` (`Plugin/export/materials/graph.py:257-286`).

### 2.1 What selects it

`materialx_surface_profile`, a scene property (`Plugin/ui/panel.py:244-265`), default
`realitykit_portable` (`Plugin/api/commands/_settings_common.py:26`).

- **Blender UI**: *Surface Profile* enum, labelled "RealityKit PBR (Recommended)",
  "RealityKit PBR Surface 2 (Experimental)", "OpenPBR 1.1 / MaterialX 1.39 (Experimental)".
- **CLI**: `--materialx-surface-profile` (`Plugin/cli/__main__.py:427`) or a setting
  override; accepted values are exactly those three (`Plugin/api/commands/_settings_common.py:28-31`).

Selection is strict. An unknown value raises `Unknown MaterialX surface profile`
(`:280`). A profile whose nodedef is missing from the bundled manifest raises rather than
falling back — explicitly, *"refusing to switch shading models silently"* (`:283-286`).

Choosing `realitykit_pbr2` adds a standing diagnostics warning
(`Plugin/export/materials/graph.py:20-23`, emitted at
`Plugin/export/materials/rewrite.py:28-30`):

> RealityKit PBR Surface 2 is experimental. Mandatory strict USD/USDZ validation remains
> enabled for this profile.

`openpbr_1_1` gets no such standing warning.

### 2.2 Unlit

Unlit is never chosen by the profile enum. Two independent things produce it:

1. **Material shape.** `type` of `simple` or `emission` always builds an unlit graph,
   whatever the profile is (`Plugin/export/materials/rewrite.py:273-274`). A material with
   `use_nodes` off, or one whose active output is an Emission node, silently becomes an
   unlit RealityKit material.
2. **`force_unlit_materials`.** A `HIDDEN` scene property
   (`Plugin/ui/panel.py:524-530`) that no panel exposes. It is set only by the bake
   pipeline, from `bake_mode` (`Plugin/export/bake_finalize.py:10-22`):
   `LIT_ALBEDO` → PBR; `UNLIT_ALBEDO` and `LIT_IBL` → unlit, the latter because Blender
   lighting is already burned into the baked texels.

The artist-facing mapping lives in `Plugin/export_profile.py:33-52`: *Material Type*
→ RealityKit PBR (translate or bake) or RealityKit Unlit (material colour, or lighting +
shadows).

The unlit surface carries only `color`, `opacity`, `opacityThreshold`, and
`hasPremultipliedAlpha` (`Plugin/export/materials/graph.py:996-1039`). Linked
expression graphs are filtered against the **nodedef's declared inputs** rather than a
hard-coded list (`:963-994`), with a warning naming what was dropped.

### 2.3 What each profile carries

`realitykit_pbr2` is the superset the other two are derived from
(`_map_realitykit_pbr2_inputs`, `Plugin/export/materials/graph.py:433-594`).

| Blender Principled input | pbr2 | portable | openpbr_1_1 |
|---|---|---|---|
| Base Color | `baseColor` | `baseColor` | `base_color` |
| Metallic | `metallic` | `metallic` | `base_metalness` |
| Roughness | `roughness` | `roughness` | `specular_roughness` |
| Normal | `normal` | `normal` | `geometry_normal` |
| Emission Color × Strength | `emissiveColor` | `emissiveColor` | `emission_color` |
| Alpha | `opacity` | `opacity` | `geometry_opacity` |
| (cutout threshold) | `opacityThreshold` | `opacityThreshold` | **raises** |
| AO (baked) | `ambientOcclusion` | `ambientOcclusion` | — |
| Specular IOR Level | `specular` | `specular` | `specular_weight` (×2) |
| Coat Weight / Roughness / Normal | `clearcoat*` | `clearcoat*` | `coat_weight`, `coat_roughness`, `geometry_coat_normal` |
| Coat IOR | `clearcoatIOR` | **dropped** | `coat_ior` |
| Coat Tint | — | **dropped** | `coat_color` |
| IOR | `specularIOR` | **dropped** | `specular_ior` |
| Specular Tint | `specularColor` | **dropped** | `specular_color` |
| Diffuse Roughness | `baseDiffuseRoughness` | **dropped** | `base_diffuse_roughness` |
| Subsurface Weight / Radius / Scale / Anisotropy | `subsurface*` | **dropped** | `subsurface_*` |
| Sheen Weight / Tint | `sheenColor` (combined) | **dropped** | `fuzz_weight`, `fuzz_color` |
| Sheen Roughness | **warns, dropped** | **dropped** | `fuzz_roughness` |
| Anisotropic / Rotation | `specularAnisotropy*` | **dropped** | `specular_roughness_anisotropy` only |
| Premultiplied alpha | `hasPremultipliedAlpha` | `hasPremultipliedAlpha` | — |

Portable's allowlist is the 13 names at `Plugin/export/materials/graph.py:599-613`.
OpenPBR's rename table is at `:620-642` and `:818-839`.

**Practical consequence.** Under the default portable profile, most of the "dropped" column
never reaches the graph builder at all: the strict validator rejects the export first with
an actionable message. Verified by exporting a cube whose Principled had `IOR = 1.45` and
`Sheen Weight = 0.3`:

```
Principled 'IOR' is active, but the RealityKit Portable profile does not export it;
  select RealityKit PBR Surface 2 or OpenPBR 1.1 or bake the material.
Principled 'Sheen Weight' is active, but the RealityKit Portable profile does not export it;
  select RealityKit PBR Surface 2 or OpenPBR 1.1 or bake the material.
```

The neutral values that make an input "inactive" are listed in
`_PORTABLE_OMITTED_PRINCIPLED_INPUTS` (`Plugin/nodes/validate.py:147-185`) — note
`IOR` neutral is `1.5`, `Sheen Roughness` neutral is `0.5`, `Subsurface Scale` neutral is
`0.005`.

---

## 3. Decisions the exporter makes for you

This is the section to read before you file a bug. Each entry names the trigger, the
substitution, whether you are told, and how to control it.

Legend for **Told?**: **Error** = export stops; **Warning** = diagnostics + UI/CLI
warning; **Info** = diagnostics sidecar only; **Silent** = no record anywhere.

### 3.1 Colour space

| Trigger | What happens | Told? | Control |
|---|---|---|---|
| Colour input, image tagged **Non-Color/Raw** | authored `lin_rec709` | **Warning** | retag the image, or accept |
| Colour input, image tagged **sRGB** or untagged | authored `srgb_texture` | — | — |
| Colour input, image tagged **Linear Rec.709** | authored `lin_rec709` | — | — |
| Data input, image tagged **Non-Color/Raw** | authored `raw` | — | — |
| Data input, image tagged **sRGB/lin_rec709** | **export fails** | **Error** | retag the image `Non-Color` |
| Data input, **alpha channel**, any tagging | forced `raw` | **Silent** | — |
| Any input, colour space outside the verified set | **export fails** | **Error** | retag to sRGB / Non-Color / Linear Rec.709 |
| Baked AO texture | forced `Non-Color` | **Silent** | — |

Roles come from `texture_colorspace_role` (`Plugin/export/materials/graph.py:41-50`):
`color` for the twelve names at `:25-38` (`baseColor`, `emissiveColor`, `subsurfaceColor`,
`sheenColor`, `specularColor`, `coat_color`, `fuzz_color`, and the snake_case variants),
`data` for everything else. Normal maps are forced to `data`
(`Plugin/export/materials/graph.py:1094-1098`).

The Blender token is first normalized by `_normalize_colorspace`
(`Plugin/export/materials/extract/core.py:2898-2917`) to one of `srgb`, `raw`,
`lin_rec709`, or `unsupported:<name>`. The MaterialX token is then chosen by
`_materialx_file_colorspace` (`Plugin/export/materials/textures.py:354-412`) and written
with `SetColorSpace` (`:161-163`).

**Non-Color on a colour input** is the one place the exporter deliberately overrides you,
and the code explains why (`Plugin/export/materials/textures.py:399-404`): Blender applies
no transfer function to a Non-Color image, so a colour input reads its texels as
scene-linear. MaterialX has no `raw` contract for colour and RealityKit rejects the token,
so the exporter names the pass-through Blender actually performs. Telling you to retag as
sRGB would introduce a decode Blender never applied.

> Verified on Blender 5.2. A cube with a Non-Color image on Base Color produced the
> warning `Non-Color image on perceptual color input 'baseColor' exported as lin_rec709
> (already-linear scene color).` — **but the export still failed**, because the retained
> native `UsdPreviewSurface` network carries Blender's own `colorSpace:name = "data"`.
> See [defect note](#note-non-color-base-colour-currently-cannot-export).

`AO` textures authored by the bake path are force-tagged `'Non-Color'` regardless of the
file's actual tagging (`Plugin/export/materials/extract/core.py:304`).

The material prim and the stage root both get `ColorSpaceAPI` with
`colorSpace:name = "lin_rec709_scene"` (`Plugin/export/materials/author.py:288-316`).

#### Note: Non-Color base colour currently cannot export

Measured on Blender 5.2 at commit `35354bb`. The MaterialX graph is authored correctly
(`colorSpace = "lin_rec709"`), but the exporter leaves Blender's native
`UsdPreviewSurface` network in place alongside it, and Blender's own USD exporter writes
`colorSpace:name = "data"` on that reader. Preflight's role inference sees a texture
feeding `diffuseColor` with a data colour space and fails:

```
[TEXTURE_COLOR_SPACE_MISMATCH] /root/_materials/MatNonColorBase/Image_Texture:
  Base, emissive, and other perceptual color textures must use an authored sRGB or
  linear Rec.709 color space.   details: {"actual": "data"}
```

`Image_Texture` is Blender's naming; the exporter names its own readers `Image`, `Image_1`,
… (`Plugin/export/materials/helpers.py:111-119`). Workaround: tag the image `sRGB`.

### 3.2 Profile-driven drops

| Trigger | What happens | Told? | Control |
|---|---|---|---|
| Portable profile, PBR2-only **constant** (IOR, Specular Tint, subsurface, sheen, anisotropy, Coat IOR/Tint, Diffuse Roughness) | dropped from the surface | **Error** from the validator; **Silent** in the graph builder | switch profile, or bake |
| Portable profile, PBR2-only **linked** input | dropped | **Warning**: `Portable RealityKit material profile omitted PBR2-only inputs: ...` | switch profile, or bake |
| Portable profile, linked sheen | dropped | **Warning**: `Portable RealityKit material profile omitted linked sheen controls.` | switch profile |
| OpenPBR, input the surface does not declare | dropped | **Warning**, naming each | bake |
| OpenPBR, `opacityThreshold` present | **export fails** | **Error** | clear `blender_to_rcp_alpha_cutout_threshold`, or use a RealityKit profile |
| OpenPBR, non-tangent normal map | **export fails** | **Error** | bake a tangent-space normal map |
| PBR2, Sheen Roughness linked | dropped | **Warning** | select OpenPBR 1.1, or bake |
| Unlit surface, any PBR input | dropped | **Warning**, naming each | — |

The asymmetry in the first row is worth internalising. `_map_realitykit_portable_inputs`
(`Plugin/export/materials/graph.py:596-614`) filters with a bare dict comprehension and
emits **no diagnostic** for what it removed — unlike the OpenPBR path (`:714-718`) and the
unlit path (`:989-993`), which both warn. Your protection is the earlier strict validator
message (`Plugin/nodes/validate.py:347-350`). If you reach the graph builder by another
route, the drop is silent.

The OpenPBR omission report (`:674-718`) checks against the **nodedef's declared inputs**
rather than a second hard-coded list, specifically so the two cannot drift. It also
verifies that `specular` and `sheenColor`, which are absent from the rename table, really
did arrive under their substitute names `specular_weight` and `fuzz_weight`.

The OpenPBR cutout refusal (`:690-695`) is deliberate: OpenPBR has no clip, so carrying on
would ship alpha blending in place of the rendering model you asked for.

### 3.3 Opacity, transparency, and cutout

| Trigger | What happens | Told? |
|---|---|---|
| Principled `Alpha` linked, or constant `< 0.999` | material treated as transparent | **Silent** |
| Material not transparent | `opacity` is not authored at all | **Silent** |
| Transparent, and `blender_to_rcp_alpha_cutout_threshold` is a finite float in `[0,1]` | `opacityThreshold` authored → **cutout** | **Silent** |
| Anything else | no threshold → **blend** | **Silent** |
| Base Color mixes `premul` and straight textures | **export fails** | **Error** |
| Base Color textures are all `premul` | `hasPremultipliedAlpha = true` | **Silent** |
| Premultiplied base colour + AVIF encode/resize | **export fails** | **Error** |

`material_has_transparency` (`Plugin/export/materials/extract/core.py:60-94`) reads the
actual `Alpha` input, not the render method. The docstring is explicit: Blender 5.2's
`surface_render_method` chooses *how* Eevee renders transparency, not *whether* the surface
has any.

**Cutout is opt-in and never inferred.** Blender 5.2 exposes only `DITHERED` and `BLENDED`;
neither is a cutout declaration, so the exporter refuses to imply a hard threshold
(`opacity_threshold_from_material`, `:97-124`). A boolean flag is deliberately
insufficient — without a numeric threshold there is no complete cutout contract. Set the
custom property `blender_to_rcp_alpha_cutout_threshold` on the material to a float in
`[0, 1]` to get one. Out-of-range, non-finite, boolean, and non-numeric values are ignored
silently.

`hasPremultipliedAlpha` is a **material-level** flag in RealityKit, so the exporter derives
it from the closure of every texture feeding Base Color
(`_apply_base_color_texture_semantics`, `:2456-2494`). It is set only when the mode set is
exactly `["premul"]`. A mix is fatal (`Plugin/export/materials/rewrite.py:405-413`):

> RealityKit has one material-level hasPremultipliedAlpha flag. Bake Base Color and Alpha
> to one PNG, or make every contributing texture use the same straight-alpha convention.

A second gate refuses to let Blender 5.2's AVIF writer touch premultiplied base colour,
because that encoder does not preserve the premultiplied relationship
(`require_safe_texture_alpha_staging_policy`, `Plugin/export/usd_textures.py:730-774`). A
byte-for-byte `ORIGINAL` AVIF copy is still allowed, since no encoder runs.

### 3.4 Normal maps

| Trigger | What happens | Told? |
|---|---|---|
| Normal Map node, Strength ≈ 1.0, tangent space | `ND_normal_map_decode` (RealityKit's decoder) | **Silent** |
| Strength ≠ 1.0, or object space | generic `ND_normalmap` with explicit `scale`/`space` | **Silent** |
| OpenPBR profile | forced to `ND_normalmap` (`normal_decode = 'materialx'`) | **Silent** |
| OpenPBR + object-space normal | **export fails** | **Error** |
| PBR2 + non-default Strength | **export fails** (strict validator) | **Error** |
| PBR2 + non-tangent space | **export fails** (strict validator) | **Error** |
| Normal Map node with **linked** Strength | **export fails** (strict validator) | **Error** |
| Normal Map node set to **DirectX** convention | **export fails** (strict validator) | **Error** |
| Bump node anywhere in the chain | **export fails** (strict validator) | **Error** |

Decoder choice: `_can_use_realitykit_normal_map_decode`
(`Plugin/export/materials/textures.py:662-665`) and the branch at `:272-322`. The reader
itself is always authored `raw`/`vector3` (`_image_output_hint`, `:627-628`).

The DirectX check is `Plugin/nodes/validate.py:557-565`; RealityKit expects OpenGL green.
The PBR2 strength and space checks are `:580-607`, both justified by double-decoding.

The Bump case is worth calling out. `_resolve_socket_value` contains a branch that walks a
Bump node's `Height` input and returns it as if it were the normal
(`Plugin/export/materials/extract/core.py:1420-1431`). That would be wrong — a height map
is not a normal map. It never runs: `BUMP` is in the validator's `BAKE_TYPES`
(`Plugin/nodes/validate.py:65`) and every caller is strict, so the export is blocked first.

> Verified on Blender 5.2. A cube with `Image → Bump → Normal` was rejected with
> `UNSUPPORTED_MATERIAL_NODES`, `"node_type": "BUMP"`, `"Node requires baking for RealityKit."`

### 3.5 Specular and IOR

| Trigger | What happens | Told? |
|---|---|---|
| `Specular IOR Level` present | `specular_weight = clamp(value × 2, 0, ∞)` | **Silent** |
| `Specular IOR Level` linked | `specularWeight` = a `multiply` node × 2.0 | **Silent** |
| Constant achromatic Specular Tint > 1.0, **and** *Normalize Unsupported Values* on | clamped to `[1,1,1]` for this export only | **Warning**, prominent |
| Same, but the setting is off | **export fails** | **Error** |
| Coloured or linked overbright Specular Tint | **export fails** regardless of the setting | **Error** |
| Nothing sets `specular` | defaulted to `0.5` | **Silent** |

Blender's default `0.5` multiplier corresponds to PBR2 weight `1`
(`Plugin/export/materials/extract/core.py:279-281`, `:437-438`;
`Plugin/export/materials/graph.py:773`, `:784`).

The Specular Tint normalization is the exporter's only value rewrite, and it is
deliberately narrow. `safe_overbright_achromatic_specular_tint`
(`Plugin/material_policies.py:20-52`) accepts a constant only when it is finite,
achromatic, non-negative, and brighter than `1.0`. A linked value is never rewritten; a
coloured value requires artist judgement because a clamp would shift hue or saturation. The
operation is export-only and non-destructive — the module never assigns to Blender
datablocks (`Plugin/material_policies.py:1-6`), and the warning says so
(`:75-84`):

> Export-only normalization applied: Principled 'Specular Tint' [...] was clamped to
> [...]. The source Blender material and .blend file were not changed. Review the result
> in Reality Composer Pro.

Control: `normalize_unsupported_values`, *Normalize Unsupported Values*
(`Plugin/ui/panel.py:267-275`).

### 3.6 Emission

| Trigger | What happens | Told? |
|---|---|---|
| Emission Strength ≈ 1.0 | strength dropped entirely | **Silent** |
| Constant strength + emission **texture** | folded into the texture's `scale` | **Silent** |
| Constant strength + constant colour | multiplied into `emissiveColor` | **Silent** |
| Linked strength | `combine3` + `multiply` nodes inserted | **Silent** |
| OpenPBR | `emission_luminance = 1.0` forced, since strength is already in the colour | **Silent** |

`_scaled_color_expr` (`Plugin/export/materials/graph.py:888-914`), constant fold at
`:433-508`, OpenPBR at `:659-661` and `:114-119`.

### 3.7 Subsurface colour

If a subsurface weight is present but no subsurface colour is,
the exporter copies **Base Color** into `subsurfaceColor` / `subsurface_color`
(`Plugin/export/materials/graph.py:121-139`, and again at `:585-589`). Silent. Blender has
no separate subsurface colour input in 5.2's Principled, so this is a reconstruction, not a
translation.

### 3.8 Sheen

`sheen_color` is synthesised as `sheen_tint × sheen_weight`
(`Plugin/export/materials/extract/core.py:274-278`, recomputed at `:427-436`). For PBR2
with linked controls, the graph builder instead inserts `combine3(weight, weight, weight)`
then `multiply(tint, that)` (`Plugin/export/materials/graph.py:746-765`). When either
control is linked the pre-combined constant is discarded so the profile can decide
(`:439-443`) — PBR2 combines, OpenPBR keeps `fuzz_weight` and `fuzz_color` separate.

### 3.9 UVs and texture transforms

| Trigger | What happens | Told? |
|---|---|---|
| No UV named | `texcoord` node, semantic `UV0` | **Silent** |
| Named UV map | `geompropvalue` node with `geomprop = <name>` | **Silent** |
| Blender `Mapping` node with identity values | **no transform node authored** | **Silent** |
| Non-identity `Mapping` | one `place2d` node, rotation converted to **degrees** | **Silent** |
| Two textures, same effective mapping | **one shared** `place2d` | **Silent** |
| Two distinct non-default mappings | **export fails** | **Error** (both validator and preflight) |
| An explicit `place2d` plus a Blender `Mapping` | **export fails** | **Error** |
| More than one explicit `place2d` | **export fails** | **Error** |

RealityKit honours at most one 2D texture transform per material. The equivalence rules
live in one import-safe module so source validation, MaterialX authoring, and composed-USD
preflight agree on what counts as a *distinct* transform
(`Plugin/export/materials/mapping.py:1-7`).

An identity mapping returns `None` and authors nothing, because pivot and operation order
have no effect when offset, scale, and rotation are neutral
(`effective_texture_mapping_contract`, `:63-119`). An **explicitly authored** identity
`place2d` is different — it still consumes RealityKit's single slot, so it cannot be
discarded (`authored_texture_mapping_contract`, `:122-144`).

The resolved UV set is part of the contract (`:111-118`): one shared transform cannot
consume two different UV sets, so the same offset/scale/rotation on two different UV maps
still counts as two transforms.

Blender radians become MaterialX degrees at
`Plugin/export/materials/textures.py:526`.

### 3.10 Type coercion

The authoring stage inserts conversion nodes rather than failing on a type mismatch.

| Trigger | What happens | Told? |
|---|---|---|
| Texture output type ≠ input type | `_coerce_texture_spec_for_input` rewrites the hint | **Warning** |
| Float input, texture, **no channel specified** | defaults to channel `r` | **Warning** |
| Remaining type mismatch | `convert` node inserted | **Warning** |
| No exact nodedef for a node name + signature | the manifest selector falls back to **output type only**, then to **any** nodedef of that name | **Silent** |
| No `convert` nodedef for the requested pair | selector returns an unrelated `convert` nodedef of the right *output* type | **Silent** |
| Colour with 3 components into `color4` | alpha padded with `1.0` | **Silent** |
| Vector with 3 components into `vector4` | padded with `0.0` | **Silent** |
| List into a float input | takes element `[0]` | **Silent** |

`Plugin/export/materials/textures.py:46-79`, `:689-695`;
`Plugin/export/materials/conversions.py:243-295`, `:205-240`.

The nodedef selector's fallback chain is the one to watch
(`Plugin/manifest/materialx_nodes.py:91-95`). `_create_convert_output` has a
`missing_mappings` diagnostic for the "no matching convert nodedef" case
(`Plugin/export/materials/conversions.py:265-280`), but it only fires when the selector
returns nothing. Because the selector returns a wrong-signature nodedef instead of `None`,
that diagnostic is bypassed and the mismatch is authored silently. Measured on the shipped
manifest:

```
select_nodedef_name_for_node(m, "luminance", output_type="float")        -> ND_luminance_color3
select_nodedef_name_for_node(m, "convert", color3 -> float)              -> ND_convert_boolean_float
```

> Verified on Blender 5.2. `Image Texture → RGB to BW → Roughness`, portable profile,
> exported with `"ok": true` and no diagnostics file. The resulting USD contains:
> ```
> def Shader "Convert_roughness" {
>     uniform token info:id = "ND_convert_boolean_float"
>     color3f inputs:in.connect = </.../pbr_surfaceshader_1_roughness_2.outputs:out>
>     float outputs:out
> }
> ```
> a boolean→float nodedef whose `in` is declared `color3f`, feeding `inputs:roughness`.
> Check RGB-to-BW graphs in Reality Composer Pro before relying on them.

### 3.11 Stage-level rewrites

| Trigger | What happens | Told? |
|---|---|---|
| Texture came from dirty or generated pixels | native `UsdPreviewSurface` subtree **deleted** | **Warning** |
| Otherwise | native preview network **retained** alongside MaterialX | **Silent** |
| Material bound but no Blender counterpart | **export fails** | **Error** |
| Material defined inside a variant | **export fails** | **Error** |
| Material inside a read-only OpenUSD prototype | **export fails** | **Error** |
| Material binding authored in an inactive variant with an unresolvable target | **export fails** | **Error** |

`_remove_stale_preview_network` (`Plugin/export/materials/rewrite.py:681-699`) runs only
when `native_preview_stale` is set, which happens only when a contributing image was dirty
or `GENERATED` (`Plugin/export/materials/extract/core.py:2347-2350`). In every other case
the exported USD carries **two** surface networks: `outputs:surface` → Blender's
`UsdPreviewSurface`, and `outputs:mtlx:surface` → the RealityKit graph.

> Verified on Blender 5.2. A clean file-backed material exported with both:
> ```
> token outputs:mtlx:surface.connect = </root/_materials/MatFull/pbr_surfaceshader_1.outputs:out>
> token outputs:surface.connect = </root/_materials/MatFull/Principled_BSDF.outputs:surface>
> ```
> This is normally harmless — RealityKit prefers the `mtlx` output — but preflight checks
> both networks, which is the mechanism behind the Non-Color failure in 3.1.

---

## 4. Node coverage

### 4.1 Where the lists live

Four places encode "what can this exporter handle", and they are independent copies:

| Location | Purpose |
|---|---|
| `Plugin/nodes/validate.py:18-145` | the gate. `ALLOWED_UI_TYPES`, `SUPPORTED_TYPES`, `SHADERGRAPH_SUPPORTED_TYPES`, `PARTIAL_TYPES`, `BAKE_TYPES`, `UNSUPPORTED_TYPES` |
| `Plugin/export/materials/extract/core.py:575-673` | advisory warnings only. Local `supported_types`, `partial_types`, `bake_types`, `unsupported_types` inside `collect_material_warnings` |
| `Plugin/export/materials/extract/core.py:1308-2300` | the real resolver. `_resolve_socket_value`'s branch chain |
| `Plugin/manifest/rk_nodes_manifest.json` | the MaterialX nodedefs the graph may reference |

Only the first decides whether your export runs. Only the third decides what the output
actually contains.

### 4.2 The categories

**Rejected outright** (`UNSUPPORTED_TYPES`, `Plugin/nodes/validate.py:94-145`) — every
non-Principled BSDF (`BSDF_DIFFUSE`, `BSDF_GLOSSY`, `BSDF_GLASS`, `BSDF_METALLIC`,
`BSDF_REFRACTION`, `BSDF_SPECULAR`, `BSDF_TRANSLUCENT`, `BSDF_TRANSPARENT`, `BSDF_SHEEN`,
`BSDF_VELVET`, `BSDF_TOON`, `BSDF_RAY_PORTAL`, hair BSDFs), shader combinators
(`MIX_SHADER`, `ADD_SHADER`), all volume nodes, all geometry/attribute inputs
(`GEOMETRY`, `OBJECT_INFO`, `CAMERA_DATA`, `HAIR_INFO`, `CURVE_INFO`, `PARTICLE_INFO`,
`POINT_INFO`, `VERTEX_COLOR`, `VOLUME_INFO`, `WIREFRAME`, `ATTRIBUTE`, `TANGENT`),
view-dependent nodes (`LIGHT_PATH`, `FRESNEL`, `LAYER_WEIGHT`), `AMBIENT_OCCLUSION`,
`BEVEL`, `HOLDOUT`, `BACKGROUND`, and non-surface outputs. Also: any node group that is not
an `RK_*` RealityKit group (`:520-524`), and any node type the exporter does not recognise
at all (`:675`).

**Requires baking** (`BAKE_TYPES`, `:64-92`) — `BUMP`, `DISPLACEMENT`,
`VECTOR_DISPLACEMENT`, the procedural textures `TEX_WAVE`, `TEX_WHITE_NOISE`, `TEX_MAGIC`,
`TEX_CHECKER`, `TEX_BRICK`, `TEX_POINTDENSITY`, `TEX_SKY`, `TEX_GABOR`, `TEX_IES`, plus
`BLACKBODY`, `LIGHT_FALLOFF`, `WAVELENGTH`, `VECTOR_MATH`, `GAMMA`, `SHADER_TO_RGB`,
`COMBXYZ`, `CURVE_VEC`, `RADIAL_TILING`, the cylindrical/spherical combine-separate pairs,
`FLOAT_CURVE`, and `CURVE_RGB`. Under `strict=True` — i.e. always — these are **errors**,
not warnings.

**Conditionally supported** — `MIX_RGB`/`MIX` pass only when they are a plain mix or a
multiply/add/subtract of resolvable inputs, or when Factor is 0/1 with a passthrough input
(`_is_supported_mix`, `Plugin/export/materials/extract/core.py:2705`; gate at
`Plugin/nodes/validate.py:631-641`). `MATH` passes only as a true pass-through — add 0,
subtract 0, multiply 1, divide 1 (`_is_identity_math_node`, `:2725`; gate at `:643-652`).
`VALTORGB` (Color Ramp) passes only in RGB colour mode with Linear, Constant, or Ease
interpolation (`:608-620`).

**Limited support** (`PARTIAL_TYPES`, `:58-62`) — `TEX_COORD`, `UVMAP`, `MAPPING`. Warning:
UV mapping is applied for Image Texture inputs only.

**Supported** (`SUPPORTED_TYPES`, `:23-53`) — 29 types: `OUTPUT_MATERIAL`,
`BSDF_PRINCIPLED`, `EMISSION`, `TEX_IMAGE`, `NORMAL_MAP`, `RGB`, `VALUE`, `INPUT_BOOL`,
`INPUT_INT`, `INPUT_VECTOR`, `SEPARATE_COLOR`, `SEPARATE_RGB`, `SEPARATE_XYZ`, `SEPXYZ`,
`TEX_NOISE`, `TEX_VORONOI`, `TEX_GRADIENT`, `TEX_ENVIRONMENT`, `CLAMP`, `HUE_SAT`,
`BRIGHTCONTRAST`, `VALTORGB`, `RGBTOBW`, `COMBINE_COLOR`, `VECTOR_ROTATE`,
`VECTOR_TRANSFORM`, `NORMAL`, `MAP_RANGE`, `INVERT`. Plus `FRAME` and `REROUTE`, which are
skipped entirely (`ALLOWED_UI_TYPES`, `:18-21`).

`SHADERGRAPH_SUPPORTED_TYPES` (`:55-56`) is written `{\n}`, which Python parses as an empty
**dict**, not a set. Its branch (`:623-629`) — "supported by ShaderGraph but not yet mapped
by the exporter" — is unreachable.

### 4.3 Group traversal

The three layers do not traverse identically.

| Concern | Validator | Extractor warnings | Resolver |
|---|---|---|---|
| Descends into node groups | **no** | **no** | yes (`extract/core.py:1442-1472`) |
| `GROUP_INPUT` | n/a | n/a | **unhandled** — no branch exists |
| Reroute | skipped | falls through to "unrecognized" | traversed transparently |
| `node.mute` | **ignored** | **ignored** | **ignored** |
| RK-group identity | `rk_node_id` **or** catalog name (`validate.py:785-793`) | `rk_node_id` **or** `RK_` prefix (`core.py:152-157`) | `rk_node_id` **only** (`core.py:1137-1144`) |

Two consequences worth knowing as an artist:

- **Nodes inside a group are invisible to validation.** Both `_collect_used_nodes`
  implementations (`Plugin/nodes/validate.py:796-833`,
  `Plugin/export/materials/extract/core.py:753-796`) walk only the material's own node tree.
  A `VOLUME_SCATTER` inside a group is never reported by either. In practice the validator's
  blanket rejection of non-RK groups (`:520-524`) prevents this from mattering.
- **Muted nodes are evaluated as if enabled.** No material-path code reads `node.mute`. A
  muted Invert still inverts in the exported material, so the export can diverge from the
  Blender viewport with no diagnostic. This is consistent across all three layers.

### 4.4 The three lists disagree

They have drifted, in both directions.

**A. The extractor's warning table is 11 types behind the validator.** Its local
`supported_types` (`Plugin/export/materials/extract/core.py:575-591`) has 15 entries; the
validator's has 26. These types validate clean and translate correctly, but produce a
spurious advisory warning during export:

| Node type | Validator | Extractor warning table | Warning you see |
|---|---|---|---|
| `TEX_NOISE`, `TEX_VORONOI`, `TEX_GRADIENT`, `TEX_ENVIRONMENT` | supported | *unlisted* | `... is unrecognized; export may differ.` |
| `CLAMP`, `HUE_SAT`, `BRIGHTCONTRAST`, `RGBTOBW`, `COMBINE_COLOR`, `VECTOR_ROTATE`, `VECTOR_TRANSFORM`, `NORMAL`, `MAP_RANGE` | supported | *unlisted* | `... is unrecognized; export may differ.` |
| `INVERT` | supported | `bake_types` | `... requires baking for RCP.` |

The resolver handles all of them (`Plugin/export/materials/extract/core.py:1561`,
`:1599`, `:1652`, `:1712`, `:1719`, `:1727`, `:2012`, `:2022`, `:2069`, `:2098`, `:2115`,
`:2127`, `:2140`). The export succeeds; the diagnostics contradict it.

**B. `CURVE_RGB` is rejected despite a full implementation.** The resolver has a complete
RGB Curves translation — knot extraction, identity detection, MaterialX curve authoring
(`Plugin/export/materials/extract/core.py:1917`, helpers at `:2866-2895`). The validator
puts `CURVE_RGB` in `BAKE_TYPES` (`Plugin/nodes/validate.py:91`), so under strict mode it
is always an error. The code cannot be reached from any shipped surface.

> Verified on Blender 5.2. A cube with `Image → RGB Curves → Base Color` was rejected:
> `"node_type": "CURVE_RGB", "message": "Node requires baking for RealityKit."`

**C. Colour space is checked by nobody until authoring.** Neither the validator nor
`collect_material_warnings` inspects `image.colorspace_settings`. An sRGB-tagged roughness
map validates clean and then kills the export in stage 4 — see [1.4](#14-author-usd).

**D. `BUMP` is safe by accident.** The resolver would silently reinterpret a height map as
a normal map (`:1420-1431`); only the validator's `BAKE_TYPES` membership prevents it.

**E. Node properties inside `SUPPORTED_TYPES` are unchecked.** Membership is by node
*type*; several types are only translatable in certain configurations, and the validator
checks some of those but not others.

| Configuration | Validator | Resolver | Result |
|---|---|---|---|
| `VALTORGB` non-RGB mode or exotic interpolation | checked (`validate.py:608-620`) | rejects | agreed |
| `VALTORGB` with fewer than 2 stops | **unchecked** | rejects (`core.py:1831-1832`) | validate clean → export fatal |
| `COMBINE_COLOR` in HSV/HSL mode | **unchecked** | rejects (`core.py:2023-2025`) | validate clean → export fatal |
| `TEX_IMAGE` with no image | checked (`validate.py:527`) | returns `None` | agreed |
| `TEX_ENVIRONMENT` with no image | **unchecked** | falls through to unresolved (`core.py:2220-2227`) | validate clean → export fatal |

**F. A material with no active surface shader validates clean.** With no
`OUTPUT_MATERIAL`, or with its `Surface` unconnected, `_collect_used_nodes` returns an
empty or single-node set (`Plugin/nodes/validate.py:800-802`, `:824-833`), so there is
nothing to complain about. Extraction then leaves `type` as `unknown` and
`_build_material_graph` returns `None`, producing
`Material type 'unknown' could not be mapped to a RealityKit graph.`
(`Plugin/export/materials/rewrite.py:173-177`).

**G. A `Mapping` node on a procedural texture is silently discarded.** The validator's
transform audit inspects `TEX_IMAGE` and `TEX_ENVIRONMENT` only
(`Plugin/nodes/validate.py:421`), and the resolver's `MAPPING` branch just forwards the
`Vector` input (`Plugin/export/materials/extract/core.py:1431-1440`). A `Mapping` driving
`TEX_NOISE.Vector` changes nothing in the export and nothing reports it.

**H. Nested unresolved sub-expressions are dropped without a warning.** The unresolved
check inspects only the **top level** of each Principled input
(`Plugin/export/materials/extract/core.py:402`). `_expr_from_socket` (`:2624-2654`) returns
the `{"kind": "unresolved"}` dict rather than `None`, so a surrounding `mix`, `clamp`,
`hsvadjust`, or similar node is still built around it; the graph builder then returns
`None` for that child (`Plugin/export/materials/graph.py:350-351`, `:399-401`) and the
input is simply never authored, falling back to the nodedef default. The material exports
"successfully" with a missing input. Every multi-input resolver branch has this shape.

**What agrees.** The mapping/transform contract is genuinely shared — `validate.py`
imports the extractor's `_extract_mapping_from_node` and the canonical
`effective_texture_mapping_contract` (`Plugin/nodes/validate.py:409-413`), and preflight
uses the same module (`Plugin/export/materials/mapping.py`). `UNSUPPORTED_TYPES` and
`PARTIAL_TYPES` are identical between the validator and the extractor's table, and
`BAKE_TYPES` differs only by `INVERT`. The Mix/Math passthrough predicates are duplicated
verbatim and behave identically. Profile-driven input drops agree because the OpenPBR and
unlit paths read the nodedef directly instead of duplicating a list.

---

## 5. The texture pipeline

Three modules, in this order:

| Stage | Module | Entry point |
|---|---|---|
| Datablock → absolute path | `materials/extract/core.py` | `_resolve_image_path` (`:2988`) |
| MaterialX reader authoring | `materials/textures.py` | `_create_texture_connection` (`:82`) |
| Copy/transcode into the output tree | `export/usd_textures.py` | `_stage_texture_source` (`:336`) |

`materials/textures.py` performs no file I/O at all; it treats `texture_spec['path']` as an
opaque string (`:94-96`, `:159-160`). Staging runs twice — once before material rewrite
(`Plugin/export/postprocess_usd.py:38-46`) and once after (`:74-82`), the second pass being
what localizes the absolute temp paths MaterialX authoring wrote.

### 5.1 Resolution

`_resolve_image_path` (`Plugin/export/materials/extract/core.py:2988-3046`). The rule is
*current Blender pixels win*.

| Image state | Behaviour |
|---|---|
| Clean, file-backed, not in a temp dir | absolute path used directly |
| **Packed** | `packed.data` bytes written verbatim to a temp file (`:3113-3124`) |
| **Generated / procedural** | live pixels snapshotted; `.exr` if float, else `.png` (`:3086-3087`) |
| **Dirty** | live pixels snapshotted, `force_refresh=True` (`:3099-3102`) |
| Dirty **and** `TILED`/`SEQUENCE`/`MOVIE` | **export fails**: *must be baked to a single current frame* (`:2998-3002`) |
| **UDIM / tiled** (clean) | **export fails** at staging, `Texture file not found: .../tile.<UDIM>.png` |
| Relative `//` path | resolved via `bpy.path.abspath` (`:3007`) |
| Missing file | **export fails**: `Texture file not found` (`Plugin/export/usd_textures.py:347-350`) |
| Image node with no image | input silently falls back to a constant (`:2306-2308`) |

Staging a snapshot copies `colorspace_settings.name` and `alpha_mode` **before** the pixels,
because Blender 5.2 clears the buffer otherwise (`:3168-3179`).

The reuse cache (`_image_cache_key`, `:3191-3237`) mixes the datablock pointer, name,
source, dirty and packed state, both filepaths, a `(st_dev, st_ino, st_size, st_mtime_ns)`
fingerprint, dimensions, float-ness, file format, and the library filepath — because a
pointer alone is not an image identity. A cache hit is honoured only for clean, unpacked,
non-generated images (`:3023-3030`).

> Verified on Blender 5.2. A 2-tile UDIM set (`tile.<UDIM>.png`, tiles 1001/1002) on Base
> Color failed the export with `Texture file not found:
> .../udim/tile.<UDIM>.png`. UDIM is not supported, but it does fail closed — it does not
> ship a collapsed or missing texture.

### 5.2 Staging layout

```
<usd_dir>/textures/<portable-usd-filename>/<32-hex generation token>/
```

`Plugin/export/usd_textures.py:131`, namespace from
`Plugin/export/staging_namespace.py:17-28`. The generation token is a
`secrets.token_hex(16)` recorded in an `O_EXCL` marker under
`<usd_dir>/.blendertorcp_generations/` (`:31-66`), so every sidecar of one export attempt
shares one immutable namespace and the root USD can be swapped in last.

Authored asset values are made relative with `os.path.relpath` against the owning layer's
directory (`Plugin/export/usd_textures.py:249-253`). `"textures"` is a hard-coded literal
and is **not configurable**.

### 5.3 Content-addressed naming

`_finalize_content_addressed_texture` (`Plugin/export/usd_textures.py:892-951`).

The **final destination file's bytes** are hashed with SHA-256, streamed in 1 MiB chunks
(`:975-983`). Not the source, not the pixels, not the path, not the override parameters.
The digest is never truncated, because publication installs sidecars before atomically
switching the root USD, and a stable name could otherwise be observed with stale bytes
(`:893-898`).

```
<usd-file-stem>-<source-stem>-<sha256 64 hex><.ext>
```

The semantic stem is NFC-normalized, has any pre-existing `-<64hex>` suffix stripped for
idempotency (`:924-926`), and is truncated to 120 UTF-8 bytes (`:90`, `:1002-1007`).

Deduplication happens at four levels: current-generation recognition (`:954-972`), a
`(source path, override key)` map, a `(SHA-1 of source bytes, override key)` map
(`:864-889`), and content-address arrival, where a byte-identical existing file is reused
and the duplicate unlinked (`:938-948`). A same-name file with *different* bytes, or a
symlink, raises `Content-addressed texture collision` (`:944-946`).

> Verified on Blender 5.2. Three distinct 8×8 images (albedo/orm/nrm) produced three
> staged files; three images with *identical* pixel content produced exactly one, shared by
> all three MaterialX readers.

### 5.4 Format conversion

Package contract (`Plugin/export/usd_textures.py:72-78`): `.avif`, `.exr`, `.jpg`,
`.jpeg`, `.png`. Decision in `_effective_texture_override` (`:705-727`):

| Source | Behaviour |
|---|---|
| `.exr` | **always** byte-copied. Overrides ignored, with a warning (`:709-710`, `:379-383`) |
| `.hdr` | **export fails** — convert to OpenEXR first (`:370-378`) |
| `.png`, `.jpg`, `.jpeg`, `.avif` | byte-copied, unless you enabled an override |
| everything else (`.tif`, `.tga`, `.bmp`, `.gif`, `.dds`, `.webp`, `.ktx`) | **forced PNG conversion, even with overrides off** (`:723-727`) |

Encoding goes through `imbuf` first (`:1188-1224`, quality 90 for lossy formats, `:58`),
falling back to Blender's image API (`:1158-1185`). Conversions are atomic — encoded into a
temp file in the same directory, validated by a real decode (`:1014-1081`), then
`os.replace` (`:1084-1126`) — because source and destination can be the same file across
the two staging passes.

A failed AVIF conversion retries as PNG at the same resolution and warns
(`:813-825`, `:452-454`).

**Setting**: *Optimize Source Textures* (`export_texture_settings_enabled`, default off,
`Plugin/ui/panel.py:442-447`) gates *Image Format* (`bake_image_format`: `ORIGINAL` /
`AVIF` / `PNG`, default `AVIF`, `:464-474`).

### 5.5 Resizing

A max-dimension clamp only. Never upscales, never forces power-of-two.

*Texture Resolution* (`bake_resolution`: `ORIGINAL`/512/1024/2048/4096/`CUSTOM`, default
`2048`, `Plugin/ui/panel.py:449-462`). `ORIGINAL` maps to `0` = no clamp
(`Plugin/export/bake_textures.py:1133-1145`).

When the longest edge exceeds the limit, both dimensions scale by
`max_resolution / longest`, floored at 1, aspect preserved — bilinear via imbuf
(`Plugin/export/usd_textures.py:1227-1238`) or Blender's default filter via `image.scale`
(`:1249-1264`).

You are **not told the dimensions**. Neither resize helper takes a `diagnostics` argument;
the only trace is an anonymous counter (`Plugin/export/diagnostics.py:147-149`) and a
`generated_files` entry with role `texture_override`
(`Plugin/export/usd_textures.py:492-500`).

### 5.6 Reader authoring and channel extraction

`_image_output_hint` (`Plugin/export/materials/textures.py:617-646`) picks the reader type:

| Situation | Reader |
|---|---|
| normal map | `ND_image_vector3` |
| data role | `ND_image_vector4` — a four-channel reader preserves packed scalars without colour conversion (`:637-639`) |
| alpha channel, or explicit color4/vector4 | `ND_image_color4` / `ND_image_vector4` |
| everything else | `ND_image_color3` |

Channel selection then inserts a `swizzle` node (`:889-943`), or a `separate4` when the
reader is `color4` (`:766-806`), or `separate4` + `combine3` when the same image must serve
both RGB and alpha (`:714-733`). Every swizzle emits an informational warning naming the
nodedef and channel (`:938-941`).

Readers are shared via a cache keyed on path, texcoord, the full mapping tuple, colorspace,
colorspace role, alpha mode, type, output type, **channel**, image-type override, the
`force_separate4` flag, and the sampling modes (`_texture_cache_key`, `:18-44`).

Non-default sampling modes from the Blender Image Texture node are authored on the reader
as the uniform string inputs the shipped RCP 3 (80.0.1.500.1) `ND_image_*` nodedefs
declare: Extension **Extend** → `uaddressmode`/`vaddressmode = "clamp"`, **Clip** →
`"constant"`, **Mirror** → `"mirror"`; Interpolation **Closest** → `filtertype =
"closest"`, **Cubic**/**Smart** → `"cubic"`. Repeat and Linear are the nodedef defaults
and author nothing (`_image_node_sampling`,
`Plugin/export/materials/extract/core.py`).

Because `channel` is part of that key, a packed ORM texture read for two different channels
produces two separate image readers.

> Verified on Blender 5.2. One `orm.png` feeding Roughness (G) and Metallic (B) through a
> Separate Color node authored two `ND_image_vector4` prims — `Image_1` swizzled to `b`,
> `Image_2` swizzled to `g` — both pointing at the same staged file with
> `colorSpace = "raw"`.

### 5.7 Worked example

The MaterialX half of a portable-profile export with an sRGB albedo, a packed Non-Color
ORM, and a Non-Color tangent normal map. Verified output, Blender 5.2:

```
def Shader "pbr_surfaceshader_1" {
    uniform token info:id = "ND_realitykit_pbr_surfaceshader"
    color3f inputs:baseColor.connect  = </.../Image.outputs:out>
    float   inputs:metallic.connect   = </.../swizzle_metallic_b.outputs:out>
    float   inputs:roughness.connect  = </.../swizzle_roughness_g.outputs:out>
    float3  inputs:normal.connect     = </.../NormalMap_normal.outputs:out>
    float   inputs:specular = 0.5
    color3f inputs:emissiveColor = (0, 0, 0)
}
def Shader "Image"   { ND_image_color3  ... ( colorSpace = "srgb_texture" ) }
def Shader "Image_1" { ND_image_vector4 ... ( colorSpace = "raw" ) }
def Shader "Image_2" { ND_image_vector4 ... ( colorSpace = "raw" ) }
def Shader "Image_3" { ND_image_vector3 ... ( colorSpace = "raw" ) }
def Shader "NormalMap_normal" { ND_normal_map_decode }
```

with material-prim metadata:

```
prepend apiSchemas = ["ColorSpaceAPI", "MaterialXConfigAPI"]
customData = { dictionary BlenderToRCP = { string surfaceProfile = "realitykit_portable" } }
uniform token colorSpace:name = "lin_rec709_scene"
string config:mtlx:version = "1.38"
```

---

## 6. Diagnostic and error reference

### 6.1 CLI error codes

Material translation surfaces through these `error.code` values:

| Code | Stage | Raised at |
|---|---|---|
| `UNSUPPORTED_MATERIAL_NODES` | validation | `Plugin/api/commands/export.py:236-243` |
| `POSTPROCESS_FAILED` | export | `Plugin/api/commands/export.py:277-284` |
| `EXPORT_FAILED` | export | `Plugin/api/commands/export.py:328-336` |
| `BAKE_EXPORT_FAILED` | bake-export | `Plugin/api/commands/bake_export.py:703-708` |
| `MISSING_EXTERNAL_TEXTURES` | preflight | `Plugin/export/asset_preflight.py:186-194` (bake path only) |

There is **no central registry**. `CommandError` takes a free-form `code: str`
(`Plugin/api/errors.py:222-252`) and every code is a string literal at its raise site.
Preflight issue codes are a separate namespace and **never** appear in `error.code` — they
survive only inside `error.message` and as structured objects in the diagnostics sidecar.

### 6.2 Where diagnostics go

- **CLI**: the JSON envelope on stdout, plus `artifacts.diagnostics_path` pointing at
  `<output>.diagnostics.json`. Failed exports always write it; successful ones only when
  `diagnostics_enabled` is on (`Plugin/ui/panel.py:533-541`).
- **Blender UI**: the first five errors and warnings via `self.report`
  (`Plugin/ops/export_operator.py:231-240`, `:276-282`), full JSON through
  *Show Diagnostics*.
- **Preflight payload**: `diagnostics.data["realitykit_preflight"]` and the alias
  `diagnostics.data["validation"]["realitykit"]`, each
  `{profile, asset_path, ok, counts, issues[]}`
  (`Plugin/export/realitykit_preflight.py:213-224`, `:1689-1700`). This is the only place
  `info`-severity findings appear.

### 6.3 Fatal material messages

Every one of these stops the export.

| Message | Source |
|---|---|
| `Material graph contains unresolved input(s): ...` | `rewrite.py:142-148` |
| `MaterialX graph construction failed: ...` | `rewrite.py:180-186` |
| `MaterialX authoring failed: ...` | `rewrite.py:232-239` |
| `Data texture '<input>' must use Blender Non-Color/raw, not '<x>'` | `textures.py:392-395` |
| `Unsupported Blender image color space '<x>' for '<input>'` | `textures.py:377-383` |
| `OpenPBR 1.1 has no alpha-cutout input; ...` | `graph.py:690-695` |
| `OpenPBR geometry normals require a tangent-space normal map; ...` | `graph.py:949-953`, `:652-655` |
| `Material '<n>' requires N distinct non-default texture mappings, ...` | `mapping.py:266-272` |
| `Material '<n>' combines an explicit MaterialX place2d node with a Blender texture Mapping transform.` | `mapping.py:244-249` |
| `Material '<n>' contains N explicit MaterialX place2d nodes.` | `mapping.py:250-256` |
| `... RealityKit has one material-level hasPremultipliedAlpha flag. ...` | `rewrite.py:405-413` |
| `Premultiplied base-color texture '<p>' cannot be encoded or resized as AVIF safely ...` | `usd_textures.py:770-774` |
| `Material '<n>' at <path> is defined inside a variant.` | `rewrite.py:653-657` |
| `Material '<n>' at <path> exists only inside a read-only OpenUSD prototype.` | `rewrite.py:644-648` |
| `Texture file not found: <p>` | `usd_textures.py:347-350` |
| `Texture '<p>' uses Radiance HDR. ...` | `usd_textures.py:370-378` |
| `Dirty <source> image '<n>' must be baked to a single current frame ...` | `extract/core.py:2998-3002` |
| `RealityKit OS 27 preflight failed with N error(s): ...` | `postprocess_usd.py:181-184` |
