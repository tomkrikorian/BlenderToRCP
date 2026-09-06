# BlenderToRCP Documentation

This page is the index of the BlenderToRCP documentation. Use it to find the
right page for what you want to know, or to trace an export that surprised you.

## Start here

| Document | Read it when you want to know |
|---|---|
| [ARCHITECTURE.MD](ARCHITECTURE.MD) | How the codebase is laid out and which module owns what |
| [CLI.md](CLI.md) | Every command, flag, exit code, and the JSON envelope |
| [SETTINGS.md](SETTINGS.md) | What every toggle changes, and which ones override each other |
| [FEATURE_SUPPORT.md](FEATURE_SUPPORT.md) | Which Blender features survive an export, and which are refused, dropped, or dropped silently |
| [APPLE_PLATFORM_CONTRACT.md](APPLE_PLATFORM_CONTRACT.md) | Which USD and MaterialX features Reality Composer Pro and RealityKit accept: file-format ceilings, the MaterialX node library, and why one validation covers every OS 27 device |
| [STYLE_GUIDE.md](STYLE_GUIDE.md) | How these pages are written — voice, page types, and what stays out of `docs/` (for contributors) |

## What the exporter does to your scene

These three describe the pipeline in the order it runs. Each documents the
decisions the exporter makes **on your behalf** — the substitutions, inferences
and rejections that happen without you asking — and, for each one, whether you
are told about it.

| Document | Covers |
|---|---|
| [MATERIAL_TRANSLATION.md](MATERIAL_TRANSLATION.md) | Blender shader graph → RealityKit MaterialX ShaderGraph: the surface, node coverage, color-space handling, the texture pipeline |
| [BAKING.md](BAKING.md) | When a bake happens at all, what each bake mode captures, what scene state is overridden and restored, resolution/format/UV choices |
| [EXPORT_PIPELINE.md](EXPORT_PIPELINE.md) | Geometry, transforms, units, animation, staging and publication, USDZ packaging |

If you are chasing a specific surprise:

- **"My texture looks wrong."** → [BAKING.md](BAKING.md) for baked output,
  [MATERIAL_TRANSLATION.md](MATERIAL_TRANSLATION.md) for color space and
  texture staging.
- **"My object is the wrong size."** → [EXPORT_PIPELINE.md](EXPORT_PIPELINE.md),
  the Apple spatial contract section.
- **"The export doesn't match my viewport."** → [BAKING.md](BAKING.md); view
  transform is deliberately not applied to baked textures.
- **"I set a setting and nothing happened."** → [SETTINGS.md](SETTINGS.md),
  which records the settings that other settings silently override.
- **"Something is missing from the export and nothing told me."** →
  [FEATURE_SUPPORT.md](FEATURE_SUPPORT.md), which ends with the list of
  features that leave without a warning.

## Known issues

Open defects, including several that produce silently wrong output, are tracked
in [GitHub Issues](https://github.com/tomkrikorian/BlenderToRCP/issues). Search
there before filing a bug — it may already be recorded, with a measurement
attached.

## How these pages are verified

Behavioral claims in the pipeline documents are linked to the source lines that
implement them and pinned to the versions they were checked against. A finding
that contradicts a documented claim is filed as an issue and the page is
corrected — the page is never left standing against a measurement.
