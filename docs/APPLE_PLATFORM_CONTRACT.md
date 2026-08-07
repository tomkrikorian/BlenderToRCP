# USD and MaterialX support on Apple platforms

This page explains which USD and MaterialX features Reality Composer Pro and
RealityKit accept, and what that means for files exported from Blender. Read
it if you want to know whether an export will open — in Reality Composer Pro,
in Quick Look, or in a RealityKit app on device.

*Applies to: macOS 27, iOS 27, iPadOS 27, tvOS 27, visionOS 27; Reality
Composer Pro 3.0 (build 80.0.1.500.1); Xcode 27.*

## One stack, everywhere

Reality Composer Pro and RealityKit are not separate targets. On the OS 27
platforms they share one USD library and one MaterialX library:

- Apple ships its own build of OpenUSD. The same library serves the
  RealityKit runtime, Reality Composer Pro, the `usdchecker`/`usdzip`
  command-line tools, and Xcode's `realitytool`.
- The operating system ships the ShaderGraph engine and its MaterialX node
  library as part of RealityKit. Reality Composer Pro uses the identical
  library. There is no "editor supports it, the device doesn't" gap.
- MaterialX materials compile on the device when a USDZ loads. Compiling
  ahead of time (a `.reality` file) is an optimization, not a requirement.

One tool stands outside that stack. Xcode's `realitytool` links neither
`ShaderGraph.framework` nor the `libtm-*` libraries, so it is not the compiler
Reality Composer Pro and RealityKit use. It accepts materials they reject, and
reports a successful shader graph while doing so. Use it to check that a file
parses and packages. Do not use it, or `usdchecker`, to judge whether a material
renders — run `scripts/check_shader_implementations.py` and then look at the
asset in Reality Composer Pro.

The parts of Reality Composer Pro that are genuinely unique to the app are its
editor: the project format, its private asset cache, and the editing UI. None of
those are an interchange format, and this exporter does not write them.

For you this means one validation is enough: a file that opens correctly in
Reality Composer Pro will load the same way on every OS 27 device.

## Which USD versions are supported

"USD version" can mean three things. Here are all three.

### File formats — the numbers that decide whether a file opens

| Format | Reads up to | Writes by default |
|---|---|---|
| Binary (`.usdc`, inside `.usdz`) | crate 0.14 | crate 0.8 |
| Text (`.usda`) | `#usda 1.2` | `#usda 1.0` |

"Crate" is USD's binary container format. Its version only increases when a
file uses a feature that needs it — path expressions (0.10), relocates
(0.11), animation splines (0.12–0.13), array edits (0.14). Files that use
none of these stay at crate 0.8, which every USD tool of the last several
years reads and writes.

### The library behind them

Apple's USD build is based on OpenUSD 24.07 with features added from later
releases, up to roughly OpenUSD 25.11. Features introduced in OpenUSD 26.x
are not present.

### What this means for Blender exports

Blender 5.2 writes crate 0.8 and `#usda 1.0` — well below the ceilings
above. Every file this exporter produces opens in Reality Composer Pro and
loads on every OS 27 platform. The version numbers of Blender's or your
tooling's USD library (26.x) don't matter; only the file format written
matters, and the defaults are conservative.

If a future exporter feature ever required a newer crate version, the file
would fail identically in Reality Composer Pro and on device, so validating
in one place still catches it.

### USDKit

OS 27 introduces USDKit, a public Swift framework exposing the same Apple
USD build: stages, layers, composition, and a USDZ writer
(`USDStage.exportPackage`). RealityKit can attach a live USD stage to an
entity (`USDStageComponent`). None of this changes what you export — but it
signals that USDZ is the format Apple is investing in, which is why USDZ is
this exporter's primary target.

## Which MaterialX nodes are supported

