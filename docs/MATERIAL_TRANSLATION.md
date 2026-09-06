# Material translation

This page explains how the exporter turns a Blender material into a RealityKit
MaterialX ShaderGraph — including every place where it substitutes, infers, or
drops something on your behalf. Read it to predict what a material exports as,
and to know which Blender controls survive the trip.

*Applies to: Blender 5.2; Reality Composer Pro 3.0 (build 80.0.1.500.1).*

Source references like `file.py:123` are asides for contributors. You do not
need the source code to use this page.

Related: [ARCHITECTURE.MD](ARCHITECTURE.MD) for the export pipeline as a whole,
[CLI.md](CLI.md) for the commands referenced here.

## Contents

1. [The export pipeline](#the-export-pipeline)
2. [Surface profiles](#surface-profiles)
3. [Decisions the exporter makes for you](#decisions-the-exporter-makes-for-you)
4. [Which Blender nodes export](#which-blender-nodes-export)
5. [The texture pipeline](#the-texture-pipeline)
6. [Diagnostics and errors](#diagnostics-and-errors)

---

## The export pipeline

A material crosses five stages. Each stage can stop the export, and each fails
in a different way. The last stage is the *preflight* — the exporter's final
validation pass over the composed USD stage, after all authoring is done.

| # | Stage | Code | Runs on | Failure mode |
|---|-------|------|---------|--------------|
| 1 | Validate | `Plugin/nodes/validate.py` | Blender node tree | `UNSUPPORTED_MATERIAL_NODES`, before any USD is written |
| 2 | Extract | `Plugin/export/materials/extract/core.py` | Blender node tree | recorded per material, batched into one `RuntimeError` |
| 3 | Build graph | `Plugin/export/materials/graph.py` | extracted payload | recorded per material, batched |
| 4 | Author USD | `Plugin/export/materials/author.py`, `textures.py` | USD stage | recorded per material, batched, stage rolled back |
| 5 | Preflight | `Plugin/export/realitykit_preflight.py` | composed USD stage | `RuntimeError` listing preflight issue codes |

Stages 2–4 run inside `rewrite_materials`
(`Plugin/export/materials/rewrite.py:20`), which is step 4 of
`process_usd_stage` (`Plugin/export/postprocess_usd.py:68`). Preflight is the
last step before the stage is saved
(`Plugin/export/postprocess_usd.py:96-108`).

### Validate

Validation walks the nodes that contribute to the active Material Output and
classifies each one (`validate_material`, `Plugin/nodes/validate.py:448`). It
also checks Principled inputs against the selected
[surface profile](#surface-profiles) (`Plugin/nodes/validate.py:220`) and
enforces RealityKit's rule of one texture transform per material
(`Plugin/nodes/validate.py:484-511`).

Every production caller passes `strict=True`: the export gate
(`Plugin/api/commands/export.py:216-222`), the `validate` CLI command
(`Plugin/api/commands/validate.py:76-81`), the Shader Editor panel
(`Plugin/ui/shader_panel.py:67`), the validation operators
(`Plugin/ops/validation_operators.py:57`, `:86`, `:112`), the support bundle
(`Plugin/export/support_bundle.py:219`), and the background bake runner
(`Plugin/bake_export_runner.py:701`, `:800`). Under strict validation most
warnings become errors, so `blendertorcp validate` previews the export gate
faithfully rather than running a softer check. The `strict=False` default in
the function signature is not reachable from any shipped surface.

On failure the CLI returns:

```json
{"ok": false, "error": {"code": "UNSUPPORTED_MATERIAL_NODES",
 "stage": "validation", "details": [{"node_name": "...", "node_type": "...", "message": "..."}]}}
```

### Extract

Extraction reduces the node tree to a flat dictionary plus an `input_graphs`
map of expression trees for anything that cannot be flattened to a constant or
a single texture (`extract_blender_material_data`,
`Plugin/export/materials/extract/core.py:132`).

It classifies the material into one of five `type` values, which decide the
graph built in stage 3 (`Plugin/export/materials/rewrite.py:263-282`):

| `type` | Trigger | Graph built |
|--------|---------|-------------|
| `simple` | `use_nodes == False` | **Unlit** |
| `principled` | active output drives a Principled BSDF | PBR, per profile |
| `emission` | active output drives an Emission node | **Unlit** |
| `rk_group` | active output drives an `RK_*` nodegroup | that RealityKit nodedef |
| `rk_graph` | a pre-built RealityKit node graph | passed through |

Only the shader wired to the **active** Material Output contributes
(`Plugin/export/materials/extract/core.py:83-85`, `:450-456`). A disconnected
Principled node cannot make an opaque material transparent, and an orphan
Emission node never replaces an unsupported active shader.

A second routine, `collect_material_warnings`
(`Plugin/export/materials/extract/core.py:559`), runs alongside extraction and
emits advisory strings into diagnostics
(`Plugin/export/materials/rewrite.py:105-108`). These are not fatal. Its node
table has drifted from the validator's — see
[Where the lists disagree](#where-the-lists-disagree).

A material whose `input_graphs` contain anything the resolver cannot translate
exactly is rejected: unresolved inputs become a per-material failure
(`Plugin/export/materials/rewrite.py:136-149`) with the message
`Material graph contains unresolved input(s): ...`.

### Build graph

The graph builder selects the surface *nodedef* — a MaterialX node definition,
the typed signature a shader node references — maps Blender parameter names
onto MaterialX input names, and filters out everything the chosen surface
cannot carry (`MaterialXGraphBuilder`,
`Plugin/export/materials/graph.py:61`). It emits a nested `{nodes,
connections, output, surface_profile, materialx_version}` structure — still no
USD.

The builder then rejects any graph that needs more than one distinct 2D
texture transform (`require_realitykit_mapping_contract`,
`Plugin/export/materials/mapping.py:232`).

### Author USD

Authoring turns the graph into `UsdShade.Shader` prims under the existing
`Material` prim (`create_materialx_material`,
`Plugin/export/materials/author.py:34`). Where types or channels do not line
up, it inserts helper nodes: `convert`, `swizzle` (a node that extracts or
reorders channels), `separate4`, `combine3`, `place2d` (MaterialX's 2D
texture-transform node), and normal-decode nodes.

Authoring is transactional. Every material is resolved, validated, extracted,
and built **before** the stage receives its first MaterialX opinion
(`Plugin/export/materials/rewrite.py:84-91`); the edit layer is backed up
(`:203-206`) and restored if any authoring call fails (`:241-249`). A
partially converted stage is never saved.

The original `material:binding` is deliberately left alone
(`Plugin/export/materials/rewrite.py:257-261`): the MaterialX surface is
authored at the same prim path, so rebinding would author a stronger
relationship outside the variant edit context and override inactive variant
selections.

Color-space failures surface here, not earlier. For example, a cube whose
Principled `Roughness` is driven by an image tagged `sRGB` fails with:

```
"code": "EXPORT_FAILED",
"message": "MaterialX rewrite failed for 1 used material(s):
 - MatSRGBData (/root/_materials/MatSRGBData): MaterialX authoring failed:
   Data texture 'roughness' must use Blender Non-Color/raw, not 'srgb'"
```

`blendertorcp validate` on the same file reports `"ok": true,
"error_count": 0, "warning_count": 0`. Validation does not catch color-space
problems; authoring does.

*Verification: observed by exporting from Blender 5.2.*

### Preflight

Preflight inspects the **composed USD stage**, not the Blender graph, and
never imports `bpy` (`validate_stage`,
`Plugin/export/realitykit_preflight.py:227`). It re-runs its whole check set
once per reachable variant combination, up to
`MAX_VARIANT_COMBINATIONS = 256`
(`Plugin/export/realitykit_preflight.py:36`, walk at `:319-388`).

Preflight returns a report; the caller decides what to do with it.
`_require_realitykit_preflight` (`Plugin/export/postprocess_usd.py:171-185`)
raises whenever the report contains errors, previewing the first five issues.
Severity semantics:

- `error` — hard abort, stage never saved.
- `warning` — forwarded to `diagnostics.data["warnings"]` (`:1697-1700`).
- `info` — appears **only** in the `realitykit_preflight` diagnostics payload.
  `_record_diagnostics` forwards errors and warnings only (`:1693-1700`), so
  info findings never reach the UI report or the CLI message.

There is no suppression list, allowlist, or lenient mode. The two strictness
flags `require_lightmap_uv` (`:844`) and `require_accessibility_metadata`
(`:1619`) are read with `getattr(..., False)` and are defined nowhere else in
the codebase — no property, no settings key, no CLI flag. They are permanently
`False`, and enabling them would *increase* strictness, not bypass it.

Preflight is profile-blind: it never reads `materialx_surface_profile`. The
`"profile"` field in its report is the constant
`TARGET_PROFILE = "RealityKit-AppleOS27"` (`:28`, `:176`) — an Apple OS target
label, not the MaterialX surface profile.

Material-relevant preflight codes:

| Code | Severity | Meaning |
|------|----------|---------|
| `TEXTURE_COLOR_SPACE_MISMATCH` | error | perceptual-color texture not sRGB/lin_rec709, or data texture tagged as color |
| `TEXTURE_COLOR_SPACE_UNSUPPORTED_TOKEN` | error | MaterialX image reader carries a color-space token RealityKit cannot map |
| `TEXTURE_ALPHA_SOURCE_MISSING` | warning | four-channel reader points at a texture with no alpha channel |
| `MATERIALX_NODEDEF_UNSUPPORTED_BY_RCP` | error | four-channel vector reader or extractor Reality Composer Pro replaces with a placeholder |
| `TEXTURE_COLOR_ROLES_CONFLICT` | error | one texture feeds both a color and a data input (`:1386-1393`) |
| `TEXTURE_COLOR_ROLE_UNRESOLVED` | info | role could not be inferred (`:1419-1426`) |
| `TEXTURE_ASSET_MISSING` | error | dependency does not resolve after staging (`:1374-1381`) |
| `USDZ_TEXTURE_FORMAT_UNSUPPORTED` | error | not JPEG/PNG/EXR/AVIF (`:1356-1364`) |
| `USDZ_TEXTURE_PATH_EXTERNAL` | error | texture path not localized and relative (`:1365-1372`) |
| `MATERIAL_TEXTURE_TRANSFORM_CONFLICT` | error | more than one distinct 2D transform (`:1082-1102`) |
| `TEXTURE_TRANSFORM_UNINSPECTABLE` | error | connected or time-sampled transform inputs (`:1063-1078`) |
| `MATERIAL_BINDING_API_MISSING` | error | binding authored without `MaterialBindingAPI` (`:997-1001`) |
| `MATERIAL_BINDING_INVALID` | error | binding does not resolve to a Material (`:1003-1010`) |

The full preflight code set also covers stage metadata, prim types, meshes,
and skeletons; those are outside material translation.

---

## The surface

Every translated material terminates in one MaterialX surface nodedef.

| Surface | Nodedef | MaterialX | Status |
|---------|---------|-----------|--------|
| RealityKit PBR Surface 2 | `ND_realitykit_pbr_surfaceshader_2_0` | 1.38 | Verified — imports into Reality Composer Pro 3 as native "PBR Surface 2 (RealityKit)", builds, renders |
| *(unlit)* | `realitykit_unlit_surfaceshader` | 1.38 | Produced by material shape or by the bake pipeline — see [When a material exports as unlit](#when-a-material-exports-as-unlit) |

The nodedef name and the `surfaceProfile` label written into the USD
(`realitykit_pbr2`) are constants at the top of
`Plugin/export/materials/graph.py`. There is nothing to select. A build whose
bundled manifest lacks the nodedef raises (`_require_pbr_surface_2`) rather
than falling back: the code refuses to switch shading models silently.

### Why there is nothing else to choose

RealityKit has two other lit PBR surfaces, and neither carries anything this
one does not.

- The original `ND_realitykit_pbr_surfaceshader` declares 13 inputs, every one
  of them also on PBR Surface 2 under the same name. Exporting to it could only
  drop controls.
- OpenPBR 1.1 (`ND_open_pbr_surface_surfaceshader`, MaterialX 1.39) has no
  Metal implementation of its own on RealityKit. Reality Composer Pro expands
  it through a `realitykit`-target nodegraph that terminates in PBR Surface 2
  and connects 22 of its 30 inputs; sheen, specular and coat anisotropy, coat
  colour, transmission and thin film are converted and then discarded. The
  editor shows this on the node by greying out *Fuzz Color*, *Fuzz Roughness*,
  *Fuzz Weight* and *Specular Anisotropy* and hiding the transmission and
  thin-film inputs. An OpenPBR export is a PBR Surface 2 export with fewer
  inputs.

*Verification: `t08_opacity` exported to each of the three surfaces and
imported into Reality Composer Pro 3.0 (build 80.0.1.500.1), 2026-08; the
built `.tm_material` records the nodedef each landed on. The OpenPBR expansion
is measured in `Apple/apple_nodedefs_overrides/apple_open_pbr_overrides.mtlx`
under Reality Composer Pro's MaterialX libraries.*

### When a material exports as unlit

Two independent things produce an unlit material:

1. **Material shape.** A `type` of `simple` or `emission` always builds an
   unlit graph (`Plugin/export/materials/rewrite.py`). A material with
   `use_nodes` off, or one whose active output is an Emission node, becomes an
   unlit RealityKit material without further notice.
2. **`force_unlit_materials`.** A `HIDDEN` scene property
   (`Plugin/ui/panel.py`) that no panel exposes. Only the bake pipeline sets
   it, from `bake_mode` (`Plugin/export/bake_finalize.py`): `LIT_ALBEDO`
   builds PBR; `UNLIT_ALBEDO` and `LIT_IBL` build unlit — the latter because
   Blender lighting is already burned into the baked texels.

The artist-facing mapping lives in `Plugin/export_profile.py`: *Material
Type* maps to RealityKit PBR (translate or bake) or RealityKit Unlit (material
color, or lighting + shadows).

The unlit surface carries only `color`, `opacity`, `opacityThreshold`, and
`hasPremultipliedAlpha` (`Plugin/export/materials/graph.py`). Linked
expression graphs are filtered against the nodedef's declared inputs rather
than a hard-coded list, with a warning naming what was dropped.

### What the surface carries

`_map_realitykit_pbr2_inputs` (`Plugin/export/materials/graph.py`) maps
Principled inputs onto the surface's 30 declared inputs; 28 are reachable from
Blender. `bentNormal` and `bakedIndirectIrradiance` have no Blender source.

| Blender Principled input | PBR Surface 2 input |
|---|---|
| Base Color | `baseColor` |
| Metallic | `metallic` |
| Roughness | `roughness` |
| Normal | `normal` |
| Emission Color × Strength | `emissiveColor` |
| Alpha | `opacity` |
| (cutout threshold) | `opacityThreshold` |
| AO (baked) | `ambientOcclusion` |
| Specular IOR Level | `specular` |
| Coat Weight / Roughness / Normal | `clearcoat*` |
| Coat IOR | `clearcoatIOR` |
| IOR | `specularIOR` |
| Specular Tint (achromatic, ≤ 1) | `specularColor` |
| Diffuse Roughness | `baseDiffuseRoughness` |
| Subsurface Weight / Radius / Scale / Anisotropy | `subsurface*` |
| Sheen Weight × Tint | `sheenColor` |
| Premultiplied alpha | `hasPremultipliedAlpha` |

The strict validator refuses these before the graph builder runs:

| Blender Principled input | Why |
|---|---|
| Coat Tint | No RealityKit surface carries a coat tint |
| Sheen Roughness other than `0.5` | The surface has no such input |
| Specular Tint, coloured or linked | Colour semantics are not verified against the surface |
| Specular Tint, achromatic and brighter than 1 | Outside the verified range; `normalize_unsupported_values` clamps it for the export instead |
| Anisotropic, Anisotropic Rotation, Tangent | The surface has `specularAnisotropyLevel` and `specularAnisotropyAngle`, but Blender's level factor and tangent rotation are not reproduced, and a partial mapping is worse than a refusal |
| Transmission Weight, Thin Film, Thin Wall, Subsurface IOR | No surface input |
| Linked Coat Weight / Roughness / Tint | Linked coat controls are not preserved; constants are |

Every refusal names the input and ends with a bake remedy. A cube whose
Principled has `Coat Weight = 0.5` with a red `Coat Tint`, and
`Sheen Weight = 0.3` with `Sheen Roughness = 0.2`, fails validation with:

```
Principled 'Coat Tint' has no RealityKit PBR Surface 2 input, and no RealityKit surface carries a coat tint; bake the material.
Principled 'Sheen Roughness' has no RealityKit PBR Surface 2 input; bake the material.
```

An input only counts as active when it is linked or differs from its neutral
value — white for Coat Tint and Specular Tint, `0.5` for Sheen Roughness, `0`
for Anisotropic. Subordinate controls are judged only while their weight is
non-zero, so a red Coat Tint under `Coat Weight = 0` is silent. The rules are
`_unsupported_principled_inputs` in `Plugin/nodes/validate.py`.

*Verification: messages transcribed from `Plugin/nodes/validate.py`; the
input map read from `_map_realitykit_pbr2_inputs` and checked against the
shipped nodedef's 30 declared inputs.*

---

## Decisions the exporter makes for you

Read this section before you file a bug. Each entry names the trigger, the
substitution, whether you are told, and how to control it.

Legend for **Told?**: **Error** = export stops; **Warning** = diagnostics +
UI/CLI warning; **Info** = diagnostics sidecar only; **Silent** = no record
anywhere.

### Color space

| Trigger | What happens | Told? | Control |
|---|---|---|---|
| Color input, image tagged **Non-Color/Raw** | authored `lin_rec709` | **Warning** | retag the image, or accept |
| Color input, image tagged **sRGB** or untagged | authored `srgb_texture` | — | — |
| Color input, image tagged **Linear Rec.709** | authored `lin_rec709` | — | — |
| Data input, image tagged **Non-Color/Raw** | no color space authored | — | — |
| Data input, image tagged **sRGB/lin_rec709** | **export fails** | **Error** | retag the image `Non-Color` |
| Data input, **alpha channel**, any tagging | no color space authored | **Silent** | — |
| Any input, color space outside the verified set | **export fails** | **Error** | retag to sRGB / Non-Color / Linear Rec.709 |
| Baked AO texture | forced `Non-Color` | **Silent** | — |

The token set the preflight accepts, and the postprocess rename of Blender's
ColorSpaceAPI opinion `srgb_rec709_display` to `srgb_rec709_scene`, follow what
the RealityKit engine actually recognizes — see the color-space section of
[APPLE_PLATFORM_CONTRACT.md](APPLE_PLATFORM_CONTRACT.md).

A data texture carries no MaterialX color space at all. An absent color space
is MaterialX's no-transform contract, which is exactly what a roughness,
metallic, or normal image needs. RealityKit has no mapping for the lowercase
`raw` token, and a reader that carries it makes Reality Composer Pro replace
the whole material with a striped placeholder. The check you retag images for
is unchanged: a roughness or normal map left at sRGB still stops the export.

The retained `UsdPreviewSurface` network is separate. It keeps
`sourceColorSpace = "raw"` and `colorSpace:name = "data"` on its
`UsdUVTexture` nodes, which is the USD preview contract and is what Quick Look
reads.

Each surface input has a role: `color` or `data`
(`texture_colorspace_role`, `Plugin/export/materials/graph.py:41-50`). The
`color` role covers the twelve names at `:25-38` — `baseColor`,
`emissiveColor`, `subsurfaceColor`, `sheenColor`, `specularColor`,
`coat_color`, `fuzz_color`, and the snake_case variants. Everything else is
`data`. Normal maps are always forced to `data`
(`Plugin/export/materials/graph.py:1094-1098`).

The Blender token is first normalized to one of `srgb`, `raw`, `lin_rec709`,
or `unsupported:<name>` (`_normalize_colorspace`,
`Plugin/export/materials/extract/core.py:2898-2917`). The MaterialX token is
then chosen by `_materialx_file_colorspace`
(`Plugin/export/materials/textures.py:354-412`) and written with
`SetColorSpace` (`:161-163`).

**Non-Color on a color input** is the one place the exporter deliberately
overrides your tagging, and for a reason
(`Plugin/export/materials/textures.py:399-404`). Blender applies no transfer
function to a Non-Color image, so a color input reads its texels as
scene-linear. MaterialX has no `raw` contract for color and RealityKit rejects
the token, so the exporter names the pass-through Blender actually performs:
`lin_rec709`. Retagging as sRGB would introduce a decode Blender never
applied.

AO textures authored by the bake path are force-tagged `'Non-Color'`
regardless of the file's actual tagging
(`Plugin/export/materials/extract/core.py:304`).

The material prim and the stage root both get `ColorSpaceAPI` with
`colorSpace:name = "lin_rec709_scene"`
(`Plugin/export/materials/author.py:288-316`).

#### Limitation: a Non-Color image on Base Color fails the export

A Non-Color image on a perceptual color input currently cannot export, even
though the MaterialX graph itself is authored correctly. The exporter emits
the warning `Non-Color image on perceptual color input 'baseColor' exported as
lin_rec709 (already-linear scene color).` and authors
`colorSpace = "lin_rec709"` — but it also leaves Blender's native
`UsdPreviewSurface` network in place alongside the MaterialX graph, and
Blender's own USD exporter writes `colorSpace:name = "data"` on that native
reader. Preflight's role inference then sees a texture feeding `diffuseColor`
with a data color space and fails:

```
[TEXTURE_COLOR_SPACE_MISMATCH] /root/_materials/MatNonColorBase/Image_Texture:
  Base, emissive, and other perceptual color textures must use an authored sRGB or
  linear Rec.709 color space.   details: {"actual": "data"}
```

`Image_Texture` in that path is Blender's naming; the exporter names its own
readers `Image`, `Image_1`, and so on
(`Plugin/export/materials/helpers.py:111-119`).

**What to do:** tag the image `sRGB`.

*Verification: observed on Blender 5.2 at repository commit `35354bb`.*

### Refused and dropped Principled inputs

| Trigger | What happens | Told? | Control |
|---|---|---|---|
| Coat Tint, Sheen Roughness, coloured or linked Specular Tint, anisotropy, transmission, thin film, thin wall, Subsurface IOR, linked coat controls | **export fails** (strict validator) | **Error**, naming the input, with a bake remedy | bake |
| Specular Tint achromatic and brighter than 1 | **export fails**; with `normalize_unsupported_values` it is clamped to white for the export instead | **Error** naming the clamp; **Warning** naming the clamped value once applied | enable the clamp, or set it to white |
| Sheen Roughness reaching the graph builder by another route | dropped | **Warning**: `RealityKit PBR Surface 2 has no sheen roughness input; bake this control.` | bake |
| Unlit surface, any PBR input | dropped | **Warning**, naming each | — |

The validator runs first, so the builder's own sheen-roughness warning is a
second line of defence for a caller that skips validation. The unlit path
filters against the nodedef's declared inputs rather than a second hard-coded
list, so the two cannot drift.

### Opacity, transparency, and cutout

| Trigger | What happens | Told? |
|---|---|---|
| Principled `Alpha` linked, or constant `< 0.999` | material treated as transparent | **Silent** |
| Material not transparent | `opacity` is not authored at all | **Silent** |
| Transparent, and `blender_to_rcp_alpha_cutout_threshold` is a finite float in `[0,1]` | `opacityThreshold` authored → **cutout** | **Silent** |
| Anything else | no threshold → **blend** | **Silent** |
| Base Color mixes `premul` and straight textures | **export fails** | **Error** |
| Base Color textures are all `premul` | `hasPremultipliedAlpha = true` | **Silent** |
| Premultiplied base color + AVIF encode/resize | **export fails** | **Error** |

Transparency detection reads the actual `Alpha` input, not the render method
(`material_has_transparency`,
`Plugin/export/materials/extract/core.py:60-94`). Blender 5.2's
`surface_render_method` chooses *how* Eevee renders transparency, not
*whether* the surface has any.

**Cutout is opt-in and never inferred.** Blender 5.2 exposes only `DITHERED`
and `BLENDED`; neither declares a cutout, so the exporter refuses to imply a
hard threshold (`opacity_threshold_from_material`, `:97-124`). A boolean flag
would not be enough — without a numeric threshold there is no complete cutout
contract. To get a cutout, set the custom property
`blender_to_rcp_alpha_cutout_threshold` on the material to a float in
`[0, 1]`. Out-of-range, non-finite, boolean, and non-numeric values are
ignored silently.

`hasPremultipliedAlpha` is a material-level flag in RealityKit, so the
exporter derives it from every texture feeding Base Color
(`_apply_base_color_texture_semantics`, `:2456-2494`). It is set only when the
alpha-mode set is exactly `["premul"]`. A mix is fatal
(`Plugin/export/materials/rewrite.py:405-413`):

> RealityKit has one material-level hasPremultipliedAlpha flag. Bake Base
> Color and Alpha to one PNG, or make every contributing texture use the same
> straight-alpha convention.

A second gate refuses to let Blender 5.2's AVIF writer touch premultiplied
base color, because that encoder does not preserve the premultiplied
relationship (`require_safe_texture_alpha_staging_policy`,
`Plugin/export/usd_textures.py:730-774`). A byte-for-byte `ORIGINAL` AVIF copy
is still allowed, since no encoder runs.

### Normal maps

| Trigger | What happens | Told? |
|---|---|---|
| Normal Map node, tangent space, Strength 1.0 | `ND_normal_map_decode` (RealityKit's decoder) | **Silent** |
| Tangent space, constant Strength ≠ 1.0 | `ND_normal_map_decode`, then a mix toward the geometric normal and a renormalize — Blender's own smooth-shaded strength, expressed in tangent space | **Silent** |
| Object or world space | **export fails** with bake advice | **Error** |
| Normal Map node with **linked** Strength | **export fails** (strict validator) | **Error** |
| Normal Map node set to **DirectX** convention | **export fails** (strict validator) | **Error** |
| Bump node anywhere in the chain | **export fails** (strict validator) | **Error** |

The decoder choice lives at `_can_use_realitykit_normal_map_decode`
(`Plugin/export/materials/textures.py`) and the branch above it. The image
reader is always `ND_image_vector3` with no authored color space
(`_image_output_hint`). It also carries `inputs:default = (0.5, 0.5, 1.0)`, a
flat tangent normal, so a texture that fails to resolve degrades to unbumped
shading instead of feeding `(-1, -1, -1)` into the decoder.

`ND_image_vector3` → `ND_normal_map_decode` → `inputs:normal` is the chain
PBR Surface 2 takes, and it is the chain shipping RealityKit packages use.

RealityKit expects the OpenGL green-channel convention, so the DirectX
convention is rejected (`Plugin/nodes/validate.py`). The space check exists to
prevent double-decoding; a linked Strength is refused because only a constant
can be folded into the tangent-space mix.

The Bump rejection deserves a note. The resolver contains a branch that walks
a Bump node's `Height` input and returns it as if it were the normal
(`Plugin/export/materials/extract/core.py:1420-1431`). That would be wrong — a
height map is not a normal map. The branch never runs: `BUMP` is in the
validator's `BAKE_TYPES` (`Plugin/nodes/validate.py:65`) and every caller is
strict, so the export is blocked first. A material with
`Image → Bump → Normal` is rejected with `UNSUPPORTED_MATERIAL_NODES`,
`"node_type": "BUMP"`, `"Node requires baking for RealityKit."`

*Verification: Bump rejection observed by exporting from Blender 5.2.*

### Specular and IOR

| Trigger | What happens | Told? |
|---|---|---|
| `Specular IOR Level` present | `specular_weight = clamp(value × 2, 0, ∞)` | **Silent** |
| `Specular IOR Level` linked | `specularWeight` = a `multiply` node × 2.0 | **Silent** |
| Constant achromatic Specular Tint > 1.0, **and** *Normalize Unsupported Values* on | clamped to `[1,1,1]` for this export only | **Warning**, prominent |
| Same, but the setting is off | **export fails** | **Error** |
| Colored or linked overbright Specular Tint | **export fails** regardless of the setting | **Error** |
| Nothing sets `specular` | defaulted to `0.5` | **Silent** |

**Why clamping, rather than moving the excess elsewhere.** An overbright tint of
`[2,2,2]` could in principle be expressed as `[1,1,1]` with `specularWeight = 2`,
preserving the energy instead of discarding it. The exporter does not do this.
Apple does not document PBR Surface 2 closely enough to assume that weight and
tint trade off that way, and no measurement settled it — so redistribution is a
guess that happens to look plausible, and a clamp is a loss you can see. If you
want to revisit it, `scripts/generate_pbr2_specular_tint_research.py` builds a
three-sphere comparison (direct, clamped, redistributed) to view under one fixed
Reality Composer Pro environment.

Blender's default `0.5` multiplier corresponds to PBR2 weight `1`
(`Plugin/export/materials/extract/core.py:279-281`, `:437-438`;
`Plugin/export/materials/graph.py:773`, `:784`).

The Specular Tint normalization is the exporter's only value rewrite, and it
is deliberately narrow (`safe_overbright_achromatic_specular_tint`,
`Plugin/material_policies.py:20-52`). It accepts a constant only when it is
finite, achromatic, non-negative, and brighter than `1.0`. A linked value is
never rewritten. A colored value requires your judgment, because a clamp would
shift hue or saturation. The operation is export-only and non-destructive —
the module never assigns to Blender datablocks
(`Plugin/material_policies.py:1-6`), and the warning says so (`:75-84`):

> Export-only normalization applied: Principled 'Specular Tint' [...] was
> clamped to [...]. The source Blender material and .blend file were not
> changed. Review the result in Reality Composer Pro.

Control: the *Normalize Unsupported Values* setting
(`normalize_unsupported_values`, `Plugin/ui/panel.py:267-275`).

### Emission

| Trigger | What happens | Told? |
|---|---|---|
| Emission Strength ≈ 1.0 | strength dropped entirely | **Silent** |
| Constant strength + emission **texture** | folded into the texture's `scale` | **Silent** |
| Constant strength + constant color | multiplied into `emissiveColor` | **Silent** |
| Linked strength | `combine3` + `multiply` nodes inserted | **Silent** |

Implementation: `_scaled_color_expr`
(`Plugin/export/materials/graph.py:888-914`), the constant fold at
`:433-508`.

### Subsurface color

If a subsurface weight is present but no subsurface color is, the exporter
copies **Base Color** into `subsurfaceColor` / `subsurface_color`
(`Plugin/export/materials/graph.py:121-139`, and again at `:585-589`). This is
silent. Blender 5.2's Principled has no separate subsurface color input, so
this is a reconstruction, not a translation.

### Sheen

`sheen_color` is synthesized as `sheen_tint × sheen_weight`
(`Plugin/export/materials/extract/core.py:274-278`, recomputed at
`:427-436`). For PBR2 with linked controls, the graph builder instead inserts
`combine3(weight, weight, weight)` then `multiply(tint, that)`
(`Plugin/export/materials/graph.py:746-765`). When either control is linked
the pre-combined constant is discarded and the graph builder combines them
into `sheenColor` itself.

### UVs and texture transforms

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

RealityKit honors at most one 2D texture transform per material. The
equivalence rules live in one import-safe module so source validation,
MaterialX authoring, and composed-USD preflight agree on what counts as a
*distinct* transform (`Plugin/export/materials/mapping.py:1-7`).

An identity mapping resolves to no transform at all — the contract returns
`None` and nothing is authored — because pivot and operation order have no
effect when offset, scale, and rotation are neutral
(`effective_texture_mapping_contract`, `:63-119`). An **explicitly authored**
identity `place2d` is different — it still consumes RealityKit's single
transform slot, so it cannot be discarded
(`authored_texture_mapping_contract`, `:122-144`).

The resolved UV set is part of the contract (`:111-118`): one shared transform
cannot consume two different UV sets, so the same offset/scale/rotation on two
different UV maps still counts as two transforms.

Blender radians become MaterialX degrees at
`Plugin/export/materials/textures.py:526`.

### Type coercion

The authoring stage inserts conversion nodes rather than failing on a type
mismatch.

| Trigger | What happens | Told? |
|---|---|---|
| Texture output type ≠ input type | `_coerce_texture_spec_for_input` rewrites the hint | **Warning** |
| Float input, texture, **no channel specified** | defaults to channel `r` | **Warning** |
| Remaining type mismatch | `convert` node inserted | **Warning** |
| No exact nodedef for a node name + signature | the manifest selector falls back to **output type only**, then to **any** nodedef of that name | **Silent** |
| No `convert` nodedef for the requested pair | selector returns an unrelated `convert` nodedef of the right *output* type | **Silent** |
| Color with 3 components into `color4` | alpha padded with `1.0` | **Silent** |
| Vector with 3 components into `vector4` | padded with `0.0` | **Silent** |
| List into a float input | takes element `[0]` | **Silent** |

Implementation: `Plugin/export/materials/textures.py:46-79`, `:689-695`;
`Plugin/export/materials/conversions.py:243-295`, `:205-240`.

#### Limitation: a wrong-signature convert nodedef can be authored silently

The nodedef selector's fallback chain
(`Plugin/manifest/materialx_nodes.py:91-95`) is the one to watch.
`_create_convert_output` has a `missing_mappings` diagnostic for the "no
matching convert nodedef" case
(`Plugin/export/materials/conversions.py:265-280`), but it only fires when the
selector returns nothing. Because the selector returns a wrong-signature
nodedef instead of `None`, that diagnostic is bypassed and the mismatch is
authored silently. On the shipped manifest:

```
select_nodedef_name_for_node(m, "luminance", output_type="float")        -> ND_luminance_color3
select_nodedef_name_for_node(m, "convert", color3 -> float)              -> ND_convert_boolean_float
```

For example, `Image Texture → RGB to BW → Roughness` exports with `"ok": true` and no diagnostics file, and the resulting
USD contains:

```
def Shader "Convert_roughness" {
    uniform token info:id = "ND_convert_boolean_float"
    color3f inputs:in.connect = </.../pbr_surfaceshader_1_roughness_2.outputs:out>
    float outputs:out
}
```

That is a boolean-to-float nodedef whose `in` is declared `color3f`, feeding
`inputs:roughness`.

**What to do:** check RGB-to-BW graphs in Reality Composer Pro before relying
on them.

*Verification: selector results measured on the shipped manifest; the RGB to
BW export observed on Blender 5.2.*

### Stage-level rewrites

| Trigger | What happens | Told? |
|---|---|---|
| Texture came from dirty or generated pixels | native `UsdPreviewSurface` subtree **deleted** | **Warning** |
| Otherwise | native preview network **retained** alongside MaterialX | **Silent** |
| Material bound but no Blender counterpart | **export fails** | **Error** |
| Material defined inside a variant | **export fails** | **Error** |
| Material inside a read-only OpenUSD prototype | **export fails** | **Error** |
| Material binding authored in an inactive variant with an unresolvable target | **export fails** | **Error** |

The native-network deletion (`_remove_stale_preview_network`,
`Plugin/export/materials/rewrite.py:681-699`) runs only when
`native_preview_stale` is set, which happens only when a contributing image
was dirty or `GENERATED`
(`Plugin/export/materials/extract/core.py:2347-2350`). In every other case
the exported USD carries **two** surface networks — `outputs:surface`
connecting to Blender's `UsdPreviewSurface`, and `outputs:mtlx:surface`
connecting to the RealityKit graph:

```
token outputs:mtlx:surface.connect = </root/_materials/MatFull/pbr_surfaceshader_1.outputs:out>
token outputs:surface.connect = </root/_materials/MatFull/Principled_BSDF.outputs:surface>
```

This is normally harmless — RealityKit prefers the `mtlx` output — but
preflight checks both networks, which is the mechanism behind the
[Non-Color Base Color limitation](#limitation-a-non-color-image-on-base-color-fails-the-export).

*Verification: dual-network output observed by exporting a clean file-backed
material from Blender 5.2.*

---

## Which Blender nodes export

### Where the supported-node lists live

Four places encode "what can this exporter handle", and they are independent
copies:

| Location | Purpose |
|---|---|
| `Plugin/nodes/validate.py:18-145` | the gate. `ALLOWED_UI_TYPES`, `SUPPORTED_TYPES`, `SHADERGRAPH_SUPPORTED_TYPES`, `PARTIAL_TYPES`, `BAKE_TYPES`, `UNSUPPORTED_TYPES` |
| `Plugin/export/materials/extract/core.py:575-673` | advisory warnings only. Local `supported_types`, `partial_types`, `bake_types`, `unsupported_types` inside `collect_material_warnings` |
| `Plugin/export/materials/extract/core.py:1308-2300` | the real resolver. `_resolve_socket_value`'s branch chain |
| `Plugin/manifest/rk_nodes_manifest.json` | the MaterialX nodedefs the graph may reference |

Only the first decides whether your export runs. Only the third decides what
the output actually contains.

The manifest is measured against the installed platform: of its 928 nodedefs,
872 resolve in the runtime's own ShaderGraph libraries and 56 are flagged
`policy.editor_unresolvable` — unrenderable on every Apple 27 runtime, refused
by selection and preflight. See
[APPLE_PLATFORM_CONTRACT.md](APPLE_PLATFORM_CONTRACT.md) for the measurement
and the drift-detection tests.

### Node categories

**Rejected outright** (`UNSUPPORTED_TYPES`,
`Plugin/nodes/validate.py:94-145`) — every non-Principled BSDF
(`BSDF_DIFFUSE`, `BSDF_GLOSSY`, `BSDF_GLASS`, `BSDF_METALLIC`,
`BSDF_REFRACTION`, `BSDF_SPECULAR`, `BSDF_TRANSLUCENT`, `BSDF_TRANSPARENT`,
`BSDF_SHEEN`, `BSDF_VELVET`, `BSDF_TOON`, `BSDF_RAY_PORTAL`, hair BSDFs),
shader combinators (`MIX_SHADER`, `ADD_SHADER`), all volume nodes, all
geometry/attribute inputs (`GEOMETRY`, `OBJECT_INFO`, `CAMERA_DATA`,
`HAIR_INFO`, `CURVE_INFO`, `PARTICLE_INFO`, `POINT_INFO`, `VERTEX_COLOR`,
`VOLUME_INFO`, `WIREFRAME`, `ATTRIBUTE`, `TANGENT`), view-dependent nodes
(`LIGHT_PATH`, `FRESNEL`, `LAYER_WEIGHT`), `AMBIENT_OCCLUSION`, `BEVEL`,
`HOLDOUT`, `BACKGROUND`, and non-surface outputs. Also: any node group that is
not an `RK_*` RealityKit group (`:520-524`), and any node type the exporter
does not recognize at all (`:675`).

**Requires baking** (`BAKE_TYPES`, `:64-92`) — `BUMP`, `DISPLACEMENT`,
`VECTOR_DISPLACEMENT`, the procedural textures `TEX_WAVE`,
`TEX_WHITE_NOISE`, `TEX_MAGIC`, `TEX_CHECKER`, `TEX_BRICK`,
`TEX_POINTDENSITY`, `TEX_SKY`, `TEX_GABOR`, `TEX_IES`, plus `BLACKBODY`,
`LIGHT_FALLOFF`, `WAVELENGTH`, `VECTOR_MATH`, `GAMMA`, `SHADER_TO_RGB`,
`COMBXYZ`, `CURVE_VEC`, `RADIAL_TILING`, the cylindrical/spherical
combine-separate pairs, `FLOAT_CURVE`, and `CURVE_RGB`. Under `strict=True` —
which is always — these are **errors**, not warnings.

**Conditionally supported** — `MIX_RGB`/`MIX` pass only when they are a plain
mix or a multiply/add/subtract of resolvable inputs, or when Factor is 0/1
with a passthrough input (`_is_supported_mix`,
`Plugin/export/materials/extract/core.py:2705`; gate at
`Plugin/nodes/validate.py:631-641`). `MATH` passes only as a true
pass-through — add 0, subtract 0, multiply 1, divide 1
(`_is_identity_math_node`, `:2725`; gate at `:643-652`). `VALTORGB`
(Color Ramp) passes only in RGB color mode with Linear, Constant, or Ease
interpolation (`:608-620`).

**Limited support** (`PARTIAL_TYPES`, `:58-62`) — `TEX_COORD`, `UVMAP`,
`MAPPING`. Warning: UV mapping is applied for Image Texture inputs only.

**Supported** (`SUPPORTED_TYPES`, `:23-53`) — 29 types: `OUTPUT_MATERIAL`,
`BSDF_PRINCIPLED`, `EMISSION`, `TEX_IMAGE`, `NORMAL_MAP`, `RGB`, `VALUE`,
`INPUT_BOOL`, `INPUT_INT`, `INPUT_VECTOR`, `SEPARATE_COLOR`, `SEPARATE_RGB`,
`SEPARATE_XYZ`, `SEPXYZ`, `TEX_NOISE`, `TEX_VORONOI`, `TEX_GRADIENT`,
`TEX_ENVIRONMENT`, `CLAMP`, `HUE_SAT`, `BRIGHTCONTRAST`, `VALTORGB`,
`RGBTOBW`, `COMBINE_COLOR`, `VECTOR_ROTATE`, `VECTOR_TRANSFORM`, `NORMAL`,
`MAP_RANGE`, `INVERT`. Plus `FRAME` and `REROUTE`, which are skipped entirely
(`ALLOWED_UI_TYPES`, `:18-21`).

`SHADERGRAPH_SUPPORTED_TYPES` (`:55-56`) is written `{\n}`, which Python
parses as an empty **dict**, not a set. Its branch (`:623-629`) — "supported
by ShaderGraph but not yet mapped by the exporter" — is unreachable.

### Node groups, reroutes, and muted nodes

The three layers do not traverse the node tree identically.

| Concern | Validator | Extractor warnings | Resolver |
|---|---|---|---|
| Descends into node groups | **no** | **no** | yes (`extract/core.py:1442-1472`) |
| `GROUP_INPUT` | n/a | n/a | **unhandled** — no branch exists |
| Reroute | skipped | falls through to "unrecognized" | traversed transparently |
| `node.mute` | **ignored** | **ignored** | **ignored** |
| RK-group identity | `rk_node_id` **or** catalog name (`validate.py:785-793`) | `rk_node_id` **or** `RK_` prefix (`core.py:152-157`) | `rk_node_id` **only** (`core.py:1137-1144`) |

Two consequences matter to you as an artist:

- **Nodes inside a group are invisible to validation.** Both
  `_collect_used_nodes` implementations
  (`Plugin/nodes/validate.py:796-833`,
  `Plugin/export/materials/extract/core.py:753-796`) walk only the material's
  own node tree. A `VOLUME_SCATTER` inside a group is never reported by
  either. In practice the validator's blanket rejection of non-RK groups
  (`:520-524`) prevents this from mattering.
- **Muted nodes are evaluated as if enabled.** No material-path code reads
  `node.mute`. A muted Invert still inverts in the exported material, so the
  export can diverge from the Blender viewport with no diagnostic. This is
  consistent across all three layers.

### Where the lists disagree

The lists have drifted, in both directions. Each divergence below is a current
limitation of the exporter.

**A. The extractor's warning table is 11 types behind the validator.** Its
local `supported_types` (`Plugin/export/materials/extract/core.py:575-591`)
has 15 entries; the validator's has 26. The following types validate clean and
translate correctly, but produce a spurious advisory warning during export:

| Node type | Validator | Extractor warning table | Warning you see |
|---|---|---|---|
| `TEX_NOISE`, `TEX_VORONOI`, `TEX_GRADIENT`, `TEX_ENVIRONMENT` | supported | *unlisted* | `... is unrecognized; export may differ.` |
| `CLAMP`, `HUE_SAT`, `BRIGHTCONTRAST`, `RGBTOBW`, `COMBINE_COLOR`, `VECTOR_ROTATE`, `VECTOR_TRANSFORM`, `NORMAL`, `MAP_RANGE` | supported | *unlisted* | `... is unrecognized; export may differ.` |
| `INVERT` | supported | `bake_types` | `... requires baking for RCP.` |

The resolver handles all of them
(`Plugin/export/materials/extract/core.py:1561`, `:1599`, `:1652`, `:1712`,
`:1719`, `:1727`, `:2012`, `:2022`, `:2069`, `:2098`, `:2115`, `:2127`,
`:2140`). The export succeeds; the diagnostics contradict it. Trust the
export.

**B. `CURVE_RGB` is rejected despite a full implementation.** The resolver has
a complete RGB Curves translation — knot extraction, identity detection,
MaterialX curve authoring
(`Plugin/export/materials/extract/core.py:1917`, helpers at `:2866-2895`).
The validator puts `CURVE_RGB` in `BAKE_TYPES`
(`Plugin/nodes/validate.py:91`), so under strict mode it is always an error.
The translation code cannot be reached from any shipped surface. A material
with `Image → RGB Curves → Base Color` is rejected with
`"node_type": "CURVE_RGB", "message": "Node requires baking for RealityKit."`
Bake the material, or remove the RGB Curves node.

**C. No stage checks color space until authoring.** Neither the validator nor
`collect_material_warnings` inspects `image.colorspace_settings`. An
sRGB-tagged roughness map validates clean and then fails the export in
stage 4 — see [Author USD](#author-usd).

**D. `BUMP` is safe only because the validator blocks it.** The resolver
would silently reinterpret a height map as a normal map (`:1420-1431`); only
`BUMP`'s membership in the validator's `BAKE_TYPES` prevents that from
running. See [Normal maps](#normal-maps).

**E. Node properties inside `SUPPORTED_TYPES` are unchecked.** Membership is
by node *type*. Several types are only translatable in certain
configurations, and the validator checks some of those but not others:

| Configuration | Validator | Resolver | Result |
|---|---|---|---|
| `VALTORGB` non-RGB mode or exotic interpolation | checked (`validate.py:608-620`) | rejects | agreed |
| `VALTORGB` with fewer than 2 stops | **unchecked** | rejects (`core.py:1831-1832`) | validate clean → export fatal |
| `COMBINE_COLOR` in HSV/HSL mode | **unchecked** | rejects (`core.py:2023-2025`) | validate clean → export fatal |
| `TEX_IMAGE` with no image | checked (`validate.py:527`) | returns `None` | agreed |
| `TEX_ENVIRONMENT` with no image | **unchecked** | falls through to unresolved (`core.py:2220-2227`) | validate clean → export fatal |

**F. A material with no active surface shader validates clean.** With no
`OUTPUT_MATERIAL`, or with its `Surface` unconnected, `_collect_used_nodes`
returns an empty or single-node set (`Plugin/nodes/validate.py:800-802`,
`:824-833`), so there is nothing to complain about. Extraction then leaves
`type` as `unknown` and the graph build returns nothing, producing
`Material type 'unknown' could not be mapped to a RealityKit graph.`
(`Plugin/export/materials/rewrite.py:173-177`).

**G. A `Mapping` node on a procedural texture is silently discarded.** The
validator's transform audit inspects `TEX_IMAGE` and `TEX_ENVIRONMENT` only
(`Plugin/nodes/validate.py:421`), and the resolver's `MAPPING` branch just
forwards the `Vector` input
(`Plugin/export/materials/extract/core.py:1431-1440`). A `Mapping` driving
`TEX_NOISE.Vector` changes nothing in the export, and nothing reports it.

**H. Nested unresolved sub-expressions are dropped without a warning.** The
unresolved check inspects only the **top level** of each Principled input
(`Plugin/export/materials/extract/core.py:402`). `_expr_from_socket`
(`:2624-2654`) returns the `{"kind": "unresolved"}` dict rather than `None`,
so a surrounding `mix`, `clamp`, `hsvadjust`, or similar node is still built
around it; the graph builder then returns `None` for that child
(`Plugin/export/materials/graph.py:350-351`, `:399-401`) and the input is
simply never authored, falling back to the nodedef default. The material
exports "successfully" with a missing input. Every multi-input resolver
branch has this shape.

**What agrees.** The mapping/transform contract is genuinely shared —
`validate.py` imports the extractor's `_extract_mapping_from_node` and the
canonical `effective_texture_mapping_contract`
(`Plugin/nodes/validate.py:409-413`), and preflight uses the same module
(`Plugin/export/materials/mapping.py`). `UNSUPPORTED_TYPES` and
`PARTIAL_TYPES` are identical between the validator and the extractor's
table, and `BAKE_TYPES` differs only by `INVERT`. The Mix/Math passthrough
predicates are duplicated verbatim and behave identically. The unlit path
reads the nodedef's declared inputs directly instead of duplicating a list.

*Verification: the `CURVE_RGB` rejection was observed by exporting from
Blender 5.2.*

---

## The texture pipeline

Three modules run in this order:

| Stage | Module | Entry point |
|---|---|---|
| Datablock → absolute path | `materials/extract/core.py` | `_resolve_image_path` (`:2988`) |
| MaterialX reader authoring | `materials/textures.py` | `_create_texture_connection` (`:82`) |
| Copy/transcode into the output tree | `export/usd_textures.py` | `_stage_texture_source` (`:336`) |

`materials/textures.py` performs no file I/O at all; it treats
`texture_spec['path']` as an opaque string (`:94-96`, `:159-160`). Staging
runs twice — once before material rewrite
(`Plugin/export/postprocess_usd.py:38-46`) and once after (`:74-82`). The
second pass localizes the absolute temp paths that MaterialX authoring wrote.

### How image paths resolve

The rule is *current Blender pixels win* (`_resolve_image_path`,
`Plugin/export/materials/extract/core.py:2988-3046`).

| Image state | Behavior |
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

UDIM texture sets are not supported, but they fail closed: the export stops
with `Texture file not found` rather than shipping a collapsed or missing
texture. Bake UDIM materials to a single texture.

Staging a snapshot copies `colorspace_settings.name` and `alpha_mode`
**before** the pixels, because Blender 5.2 clears the buffer otherwise
(`:3168-3179`).

The reuse cache key (`_image_cache_key`, `:3191-3237`) mixes the datablock
pointer, name, source, dirty and packed state, both filepaths, a
`(st_dev, st_ino, st_size, st_mtime_ns)` fingerprint, dimensions, float-ness,
file format, and the library filepath — because a pointer alone is not an
image identity. A cache hit is honored only for clean, unpacked,
non-generated images (`:3023-3030`).

*Verification: the UDIM failure was observed on Blender 5.2 with a 2-tile
`tile.<UDIM>.png` set (tiles 1001/1002) on Base Color.*

### Where staged textures go

```
<usd_dir>/textures/<portable-usd-filename>/<32-hex generation token>/
```

Layout at `Plugin/export/usd_textures.py:131`, namespace from
`Plugin/export/staging_namespace.py:17-28`. The generation token is a
`secrets.token_hex(16)` recorded in an `O_EXCL` marker under
`<usd_dir>/.blendertorcp_generations/` (`:31-66`), so every sidecar of one
export attempt shares one immutable namespace and the root USD can be swapped
in last.

Authored asset values are made relative with `os.path.relpath` against the
owning layer's directory (`Plugin/export/usd_textures.py:249-253`). The
`"textures"` directory name is a hard-coded literal and is not configurable.

### Content-addressed file names

Staged textures are named after their content
(`_finalize_content_addressed_texture`,
`Plugin/export/usd_textures.py:892-951`):

```
<usd-file-stem>-<source-stem>-<sha256 64 hex><.ext>
```

The **final destination file's bytes** are hashed with SHA-256, streamed in
1 MiB chunks (`:975-983`) — not the source, not the pixels, not the path, not
the override parameters. The digest is never truncated, because publication
installs sidecars before atomically switching the root USD, and a stable name
could otherwise be observed with stale bytes (`:893-898`).

The semantic stem is NFC-normalized, has any pre-existing `-<64hex>` suffix
stripped for idempotency (`:924-926`), and is truncated to 120 UTF-8 bytes
(`:90`, `:1002-1007`).

Deduplication happens at four levels: current-generation recognition
(`:954-972`), a `(source path, override key)` map, a
`(SHA-1 of source bytes, override key)` map (`:864-889`), and
content-address arrival, where a byte-identical existing file is reused and
the duplicate unlinked (`:938-948`). Images with identical pixel content
stage as one shared file. A same-name file with *different* bytes, or a
symlink, raises `Content-addressed texture collision` (`:944-946`).

*Verification: on Blender 5.2, three distinct 8×8 images (albedo/orm/nrm)
staged three files; three images with identical pixel content staged exactly
one, shared by all three MaterialX readers.*

### Format conversion

The package accepts `.avif`, `.exr`, `.jpg`, `.jpeg`, and `.png`
(`Plugin/export/usd_textures.py:72-78`). The decision lives in
`_effective_texture_override` (`:705-727`):

| Source | Behavior |
|---|---|
| `.exr` | **always** byte-copied. Overrides ignored, with a warning (`:709-710`, `:379-383`) |
| `.hdr` | **export fails** — convert to OpenEXR first (`:370-378`) |
| `.png`, `.jpg`, `.jpeg`, `.avif` | byte-copied, unless you enabled an override |
| everything else (`.tif`, `.tga`, `.bmp`, `.gif`, `.dds`, `.webp`, `.ktx`) | **forced PNG conversion, even with overrides off** (`:723-727`) |

Encoding goes through `imbuf` first (`:1188-1224`, quality 90 for lossy
formats, `:58`), falling back to Blender's image API (`:1158-1185`).
Conversions are atomic — encoded into a temp file in the same directory,
validated by a real decode (`:1014-1081`), then `os.replace`
(`:1084-1126`) — because source and destination can be the same file across
the two staging passes.

A failed AVIF conversion retries as PNG at the same resolution and warns
(`:813-825`, `:452-454`).

**Setting**: *Optimize Source Textures*
(`export_texture_settings_enabled`, default off,
`Plugin/ui/panel.py:442-447`) gates *Image Format* (`bake_image_format`:
`ORIGINAL` / `AVIF` / `PNG`, default `AVIF`, `:464-474`).

### Resizing

Resizing is a max-dimension clamp only. It never upscales and never forces
power-of-two dimensions.

The setting is *Texture Resolution* (`bake_resolution`:
`ORIGINAL`/512/1024/2048/4096/`CUSTOM`, default `2048`,
`Plugin/ui/panel.py:449-462`). `ORIGINAL` maps to `0`, meaning no clamp
(`Plugin/export/bake_textures.py:1133-1145`).

When the longest edge exceeds the limit, both dimensions scale by
`max_resolution / longest`, floored at 1, aspect preserved — bilinear via
imbuf (`Plugin/export/usd_textures.py:1227-1238`) or Blender's default filter
via `image.scale` (`:1249-1264`).

You are not told the resulting dimensions. Neither resize helper takes a
`diagnostics` argument; the only trace is an anonymous counter
(`Plugin/export/diagnostics.py:147-149`) and a `generated_files` entry with
role `texture_override` (`Plugin/export/usd_textures.py:492-500`).

### Reader authoring and channel extraction

The reader follows what the shader input needs, not what the file contains.
`_image_output_hint` (`Plugin/export/materials/textures.py`) picks it:

| Situation | Reader |
|---|---|
| normal map | `ND_image_vector3` |
| one scalar channel — roughness, metallic, occlusion | `ND_image_color3`, then a swizzle |
| a shader input that needs the alpha channel | `ND_image_color4`, then a `separate4` |
| everything else | `ND_image_color3` |

Two four-channel readers exist in the MaterialX libraries but are never
authored: `ND_image_vector4` and its partner `ND_swizzle_vector4_float`.
Reality Composer Pro 3.0 cannot instantiate them and replaces the whole
material with a striped placeholder. The preflight rejects them, along with
`ND_extract_vector4` and `ND_separate4_vector4`, so the export stops instead
of shipping a placeholder.

Channel selection then inserts a `swizzle` node, or a `separate4` when the
reader is `color4`, or `separate4` + `combine3` when the same image must serve
both RGB and alpha. Every swizzle emits an informational warning naming the
nodedef and channel.

Readers are shared via a cache keyed on path, texcoord, the full mapping
tuple, colorspace, colorspace role, alpha mode, type, image-type override, the
`force_separate4` flag, and the sampling modes (`_texture_cache_key`). The
requested output type and channel are deliberately not part of the key: one
file is one reader, and each consumer hangs its own swizzle off it.

### When a texture has no alpha

Asking for the alpha channel of a file that has only three is the one case
where the source's real channel count matters. The exporter measures it from
the Blender image datablock, falling back to the file header, and refuses the
read: the shader input keeps its default — fully opaque, for opacity — and a
warning names the file and the input. No four-channel reader is authored over
a three-channel file.

A file that has alpha nothing reads is unaffected. The reader stays
`ND_image_color3`; alpha alone never upgrades it.

Non-default sampling modes from the Blender Image Texture node are authored
on the reader as the uniform string inputs the shipped RCP 3 (80.0.1.500.1)
`ND_image_*` nodedefs declare: Extension **Extend** →
`uaddressmode`/`vaddressmode = "clamp"`, **Clip** → `"constant"`,
**Mirror** → `"mirror"`; Interpolation **Closest** →
`filtertype = "closest"`, **Cubic**/**Smart** → `"cubic"`. Repeat and Linear
are the nodedef defaults and author nothing (`_image_node_sampling`,
`Plugin/export/materials/extract/core.py`).

A packed ORM texture read for two channels produces one reader. One `orm.png`
feeding Roughness (G) and Metallic (B) through a Separate Color node authors a
single `ND_image_color3` prim with two `ND_swizzle_color3_float` nodes hanging
off it — one set to `b`, one to `g` — and no authored color space.

*Verification: checked against Reality Composer Pro 3.0 (80.0.1.500.1) and
Blender 5.2. `tests/unit/test_reader_chain_rcp_contract.py` pins the reader,
swizzle, and color-space contract; `tests/integration/test_supported_node_sweep.py`
pins it across a real Blender export.*

### Worked example

The MaterialX half of an export with an sRGB albedo, a packed
Non-Color ORM, and a Non-Color tangent normal map:

```
def Shader "pbr_surfaceshader_1" {
    uniform token info:id = "ND_realitykit_pbr_surfaceshader_2_0"
    color3f inputs:baseColor.connect  = </.../Image.outputs:out>
    float   inputs:metallic.connect   = </.../swizzle_metallic_b.outputs:out>
    float   inputs:roughness.connect  = </.../swizzle_roughness_g.outputs:out>
    float3  inputs:normal.connect     = </.../NormalMap_normal.outputs:out>
    float   inputs:specular = 0.5
    color3f inputs:emissiveColor = (0, 0, 0)
}
def Shader "Image"   { ND_image_color3  ... ( colorSpace = "srgb_texture" ) }
def Shader "Image_1" { ND_image_color3  ... }
def Shader "swizzle_metallic_b"  { ND_swizzle_color3_float  inputs:channels = "b" }
def Shader "swizzle_roughness_g" { ND_swizzle_color3_float  inputs:channels = "g" }
def Shader "Image_2" { ND_image_vector3 ...  float3 inputs:default = (0.5, 0.5, 1) }
def Shader "NormalMap_normal" { ND_normal_map_decode }
```

with material-prim metadata:

```
prepend apiSchemas = ["ColorSpaceAPI", "MaterialXConfigAPI"]
customData = { dictionary BlenderToRCP = { string surfaceProfile = "realitykit_pbr2" } }
uniform token colorSpace:name = "lin_rec709_scene"
string config:mtlx:version = "1.38"
```

*Verification: output produced by exporting from Blender 5.2.*

---

## Diagnostics and errors

### CLI error codes

Material translation surfaces through these `error.code` values:

| Code | Stage | Raised at |
|---|---|---|
| `UNSUPPORTED_MATERIAL_NODES` | validation | `Plugin/api/commands/export.py:236-243` |
| `POSTPROCESS_FAILED` | export | `Plugin/api/commands/export.py:277-284` |
| `EXPORT_FAILED` | export | `Plugin/api/commands/export.py:328-336` |
| `BAKE_EXPORT_FAILED` | bake-export | `Plugin/api/commands/bake_export.py:703-708` |
| `MISSING_EXTERNAL_TEXTURES` | preflight | `Plugin/export/asset_preflight.py:186-194` (bake path only) |

There is no central registry. `CommandError` takes a free-form `code: str`
(`Plugin/api/errors.py:222-252`) and every code is a string literal at its
raise site. Preflight issue codes are a separate namespace and never appear
in `error.code` — they survive only inside `error.message` and as structured
objects in the diagnostics sidecar.

### Where diagnostics go

- **CLI**: the JSON envelope on stdout, plus `artifacts.diagnostics_path`
  pointing at `<output>.diagnostics.json`. Failed exports always write it;
  successful ones only when `diagnostics_enabled` is on
  (`Plugin/ui/panel.py:533-541`).
- **Blender UI**: the first five errors and warnings via `self.report`
  (`Plugin/ops/export_operator.py:231-240`, `:276-282`), full JSON through
  *Show Diagnostics*.
- **Preflight payload**: `diagnostics.data["realitykit_preflight"]` and the
  alias `diagnostics.data["validation"]["realitykit"]`, each
  `{profile, asset_path, ok, counts, issues[]}`
  (`Plugin/export/realitykit_preflight.py:213-224`, `:1689-1700`). This is
  the only place `info`-severity findings appear.

### Fatal material messages

Every one of these stops the export.

| Message | Source |
|---|---|
| `Material graph contains unresolved input(s): ...` | `rewrite.py:142-148` |
| `MaterialX graph construction failed: ...` | `rewrite.py:180-186` |
| `MaterialX authoring failed: ...` | `rewrite.py:232-239` |
| `Data texture '<input>' must use Blender Non-Color/raw, not '<x>'` | `textures.py:392-395` |
| `Unsupported Blender image color space '<x>' for '<input>'` | `textures.py:377-383` |
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
