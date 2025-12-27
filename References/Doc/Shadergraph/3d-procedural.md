Source: https://developer.apple.com/documentation/shadergraph/3d-procedural

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* 3D-Procedural

ShaderGraph Node Group

# 3D-Procedural

Generate 3D noise patterns programmatically for your material.

## [Overview](https://developer.apple.com/documentation/shadergraph/3d-procedural#overview)

3D Procedural nodes generate noise patterns that don’t repeat along the z-axis of your model. Use the nodes to add random variations to parts of your material, such as its surface roughness. Each node produces a different type of noise pattern based on a specific algorithm.

### [Nodes](https://developer.apple.com/documentation/shadergraph/3d-procedural#Nodes)

[`Noise 3D`](https://developer.apple.com/documentation/shadergraph/3d-procedural/noise-3d)

A 3D Perlin noise generator.

[`Fractal Noise 3D`](https://developer.apple.com/documentation/shadergraph/3d-procedural/fractal-noise-3d)

Zero-centered 3D fractal noise created by summing several octaves of 3D Perlin noise.

[`Cellular Noise 3D`](https://developer.apple.com/documentation/shadergraph/3d-procedural/cellular-noise-3d)

A 3D cellular noise generator.

[`Worley Noise 3D`](https://developer.apple.com/documentation/shadergraph/3d-procedural/worley-noise-3d)

A 3D Worley noise generator.

### [Node Categories](https://developer.apple.com/documentation/shadergraph/3d-procedural#Node-Categories)

[`2D-Procedural`](https://developer.apple.com/documentation/shadergraph/2d-procedural)

Generate 2D gradients, noise, and other patterns programmatically for your material.

[`2D-Texture`](https://developer.apple.com/documentation/shadergraph/2d-texture)

Load and configure 2D texture files.

[`3D-Texture`](https://developer.apple.com/documentation/shadergraph/3d-texture)

Project multiple 2D images onto a surface to create a 3D texture.

[`Adjustment`](https://developer.apple.com/documentation/shadergraph/adjustment)

Modify or convert values, or ranges of values, from one form to another.

[`Application`](https://developer.apple.com/documentation/shadergraph/application)

Get system values such as the current time or the direction of the up vector.

[`Compositing`](https://developer.apple.com/documentation/shadergraph/compositing)

Generate a single output from the combination of multiple data values.

[`Data`](https://developer.apple.com/documentation/shadergraph/data)

Convert data values to different formats, or manipulate individual elements within a data structure.

[`Geometric`](https://developer.apple.com/documentation/shadergraph/geometric)

Access scene geometry while your graph runs.

[`Logic`](https://developer.apple.com/documentation/shadergraph/logic)

Perform Boolean operations and other logical comparisons on data values.

[`Material`](https://developer.apple.com/documentation/shadergraph/material)

Encapsulate a set of shader graph nodes into a single module.

[`Math`](https://developer.apple.com/documentation/shadergraph/math)

Perform a wide variety of mathematical and transformative operations on data values.

[`Organization`](https://developer.apple.com/documentation/shadergraph/organization)

Modify the visual flow of data within your graph without changing any values.

[`Procedural`](https://developer.apple.com/documentation/shadergraph/procedural)

Add a constant number, vector, matrix, color, string, or other value to your graph.

[`RealityKit`](https://developer.apple.com/documentation/shadergraph/realitykit)

Add RealityKit surfaces or textures to your material and access and manipulate scene geometry.

[`Surface`](https://developer.apple.com/documentation/shadergraph/surface)

Generate a MaterialX preview surface.
