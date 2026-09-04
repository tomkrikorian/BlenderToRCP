# Changelog

Notable changes to BlenderToRCP, newest first. Dates are release dates.

Entries describe what changed for you — what now works, what stops the export,
and what you have to do differently. Internal refactors are not listed.

## 2.0.0 — unreleased

A major release. Every export now targets one fixed spatial contract, material
validation is always strict, and a family of materials that Reality Composer
Pro used to replace with its striped placeholder now build. Several settings
are gone, and some scenes that exported in 1.3.0 are now refused — read the
breaking changes before upgrading a pipeline.

Requires Blender 5.2 LTS.

### Breaking

- The export panel has **one Export button**. A **Profile** choice above it —
  RealityKit PBR with Translate or Bake Materials, or RealityKit Unlit with
  Material Color Only or Lighting & Shadows — decides whether the export bakes
  and in which mode. The separate `Bake Textures & Export` button is gone.
  Exporting from the sidebar writes the Profile's bake mode into the scene,
  overwriting a bake mode you set from the command line.
- Orientation and units are no longer adjustable. Every export is Y-up, -Z
  forward, meters at `metersPerUnit=1`, with relative dependencies. The
  settings that used to control this are gone, so a script passing any of them
  fails with `INVALID_SETTING_OVERRIDE`.
- Validation is always strict. `validate --strict` no longer exists, and scenes
  that passed in 1.3.0 can now be refused.
- The default surface is now **RealityKit PBR Surface 2**, the 30-input
  surface verified by import into Reality Composer Pro 3. A fresh scene
  exports IOR, Specular Tint, Diffuse Roughness, subsurface, sheen and coat IOR
  on the surface instead of refusing them. A `.blend` that saved a Surface
  Model keeps it: a scene already on the older portable surface still refuses
  those controls until you switch it.
- **Alpha cutout is never inferred.** A material that relied on Blender's Clip
  or Hashed blend method now exports as alpha blending. To keep a cutout, set
  the custom property `blender_to_rcp_alpha_cutout_threshold` (float, 0–1) on
  the material.
- **RGB Curves** is no longer exportable — bake the material or remove the node.
- **Mix Shader** is refused by direct export; reach it through a baking Profile.
- **Normal Map** nodes in object or world space, in DirectX convention, or with
  a linked Strength are refused rather than approximated.
- `bake-export --timeout` is now `--step-timeout`. A plain `--timeout` belongs
  before the subcommand and bounds the whole Blender run.
- Argument errors exit **1**. Exit 2 now means only that Blender could not be
  found or started, and exit 3 that the add-on failed to load.
- Boolean settings accept only `true`/`1`/`yes` and `false`/`0`/`no`. `on` and
  `off` are now errors instead of being read as `false`.
- `settings set` needs `--save` to change the file, and a save that cannot
  happen is an error rather than a quiet `"saved": false`.
- `bake_resolution` defaults to `ORIGINAL` rather than `2048`. Set it
  explicitly if a fixed size matters.

### Added

**Materials**

- **Surface Model** setting, choosing which MaterialX surface your materials
  terminate in: RealityKit PBR Surface 2 (the default, verified by import),
  the original RealityKit PBR (portable, for pinned pipelines), or OpenPBR
  1.1, which Reality Composer Pro expands into PBR Surface 2 and warns about
  what it drops.
- **Normalize Unsupported Values**, an export-only clamp for an unlinked,
  achromatic Principled **Specular Tint** brighter than 1. The Blender node and
  the `.blend` are left untouched.
- Color Attribute (vertex color) materials export, alpha included.
- Math node translation for twenty-four operations, including Multiply Add,
  Power, Logarithm with any base, Floored Modulo and the trigonometric family.
  **Use Clamp** is honored.
- Boolean, Integer and Vector input nodes are translated.
- Image Texture **Extension** and **Interpolation** reach the exported
  material: Extend, Clip and Mirror wrap modes, and the Closest, Cubic and
  Smart filters.
