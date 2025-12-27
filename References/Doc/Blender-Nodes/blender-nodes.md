# Blender 5.0 — Shader Nodes Reference (Complete & Explicit)

> Source: Official Blender Manual
>
> This document **exhaustively lists all Shader Editor nodes** in Blender 5.0.
>
> For **every node**, we clearly state:
> - **Node name** (exact Blender name)
> - **What it is** (conceptual role)
> - **What it’s used for** (practical usage)
> - **Inputs** (socket name + data type)
> - **Outputs** (socket name + data type)
>
> Style goals: factual, compact, unambiguous, AI-friendly.

---

# 1. INPUT NODES

## Ambient Occlusion
- **What it is:** Computes how much surrounding geometry blocks ambient light.
- **Used for:** Dirt masks, crevice darkening, wear effects.
- **Inputs:** Color (Color), Distance (Float), Normal (Vector)
- **Outputs:** Color (Color), AO (Float)

## Attribute
- **What it is:** Reads a named attribute from geometry, object, or scene.
- **Used for:** Custom data access (IDs, masks, metadata).
- **Inputs:** —
- **Outputs:** Color (Color), Vector (Vector), Factor (Float), Alpha (Float)

## Bevel *(Cycles)*
- **What it is:** Modifies normals to simulate rounded edges.
- **Used for:** Softer highlights without geometry bevels.
- **Inputs:** Radius (Float), Normal (Vector)
- **Outputs:** Normal (Vector)

## Camera Data
- **What it is:** Provides camera-relative shading information.
- **Used for:** Depth-based fades, fog, camera effects.
- **Inputs:** —
- **Outputs:** View Vector (Vector), View Z Depth (Float), View Distance (Float)

## Fresnel
- **What it is:** Computes angle-dependent reflectivity using IOR.
- **Used for:** Physically correct shader mixing.
- **Inputs:** IOR (Float), Normal (Vector)
- **Outputs:** Factor (Float)

## Geometry
- **What it is:** Exposes geometric data at the shading point.
- **Used for:** Curvature masks, backface checks, variation.
- **Inputs:** —
- **Outputs:** Position (Vector), Normal (Vector), Tangent (Vector), True Normal (Vector), Incoming (Vector), Parametric (Vector), Backfacing (Float), Pointiness (Float), Random per Island (Float)

## Curves Info
- **What it is:** Provides per-curve / hair data.
- **Used for:** Hair shading variation.
- **Inputs:** —
- **Outputs:** Is Strand (Float), Intercept (Float), Length (Float), Thickness (Float), Tangent Normal (Vector), Random (Float)

## Layer Weight
- **What it is:** Computes view-angle based weights.
- **Used for:** Edge highlights, plastic look.
- **Inputs:** Blend (Float), Normal (Vector)
- **Outputs:** Fresnel (Float), Facing (Float)

## Light Path
- **What it is:** Identifies the type of ray being shaded.
- **Used for:** Ray-conditional shading logic.
- **Inputs:** —
- **Outputs:** Is Camera Ray (Float), Is Shadow Ray (Float), Is Diffuse Ray (Float), Is Glossy Ray (Float), Is Reflection Ray (Float), Is Transmission Ray (Float), Ray Length (Float), Ray Depth (Int)

## Object Info
- **What it is:** Provides per-object instance information.
- **Used for:** Per-object variation and masking.
- **Inputs:** —
- **Outputs:** Location (Vector), Color (Color), Alpha (Float), Object Index (Int), Material Index (Int), Random (Float)

## Particle Info *(Cycles)*
- **What it is:** Accesses particle system data.
- **Used for:** Particle-based variation.
- **Inputs:** —
- **Outputs:** Index (Int), Random (Float), Age (Float), Lifetime (Float), Location (Vector), Size (Float), Velocity (Vector), Angular Velocity (Vector)

## Point Info *(Cycles)*
- **What it is:** Provides point cloud data.
- **Used for:** Point-based variation.
- **Inputs:** —
- **Outputs:** Location (Vector), Radius (Float), Random (Float)

