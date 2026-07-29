# BlenderToRCP Settings Reference

Every user-facing toggle in BlenderToRCP, what it actually changes in the exporter, and where it lives.

This document is the behavioural companion to [`CLI.md`](CLI.md). `CLI.md` tells you how to
*pass* a setting; this file tells you what the exporter *does* with it, which control exposes
it, and which other settings silently override it.

All line references are against the code as of this document's revision.

---

## Two independent stores

BlenderToRCP has two kinds of configuration and they behave very differently.

| | Per-scene export settings | Add-on preferences |
|---|---|---|
| Defined in | `Plugin/ui/panel.py:98` (`BlenderToRCPExportSettings`) | `Plugin/prefs.py:43` (`BlenderToRCPPreferences`) |
| Attached to | `bpy.types.Scene.blender_to_rcp_export_settings` (`Plugin/ui/panel.py:1000`) | Blender user preferences (`Edit ▸ Preferences ▸ Add-ons`) |
| UI location | 3D Viewport ▸ N-panel ▸ **RCP Exporter** tab | `Edit ▸ Preferences ▸ Add-ons ▸ BlenderToRCP` |
| CLI access | `settings get` / `settings set` / positional `key=value` overrides | `preferences get` / `preferences set` |
| Count | 40 public + 9 internal | 2 user-visible + 3 hidden |

### How per-scene settings persist

Every public property declares `update=_on_settings_changed` (`Plugin/ui/panel.py:89`). On any
UI edit that callback:

1. rewrites `filepath` so its extension matches `export_format` (`Plugin/ui/panel.py:69`), then
2. serialises **all** settings except `filepath` and the internal keys into the add-on
   preference `last_export_settings_json` (`Plugin/prefs.py:24`, `:222`, `:336`).

Consequences worth knowing:

- Export settings are **sticky across scenes and .blend files**, because the payload lives in
  user preferences, not in the scene. A new scene inherits your last-used values
  (`Plugin/prefs.py:355`).
- `filepath` is deliberately excluded from that payload and is instead remembered *per .blend*
  in `last_export_paths_json` (`Plugin/prefs.py:424`).
- The payload is version- and profile-stamped (`schema` `blendertorcp.export-settings`,
  `version` 3, `profile` `REALITYKIT_OS27`). A payload from an older add-on build, a different
  profile, or with a missing/extra key is **discarded wholesale** and the scene is reset to RNA
  defaults (`Plugin/prefs.py:294`, `:377`).
- CLI commands suspend this persistence for the duration of the command
  (`Plugin/api/commands/_settings_common.py:192`), so a CLI override never leaks into your saved
  preferences.

---

## Read this first: the UI does not expose `bake_mode`, it computes it

`bake_mode` is the single most important setting for baked exports, and it is **not drawn
anywhere in the Blender UI**. The panel presents three artist-facing controls instead —
`ui_material_type`, `ui_pbr_processing`, `ui_unlit_appearance` — and
`export_profile.resolve_ui_export_route()` (`Plugin/export_profile.py:32`) maps them onto a
pipeline plus a `bake_mode`:

| `ui_material_type` | `ui_pbr_processing` | `ui_unlit_appearance` | Pipeline | Resulting `bake_mode` |
|---|---|---|---|---|
| `REALITYKIT_PBR` | `TRANSLATE` | — | `DIRECT` (`blendertorcp.export`) | *n/a — no bake* |
| `REALITYKIT_PBR` | `BAKE` | — | `BAKE` (`blendertorcp.bake_export_background`) | `LIT_ALBEDO` |
| `REALITYKIT_UNLIT` | — | `MATERIAL_COLOR` | `BAKE` | `UNLIT_ALBEDO` |
| `REALITYKIT_UNLIT` | — | `LIGHTING_SHADOWS` | `BAKE` | `LIT_IBL` |

> **`bake_mode` is unconditionally overwritten when you press Export in the panel.**
> The panel sets `operator.apply_ui_profile = True` on the bake operator
> (`Plugin/ui/panel.py:638`), and `_apply_ui_profile()` then executes
> `settings.bake_mode = route.bake_mode` (`Plugin/ops/bake_export_operator.py:116`).
> Whatever you set via `blendertorcp settings set scene.blend bake_mode=… --save` is replaced
> the moment the artist clicks Export. **Set `bake_mode` from the CLI only for
> `blendertorcp bake-export`, which honours it** (`Plugin/api/commands/bake_export.py:118`).