- Image Texture **Box** projection exports as a triplanar projection instead of
  flattening to a flat UV sample.
- Mix and Mix Color nodes accept a linked **Factor**.
- The Shader Editor's **RealityKit Authoring** panel and the **Add ▸ RealityKit
  Nodes** menu now appear in Blender. They were documented but never registered.
- The **RealityKit Compatibility** panel judges your material against the
  selected Surface Model, so it agrees with what the export will do.

**Export and packaging**

- Export refuses to run when the scene's Unit Scale is not 1.0, states how many
  times oversized the asset would have been, and tells you how to fix it.
- USDZ packages are checked against Apple's archive rules before publication:
  uncompressed members, every payload on a 64-byte boundary, the root USD layer
  first, and only USD, PNG, JPEG, EXR, AVIF and audio members.
- USDZ output is additionally run through `usdchecker` when one can be found,
  using the ARKit profile where supported. The export stops if the check fails.
- A root prim name containing slashes or characters USD does not allow is
  folded into a valid name instead of producing an unusable default prim.
- **Selection Only** stops with a message when nothing is selected, pulls in the
  armature that deforms a selected skinned mesh, and limits material checks to
  the objects you are exporting.

**Animation and baking**

- Mix Shader materials bake. A mix over two Principled BSDFs is rendered into
  the baked texture in every mode; a mix whose passed-through channels disagree
  is refused with the diverging channel named.
- Skeletal validation stops the export on more than one skeleton, a skeleton
  outside its skeleton root, a skeleton with no joints, a mesh carrying only
  half its skin weights, or a skinned mesh that resolves to no skeleton.
- Vertex-cache animation is refused with advice to convert it to shape keys or
  skinning, because RealityKit cannot play time-sampled mesh points.
- Animation on objects inside a collection instance is collected and baked
  instead of being silently dropped.
- NLA tweak mode anywhere in the export scope stops the export.
- New warnings: a Lighting & Shadows bake with no World and no lights, stashed
  Actions left out of an export, an Action with a fractional frame range, and
  one object carrying several takes.
- `--roughness-mode` on `bake-export`, matching the sidebar's Roughness control.

**Command line**

- A global `--timeout` bounding the whole Blender run, defaulting to 600
  seconds and accepting `0` for no limit.
- Per-step timeout enforcement in `bake-export`: a stalled step is stopped and
  reported as `BAKE_STEP_TIMEOUT`, naming the step that hung.
- `validate --materialx-surface-profile` and `validate
  --normalize-unsupported-values`, checking a scene against a profile for one
  run without changing it.
- A `warnings` array on successful `export` and `bake-export` results, also
  printed to stderr, so a bake that produced black textures says so instead of
  reporting only `Done`. `--quiet` does not hide these.
- `MISSING_EXTERNAL_ASSETS`, raised when the preflight finds a missing
  non-image dependency — linked libraries, caches, collection prototypes,
  Geometry Nodes and modifier textures, and the bake HDRI.
- Stable error codes for failures raised before Blender starts, and a `--json`
  envelope for argument errors and for Ctrl-C.
- The offending key, its value and the allowed values under `error.details`
  whenever a setting or override is rejected.
- A settings reference page, and a baking reference page covering when the
  Export button bakes at all and what each mode includes.

### Changed

- Textures beside a `.usda` or `.usdc` export sit in
  `textures/<output name>/<generation>/` rather than a flat `textures/` folder.
  A `.usdz` keeps the same layout inside the archive.
- Exports are published atomically: textures are installed first and the USD
  file is swapped in last, so an interrupted export leaves the previous asset
  whole instead of half-replaced.
- A second export to the same path while the first is still publishing is
  refused rather than interleaving.
- Exports leave bookkeeping folders next to the output — `.blendertorcp_temp`,
  `.blendertorcp_generations`, `.blendertorcp_sidecars` and
  `.blendertorcp_publish`. Ignore them; do not ship them.