## Color
- **What it is:** Outputs a constant color value.
- **Used for:** Parameters and color constants.
- **Inputs:** —
- **Outputs:** Color (Color)

## Tangent
- **What it is:** Generates a tangent vector.
- **Used for:** Anisotropic shading.
- **Inputs:** —
- **Outputs:** Tangent (Vector)

## Texture Coordinate
- **What it is:** Provides multiple coordinate spaces.
- **Used for:** Texture mapping.
- **Inputs:** —
- **Outputs:** Generated (Vector), Normal (Vector), UV (Vector), Object (Vector), Camera (Vector), Window (Vector), Reflection (Vector)

## UV Map
- **What it is:** Outputs a specific UV map.
- **Used for:** Multi-UV workflows.
- **Inputs:** —
- **Outputs:** UV (Vector)

## Value
- **What it is:** Outputs a constant numeric value.
- **Used for:** Scalar parameters.
- **Inputs:** —
- **Outputs:** Value (Float)

## Color Attribute
- **What it is:** Reads mesh color attributes.
- **Used for:** Vertex colors, masks.
- **Inputs:** —
- **Outputs:** Color (Color), Alpha (Float)

## Volume Info
- **What it is:** Reads smoke/fire simulation grids.
- **Used for:** Volume shading.
- **Inputs:** —
- **Outputs:** Color (Color), Density (Float), Flame (Float), Temperature (Float)

## Wireframe
- **What it is:** Generates an edge mask.
- **Used for:** Stylized wireframe effects.
- **Inputs:** —
- **Outputs:** Factor (Float)

---

# 2. SHADER NODES

## Add Shader
- **What it is:** Adds two shaders together.
- **Used for:** Layering light contributions.
- **Inputs:** Shader (Shader), Shader (Shader)
- **Outputs:** Shader (Shader)

## Background
- **What it is:** Emits light from the world.
- **Used for:** Environment lighting.
- **Inputs:** Color (Color), Strength (Float)
- **Outputs:** Background (Shader)

## Diffuse BSDF
- **What it is:** Diffuse surface reflection.
- **Used for:** Matte materials.
- **Inputs:** Color (Color), Roughness (Float), Normal (Vector)
- **Outputs:** BSDF (Shader)

## Emission
- **What it is:** Emits light from a surface.
- **Used for:** Screens, LEDs.
- **Inputs:** Color (Color), Strength (Float)
- **Outputs:** Emission (Shader)

## Glass BSDF
- **What it is:** Combined reflection and refraction.
- **Used for:** Glass materials.
- **Inputs:** Color (Color), Roughness (Float), IOR (Float), Normal (Vector)
- **Outputs:** BSDF (Shader)

## Glossy BSDF
- **What it is:** Specular reflection.
- **Used for:** Metals, mirrors.
- **Inputs:** Color (Color), Roughness (Float), Anisotropy (Float), Rotation (Float), Normal (Vector), Tangent (Vector)
- **Outputs:** BSDF (Shader)

## Hair BSDF *(Cycles)*
- **What it is:** Physically-based hair shader.
- **Used for:** Legacy hair systems.
- **Inputs:** Color (Color), Offset (Float), Roughness U (Float), Roughness V (Float), Tangent (Vector)
- **Outputs:** BSDF (Shader)

## Holdout
- **What it is:** Cuts holes in alpha.
- **Used for:** Compositing masks.
- **Inputs:** —
- **Outputs:** Holdout (Shader)

## Mix Shader
- **What it is:** Blends two shaders.
- **Used for:** Material layering.
- **Inputs:** Shader A (Shader), Shader B (Shader), Factor (Float)
- **Outputs:** Shader (Shader)

## Metallic BSDF
- **What it is:** Physically-based metal shader.
- **Used for:** Accurate metals.
- **Inputs:** Base Color (Color), Roughness (Float), IOR / Extinction (Color), Normal (Vector), Tangent (Vector)
- **Outputs:** BSDF (Shader)

