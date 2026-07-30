# PBR Surface 2 Specular Tint research fixture

This fixture compares three interpretations of Blender's constant achromatic
`Specular Tint = [2, 2, 2]` in Reality Composer Pro 3:

1. `DirectOverbright`: authors `[2, 2, 2]` directly with `specularWeight = 1`.
2. `ClampOnly`: authors `[1, 1, 1]` with `specularWeight = 1`. This is the only
   strategy available through the exporter's explicit normalization option.
3. `ClampAndRedistribute`: authors `[1, 1, 1]` with `specularWeight = 2`.

The third variant is a research hypothesis, not a production mapping. Apple
does not document PBR Surface 2 closely enough to assume that excess tint
energy can be transferred to `specularWeight`. Compare the three spheres under
the same RCP 3 environment and lights, on current visionOS and macOS hardware,
before changing exporter policy.

Generate the fixture with Blender 5.2:

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background \
  --python scripts/generate_pbr2_specular_tint_research.py \
  -- \
  --output /tmp/PBR2SpecularTintResearch.usda
```

Import the result into RCP 3, use one fixed environment, and capture the same
view of each sphere. Record the RCP build and OS build with the comparison.
The generator authors USD only; it does not open, save, or modify a `.blend`.