The same operator path also forces `export_texture_settings_enabled = True` into the background
job payload (`Plugin/ops/bake_export_operator.py:183` → `:730`). See
[`export_texture_settings_enabled`](#export_texture_settings_enabled) — this is why the
Optimization panel's fields work in the UI bake route even though the toggle is not drawn there.

Three further derived values are never user-editable:

- `force_unlit_materials` is recomputed from `bake_mode` before every export
  (`Plugin/export/bake_finalize.py:17`, `:22`).
- `export_format` is rewritten to `USDA` whenever `RCP_IMPORT` is requested, because the
  `.import` package is generated from the post-processed USDA
  (`Plugin/api/commands/export.py:107`, `Plugin/api/commands/bake_export.py:307`).
- The legacy value `USD` is silently normalised to `USDC`
  (`Plugin/ops/export_operator.py:33`).

---

## Summary table

40 public settings. `Group` is the `settings get --group` / `settings list` membership defined in
`Plugin/api/commands/_settings_common.py:63`.

| Key | Type | Default | Group | UI control | Applies to |
|-----|------|---------|-------|-----------|-----------|
| `filepath` | string | `""` | general | Export ▸ Output Path | both |
| `export_format` | enum | `USDA` | general | Export ▸ Format | both |
| `root_prim_name` | string | `/root` | general | Advanced USD ▸ General | both |
| `export_animation` | bool | `false` | general | Advanced USD ▸ General ▸ Include | both |
| `author_animation_library` | bool | `false` | general | Advanced USD ▸ General *(needs `export_animation`)* | both |
| `selected_objects_only` | bool | `false` | general | Advanced USD ▸ General ▸ Include | both |
| `export_custom_properties` | bool | `true` | general | Advanced USD ▸ General | both |
| `custom_properties_namespace` | string | `userProperties` | general | Advanced USD ▸ General *(needs `export_custom_properties`)* | both |
| `author_blender_name` | bool | `true` | general | Advanced USD ▸ General *(needs `export_custom_properties`)* | both |
| `allow_unicode` | bool | `true` | general | Advanced USD ▸ General | both |
| `xform_op_mode` | enum | `TRS` | general | Advanced USD ▸ General | both |
| `evaluation_mode` | enum | `RENDER` | general | Advanced USD ▸ General | both |
| `use_instancing` | bool | `true` | general | Advanced USD ▸ General | both |
| `merge_parent_xform` | bool | `false` | geometry | Advanced USD ▸ Geometry | both |
| `triangulate_meshes` | bool | `false` | geometry | Advanced USD ▸ Geometry | both |
| `quad_method` | enum | `SHORTEST_DIAGONAL` | geometry | Advanced USD ▸ Geometry *(needs `triangulate_meshes`)* | both |
| `ngon_method` | enum | `BEAUTY` | geometry | Advanced USD ▸ Geometry *(needs `triangulate_meshes`)* | both |
| `export_subdivision` | enum | `BEST_MATCH` | geometry | Advanced USD ▸ Geometry | both |
| `export_armatures` | bool | `true` | rigging | Advanced USD ▸ Rigging | both |
| `only_deform_bones` | bool | `false` | rigging | Advanced USD ▸ Rigging | both |
| `export_shapekeys` | bool | `true` | rigging | Advanced USD ▸ Rigging | both |
| `export_texture_settings_enabled` | bool | `false` | texture | Optimization *(direct route only)* | both |
| `bake_resolution` | enum | `2048` | texture | Optimization | both |
| `bake_resolution_custom` | int ≥32 | `2048` | texture | Optimization *(needs `bake_resolution=CUSTOM`)* | both |
| `bake_image_format` | enum | `AVIF` | texture | Optimization | both |
| `bake_margin` | int ≥0 | `8` | texture | Optimization *(bake route only)* | bake |
| `materialx_surface_profile` | enum | `realitykit_portable` | materials | Material Settings *(PBR ▸ Translate only)* | both |
| `normalize_unsupported_values` | bool | `false` | materials | Material Settings *(PBR ▸ Translate only)* | direct/validate |
| `bake_mode` | enum | `LIT_IBL` | bake | **none — derived, see above** | bake |
| `bake_ibl_source` | enum | `SCENE_WORLD` | bake | Material Settings *(Unlit ▸ Lighting & Shadows)* | bake (`LIT_IBL`) |
| `bake_ibl_filepath` | string | `""` | bake | Material Settings *(needs `bake_ibl_source=HDRI_FILE`)* | bake (`LIT_IBL`) |
| `bake_ibl_strength` | float ≥0 | `1.0` | bake | Material Settings *(needs `bake_ibl_source=HDRI_FILE`)* | bake (`LIT_IBL`+HDRI) |
| `bake_ibl_rotation` | float (rad) | `0.0` | bake | Material Settings *(needs `bake_ibl_source=HDRI_FILE`)* | bake (`LIT_IBL`+HDRI) |
| `bake_isolate_meshes_lit` | bool | `false` | bake | Material Settings *(Unlit ▸ Lighting & Shadows)* | bake (`LIT_IBL`) |
| `bake_base_color` | bool | `true` | bake | Material Settings ▸ Advanced | bake |
| `bake_opacity` | bool | `true` | bake | Material Settings ▸ Advanced | bake |
| `bake_keep_materials` | bool | `false` | bake | Material Settings ▸ Advanced | bake |
| `bake_step_timeout_seconds` | int ≥0 | `0` | bake | **none — CLI/API only** | bake |
| `bake_roughness_mode` | enum | `TEXTURE` | bake | Material Settings *(PBR ▸ Bake only)* | bake (`LIT_ALBEDO`) |
| `diagnostics_enabled` | bool | `false` | diagnostics | Diagnostics | both |

"both" = affects `blendertorcp export` (direct) and `blendertorcp bake-export`.
"bake" = read only by the bake pipeline; ignored by direct export.

### Panel map

```
3D Viewport ▸ N-panel ▸ "RCP Exporter"
└─ BlenderToRCP Export                       (BLENDERTORCP_PT_export_panel)
   ├─ [Background Job card — only while a job exists]
   ├─ Export box: filepath · export_format · Profile (ui_material_type) · [Export]
   ├─ Material Settings                      (bl_order 1, open)
   │  ├─ PBR      ▸ Processing (ui_pbr_processing)
   │  │  ├─ Translate ▸ materialx_surface_profile · normalize_unsupported_values
   │  │  └─ Bake      ▸ bake_roughness_mode · Advanced ▸ bake_base_color · bake_opacity · bake_keep_materials
   │  └─ Unlit    ▸ Appearance (ui_unlit_appearance)
   │     ├─ Material Color Only  ▸ Advanced ▸ (as above)
   │     └─ Lighting & Shadows   ▸ bake_ibl_source [· bake_ibl_filepath · bake_ibl_strength
   │                                · bake_ibl_rotation] · bake_isolate_meshes_lit · Advanced ▸ (as above)
   ├─ Optimization                           (bl_order 2, collapsed)
   │  ├─ direct route ▸ export_texture_settings_enabled · bake_resolution · bake_image_format [· bake_resolution_custom]
   │  └─ bake route   ▸ bake_resolution · bake_image_format [· bake_resolution_custom] · bake_margin
   ├─ Advanced USD                           (bl_order 3, collapsed)
   │  ├─ General  ▸ root_prim_name · selected_objects_only · export_animation [· author_animation_library]
   │  │             · export_custom_properties [· custom_properties_namespace · author_blender_name]
   │  │             · allow_unicode · xform_op_mode · evaluation_mode · use_instancing
   │  ├─ Geometry ▸ merge_parent_xform · triangulate_meshes [· quad_method · ngon_method] · export_subdivision
   │  └─ Rigging  ▸ export_shapekeys · export_armatures · only_deform_bones
   └─ Diagnostics                            (bl_order 4, collapsed)
      └─ diagnostics_enabled · [Show Diagnostics] [Create Support Bundle]

Shader Editor ▸ N-panel ▸ "RCP Exporter"
└─ RealityKit Compatibility                  (BLENDERTORCP_PT_shader_validation)
   reads materialx_surface_profile and normalize_unsupported_values; writes nothing
```

Every panel below the job monitor greys out while a background bake job runs
(`Plugin/ui/panel.py:728`, `:805`, `:872`, `:944`).

---

## `general`

### `filepath`

| | |
|---|---|
| Type | string (`FILE_PATH`, max 1024) |
| Default | `""` |
| Declared | `Plugin/ui/panel.py:158` |
| UI | Export box ▸ Output Path, placeholder `//export/scene.usdz` (`Plugin/ui/panel.py:617`) |

Output path for the export. **The extension is not yours to choose** — it is rewritten to match
`export_format` on every settings change (`Plugin/ui/panel.py:69`), on operator invoke
(`Plugin/ops/export_operator.py:50`), and in both CLI commands
(`Plugin/api/commands/export.py:123`, `Plugin/api/commands/bake_export.py:317`).

On the CLI this setting is not passed with `filepath=…`; use `-o/--output`, which lands in the
same field (`Plugin/cli/__main__.py:234`). It also seeds the diagnostics sidecar path
(`<output>.diagnostics.json`) and the Diagnostics panel's path preview
(`Plugin/ui/panel.py:977`).

Excluded from the persisted settings payload; remembered per-.blend instead
(`Plugin/prefs.py:24`, `:406`).

### `export_format`

| | |
|---|---|
| Type | enum |
| Values | `USDA`, `USDC`, `USDZ`, `RCP_IMPORT` |
| Default | `USDA` |
| Declared | `Plugin/ui/panel.py:167` |
| UI | Export box ▸ Format (`Plugin/ui/panel.py:618`) |

Selects the output container and drives the enforced file extension
(`.usda` / `.usdc` / `.usdz` / `.import`, `Plugin/ops/export_operator.py:40`).

Behavioural differences:

- `USDA` / `USDC` — Blender's native USD export writes this format directly, then the
  post-processed result is published to the final path
  (`Plugin/export/blender_usd_export.py:270`).
- `USDZ` — Blender exports `.usdc` into a temp location, post-processing runs, then
  `pack_usdz.create_usdz()` packages and *compliance-checks* the archive
  (`Plugin/api/commands/export.py:289`). This is also the only format that triggers the USDZ
  branch of the RealityKit preflight (`Plugin/export/realitykit_preflight.py:1337`).
- `RCP_IMPORT` — **experimental.** The property is internally coerced to `USDA` for the Blender
  export step, and the `.import` directory is generated from the post-processed USDA
  (`Plugin/api/commands/export.py:106`). The command refuses to overwrite an existing `.import`
  directory (`Plugin/api/commands/export.py:128`). Unsupported geometry fails closed.

### `root_prim_name`

| | |
|---|---|
| Type | string |
| Default | `/root` |
| Declared | `Plugin/ui/panel.py:184` |
| UI | Advanced USD ▸ General (`Plugin/ui/panel.py:877`) |

Name or absolute path of the USD root prim. A value without a leading `/` is prefixed with one
(`Plugin/export/blender_usd_export.py:280`), and the result is passed to Blender's
`wm.usd_export` as `root_prim_path` (`:1153`). Post-processing then guarantees the stage's
`defaultPrim` points at it, defining an `Xform` if the export did not create one
(`Plugin/export/usd_scene.py:43`). An empty value falls back to `Scene`
(`Plugin/export/blender_usd_export.py:280`) — which is why the UI placeholder reads `Scene`.

### `export_animation`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:192` |
| UI | Advanced USD ▸ General ▸ Include row (`Plugin/ui/panel.py:882`) |

Master switch for animation. Passed to `wm.usd_export`
(`Plugin/export/blender_usd_export.py:1127`) and gates BlenderToRCP's own animation passes:
`animation_export` returns immediately when off (`Plugin/export/animation_export.py:182`), as
does the RCP AnimationLibrary author pass (`Plugin/export/usd_animation_library.py:19`).

### `author_animation_library`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:199` |
| UI | Advanced USD ▸ General — **only drawn when `export_animation` is on** (`Plugin/ui/panel.py:883`) |
| Status | **Experimental** |

Authors Reality Composer Pro `RealityKit.AnimationLibrary` clip metadata with per-clip start
times (`Plugin/export/usd_animation_library.py:17`).

Interactions:

- Requires `export_animation`; returns early otherwise (`:19`).
- Requires diagnostics to be collecting animation segments — the pass reads
  `diagnostics.data["animations"]["segments"]` and does nothing if there are none (`:24`).
- When **off**, it is not merely a no-op: it actively *removes* any pre-existing
  AnimationLibrary from the stage and emits a warning (`:29`).

On the pinned RCP 3 build, supported USD import recognises the schema but flattens named clips
to the aggregate animation. Leave it off for RealityKit runtime exports.

### `selected_objects_only`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:209` |
| UI | Advanced USD ▸ General ▸ Include row (`Plugin/ui/panel.py:881`) |
| CLI shortcut | `--selected-only` on `export` and `bake-export` |

Restricts the export scope to the current selection. This is not just a flag forwarded to
Blender (`Plugin/export/blender_usd_export.py:1126`) — it changes several behaviours:

- Material validation narrows to materials on the selected (plus dependency-closed) objects
  instead of every scene material (`Plugin/api/commands/export.py:178`,
  `Plugin/ops/export_operator.py:137`).
- Export fails closed with `NO_EXPORTABLE_OBJECTS` when nothing is selected
  (`Plugin/api/commands/export.py:201`).
- The animation pass expands the selection to parents/dependencies before exporting
  (`Plugin/export/animation_export.py:48`, `:167`, `:1304`).
- Bake jobs re-apply the selection *after* the bake's own selection churn
  (`Plugin/bake_export_runner.py:705`).

### `export_custom_properties`

| | |
|---|---|
| Type | bool |
| Default | `true` |
| Declared | `Plugin/ui/panel.py:216` |
| UI | Advanced USD ▸ General (`Plugin/ui/panel.py:886`) |

Exports Blender custom properties as USD attributes. Forwarded to `wm.usd_export`
(`Plugin/export/blender_usd_export.py:1154`).

**It is a master switch for two other settings.** When off, the exporter forces
`custom_properties_namespace` to `""` and `author_blender_name` to `False` regardless of their
stored values (`Plugin/export/blender_usd_export.py:1155-1162`). The UI mirrors this by drawing
`author_blender_name` in a disabled row (`Plugin/ui/panel.py:891`).

### `custom_properties_namespace`

| | |
|---|---|
| Type | string |
| Default | `userProperties` |
| Declared | `Plugin/ui/panel.py:223` |
| UI | Advanced USD ▸ General — only drawn when `export_custom_properties` is on (`Plugin/ui/panel.py:888`) |

Namespace prefix applied to exported custom-property attribute names. Ignored (forced to `""`)
when `export_custom_properties` is off (`Plugin/export/blender_usd_export.py:1155`).

### `author_blender_name`

| | |
|---|---|
| Type | bool |
| Default | `true` |
| Declared | `Plugin/ui/panel.py:230` |
| UI | Advanced USD ▸ General (`Plugin/ui/panel.py:889` enabled, `:893` disabled) |

Writes the original Blender object/data names as USD attributes. Ignored (forced `False`) when
`export_custom_properties` is off (`Plugin/export/blender_usd_export.py:1160`) — the property
description states this dependency correctly.

### `allow_unicode`

| | |
|---|---|
| Type | bool |
| Default | `true` |
| Declared | `Plugin/ui/panel.py:237` |
| UI | Advanced USD ▸ General (`Plugin/ui/panel.py:894`) |

Preserves UTF-8 characters in USD identifiers (USD 24.03+). Forwarded to `wm.usd_export`
(`Plugin/export/blender_usd_export.py:1163`) **and** used again during post-processing, where
`usd_scene.normalize_scene()` re-validates every prim name and rewrites invalid identifiers
(`Plugin/export/usd_scene.py:58`, `:503`, `:524`). Turning it off ASCII-folds non-ASCII prim
names rather than failing.

### `xform_op_mode`

| | |
|---|---|
| Type | enum |
| Values | `TRS` (translate/rotate/scale), `TOS` (translate/orient/scale), `MAT` (matrix) |
| Default | `TRS` |
| Declared | `Plugin/ui/panel.py:278` |
| UI | Advanced USD ▸ General (`Plugin/ui/panel.py:895`) |

Transform-op convention written to USD. Passed straight through to `wm.usd_export`
(`Plugin/export/blender_usd_export.py:1152`); BlenderToRCP does not otherwise interpret it.

### `evaluation_mode`

| | |
|---|---|
| Type | enum |
| Values | `RENDER`, `VIEWPORT` |
| Default | `RENDER` |
| Declared | `Plugin/ui/panel.py:290` |
| UI | Advanced USD ▸ General, labelled "Use Settings for" (`Plugin/ui/panel.py:896`) |

Which dependency-graph evaluation Blender uses when generating the exported meshes
(`Plugin/export/blender_usd_export.py:1143`). Also selects the depsgraph used by the animation
sampler (`Plugin/export/animation_export.py:78`, `:694`) and by the external-asset preflight
when walking evaluated objects (`Plugin/export/asset_preflight.py:391`). `RENDER` respects
render-only modifier visibility; `VIEWPORT` matches what you see in the viewport.

### `use_instancing`

| | |
|---|---|
| Type | bool |
| Default | `true` |
| Declared | `Plugin/ui/panel.py:372` |
| UI | Advanced USD ▸ General (`Plugin/ui/panel.py:897`) |

Emits instanced objects as USD references instead of duplicated geometry
(`Plugin/export/blender_usd_export.py:1142`). The bake pipeline is designed to keep this
useful: identical source material + mesh + bake parameters share one baked material so the
instanceable reference survives baking (`Plugin/export/bake_textures.py:249`, `:291`).

> Instance sharing is disabled inside the bake cache when `bake_mode=LIT_IBL`, because
> world-space lighting genuinely differs per instance (`Plugin/export/bake_textures.py:256`).
> `use_instancing` itself is unchanged; only the bake reuse is skipped.

---

## `geometry`

### `merge_parent_xform`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:301` |
| UI | Advanced USD ▸ Geometry (`Plugin/ui/panel.py:901`) |

Merges parent transforms into the child geometry prim. Forwarded verbatim to `wm.usd_export`
(`Plugin/export/blender_usd_export.py:1174`).

> Note: `CLI.md` lists this key under its *Transform* table while the `settings get --group`
> membership is `geometry`. Use `--group geometry` to read it.

### `triangulate_meshes`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:308` |
| UI | Advanced USD ▸ Geometry (`Plugin/ui/panel.py:902`) |

Triangulates meshes during export (`Plugin/export/blender_usd_export.py:1171`). Gates
`quad_method` and `ngon_method` in the UI (`Plugin/ui/panel.py:903`).

> The gate is UI-only. `quad_method` and `ngon_method` are always sent to `wm.usd_export`
> (`:1172`, `:1173`); Blender ignores them when triangulation is off.

### `quad_method`

| | |
|---|---|
| Type | enum |
| Values | `SHORTEST_DIAGONAL`, `BEAUTY`, `FIXED`, `FIXED_ALTERNATE` |
| Default | `SHORTEST_DIAGONAL` |
| Declared | `Plugin/ui/panel.py:315` |
| UI | Advanced USD ▸ Geometry, only when `triangulate_meshes` is on (`Plugin/ui/panel.py:904`) |

How quads are split into triangles (`Plugin/export/blender_usd_export.py:1172`). No effect
unless `triangulate_meshes` is on.

### `ngon_method`

| | |
|---|---|
| Type | enum |
| Values | `BEAUTY`, `EAR_CLIP` |
| Default | `BEAUTY` |
| Declared | `Plugin/ui/panel.py:328` |
| UI | Advanced USD ▸ Geometry, only when `triangulate_meshes` is on (`Plugin/ui/panel.py:905`) |

How n-gons are split. The value is passed through a translation helper
`_ngon_method_for_usd_export()` before reaching the operator
(`Plugin/export/blender_usd_export.py:1173`), so the exported identifier may differ from the
one you set. No effect unless `triangulate_meshes` is on.

### `export_subdivision`

| | |
|---|---|
| Type | enum |
| Values | `IGNORE` (base mesh), `TESSELLATE` (subdivided mesh, no scheme), `BEST_MATCH` (author the scheme when possible) |
| Default | `BEST_MATCH` |
| Declared | `Plugin/ui/panel.py:339` |
| UI | Advanced USD ▸ Geometry (`Plugin/ui/panel.py:906`) |

Forwarded to `wm.usd_export` (`Plugin/export/blender_usd_export.py:1138`).

---

## `rigging`

### `export_armatures`

| | |
|---|---|
| Type | bool |
| Default | `true` |
| Declared | `Plugin/ui/panel.py:351` |
| UI | Advanced USD ▸ Rigging (`Plugin/ui/panel.py:911`) |

Exports armatures as `UsdSkel` skeletons (`Plugin/export/blender_usd_export.py:1139`). Also
gates skeletal animation sampling (`Plugin/export/animation_export.py:77`, `:675`) and tells the
external-asset preflight whether armature dependencies are in scope
(`Plugin/export/asset_preflight.py:717`).

### `only_deform_bones`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:358` |
| UI | Advanced USD ▸ Rigging (`Plugin/ui/panel.py:912`) |

Restricts the exported skeleton to deform bones plus their parent chain
(`Plugin/export/blender_usd_export.py:1140`). Only meaningful with `export_armatures` on; the UI
does not grey it out.

### `export_shapekeys`

| | |
|---|---|
| Type | bool |
| Default | `true` |
| Declared | `Plugin/ui/panel.py:365` |
| UI | Advanced USD ▸ Rigging (`Plugin/ui/panel.py:910`) |

Exports shape keys as USD blend shapes (`Plugin/export/blender_usd_export.py:1141`) and gates
blend-shape animation sampling (`Plugin/export/animation_export.py:709`).

---

## `texture`

This group is where the direct-export and bake pipelines diverge most sharply. Read
`export_texture_settings_enabled` first.

### `export_texture_settings_enabled`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:442` |
| UI | Optimization panel — **direct route only** (`Plugin/ui/panel.py:809`) |

The master gate for `bake_resolution`, `bake_resolution_custom`, `bake_image_format` and
`bake_margin`. When it is `false`, all four are ignored by the resolvers
(`Plugin/export/bake_textures.py:979`, `:1134`, `:1149`, `:1182`;
`Plugin/export/usd_textures.py:790`).

What "ignored" means per pipeline:

| Setting | Direct export, gate off | Bake, gate off | Gate on |
|---|---|---|---|
| `bake_resolution` | textures kept at source size | bake sized from each material's own source textures (floor 512, fallback 2048) | the configured value |
| `bake_image_format` | AVIF/PNG/JPEG/OpenEXR preserved, other LDR normalised to PNG | `AVIF` | the configured value |
| `bake_margin` | n/a | `8` | the configured value |

The one that actually bites: with the gate off, **the bake ignores the `2048` default and sizes
each material from its own source textures instead** (`Plugin/export/bake_textures.py:971-990`).

How the gate gets turned on:

- **Blender UI, direct route** — you tick "Optimize Source Textures".
- **Blender UI, bake route** — the toggle is *not drawn*, but the Export button forces it on for
  the job: `enable_texture_settings=self.apply_ui_profile` →
  `data["export_texture_settings_enabled"] = True`
  (`Plugin/ops/bake_export_operator.py:183`, `:730`). This is why the Optimization fields work
  in the UI bake route despite the hidden gate.
- **CLI `bake-export`** — passing any of `--resolution`, `--image-format`, `--margin` stages the
  gate to `true` for that run (`Plugin/api/commands/bake_export.py:137`, `:182`). Without one of
  those flags, the gate keeps its scene value.
- **CLI `export`** — no flag turns it on; set it explicitly with
  `export-texture-settings-enabled=true` or `settings set … --save`.

### `bake_resolution`

| | |
|---|---|
| Type | enum |
| Values | `ORIGINAL`, `512`, `1024`, `2048`, `4096`, `CUSTOM` |
| Default | `2048` |
| Declared | `Plugin/ui/panel.py:449` |
| UI | Optimization — "Maximum Resolution" in the direct route (`Plugin/ui/panel.py:818`), "Bake Resolution" in the bake route (`:826`) |

Two different resolvers read this key and they mean different things:

- `_resolve_bake_resolution()` (`Plugin/export/bake_textures.py:971`) sizes **newly baked**
  textures. Returns `0` for `ORIGINAL` *and* for a disabled gate, where `0` means "size each
  material from its own largest source texture feeding base colour / roughness / alpha", floored
  at 512 px and falling back to 2048 (`:1082`).
- `_resolve_texture_override_resolution()` (`:1133`) sizes **existing** textures being
  transcoded/resized during export. Returns `0` (keep original size) for `ORIGINAL`, and
  `2048` when the gate is off.

`LIT_IBL` overrides "source resolution" back to 2048, because a lighting/shadow bake's required
resolution has nothing to do with the source albedo's size
(`Plugin/export/bake_textures.py:132`).

Resolution is part of the bake reuse cache key, so changing it forces a fresh bake
(`Plugin/export/bake_textures.py:1041`).

### `bake_resolution_custom`

| | |
|---|---|
| Type | int, min 32, no max |
| Default | `2048` |
| Declared | `Plugin/ui/panel.py:476` |
| UI | Optimization, only when `bake_resolution == CUSTOM` (`Plugin/ui/panel.py:822`, `:828`) |

Read only when `bake_resolution == CUSTOM` (`Plugin/export/bake_textures.py:985`, `:1140`), and
only when `export_texture_settings_enabled` is on. On the CLI, `--resolution <int>` sets
`bake_resolution=CUSTOM` **and** this value in one step
(`Plugin/api/commands/bake_export.py:165-176`).

### `bake_image_format`

| | |
|---|---|
| Type | enum |
| Values | `ORIGINAL`, `AVIF`, `PNG` |
| Default | `AVIF` |
| Declared | `Plugin/ui/panel.py:464` |
| UI | Optimization, both routes (`Plugin/ui/panel.py:821`, `:827`) |

Resolved by `_resolve_bake_image_format()` (`Plugin/export/bake_textures.py:1148`):

- Gate off → forced to `AVIF`.
- `ORIGINAL` + saving a **newly baked** image → downgraded to `PNG` with a warning, because
  there is no source encoding to preserve (`:1156`). The UI states this inline
  (`Plugin/ui/panel.py:831`).
- `ORIGINAL` + **existing** texture staging → keeps AVIF/PNG/JPEG/OpenEXR and normalises other
  LDR inputs to PNG (`:1167`).
- A format unsupported by the running Blender build falls back to PNG with a warning (`:1169`).

OpenEXR is never re-encoded or resized, to protect float/HDR data — the override is explicitly
ignored with a warning (`Plugin/export/usd_textures.py:379`, `:709`). Radiance `.hdr` fails with
remediation to convert to OpenEXR rather than silently losing dynamic range (`:374`).

### `bake_margin`

| | |
|---|---|
| Type | int, min 0, no max |
| Default | `8` |
| Declared | `Plugin/ui/panel.py:484` |
| UI | Optimization — **bake route only** (`Plugin/ui/panel.py:830`) |

Bake padding in pixels, in the bake pipeline only (`Plugin/export/bake_textures.py:1181`).
Falls back to `8` when `export_texture_settings_enabled` is off. Not read by direct export.

---

## `materials`

### `materialx_surface_profile`

| | |
|---|---|
| Type | enum |
| Values | `realitykit_portable`, `realitykit_pbr2`, `openpbr_1_1` |
| Default | `realitykit_portable` |
| Declared | `Plugin/ui/panel.py:244` |
| UI | Material Settings, labelled "Surface Model" — **only in PBR ▸ Translate** (`Plugin/ui/panel.py:737`) |
| Status | `realitykit_portable` production; other two **experimental** |

The MaterialX surface contract used when rewriting Blender materials. Read by:

- the material rewrite pass, which builds the graph against the selected profile and emits
  profile-specific runtime warnings (`Plugin/export/materials/rewrite.py:23-34`);
- strict material validation on `export` and `validate`
  (`Plugin/api/commands/export.py:147`, `Plugin/api/commands/validate.py:16`);
- the Shader Editor compatibility panel (`Plugin/ui/shader_panel.py:33`) and the interactive
  validation operators (`Plugin/ops/validation_operators.py:32`);
- diagnostics and support bundles (`Plugin/export/support_bundle.py:235`).

> **The UI hides this in the bake routes, but the exporter still reads it.** `rewrite_materials`
> runs in `postprocess_usd.process_usd_stage()` for both pipelines
> (`Plugin/export/postprocess_usd.py:68`), so a non-default profile left over from a Translate
> session continues to apply to baked exports even though no control is shown.

Only `realitykit_portable` is verified for current RealityKit/RCP. USDZ validation is not
weakened for the experimental profiles.

`validate` accepts a per-run override with `--materialx-surface-profile`
(`Plugin/api/commands/validate.py:20`) that does not touch the scene setting.

### `normalize_unsupported_values`

| | |
|---|---|
| Type | bool |
| Default | `false` (`REALITYKIT_OS27_DEFAULTS`, `Plugin/api/commands/_settings_common.py:34`) |
| Declared | `Plugin/ui/panel.py:268` |
| UI | Material Settings — **only in PBR ▸ Translate**, with an explanatory policy box when on (`Plugin/ui/panel.py:740-750`) |

A narrowly scoped, export-only repair. When on, an **unlinked constant achromatic** Principled
`Specular Tint` above `1` is clamped to `[1,1,1]` in the extracted export data only
(`Plugin/export/materials/rewrite.py:110`, `Plugin/material_policies.py:14`). The Blender node
is not assigned to and the `.blend` is not saved. Colored, linked, negative, and non-finite
values still fail the export.

It also relaxes validation symmetrically, so `validate` and the Shader Editor panel agree with
what export will do (`Plugin/nodes/validate.py:339`, `:543`;
`Plugin/ops/validation_operators.py:40`; `Plugin/ui/shader_panel.py:41`).

Deviating from `false` is recorded in diagnostics as a profile deviation
(`Plugin/api/commands/_settings_common.py:415`).

Because bake exports skip source-graph validation entirely, this setting is effectively
direct-export and `validate` only.

---

## `bake`

Every setting in this group is read exclusively by the bake pipeline
(`blendertorcp bake-export`, or the Blender Export button when the profile routes to a bake).
`blendertorcp export` ignores all of them.

### `bake_mode`

| | |
|---|---|
| Type | enum |
| Values | `UNLIT_ALBEDO`, `LIT_ALBEDO`, `LIT_IBL` |
| Default | `LIT_IBL` |
| Declared | `Plugin/ui/panel.py:379` |
| UI | **None.** Derived from the profile controls and overwritten on every UI export — see [the routing section](#read-this-first-the-ui-does-not-expose-bake_mode-it-computes-it). |
| CLI | `--bake-mode` on `bake-export` (`Plugin/api/commands/bake_export.py:118`) |

The mode drives most of the bake's behaviour (`Plugin/export/bake_textures.py:127`; unknown
values are coerced to `LIT_IBL` at `:129`):

| | `UNLIT_ALBEDO` | `LIT_ALBEDO` | `LIT_IBL` |
|---|---|---|---|
| UI name | Material Color Only - Unlit | Material Color Only - Lit PBR | Lighting & Shadows |
| Bake pass | `DIFFUSE` / `{COLOR}` | `DIFFUSE` / `{COLOR}` | `COMBINED` with an explicit pass filter (`:239`) |
| Roughness map baked | no | **yes** (`:143`) | no |
| Authored material | Unlit | **Lit PBR** | Unlit |
| Flat-material shortcut | yes | yes | no (`:182`) |
| Bake reuse across instances | yes | yes | **no** — world-space lighting differs per instance (`:256`) |
| Samples | 1 (`:454`) | 1 | scene samples |
| Temporary IBL world | no | no | yes (`:258`) |
| Extra contract checks | — | normal/metallic passthrough validated (`:1321`) | — |

`force_unlit_materials` is derived from it: everything except `LIT_ALBEDO` authors Unlit
(`Plugin/export/bake_finalize.py:17`).

`LIT_IBL` is also what makes the Scene World / HDRI a *dependency*: the external-asset preflight
only requires the World or the explicit HDRI when `bake_mode == LIT_IBL`
(`Plugin/export/asset_preflight.py:733`, `:742`).

### `bake_ibl_source`

| | |
|---|---|
| Type | enum |
| Values | `SCENE_WORLD`, `HDRI_FILE` |
| Default | `SCENE_WORLD` |
| Declared | `Plugin/ui/panel.py:391` |
| UI | Material Settings ▸ Unlit ▸ Lighting & Shadows (`Plugin/ui/panel.py:760`) |

**Only read when `bake_mode == LIT_IBL`** — `_temporary_ibl_world()` is entered with
`enabled=(bake_mode == "LIT_IBL")` and returns immediately otherwise
(`Plugin/export/bake_textures.py:258`, `:716`). With `SCENE_WORLD` the scene's own World is
used unchanged (`:721`); with `HDRI_FILE` a temporary World is built from
`bake_ibl_filepath`/`bake_ibl_strength`/`bake_ibl_rotation` and restored afterwards (`:739-752`).

It also selects which dependency the preflight demands: `SCENE_WORLD` makes the Scene World a
required dependency, `HDRI_FILE` makes the HDRI one
(`Plugin/export/asset_preflight.py:734`, `:743`).

### `bake_ibl_filepath`

| | |
|---|---|
| Type | string (`FILE_PATH`, max 1024) |
| Default | `""` |
| Declared | `Plugin/ui/panel.py:402` |
| UI | Material Settings, only when `bake_ibl_source == HDRI_FILE` (`Plugin/ui/panel.py:764`) |

Required when `bake_mode=LIT_IBL` and `bake_ibl_source=HDRI_FILE`; an empty value raises
"Bake mode is 'Lighting & Shadows' but no HDRI file is set."
(`Plugin/export/bake_textures.py:766`).

Path resolution has real semantics (`Plugin/export/bake_textures.py:755`):

- `//foo.hdr` is Blender-relative to the source `.blend`; if the `.blend` was never saved this
  fails closed with an actionable message (`:778`).
- Any other relative path is CWD-relative (`:786`).
- Background jobs resolve it to an **absolute** path before saving the temporary scene snapshot,
  so loading the copy from a private job directory cannot retarget the lighting
  (`Plugin/ops/bake_export_operator.py:744`).
- The preflight reports a missing HDRI against `{"setting": "bake_ibl_filepath"}`
  (`Plugin/export/asset_preflight.py:508`).

### `bake_ibl_strength`

| | |
|---|---|
| Type | float, min 0.0, no max |
| Default | `1.0` |
| Declared | `Plugin/ui/panel.py:411` |
| UI | Material Settings, only when `bake_ibl_source == HDRI_FILE` (`Plugin/ui/panel.py:767`) |

Multiplier on the temporary HDRI world's background strength
(`Plugin/export/bake_textures.py:733` → `_create_hdri_world`). **Ignored for `SCENE_WORLD`** —
the scene's own World strength is used as authored. The property description
("Lighting strength multiplier for the HDRI bake") is accurate; the UI reinforces it by only
drawing the field in the HDRI branch.

### `bake_ibl_rotation`

| | |
|---|---|
| Type | float, `ANGLE` subtype, stored in **radians**, unbounded |
| Default | `0.0` |
| Declared | `Plugin/ui/panel.py:419` |
| UI | Material Settings, only when `bake_ibl_source == HDRI_FILE` (`Plugin/ui/panel.py:768`) |

Z-axis rotation of the temporary HDRI environment (`Plugin/export/bake_textures.py:734`).
Blender's UI shows degrees because of the `ANGLE` subtype; `settings set` and `--ibl-rotation`
take radians. Ignored for `SCENE_WORLD`.

### `bake_isolate_meshes_lit`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:427` |
| UI | Material Settings ▸ Unlit ▸ Lighting & Shadows (`Plugin/ui/panel.py:769`) |

Hides every other mesh while baking each mesh, so meshes do not cast shadows onto one another.
**Only applies to `LIT_IBL`** — the effective flag is
`isolate_meshes = bake_mode == "LIT_IBL" and isolate_meshes_lit`
(`Plugin/export/bake_textures.py:444`). Setting it for `UNLIT_ALBEDO` or `LIT_ALBEDO` is a
silent no-op.

### `bake_base_color`

| | |
|---|---|
| Type | bool |
| Default | `true` |
| Declared | `Plugin/ui/panel.py:492` |
| UI | Material Settings ▸ Advanced (collapsed by default) (`Plugin/ui/panel.py:780`) |
| CLI | `--no-base-color` sets it `false` (`Plugin/api/commands/bake_export.py:191`) |

Enables the base-colour bake pass (`Plugin/export/bake_textures.py:141`). It participates in the
per-object step count and the bake reuse cache key, so turning it off genuinely skips work
rather than baking and discarding.

### `bake_opacity`

| | |
|---|---|
| Type | bool |
| Default | `true` |
| Declared | `Plugin/ui/panel.py:499` |
| UI | Material Settings ▸ Advanced (`Plugin/ui/panel.py:781`) |
| CLI | `--no-opacity` sets it `false` (`Plugin/api/commands/bake_export.py:192`) |

Enables the opacity bake (`Plugin/export/bake_textures.py:142`, `:579`). Opacity is only baked
for materials that actually need it (`_material_needs_opacity`), so enabling it costs nothing on
fully opaque materials.

### `bake_keep_materials`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:506` |
| UI | Material Settings ▸ Advanced (`Plugin/ui/panel.py:782`) |
| CLI | `--keep-materials` (`Plugin/api/commands/bake_export.py:193`) |

Controls whether the generated baked materials stay assigned to the objects after export, or
whether the original materials are restored
(`Plugin/api/commands/bake_export.py:761` → `restore_baked_materials`;
`Plugin/bake_export_runner.py:814`).

> In the Blender UI this is close to inert by construction: the bake runs in a **background
> Blender process against a temporary scene snapshot**
> (`Plugin/ops/bake_export_operator.py:761`), so "keeping" the materials keeps them in a worker
> process that then exits. Your open scene is unaffected either way. It is meaningful for
> `blendertorcp bake-export … --keep-materials --save`-style in-process workflows.

### `bake_step_timeout_seconds`

| | |
|---|---|
| Type | int, min 0, no max. `0` = no timeout |
| Default | `0` |
| Declared | `Plugin/ui/panel.py:434` |
| UI | **None.** The property exists and persists, but no panel draws it. |
| CLI | `--step-timeout <SEC>` on `bake-export` (`Plugin/api/commands/bake_export.py:126`) |

Per-step budget for the background bake/export worker. Each bake, USD export, post-process,
package and cleanup step gets this budget **independently**
(`Plugin/api/commands/bake_export.py:421`, `Plugin/bake_export_runner.py:585`). The UI operator
reads it to supervise its worker (`Plugin/ops/bake_export_operator.py:506`), so a value set from
the CLI does affect UI background jobs — there is simply no control to set it from.

Distinct from the CLI global `--timeout`, which bounds the whole Blender process.

### `bake_roughness_mode`

| | |
|---|---|
| Type | enum |
| Values | `TEXTURE` (per-texel map), `AVERAGE` (one constant, no roughness texture) |
| Default | `TEXTURE` |
| Declared | `Plugin/ui/panel.py:513` |
| UI | Material Settings ▸ PBR ▸ Bake, labelled "Roughness" (`Plugin/ui/panel.py:752`) |
| CLI | `--roughness-mode` (`Plugin/cli/__main__.py:297`) |

Read at `Plugin/export/bake_textures.py:145`. **Only meaningful for `LIT_ALBEDO`**, because a
roughness map is only baked when `bake_mode == "LIT_ALBEDO"` (`:143`). The property description
states this restriction, and the UI enforces it by drawing the control only in the PBR ▸ Bake
branch — which is exactly the branch that resolves to `LIT_ALBEDO`. A CLI user combining
`--bake-mode LIT_IBL --roughness-mode AVERAGE` gets a silent no-op.

`AVERAGE` still changes the bake cache key, so switching modes forces a re-bake
(`Plugin/export/bake_textures.py:1041`).

---

## `diagnostics`

### `diagnostics_enabled`

| | |
|---|---|
| Type | bool |
| Default | `false` |
| Declared | `Plugin/ui/panel.py:532` |
| UI | Diagnostics panel, labelled "Keep Success Diagnostics" (`Plugin/ui/panel.py:945`) |
| CLI | `--diagnostics` sets it on; `--no-diagnostics` suppresses success diagnostics for one run |

Controls **only** whether a *successful* export keeps its `<output>.diagnostics.json` sidecar
(`Plugin/api/commands/export.py:157`, `Plugin/api/commands/bake_export.py:346`,
`Plugin/ops/export_operator.py:114`, `Plugin/bake_export_runner.py:434`).

**Failures always write diagnostics**, regardless of this setting — the panel says so inline
(`Plugin/ui/panel.py:948`) and the code comments confirm it
(`Plugin/ops/export_operator.py:117`). Even settings-validation failures that occur before the
pipeline starts get a best-effort sidecar
(`Plugin/api/commands/_settings_common.py:131`).

`--no-diagnostics` is a per-run suppression that does not modify the setting
(`Plugin/api/commands/export.py:159`).

---

## Internal keys

These are on the same PropertyGroup but excluded from `settings list`, `settings get` and
`settings set` by `INTERNAL_KEYS` (`Plugin/api/commands/_settings_common.py:40`).

| Key | Type | Default | Why it is internal |
|---|---|---|---|
| `rna_type`, `name` | — | — | Blender PropertyGroup boilerplate. |
| `ui_material_type` | enum `REALITYKIT_PBR`/`REALITYKIT_UNLIT` | `REALITYKIT_PBR` | Artist-facing profile selector (`Plugin/ui/panel.py:101`). Drives `resolve_ui_export_route`. |
| `ui_pbr_processing` | enum `TRANSLATE`/`BAKE` | `TRANSLATE` | PBR sub-choice (`Plugin/ui/panel.py:120`). |
| `ui_unlit_appearance` | enum `MATERIAL_COLOR`/`LIGHTING_SHADOWS` | `MATERIAL_COLOR` | Unlit sub-choice (`Plugin/ui/panel.py:139`). |
| `force_unlit_materials` | bool | `false` | Derived from `bake_mode` before each export (`Plugin/export/bake_finalize.py:22`) and restored afterwards. Setting it by hand would be overwritten. |
| `history_applied` | bool | `false` | One-shot guard so persisted settings are applied once per scene (`Plugin/prefs.py:384`). `SKIP_SAVE`. |
| `persist_suspended` | bool | `false` | Reentrancy guard that suppresses the persistence callback during bulk writes (`Plugin/ui/panel.py:91`). `SKIP_SAVE`. |
| `last_diagnostics_path` | string | `""` | Path of the most recent diagnostics file, for the "Show Diagnostics" operator. |
| `background_job_dir` | string | `""` | Active background job directory; cleared on file load (`Plugin/ui/panel.py:1112`). `SKIP_SAVE`. |
| `background_job_pid` | int | `0` | PID of the background worker, used to detect a stale job (`Plugin/ui/panel.py:1070`). `SKIP_SAVE`. |

> The three `ui_*` keys are the ones a user is most likely to expect to control. They **are**
> real, persisted, artist-facing settings — the panel's most prominent controls, in fact — but
> they are unreachable from `settings set`. From the CLI you express the same intent by choosing
> the command (`export` vs `bake-export`) and `--bake-mode`. They are also stripped from the
> background-job settings payload (`Plugin/ops/bake_export_operator.py:40-42`), because the
> operator has already resolved them into `bake_mode`.

---

## Add-on preferences

`Edit ▸ Preferences ▸ Add-ons ▸ BlenderToRCP`. Declared in `Plugin/prefs.py:43`.

| Key | Type | Default | Prefs UI | CLI | Read by export? |
|---|---|---|---|---|---|
| `usdzip_path` | string (`FILE_PATH`) | `""` | yes (`Plugin/prefs.py:96`) | `preferences get`/`set` | **yes** |
| `materialx_library_path` | string (`DIR_PATH`) | `""` | yes (`Plugin/prefs.py:102`) | `preferences get`/`set` | **no — inert** |
| `enforcement_mode` | enum, single value `BLOCK_EXPORT` | `BLOCK_EXPORT` | no (`HIDDEN`, not drawn) | no | **no — dead** |
| `last_export_settings_json` | string | `""` | no (`HIDDEN`) | no | internal persistence |
| `last_export_paths_json` | string | `""` | no (`HIDDEN`) | no | internal persistence |

`preferences set` only accepts `usdzip_path` and `materialx_library_path`
(`Plugin/api/commands/preferences_set.py:5`); it calls `wm.save_userpref()` because each CLI
invocation is a throwaway Blender process (`:35`).

### `usdzip_path`

Path to an external `usdzip`. When it is set **and** points at an executable file, USDZ
packaging switches from the built-in aligned-zip writer to
`usdzip --asset … --checkCompliance` (`Plugin/export/pack_usdz.py:87-95`). A sibling
`usdchecker` next to it is then also picked up and used for stricter ARKit-profile compliance
validation (`:104`, `:490`). Leave empty to use the bundled Python packager, which still
performs structural validation.

Only consulted for `USDZ` output.

### `materialx_library_path` — inert

Presented as "Path to MaterialX library directory (optional, uses bundled if empty)" and drawn
in the preferences UI (`Plugin/prefs.py:57`, `:102`), but **nothing in the export pipeline reads
it**. Its only other appearances are the CLI preference key lists and the support bundle, which
merely records the configured value (`Plugin/export/support_bundle.py:150`). Setting it changes
no export behaviour; MaterialX definitions always come from the bundled manifest.

### `enforcement_mode` — dead

Declared with a single enum item and `options={'HIDDEN'}`, and `BlenderToRCPPreferences.draw()`
never draws it (`Plugin/prefs.py:65`, `:89`). No code reads it. The strict "block export on
unsupported nodes" behaviour it describes is unconditional, not configurable.

---

## Settings the exporter reads that do not exist

`_build_export_kwargs()` reads five names off the settings object that the PropertyGroup never
declares. Each therefore always resolves to its `getattr` fallback — they are effectively
hard-coded constants wearing a setting's clothes, and adding a property with any of these names
would silently make it live.

| Name read | Fallback used | Site |
|---|---|---|
| `incremental_frames` | `0` | `Plugin/export/blender_usd_export.py:1128` |
| `export_mesh_colors` | `True` | `Plugin/export/blender_usd_export.py:1135` |
| `accessibility_label` | `""` | `Plugin/export/blender_usd_export.py:1158` |
| `accessibility_description` | `""` | `Plugin/export/blender_usd_export.py:1159` |
| `export_meshes` | `True` | `Plugin/export/asset_preflight.py:716` |

Genuinely non-configurable policy constants — cameras, lights, curves, points, volumes, hair,
world material, orientation conversion, `-Z` forward, `Y` up, `metersPerUnit=1`, UV/normal
export, relative paths — are set as literals in the same function
(`Plugin/export/blender_usd_export.py:1132-1176`) and are not settings at all.

---

## Quick reference: settings with a precondition

| Setting | Ignored unless… |
|---|---|
| `author_animation_library` | `export_animation` is on, and diagnostics recorded animation segments |
| `custom_properties_namespace` | `export_custom_properties` is on |
| `author_blender_name` | `export_custom_properties` is on |
| `quad_method`, `ngon_method` | `triangulate_meshes` is on |
| `only_deform_bones` | `export_armatures` is on |
| `bake_resolution`, `bake_resolution_custom`, `bake_image_format`, `bake_margin` | `export_texture_settings_enabled` is on |
| `bake_resolution_custom` | `bake_resolution == CUSTOM` |
| `bake_ibl_source`, `bake_isolate_meshes_lit` | `bake_mode == LIT_IBL` |
| `bake_ibl_filepath`, `bake_ibl_strength`, `bake_ibl_rotation` | `bake_mode == LIT_IBL` **and** `bake_ibl_source == HDRI_FILE` |
| `bake_roughness_mode` | `bake_mode == LIT_ALBEDO` |
| `bake_margin`, `bake_mode`, all `bake_ibl_*`, `bake_base_color`, `bake_opacity`, `bake_keep_materials`, `bake_roughness_mode`, `bake_step_timeout_seconds` | the run is a **bake** export, not `blendertorcp export` |
| `normalize_unsupported_values` | the run performs source-graph validation (direct `export`, `validate`, Shader Editor panel) — bake exports skip it |

| Setting | Overwritten by |
|---|---|
| `bake_mode` | the Blender Export button, from `ui_material_type`/`ui_pbr_processing`/`ui_unlit_appearance` (`Plugin/ops/bake_export_operator.py:116`) |
| `export_texture_settings_enabled` | forced `true` by the Blender Export button on bake routes (`Plugin/ops/bake_export_operator.py:183`); staged `true` by `bake-export --resolution/--image-format/--margin` |
| `export_format` | coerced `RCP_IMPORT` → `USDA` for the underlying Blender export; legacy `USD` → `USDC` |
| `filepath` | extension rewritten to match `export_format` |
| `force_unlit_materials` | recomputed from `bake_mode` before every bake export |
| every setting except `filepath` | a stale/foreign persisted payload triggers a full reset to RNA defaults (`Plugin/prefs.py:377`) |