## Principled BSDF
- **What it is:** Unified PBR surface shader.
- **Used for:** Most standard materials.
- **Inputs:** Base Color, Roughness, Metallic, IOR, Alpha, Normal, many others
- **Outputs:** BSDF (Shader)

## Principled Hair BSDF *(Cycles)*
- **What it is:** Advanced hair/fur shader.
- **Used for:** Modern hair rendering.
- **Inputs:** Color / Melanin / Roughness / Randomization
- **Outputs:** BSDF (Shader)

## Principled Volume
- **What it is:** Unified volume shader.
- **Used for:** Smoke, fire.
- **Inputs:** Color, Density, Emission, Temperature
- **Outputs:** Volume (Shader)

## Ray Portal BSDF *(Cycles)*
- **What it is:** Teleports rays to another location.
- **Used for:** Portal effects.
- **Inputs:** Color (Color), Position (Vector), Direction (Vector)
- **Outputs:** BSDF (Shader)

## Refraction BSDF
- **What it is:** Glossy refraction shader.
- **Used for:** Glass layering.
- **Inputs:** Color (Color), Roughness (Float), Normal (Vector)
- **Outputs:** BSDF (Shader)

## Specular BSDF *(EEVEE)*
- **What it is:** Specular workflow shader.
- **Used for:** Legacy EEVEE materials.
- **Inputs:** Base Color (Color), Specular (Float), Roughness (Float), Normal (Vector)
- **Outputs:** BSDF (Shader)

## Subsurface Scattering
- **What it is:** BSSRDF-based subsurface shader.
- **Used for:** Skin, wax.
- **Inputs:** Color (Color), Scale (Float), Radius (Vector), Normal (Vector)
- **Outputs:** BSSRDF (Shader)

## Toon BSDF *(Cycles)*
- **What it is:** Stylized toon shading.
- **Used for:** NPR looks.
- **Inputs:** Color (Color), Size (Float), Smooth (Float), Normal (Vector)
- **Outputs:** BSDF (Shader)

## Translucent BSDF
- **What it is:** Diffuse light transmission.
- **Used for:** Thin materials.
- **Inputs:** Color (Color), Normal (Vector)
- **Outputs:** BSDF (Shader)

## Transparent BSDF
- **What it is:** Transparent surface.
- **Used for:** Alpha cutouts.
- **Inputs:** Color (Color)
- **Outputs:** BSDF (Shader)

## Sheen BSDF *(Cycles)*
- **What it is:** Microfiber reflection shader.
- **Used for:** Cloth, dust.
- **Inputs:** Color (Color), Roughness (Float), Normal (Vector)
- **Outputs:** BSDF (Shader)

## Volume Absorption
- **What it is:** Absorbs light in volumes.
- **Used for:** Colored glass, water.
- **Inputs:** Color (Color), Density (Float)
- **Outputs:** Volume (Shader)

## Volume Scatter
- **What it is:** Scatters light in volumes.
- **Used for:** Fog.
- **Inputs:** Color (Color), Density (Float), Anisotropy (Float)
- **Outputs:** Volume (Shader)

## Volume Coefficients
- **What it is:** Explicit physical volume coefficients.
- **Used for:** Measured volume data.
- **Inputs:** Absorption (Color), Scatter (Color), Emission (Color)
- **Outputs:** Volume (Shader)

---

# 3. DISPLACEMENT NODES

## Bump
- **What it is:** Perturbs normals using height data.
- **Used for:** Fake surface detail.
- **Inputs:** Strength (Float), Distance (Float), Height (Float), Normal (Vector)
- **Outputs:** Normal (Vector)

## Displacement
- **What it is:** Offsets geometry along normals.
- **Used for:** True displacement.
- **Inputs:** Height (Float), Midlevel (Float), Scale (Float), Normal (Vector)
- **Outputs:** Displacement (Vector)