- The built-in USDZ packager writes a compliant archive on its own, so a USDZ
  produced without Apple's `usdzip` is no longer a plain ZIP RealityKit can
  refuse. When packaging or validation fails, the staging folder is kept so a
  support bundle can carry the files that failed.
- Transparency is decided by the Principled **Alpha** input, not by the
  material's render method.
- Roughness driven by a plain image texture reads the **red** channel, matching
  what Quick Look and RealityKit's own USD importer read. It read green before.
- Roughness, metallic, normal and occlusion images carry no color space at all
  rather than `raw`, and are read through a three-channel reader.
- One image file produces one texture reader, with each consumer taking its own
  channel off it.
- Normal Map **Strength** is expressed in tangent space and matches Blender's
  smooth-shaded result. Strength 1.0 exports exactly as before.
- Noise Texture exports through a fractal noise node RealityKit can compile.
  Its **Distortion** input is dropped, and **Projection Blend** on a
  Box-projected texture is dropped.
- Transmission Weight, Thin Wall, Thin Film, linked coat controls and Bump
  nodes are refused with the control named instead of being dropped silently.
- Baked textures are sized from each material's own source textures, floored at
  512 px, instead of a fixed 2048 — so a 1K material stays 1K. Lighting &
  Shadows still bakes at 2048, and a `.blend` with a saved Texture Resolution
  keeps it.
- Baking applies only the Actions bound to each object through its own Blender
  5.2 Action slot, instead of laying every Action in the file onto every
  animated object.
- Concatenated takes no longer share a boundary frame.
- Shape-key weight curves are exported only for meshes whose keys are animated.
- A background bake runs on a snapshot of the scene as it is on screen rather
  than re-loading the last-saved `.blend`, so unsaved edits are included and an
  unsaved file is no longer refused. It stops before launching, with an
  actionable message, when unsaved pixels or blend-relative paths cannot travel
  into that snapshot.
- The bake follows the material's active Material Output, so a leftover
  disconnected Principled BSDF no longer decides opacity or bake resolution.
- A Material Color Only bake refuses a material with emission, coat, or a
  specular IOR level it cannot reproduce, naming the input.
- Numbers outside a setting's allowed range are rejected rather than silently
  clamped, `settings set` is all-or-nothing, and `settings get --keys` rejects
  unknown keys instead of returning nothing for them.
- Every failure writes `<output>.diagnostics.json`, including one rejected
  before any geometry is touched. The diagnostics settings now decide only
  whether a *successful* run keeps its sidecar.
- `--json` error envelopes no longer contain your home directory, and a
  diagnosed failure no longer carries a Python traceback.
- `preferences set` writes to your Blender preferences immediately, so the
  change is global to the install and outlives the command.
- Node capability warnings are derived from the validator, so `validate` and
  the export tell you the same thing about the same material.

### Removed

- `convert_orientation`, `forward_axis`, `up_axis`, `convert_scene_units`,
  `meters_per_unit`, `relative_paths` and `apply_yup_geometry`.
- The per-datatype toggles `export_meshes`, `export_lights`, `export_cameras`,
  `export_curves`, `export_points`, `export_volumes`, `export_hair` and
  `convert_world_material`, along with the `objects` group — so `settings get
  --group objects` is now an error.
- `export_uvmaps`, `rename_uvmaps` and `export_normals`. UVs and normals are
  always exported.
- `validate --strict`.
- RGB Curves node support.
- The `materialx_library_path` and `default_export_format` preferences, leaving
  `usdzip_path` as the only preference.

### Fixed

- Materials that Reality Composer Pro replaced with its gray striped
  placeholder now build: the exporter no longer writes channel-swizzle nodes
  that RealityKit resolves but has no shader for.
- Materials no longer lose their **entire** shader graph — every texture
  binding included — and fall back to a plain default surface. That happened
  whenever the exporter wrote an input the bound node definition does not
  declare, and the only symptom was an untextured object.
- Vertex-color materials render instead of coming out black.
- Noise, Voronoi and Gradient textures no longer export flat; they sample real
  object-space coordinates, with a warning that the result will not match
  Blender pixel for pixel.
