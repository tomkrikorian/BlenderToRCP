Source: https://developer.apple.com/documentation/shadergraph/2d-procedural

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* 2D-Procedural

ShaderGraph Node Group

# 2D-Procedural

Generate 2D gradients, noise, and other patterns programmatically for your material.

## [Overview](https://developer.apple.com/documentation/shadergraph/2d-procedural#overview)

Use these nodes to generate gradients, noise, and other types of patterns and apply them to textures or other 2D surfaces. For example, you might use a horizontal or vertical ramp node to create a color gradient on a surface.

### [Nodes](https://developer.apple.com/documentation/shadergraph/2d-procedural#Nodes)

[`Ramp Horizontal`](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-horizontal)

A left-to-right linear value ramp (gradient) generator.

[`Ramp Vertical`](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-vertical)

A top-to-bottom linear value ramp (gradient) generator.

[`Ramp 4 Corners`](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-4-corners)

A four-point linear value ramp (gradient) generator.

[`Split Horizontal`](https://developer.apple.com/documentation/shadergraph/2d-procedural/split-horizontal)

A left-to-right split matte, split at a specified U value.

[`Split Vertical`](https://developer.apple.com/documentation/shadergraph/2d-procedural/split-vertical)

A top-to-bottom split matte, split at a specified V value.

[`Noise 2D`](https://developer.apple.com/documentation/shadergraph/2d-procedural/noise-2d)

A 2D Perlin noise generator.

[`Cellular Noise 2D`](https://developer.apple.com/documentation/shadergraph/2d-procedural/cellular-noise-2d)

A 2D cellular noise generator.

[`Worley Noise 2D`](https://developer.apple.com/documentation/shadergraph/2d-procedural/worley-noise-2d)

A 2D Worley noise generator.

### [Node Categories](https://developer.apple.com/documentation/shadergraph/2d-procedural#Node-Categories)

[`2D-Texture`](https://developer.apple.com/documentation/shadergraph/2d-texture)

Load and configure 2D texture files.

[`3D-Procedural`](https://developer.apple.com/documentation/shadergraph/3d-procedural)

Generate 3D noise patterns programmatically for your material.

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
