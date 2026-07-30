# BlenderToRCP Documentation

## Start here

| Document | Read it when you want to know |
|---|---|
| [ARCHITECTURE.MD](ARCHITECTURE.MD) | How the codebase is laid out and which module owns what |
| [CLI.md](CLI.md) | Every command, flag, exit code, and the JSON envelope |
| [SETTINGS.md](SETTINGS.md) | What every toggle actually changes, and which ones override each other |
| [APPLE_PLATFORM_CONTRACT.md](APPLE_PLATFORM_CONTRACT.md) | What OS 27 / RCP 3 actually support: OpenUSD versions and file-format ceilings, the MaterialX nodedef universe, and the editor-vs-runtime split — all measured from the shipped binaries |

## What the exporter does to your scene

These three describe the pipeline in the order it runs. Each documents the
decisions the exporter makes **on your behalf** — the substitutions, inferences
and rejections that happen without you asking — and, for each one, whether you
are told about it.

| Document | Covers |
|---|---|
| [MATERIAL_TRANSLATION.md](MATERIAL_TRANSLATION.md) | Blender shader graph → RealityKit MaterialX ShaderGraph: surface profiles, node coverage, colour-space handling, the texture pipeline |
| [BAKING.md](BAKING.md) | When a bake happens at all, what each bake mode captures, what scene state is overridden and restored, resolution/format/UV choices |
| [EXPORT_PIPELINE.md](EXPORT_PIPELINE.md) | Geometry, transforms, units, animation, staging and publication, USDZ packaging |

If you are chasing a specific surprise:

- **"My texture looks wrong."** → [BAKING.md](BAKING.md) for baked output,
  [MATERIAL_TRANSLATION.md](MATERIAL_TRANSLATION.md) for colour space and
  texture staging.
- **"My object is the wrong size."** → [EXPORT_PIPELINE.md](EXPORT_PIPELINE.md),
  the Apple spatial contract section.
- **"The export doesn't match my viewport."** → [BAKING.md](BAKING.md); view
  transform is deliberately not applied to baked textures.
- **"I set a setting and nothing happened."** → [SETTINGS.md](SETTINGS.md),
  which records the settings that other settings silently override.

## Experimental: Reality Composer Pro `.import`

Build-pinned to RCP 3.0 build `80.0.1.500.1`, not an Apple published interchange
format, and not a compatibility claim. See
[RCP_IMPORT_EXPERIMENT.md](RCP_IMPORT_EXPERIMENT.md) for the acceptance status
and fail-closed boundaries before relying on any of it.

| Document | Covers |
|---|---|
| [RCP_IMPORT_EXPERIMENT.md](RCP_IMPORT_EXPERIMENT.md) | Measured format contract, acceptance evidence, what is and is not supported |
| [RCP_IMPORT_MULTI_MATERIAL_MESH.md](RCP_IMPORT_MULTI_MATERIAL_MESH.md) | Requirements for one mesh carrying multiple materials |
| [RCP_IMPORT_SKELETAL_CHECKPOINT.md](RCP_IMPORT_SKELETAL_CHECKPOINT.md) | Skeletal import status |

## Known issues

Open defects, including several that produce silently wrong output, are tracked
in [../CODE_REVIEW_FINDINGS.md](../CODE_REVIEW_FINDINGS.md). Read it before
filing a bug — it may already be there, with a measurement attached.

## A note on how these were written

Every behavioural claim in the pipeline documents cites the source line that
implements it, and claims verified by running Blender carry the observation that
proved them. This matters because several long-standing beliefs about this
codebase turned out to be wrong when measured, and are recorded as such in
`CODE_REVIEW_FINDINGS.md` rather than quietly corrected.