- Tiling a texture works: a Mapping node with a non-identity scale or rotation
  no longer fails with a texture-transform conflict. A Mapping node in
  **Texture** mode now rotates in the right direction; a rotated decal used to
  export mirrored about its pivot.
- A Non-Color image on Base Color exports instead of failing, written as linear
  Rec.709 with a warning naming the input.
- Roughness, metallic and normal images left at Blender's default sRGB inside a
  RealityKit node group now stop the export the same way they always did on the
  Principled path.
- Blender's `srgb_rec709_display` color-space name is renamed to one both USD
  and RealityKit resolve, so sRGB textures no longer arrive carrying no color
  space at all.
- Exporting a transparent material no longer fails with `No separate4 nodedef
  found`, and asking for the alpha channel of an image that has none is refused
  with a warning naming the file.
- The retained `UsdPreviewSurface` network that Quick Look reads no longer
  carries an off-spec normal-map scale and bias, which Reality Composer Pro
  turned into NaN on import.
- A nested unresolved node no longer vanishes leaving its input at a default
  with nothing reported.
- Clamp, Map Range, Noise Texture, Invert and a dozen other supported nodes no
  longer produce `unrecognized` or `requires baking` warnings on exports that
  succeed.
- An AVIF bake is written as AVIF; baked textures were saved as PNG whatever
  format you chose.
- Linked duplicates sharing one mesh each get their own Lighting & Shadows
  bake, instead of every copy inheriting whichever instance baked last — a cube
  in full sun could export black because its duplicate baked from inside a
  shadow.
- Baked textures are bound to the UV map they were baked into, so a mesh with
  several UV maps no longer samples through the wrong layout.
- The bake no longer inherits your scene's own Bake panel settings; a `.blend`
  saved with a vertex-colour target or the Combined pass toggles off produced
  black textures and still reported success.
- The averaged roughness value is measured over the texels the bake actually
  covered, so it no longer tracks UV coverage and bake margin — a 0.5 roughness
  material exported 0.21 at the default margin.
- Transparent materials keep their source roughness instead of exporting a
  mirror finish.
- A shape key whose name contains a quote now animates instead of exporting as
  a static value with no warning.
- Action assignments, including the exact Blender 5.2 Action slot, are restored
  after an export.
- A failed bake puts every material slot back and removes the materials and
  images it created, instead of leaving the scene half-baked.
- A `//` HDRI path is resolved against the `.blend` instead of failing as not
  found.
- Re-exporting to the same path no longer leaves an empty folder behind on
  every run, so a destination inside an `.rkassets` bundle stops accumulating
  them.
- Renaming a prim whose name USD does not allow no longer deletes its children,
  attributes, relationships and animation.
- `version` reported 1.2.0 regardless of which build was installed.
- `settings set` discarded the first key it wrote on a scene that had never
  carried export settings, while reporting it as saved. `preferences set`
  reported success but never persisted anything.
- A material the exporter refuses used to crash the CLI with a JSON
  serialization error instead of reporting the refusal and naming the nodes.
- Pointing `--blender` at a directory, or at a file that cannot be executed,
  raised a Python traceback.
- Blender exiting non-zero after printing a successful result is no longer
  reported as a success.
- The CLI locates the add-on in any configured Blender extension repository
  instead of guessing at two default names.
- **Select Offending Nodes** no longer errors the moment validation finds
  something, and reports how many nodes it selected.

## 1.3.0 — 2026-07-02

### Added

- `Material Color Only - Lit PBR` bake mode, which bakes light-independent
  material color but exports Lit PBR materials so Reality Composer Pro or
  RealityKit lights the result (`--bake-mode LIT_ALBEDO`).
- A **Roughness** option under Advanced Bake Options, choosing between a baked
  per-texel roughness map and a single averaged value that ships no roughness
  texture.
- Normal maps and metallic inputs are carried onto `Material Color Only - Lit
  PBR` bakes instead of being dropped, so baked surfaces keep their detail
  instead of looking flat and over-glossy.
