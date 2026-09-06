# Evaluation scenes

Twenty-four small `.blend` files, one behaviour each, for checking by eye what
no automated test can: whether an export **looks right** in Reality Composer
Pro.

Regenerate the scenes:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python scripts/build_test_scenes.py
```

Export all of them:

```bash
scripts/export_test_scenes.sh
```

That writes `References/RealityComposerProProject/Export/<scene>/<scene>.usdz`.
Import those into the Reality Composer Pro project yourself.

## How to read a verdict

Every row names three outcomes, because two is not enough:

- **Correct** — what you should see.
- **Wrong** — the feature reached the file but carries the wrong data. This is
  the dangerous one: the asset looks plausible.
- **Not built** — Reality Composer Pro's grey/cyan diagonal placeholder stripes,
  or a flat default-grey surface. The whole shader graph was discarded, every
  texture binding with it.

**Do not compare against the Blender render.** Lights are dropped silently, so
your Blender render is lit by a sun that never reaches the export while Reality
Composer Pro relights the asset under its own environment. A mismatch is
guaranteed and tells you nothing. Every scene that needs a reference carries its
own control object in frame instead.

## Geometry

| Scene | Correct | Wrong | Not built |
|---|---|---|---|
| `t01_orientation_scale` | An upright red post 1 m tall, base on the floor, green foot pointing one way and a blue nub the other | Lying on its side (up-axis lost), or 100× too big (unit scale lost), or the foot and nub swapped (handedness flipped) | — |
| `t02_uv_layout` | A cube whose faces each show the four-quadrant grid, white corner stamp at one corner | Faces stretched, rotated, or all showing the same quadrant | Grey cube |
| `t03_vertex_color` | Cube ramping blue at the bottom to red at the top | Flat grey or flat single colour — the colour attribute was not read | Grey cube |
| `t04_multi_material` | Alternating red and blue faces | All one colour (slots collapsed) or the two swapped | Placeholder stripes |
| `t15_dropped_curves` | **Only the green cube.** The Bezier circle and NURBS path are gone, and nothing warned | Curves present — the doc is wrong, tell someone | — |

## Materials and textures

| Scene | Correct | Wrong | Not built |
|---|---|---|---|
| `t05_metal_roughness` | Left sphere blurs its reflection across a gradient; right sphere is a sharp mirror | Both spheres identical — roughness never arrived | Grey spheres |
| `t06_normal_map` | Left panel shows diagonal ridges under moving light; right panel is flat | Both flat (map dropped), or ridges look inverted (green channel flipped) | Grey panels |
| `t07_emission` | Left sphere glows green in shadow; right stays dark | Both dark — emission dropped | Grey spheres |
| `t08_opacity` | Left sphere shows the cyan bar through it; right hides it | Both opaque (alpha dropped) or both transparent | Grey spheres |
| `t09_wrap_filter` | Left cube: grid tiled 3×, smooth edges. Right: hard-edged blocky texels, and the area outside 0–1 UV is empty rather than repeating | Right cube tiling like the left (Clip became Repeat) or smooth (Closest became Linear) | Placeholder stripes |
| `t10_texture_transform` | Grid tiled 3× and rotated 30° | Untiled and unrotated (transform dropped), or tiled ⅓× (the transform was inverted) | Placeholder stripes |
| `t17_procedural_noise` | Left sphere's reflection varies blotchily; right is evenly blurred. Export warns the noise is approximated | Both spheres identical — the noise was dropped despite the warning | Grey spheres |

The noise scene will **not** match Blender pixel for pixel. That is expected and
warned about; the verdict is only whether it varies at all.

## Animation

| Scene | Correct | Wrong | Not built |
|---|---|---|---|
| `t11_transform_animation` | Two takes: one slides the cube left-to-right, one lifts it | One take only, or both playing the same motion | — |
| `t12_skinned_limb` | The cylinder bends 75° at its midpoint, deforming smoothly | Bends rigidly at the joint, or does not move | — |
| `t13_shape_keys` | `Squash` and `Lean` appear as drivable shapes; driving `Squash` flattens the ball, `Lean` shears it sideways | Driving one produces the other's motion (targets mismatched); shading does not follow the deformation, which is expected — see below | — |

Blend-shape shading is a known Reality Composer Pro limitation: it discards
normal offsets on import, so a driven shape moves its silhouette while lighting
stays at the rest pose. Not an exporter defect.

## Dropped without a warning

These are the highest-value scenes: nothing in the export tells you, so the only
way to notice is to look.

| Scene | Correct | Wrong |
|---|---|---|
| `t14_dropped_lights_cameras` | **Only the yellow cube.** Both lights and the camera are absent from the outliner, and the export reported no warning | Any of them present — the doc is wrong |
| `t16_dropped_world` | A chrome ball reflecting Reality Composer Pro's own environment — **not** magenta | Magenta reflections would mean the world reached the export, which would be new behaviour |

`t16` is deliberately built so its failure is loud: the Blender world is
saturated magenta at strength 4. A chrome ball could not reflect that neutrally
if the world had survived.

## The bake lane

| Scene | Correct | Wrong | Not built |
|---|---|---|---|
| `t20_bake_mask_mix` | Direct export **refuses**; `bake-export --bake-mode LIT_ALBEDO` succeeds and the cube shows a red-to-blue gradient baked into its base colour | A flat single colour — the mix was lost in the bake | Placeholder stripes |

```bash
blendertorcp bake-export References/Blender/t20_bake_mask_mix.blend \
  -o out.usdz --format USDZ --bake-mode LIT_ALBEDO --resolution 256