## Normal Map
- **What it is:** Converts normal maps to normals.
- **Used for:** Tangent-space normals.
- **Inputs:** Strength (Float), Color (Color)
- **Outputs:** Normal (Vector)

## Vector Displacement
- **What it is:** Displaces geometry in arbitrary directions.
- **Used for:** High-end sculpt detail.
- **Inputs:** Vector (Vector), Midlevel (Float), Scale (Float)
- **Outputs:** Displacement (Vector)

---

# 4. TEXTURE NODES

## Brick Texture
- **What it is:** Procedural brick pattern.
- **Used for:** Masonry textures.
- **Inputs:** Vector (Vector), Color1 (Color), Color2 (Color), Mortar (Color), Scale (Float)
- **Outputs:** Color (Color), Factor (Float)

## Checker Texture
- **What it is:** Checkerboard pattern.
- **Used for:** UV testing.
- **Inputs:** Vector (Vector), Color1 (Color), Color2 (Color), Scale (Float)
- **Outputs:** Color (Color), Factor (Float)

## Environment Texture
- **What it is:** Environment map sampler.
- **Used for:** HDR lighting.
- **Inputs:** Vector (Vector)
- **Outputs:** Color (Color)

## Gabor Texture
- **What it is:** Directional procedural noise.
- **Used for:** Structured noise.
- **Inputs:** Vector (Vector), Scale (Float), Frequency (Float), Anisotropy (Float)
- **Outputs:** Value (Float), Phase (Float), Intensity (Float)

## Gradient Texture
- **What it is:** Gradient generator.
- **Used for:** Masks.
- **Inputs:** Vector (Vector)
- **Outputs:** Color (Color), Factor (Float)

## IES Texture
- **What it is:** Light profile sampler.
- **Used for:** Real-world lights.
- **Inputs:** Vector (Vector), Strength (Float)
- **Outputs:** Factor (Float)

## Image Texture
- **What it is:** Image sampler.
- **Used for:** Albedo, masks, normals.
- **Inputs:** Vector (Vector)
- **Outputs:** Color (Color), Alpha (Float)

## Magic Texture
- **What it is:** Psychedelic procedural texture.
- **Used for:** Stylized effects.
- **Inputs:** Vector (Vector), Scale (Float), Distortion (Float)
- **Outputs:** Color (Color), Factor (Float)

## Noise Texture
- **What it is:** Fractal Perlin noise.
- **Used for:** Organic variation.
- **Inputs:** Vector (Vector), Scale (Float), Detail (Float), Roughness (Float)
- **Outputs:** Color (Color), Factor (Float)

## Sky Texture
- **What it is:** Procedural sky model.
- **Used for:** Outdoor lighting.
- **Inputs:** Vector (Vector)
- **Outputs:** Color (Color)

## Voronoi Texture
- **What it is:** Cellular noise.
- **Used for:** Cracks, cells.
- **Inputs:** Vector (Vector), Scale (Float)
- **Outputs:** Distance (Float), Color (Color), Position (Vector), Radius (Float)

## Wave Texture
- **What it is:** Band / ring pattern.
- **Used for:** Stylized patterns.
- **Inputs:** Vector (Vector), Scale (Float), Distortion (Float)
- **Outputs:** Color (Color), Factor (Float)

## White Noise Texture
- **What it is:** Hash-based random noise.
- **Used for:** Stable randomness.
- **Inputs:** Vector (Vector), W (Float)
- **Outputs:** Value (Float), Color (Color)

---

# 5. COLOR NODES

## Blackbody
- **What it is:** Temperature-to-color conversion.
- **Used for:** Fire, heat.
- **Inputs:** Temperature (Float)
- **Outputs:** Color (Color)

## Brightness / Contrast
- **What it is:** Adjusts image brightness and contrast.
- **Used for:** Color correction.
- **Inputs:** Image (Color), Brightness (Float), Contrast (Float)
- **Outputs:** Image (Color)