- **Apply RealityKit (Y-Up) to Geometry**, baking the Y-up rotation into the
  mesh data and writing a native Y-up USD with no root rotation wrapper.
- **RCP Clip Library**, for authoring Reality Composer Pro animation clip
  metadata.

### Changed

- `Material Color Only` is renamed `Material Color Only - Unlit`. Its
  `UNLIT_ALBEDO` value is unchanged.
- Reality Composer Pro clip metadata is no longer written by default. Turn on
  **RCP Clip Library** if you edit clips in Reality Composer Pro; leave it off
  for RealityKit runtime exports.
- The material color, roughness and opacity passes bake at a single Cycles
  sample with denoising off, so they finish far faster. Lighting & Shadows
  still uses your scene's sample count.
- Bakes size each material's textures from the source textures feeding it, with
  a 512 px floor, instead of always using 2048.
- Flat-color materials export as constant color, roughness and metallic values
  in both Material Color Only modes, dropping a texture file per material.
- Objects sharing a source material and mesh share one baked material, so
  duplicated props export as instances instead of carrying a private texture
  set each.
- Mix Color nodes set to Mix, Multiply, Add or Subtract with both inputs
  connected export as real material nodes instead of failing validation.
- The Y-up geometry bake falls back to root orientation conversion, with a
  warning, when the scene contains animated, driven, constrained or
  armature-deformed transforms it cannot preserve.

### Removed

- The extra guessed animation clip definitions written alongside the real one.
  Orphan definitions could produce animation RealityKit fails to build.

### Fixed

- `Bake Textures & Export` failed with `Postprocess failed` and reported every
  baseColor texture missing, because the export step deleted the freshly baked
  textures before it could stage them.
- Opaque materials exported with transparency, and dithered ones as hard alpha
  cutouts. Transparency and the cutout threshold are now read from the
  material's actual Alpha input.
- Packed image textures shipped twice, roughly doubling USDZ size.
- Flat-colored surfaces with no real UV unwrap baked to an all-black texture.
- Opacity maps were baked and shipped for opaque materials.
- Baked material names compounded across repeated bakes into
  `Material_Baked_Baked_Baked`.
- The `.blendertorcp_temp` staging folder was left in your output directory
  whenever an export failed part way.
- Collection instances shipped mis-oriented inside a Y-up export, and children
  of rotated, non-uniformly scaled parents landed in the wrong place.

## 1.2.0 — 2026-05-27

### Added

- **USD Export: Texture** panel with an **Override Textures** toggle that
  resizes and transcodes textures during export, off by default so source
  textures are copied untouched.
- **Original** image format and **Keep Original** resolution, keeping each
  source texture's format or dimensions while you change the other.
- AVIF texture output, produced by the external `avifenc` encoder. Install it on
  your PATH or point `BLENDERTORCP_AVIFENC` at it; otherwise the export falls
  back to a resized PNG.
- **Diagnostics** panel with an **Enable Diagnostics** scene setting, and
  `--diagnostics` on `export` and `bake-export`.
- `texture` and `diagnostics` groups for `settings get --group`, and `ORIGINAL`
  accepted by `--resolution` and `--image-format`.

### Changed

- Export writes straight to the panel's **Output Path** instead of opening a
  file browser, and stops with an error when that field is empty.
- **Output Path** follows the selected format, so switching to USDZ rewrites
  `scene.usda` to `scene.usdz`.
- Diagnostics are off by default, so exports no longer drop a
  `.diagnostics.json` beside the output unless you ask for one.
- Texture resolution, image format and margin take effect only when **Override
  Textures** is on; bakes otherwise use 2048 px and an 8 px margin whatever the
  fields show.
- Baked textures are written as PNG rather than AVIF, because Blender's AVIF
  writer can crash while saving a bake, then re-encoded to AVIF afterwards when
  **Override Textures** is on and `.avif` is selected.
