Source: https://developer.apple.com/documentation/shadergraph/2d-texture

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* 2D-Texture

ShaderGraph Node Group

# 2D-Texture

Load and configure 2D texture files.

## [Overview](https://developer.apple.com/documentation/shadergraph/2d-texture#overview)

Use these nodes to incorporate file-based textures into your material. In addition to loading textures from disk, you can use each node to customize the rendering behavior of the texture.

For example, a Tiled Image node repeats the original image to fill the surface with content. In addition to loading textures, you can use the Transform 2D node to apply an affine transform to a 2D vector.

### [Nodes](https://developer.apple.com/documentation/shadergraph/2d-texture#Nodes)

[`Image`](https://developer.apple.com/documentation/shadergraph/2d-texture/image)

A texture referencing a 2D image file.

[`Tiled Image`](https://developer.apple.com/documentation/shadergraph/2d-texture/tiled-image)

Samples data from an image with provisions for offsetting and tiling in UV space.

[`UV Texture`](https://developer.apple.com/documentation/shadergraph/2d-texture/uv-texture)

A MaterialX version of USD UV Texture reader.

[`Transform 2D`](https://developer.apple.com/documentation/shadergraph/2d-texture/transform-2d)

A node that applies an affine transformation to a 2d input.

### [Node Categories](https://developer.apple.com/documentation/shadergraph/2d-texture#Node-Categories)

[`2D-Procedural`](https://developer.apple.com/documentation/shadergraph/2d-procedural)

Generate 2D gradients, noise, and other patterns programmatically for your material.

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