## Color Ramp
- **What it is:** Maps values to colors.
- **Used for:** Masks, gradients.
- **Inputs:** Factor (Float)
- **Outputs:** Color (Color), Alpha (Float)

## Gamma
- **What it is:** Applies gamma correction to colors.
- **Used for:** Linear ↔ gamma color space adjustments.
- **Inputs:** Color (Color), Gamma (Float)
- **Outputs:** Color (Color)

## Hue / Saturation / Value
- **What it is:** Modifies colors in HSV space.
- **Used for:** Color grading and stylization.
- **Inputs:** Color (Color), Hue (Float), Saturation (Float), Value (Float), Factor (Float)
- **Outputs:** Color (Color)

## Invert
- **What it is:** Inverts input colors.
- **Used for:** Mask inversion, negative effects.
- **Inputs:** Color (Color), Factor (Float)
- **Outputs:** Color (Color)

## Light Falloff *(Cycles)*
- **What it is:** Controls light intensity decay over distance.
- **Used for:** Non-physical lighting control.
- **Inputs:** Strength (Float), Smooth (Float)
- **Outputs:** Quadratic (Float), Linear (Float), Constant (Float)

## Mix Color
- **What it is:** Blends two values, vectors, or colors.
- **Used for:** Layering, blending, compositing logic.
- **Inputs:** Factor (Float), A (Any), B (Any)
- **Outputs:** Result (Same as input type)

## RGB Curves
- **What it is:** Per-channel curve remapping.
- **Used for:** Color correction and contrast shaping.
- **Inputs:** Color (Color), Factor (Float)
- **Outputs:** Color (Color)

## Wavelength
- **What it is:** Converts light wavelength to RGB.
- **Used for:** Spectral color generation.
- **Inputs:** Wavelength (Float)
- **Outputs:** Color (Color)

## Combine Color
- **What it is:** Combines channels into a color.
- **Used for:** Channel packing.
- **Inputs:** R/G/B or H/S/V or H/S/L (Float), Alpha (Float)
- **Outputs:** Color (Color)

## Separate Color
- **What it is:** Splits a color into channels.
- **Used for:** Channel extraction.
- **Inputs:** Color (Color)
- **Outputs:** R/G/B or H/S/V or H/S/L (Float), Alpha (Float)

## RGB to BW
- **What it is:** Converts color to luminance.
- **Used for:** Grayscale masks.
- **Inputs:** Color (Color)
- **Outputs:** Value (Float)

## Shader to RGB *(EEVEE)*
- **What it is:** Converts shader output to color.
- **Used for:** NPR and toon shading.
- **Inputs:** Shader (Shader)
- **Outputs:** Color (Color), Alpha (Float)

---

# 6. UTILITY NODES

## Math
- **What it is:** Performs scalar math operations.
- **Used for:** Procedural logic.
- **Inputs:** Value (Float), Value (Float) *(dynamic)*
- **Outputs:** Value (Float)

## Clamp
- **What it is:** Limits a value between bounds.
- **Used for:** Preventing overflow.
- **Inputs:** Value (Float), Min (Float), Max (Float)
- **Outputs:** Result (Float)

## Map Range
- **What it is:** Remaps values between ranges.
- **Used for:** Normalization and scaling.
- **Inputs:** Value/Vector, From Min, From Max, To Min, To Max
- **Outputs:** Result/Vector

## Mix
- **What it is:** Generic value/color/vector blending.
- **Used for:** Unified interpolation node.
- **Inputs:** Factor (Float), A (Any), B (Any)
- **Outputs:** Result (Same type)

---

# 7. VECTOR NODES

## Combine XYZ
- **What it is:** Builds a vector from components.
- **Used for:** Vector construction.
- **Inputs:** X (Float), Y (Float), Z (Float)
- **Outputs:** Vector (Vector)

## Separate XYZ
- **What it is:** Splits a vector into components.
- **Used for:** Axis extraction.
- **Inputs:** Vector (Vector)
- **Outputs:** X (Float), Y (Float), Z (Float)