```

Use **Material Color (LIT_ALBEDO)** here, not the Lighting & Shadows default:
this scene's single sun bakes black sides under `LIT_IBL`, which defeats a
colour check.

## Refusals — no import needed

| Scene | Expected |
|---|---|
| `t18_refused_mix_shader` | Export **stops**. The message names the Mix Shader and points at **Bake Textures & Export**. Judge whether it tells you enough to act |
| `t19_cm_scale_refusal` | Export **stops** with `Scene unit scale is 0.01, but the RealityKit export contract fixes metersPerUnit at 1.0…`. This guard is why working in centimetres does not ship an asset 100× too large. Judge whether the message tells you how to fix it |
| `t21_specular_tint_refusal` | Export **stops** with `UNSUPPORTED_MATERIAL_NODES`, naming Principled *Specular Tint*: its colour is tinted and brighter than 1, which is refused as a value-policy rather than a surface limitation. Nothing is written. This is the fixture `scripts/verify_apple_platform.sh` uses as its expected rejection, so a change here changes that script |

## The lifecycle check

Worth doing once per release on any textured, animated scene — `t13_shape_keys`
or `t12_skinned_limb` are good candidates. Import it, **save the project, close
it, reopen it**, then open the material in the shader graph editor. Materials
must still be editable graphs rather than flattened, and animation must survive.
Nothing automated reaches this, and it is where round-trip damage shows up.

## Also doubling as automated fixtures

These three are driven by `tests/conftest.py` and
`scripts/verify_apple_platform.sh` as well as by eye. Changing them changes
what the suite exports, so edit them only deliberately.

| Scene | Correct | Wrong | Not built |
|---|---|---|---|
| `t22_red_cube` | A single red cube with one material | Any other colour, or more than one material — the suite's simplest fixture is no longer simple | Grey cube |
| `t23_cube_with_4_animations` | Four takes on one cube, each a distinct motion | Fewer than four takes, or two playing the same motion | — |
| `t24_bake_test` | Direct export succeeds, its IOR carried on the surface, and the model keeps its texturing; `bake-export` succeeds with the same texturing baked down | Textures flat, black, or misaligned to the UVs on either path | Placeholder stripes |

`t24_bake_test` exports directly, and it is also the bake lane's real-world
fixture, so bake it as well and compare the two:

```bash
blendertorcp bake-export References/Blender/t24_bake_test.blend \
  -o out.usdz --format USDZ --bake-mode LIT_ALBEDO --resolution 512
```

`t24_bake_test.blend` is credited to Steve Talkowski; see
[`README.md`](README.md).

## What is not covered

Root prim naming and selection-only are settings, not scenes — point any scene at them rather than storing a variant. USDZ image
formats, custom properties and the diagnostics sidecar are checked by the
automated suite, not by eye.

*These scenes exercise the exporter, not Reality Composer Pro's correctness. A
scene that looks right proves the export survived one path through one build;
it is not a compatibility claim.*
