# Feature support

This page tells you which Blender features survive an export, and what happens
to the ones that don't. Read it before you build a scene you intend to ship.

*Applies to: Blender 5.2 LTS; Reality Composer Pro 3.0 (build 80.0.1.500.1);
macOS 27, iOS 27, iPadOS 27, tvOS 27, visionOS 27.*

BlenderToRCP writes USD — `.usda`, `.usdc`, or `.usdz`. Blender's USD exporter
runs first; this add-on then rewrites materials for RealityKit, normalizes the
stage, and validates it before anything reaches your output path.

## How to read the tables

| Word | Meaning |
|---|---|
| **Yes** | The feature reaches the output intact. |
| **Partial** | The feature is carried, but constrained or lossy. The Notes say how. |
| **Refused** | The export stops and tells you what it could not handle. Nothing is written. |
| **Dropped** | The data does not reach the output. The Notes say whether you are warned. |

**Refused and Dropped are not the same problem.** A refusal is a decision: you
get a message naming the material, mesh, or node, and you fix it. A drop means
the export succeeds and the data is gone. Warnings appear in the export result,
in Blender's status report, and in the diagnostics sidecar — but a few drops
emit nothing at all. Those are listed at the end of this page.

## Geometry

| Feature | Supported | Notes |
|---|---|---|
| Polygon meshes | Yes | Quads and n-gons keep their face structure. |
| Mesh normals | Yes | Written face-varying. |
| UV maps | Yes | Every UV map is exported; the first is named `st`. |
| Vertex colors | Yes | Published as `displayColor` and `displayOpacity` so RealityKit reads them. |
| Subdivision surfaces | Partial | The base mesh is written with its subdivision scheme; the renderer decides what to do with it. |
| Multi-material meshes | Yes | Each material becomes a `GeomSubset` binding. |
| Shape keys (blend shapes) | Yes | See the note below on shading. |
| Armature skinning | Yes | Exported through USD's skeletal schema. |
| Instanced (linked) copies | Partial | Each copy is written as its own full mesh, so a scene of linked duplicates exports at full size rather than referencing one prototype. |
| Object hierarchy | Yes | Object transforms and parenting are preserved. |
| Curves, hair, point clouds, volumes | Dropped | These object types are never exported and nothing warns. |
| Cameras and lights | Dropped | Author them in Reality Composer Pro; nothing warns that they were skipped. |

**Shape keys and shading.** Reality Composer Pro discards blend-shape normal
offsets when it imports a USD file — it logs `BlendShape Normal Offsets ignored`,
one line per shape. Shading therefore does not follow a blend-shape deformation:
the silhouette moves and the surface lights as though it had not. A small
corrective key looks right; a large squash or stretch will not. This is the
editor's behavior, and nothing the exporter writes changes it.

## Materials

| Feature | Supported | Notes |
|---|---|---|
| Principled BSDF base color, metallic, roughness, opacity | Yes | The core of every translated material. |
| Emission | Yes | Emissive color reaches the RealityKit surface. |
| Normal maps | Yes | Decoded for RealityKit, including strength. |
| Opacity clip threshold | Yes | Written on the surface. |
| Unlit surface | Yes | Produced by an Emission-output or node-less material, or by the unlit bake modes. |
| Vertex-color materials | Yes | Read from the mesh's first color attribute. |
| RealityKit PBR Surface 2 | Yes | The one surface every translated material terminates in. Verified by import; the richest surface RealityKit has. |
| IOR, Specular Tint, Diffuse Roughness, subsurface, sheen, Coat IOR | Yes | Carried on the surface. A coloured or overbright Specular Tint is refused as a value policy. |
| Coat Tint, Sheen Roughness, anisotropy | Refused | No RealityKit surface carries the first two; anisotropy waits on a verified mapping. Export stops and says bake. |
| Transmission, thin wall, thin film | Refused | Export stops and names the Principled input to bake or clear. |
| Mix Shader and other shader-level mixes | Refused | Use **Bake Textures & Export** instead; the message says so. |
| Noise and Voronoi textures | Partial | Exported as a MaterialX procedural sampled in object space, with a warning. It will not match Blender pixel for pixel. |
| Checker, Brick, Wave, Bump, Gamma and similar | Refused | These need baking; the export names each node. |
| Non-Principled BSDFs, geometry and light-path inputs | Refused | Export stops before writing anything. |
| Math nodes | Partial | Two dozen operations map exactly; the rest are refused with the operation named. |