## Mapping
- **What it is:** Transforms vectors.
- **Used for:** UV and coordinate manipulation.
- **Inputs:** Vector (Vector), Location (Vector), Rotation (Vector), Scale (Vector)
- **Outputs:** Vector (Vector)

## Normal
- **What it is:** Outputs a normal and dot product.
- **Used for:** Lighting logic.
- **Inputs:** Normal (Vector)
- **Outputs:** Normal (Vector), Dot (Float)

## Vector Curves
- **What it is:** Curve-based vector remapping.
- **Used for:** Motion shaping.
- **Inputs:** Vector (Vector), Factor (Float)
- **Outputs:** Vector (Vector)

## Radial Tiling
- **What it is:** Radial coordinate tiling.
- **Used for:** Symmetric patterns.
- **Inputs:** Vector (Vector), Sides (Float), Roundness (Float)
- **Outputs:** Segment Coordinates (Vector), Segment ID (Int), Segment Width (Float), Segment Rotation (Float)

## Vector Rotate
- **What it is:** Rotates vectors.
- **Used for:** Directional transforms.
- **Inputs:** Vector (Vector), Center (Vector), Axis (Vector), Angle (Float)
- **Outputs:** Vector (Vector)

## Vector Transform
- **What it is:** Converts vectors between spaces.
- **Used for:** Space conversion.
- **Inputs:** Vector (Vector)
- **Outputs:** Vector (Vector)

## Combine Cylindrical
- **What it is:** Cylindrical → Cartesian conversion.
- **Used for:** Radial constructions.
- **Inputs:** R (Float), Phi (Float), Z (Float)
- **Outputs:** Vector (Vector)

## Separate Cylindrical
- **What it is:** Cartesian → cylindrical conversion.
- **Used for:** Radial analysis.
- **Inputs:** Vector (Vector)
- **Outputs:** R (Float), Phi (Float), Z (Float)

## Combine Spherical
- **What it is:** Spherical → Cartesian conversion.
- **Used for:** Polar constructions.
- **Inputs:** R (Float), Phi (Float), Theta (Float)
- **Outputs:** Vector (Vector)

## Separate Spherical
- **What it is:** Cartesian → spherical conversion.
- **Used for:** Direction analysis.
- **Inputs:** Vector (Vector)
- **Outputs:** R (Float), Phi (Float), Theta (Float)

---

# 8. STRUCTURAL / ADVANCED NODES

## Repeat Zone
- **What it is:** Executes nodes repeatedly.
- **Used for:** Iterative logic.
- **Inputs:** Iterations (Int), Geometry
- **Outputs:** Geometry

## Closure
- **What it is:** Defines reusable logic blocks.
- **Used for:** Custom procedural behavior.
- **Inputs:** User-defined
- **Outputs:** User-defined

## Evaluate Closure
- **What it is:** Executes a Closure block.
- **Used for:** Injecting logic.
- **Inputs:** Closure, Parameters
- **Outputs:** Closure Outputs

## Combine Bundle
- **What it is:** Packs multiple values.
- **Used for:** Structured data.
- **Inputs:** Multiple (Any)
- **Outputs:** Bundle

## Separate Bundle
- **What it is:** Unpacks a bundle.
- **Used for:** Data extraction.
- **Inputs:** Bundle
- **Outputs:** Multiple (Any)

## Menu Switch
- **What it is:** Selects one input by menu.
- **Used for:** Conditional routing.
- **Inputs:** Menu, Options
- **Outputs:** Output, Booleans

## Script *(Cycles / OSL)*
- **What it is:** Executes OSL shader code.
- **Used for:** Custom shading.
- **Inputs:** Script-defined
- **Outputs:** Script-defined

## Group
- **What it is:** Encapsulates node graphs.
- **Used for:** Reusability and organization.
- **Inputs:** Group Inputs
- **Outputs:** Group Outputs