MaterialX materials are graphs of *nodedefs* — node definitions such as
`ND_image_color3` (read a color texture) or
`ND_realitykit_pbr_surfaceshader` (RealityKit's PBR surface). RealityKit
resolves nodedefs from a library that ships with the OS.

- The library combines MaterialX 1.39.4, a 1.38 compatibility set, and
  Apple's RealityKit-specific nodes.
- Reality Composer Pro's node library is identical to the OS runtime's. Any
  node the editor shows, the device renders.
- Everything this exporter authors — the RealityKit PBR and Unlit surfaces,
  image readers with wrap and filter modes, UV transforms, normal-map
  decoding, channel reads — exists in that library with matching signatures
  *and* a compiled implementation. Resolving is not enough on its own: a
  nodedef can resolve and have no compiled shader behind it, which makes
  RealityKit discard the whole material rather than the one node. To read one
  channel out of a texture the exporter converts the color to a vector and
  takes a dot product with a unit mask. That is the shape Reality Composer Pro
  writes for the same operation.

One family of nodes is a known trap: the MaterialX *pbrlib* closure nodes
(`ND_dielectric_bsdf`, `ND_mix_bsdf`, displacement, and similar). USD files
that reference them parse without error, but no Apple platform can render
them. The exporter refuses to author them, and its validation flags them if
they appear. In the exporter's node manifest they are marked
`editor_unresolvable`.

### Color spaces

RealityKit reads a fixed set of color-space names on textures. The ones that
matter for Blender exports:

| Name | Meaning |
|---|---|
| `srgb_texture` | sRGB-encoded color texture |
| `srgb_rec709_scene`, `lin_rec709`, `lin_rec709_scene` | Rec.709 variants |
| `raw`, `data`, `none` | non-color data, in the USD preview network only |

Blender labels sRGB textures with a name RealityKit does not know,
`srgb_rec709_display`. The exporter renames it to `srgb_rec709_scene`
automatically; the encoding is the same and you don't need to change anything
in Blender. The MaterialX metadata on the image node's file input keeps the
name MaterialX uses for that encoding, `srgb_texture` — the two live in
different vocabularies and only one of them is resolved by
`UsdColorSpaceAPI`.

MaterialX shader graphs take no color space on a non-color texture. An absent
color space is MaterialX's no-transform contract, and it is what Reality
Composer Pro and shipping RealityKit packages use. A MaterialX image reader
tagged `raw` makes Reality Composer Pro 3.0 replace the material with a
striped placeholder, so the exporter never writes that token into a shader
graph. The `raw` and `data` names still appear on the retained
`UsdPreviewSurface` network, which Quick Look reads.

### Scene setup rules

- **Units and orientation.** Reality Composer Pro converts scene units and
  up-axis when importing a file, but RealityKit apps loading a USDZ directly
  do not. The exporter therefore always writes Y-up, meters, so the file is
  correct everywhere.
- **Double-sided materials.** Reality Composer Pro's viewport honors the
  `doubleSided` flag; the RealityKit runtime ignores it. A file relying on
  it would look right in the editor and wrong on device. The exporter always
  writes single-sided geometry.

## Verification

The facts on this page were established by inspecting the shipped binaries
and libraries of macOS 27, Reality Composer Pro 3.0 (80.0.1.500.1), and the
Xcode 27 SDKs, including direct file-format probing of the USD library.
Four tests in this repository re-check the most important facts against the
locally installed software and fail if a platform update changes them:

- `tests/unit/test_manifest_matches_editor_libraries.py` — the unrenderable
  nodedef list still matches the installed MaterialX libraries.
- `tests/unit/test_rcp_contract_matches_type_index.py` — the `.import`
  contract still matches Reality Composer Pro's shipped schema.
- `tests/unit/test_material_os27.py` — the node manifest still pins the
  expected Reality Composer Pro build.
- `tests/unit/test_nodedef_input_gate.py` — the recorded per-version nodedef
  and input gaps still match the installed nodedef store.

After an OS, Reality Composer Pro, or Xcode update, run these first, then
regenerate the gap table with `scripts/dump_rcp_nodedef_inputs.py`.

The claim that `realitytool` disagrees with Reality Composer Pro is measured on
a rigged-character export since removed from this repository:
`realitytool compile --platform xros` exits
0 and emits `shadergraph_rig_skin_robot_mesh_mesh_export_pxrusdpreviewsurface5sg1`
with zero PBR fallbacks, `usdchecker --arkit --strict` reports `Success!`, and
Reality Composer Pro 3 refuses the same material with `Couldn't find compiled
shader graph buffer`. Why the editor refuses it is not established. Every
nodedef the file uses resolves to a compiled implementation, so no static check
in this repository predicts the failure either — which is the reason this page
tells you to open the asset in Reality Composer Pro rather than trust a green
tool run.