## Textures

| Feature | Supported | Notes |
|---|---|---|
| Base color, roughness, metallic, normal, occlusion, opacity | Yes | Each role is translated to its RealityKit input. |
| Several textures per material | Yes | No per-role limit. |
| Texture file formats | Partial | AVIF, PNG, JPEG and EXR pass through; other readable formats are converted to PNG. |
| USDZ image formats | Partial | A `.usdz` may contain only PNG, JPEG, EXR and AVIF; anything else fails validation. |
| Color-space tagging | Yes | Blender's `srgb_rec709_display` is renamed to a name RealityKit knows. |
| Texture transform (Mapping node) | Partial | One transform per material is honored; a second is refused. |
| Extension and interpolation modes | Yes | Wrap and filter reach the image reader. |
| Baked textures | Yes | All three bake modes; see [BAKING.md](BAKING.md). |

A USDZ carries only the images the stage references — a bake that produced more
than the material uses does not drag the extras into the package.

## Animation

| Feature | Supported | Notes |
|---|---|---|
| Object translation, rotation and scale | Yes | Sampled per frame. |
| Armature and bone animation | Yes | Including bone scale. |
| Shape key animation | Yes | Weight curves are exported. |
| Several Actions as one timeline | Yes | Actions are concatenated into takes, each with its own frame span. |
| RCP clip library | Yes | Turn on **RCP Clip Library**. See the caveat below. |
| Stashed Actions | Dropped | Warned by name — push a stashed take to an NLA strip to include it. |
| Fractional Action ranges | Partial | Ranges are quantized to whole frames and time-scaled, with a warning naming the Action. |
| Time-sampled mesh points | Refused | RealityKit cannot play deforming points; validation stops the export. |
| Material, light and camera animation | Dropped | Only object, armature and shape-key channels are collected, and nothing warns. |

**The clip library is opt-in for a reason.** Reality Composer Pro 3 flattens
named `RealityKit.AnimationLibrary` clip definitions on import: an asset
authoring four named clips comes back with one timeline. The same files loaded
through RealityKit 27 directly keep their clips. For runtime work, leave the
setting off and split the animation in app code.

## Scene and packaging

| Feature | Supported | Notes |
|---|---|---|
| Y-up axis and meter scale | Yes | Always written, so the file is correct in the editor and on device. |
| Root prim name | Yes | Set it in **Root Prim**. |
| Selection-only export | Yes | An empty selection is refused rather than exported as an empty file. |
| Custom properties | Yes | Reach the stage as `userProperties`. |
| Empties as transforms | Yes | Exported as Xforms. |
| Double-sided materials | Dropped | Always written single-sided; each changed mesh is listed in the diagnostics sidecar. |
| World material and environment lighting | Dropped | Never exported; use the **Lighting & Shadows** bake mode to keep the look. |
| USDZ packaging | Yes | Includes only referenced textures. |
| Diagnostics sidecar | Yes | Always written on failure; turn on **Keep Success Diagnostics** to keep it otherwise. |

## Dropped without a warning

Everything here leaves your scene without any message. The export reports
success and the data is not in the file. This is the list to check when an asset
looks wrong and nothing told you why.

- Cameras and lights.
- Curve, hair, point-cloud and volume objects.
- The world material and its environment lighting.
- Animation on materials, lights and cameras.

## Exports are not byte-reproducible

Exporting the same unchanged `.blend` twice does not produce the same bytes.
Blender's USD exporter writes top-level prims in an order that varies between
runs — same prims, same values, different order. If you keep exports in version
control, expect every re-export to show as changed. See
[EXPORT_PIPELINE.md](EXPORT_PIPELINE.md).