- Exported texture files are prefixed with the output file's name, for example
  `scene-wood.png`, so exports sharing one folder no longer overwrite each
  other's textures.
- Texture resolution, image format and margin moved from the bake panel into
  **USD Export: Texture**.

### Removed

- The **Enable Diagnostics** add-on preference, replaced by the per-scene
  setting, and `enable_diagnostics` as a `preferences` key.

### Fixed

- Exports to `.usda` and `.usdc` no longer reuse stale textures left in the
  destination `textures/` folder by an earlier export, and re-exporting deletes
  the texture files its own previous run wrote.
- Files left behind by an interrupted export are no longer published into the
  next one.
- Textures with identical content are copied once instead of once per source.
- Empty `textures/` and `assets/` folders are no longer created next to exports
  that have neither.
- Normal maps are exported through RealityKit's own tangent-space decoder
  instead of the MaterialX standard node, which Reality Composer Pro could fail
  to compile. Maps with a strength other than 1.0, or in object space, keep the
  standard node.

## 1.1.0 — 2026-05-06

### Added

- **Create Support Bundle** and a `support-bundle` CLI command, writing a
  redacted ZIP of diagnostics, environment details and scene settings. Your
  `.blend` and the exported files go in only with `--include-blend` or
  `--include-output`.
- `--job-dir` on `support-bundle`, folding a background bake job's settings,
  status and log into the same ZIP.
- **Open Log** and **Open Diagnostics** buttons on a background bake job.
- An **Advanced Bake Options** sub-panel.
- A check that stops a bake before it starts when the scene points at image
  files no longer on disk, naming each missing file and the objects and
  materials that use it.

### Changed

- **Lighting & Shadows** is now the default bake mode, so a new scene and
  `bake-export` without `--bake-mode` bake Blender's lighting into the textures
  instead of material color alone.
- Bake mode is now **Texture Bake Includes**, with `Unlit (Albedo)` renamed
  **Material Color Only** and `Lit (IBL baked)` renamed **Lighting & Shadows**.
  The CLI values `UNLIT_ALBEDO` and `LIT_IBL` are unchanged.
- Baking runs Blender with factory startup, so your other add-ons and
  preferences no longer influence a bake.
- A misspelled or unknown `key=value` override now fails the command and names
  the key, instead of being silently dropped.
- Diagnostics are written even when disabled if the export fails, and carry
  per-step timings, versions, a scene summary, validation errors, the files
  produced, and the traceback.
- A failed command prints the diagnostics path and a ready-to-paste
  `support-bundle` command on stderr.

### Removed

- The strict material check that ran *after* baking. Baking replaces those
  materials, so it refused scenes it did not need to. `Export Scene` and
  `validate` still enforce it.

### Fixed

- Shape key animation is exported again, and baking opacity no longer fails on
  Blender 5.
- Exporting a material that reads an image with premultiplied alpha no longer
  aborts the export.
- The CLI works against an add-on installed through Blender's extension
  installer; commands previously failed unless you pointed them at a source
  checkout.
- Cancelling a background bake no longer risks terminating an unrelated
  process, and the panel no longer shows a job as running forever when its
  status file is missing or belongs to a closed session.
- Background job state is no longer saved into the `.blend`.
- Support bundles redact Windows paths written inside JSON as well as in plain
  text.

## 1.0.0 — 2026-03-23

First stable release. Fixed the development extension setup and brought the
documentation in line with the shipped add-on.

## 1.0.0-alpha5 — 2026-03-13

The `blendertorcp` command line, the API commands behind it, and the agent
skills that drive it. Fixed a crash during bake cleanup.

## 1.0.0-alpha4 — 2026-03-06

AVIF bake and export support, with warnings on Blender 5.1.

## 1.0.0-alpha3 — 2026-03-06

Documentation updates, and temporary files are cleaned up properly after a
`.usdz` export.

## 1.0.0-alpha2 — 2026-02-20

A new unlit bake process.

## 1.0.0-alpha — 2026-02-02

First public alpha.
