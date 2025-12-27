Source: https://developer.apple.com/documentation/shadergraph/geometric

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* Geometric

ShaderGraph Node Group

# Geometric

Access scene geometry while your graph runs.

## [Overview](https://developer.apple.com/documentation/shadergraph/geometric#overview)

When the GPU applies your graph to a scene, geometric nodes reflect the data value the system is currently processing. Use these nodes to get details about that data value, such as its coordinates, normal, or tangent information. Alternatively, use the Reflect and Refract nodes to modify vectors relative to the current data value.

### [Nodes](https://developer.apple.com/documentation/shadergraph/geometric#Nodes)

[`Position`](https://developer.apple.com/documentation/shadergraph/geometric/position)

The coordinates of the currently-processed data in a given coordinate space.

[`Normal`](https://developer.apple.com/documentation/shadergraph/geometric/normal)

The geometric normal of the currently-processed data in a given coordinate space.

[`Tangent`](https://developer.apple.com/documentation/shadergraph/geometric/tangent)

The geometric tangent of the currently-processed data in a given coordinate space.

[`Bitangent`](https://developer.apple.com/documentation/shadergraph/geometric/bitangent)

The geometric bitangent vector of the currently-processed data in a given coordinate space.

[`Texture Coordinates`](https://developer.apple.com/documentation/shadergraph/geometric/texture-coordinates)

The 2D or 3D texture coordinates of the currently-processed data.

[`Geometry Color`](https://developer.apple.com/documentation/shadergraph/geometric/geometry-color)

The color associated with the geometry at the currently-processed geometric position, typically defined by vertex color.

[`Geometric Property`](https://developer.apple.com/documentation/shadergraph/geometric/geometric-property)

The value of the specified geometric property (defined using ) of the currently-bound geometry.

[`Reflect (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit))

Reflects a vector about another vector.

[`Refract (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit))

Refracts a vector using a given normal and index of refraction (eta).

### [Node Categories](https://developer.apple.com/documentation/shadergraph/geometric#Node-Categories)

[`2D-Procedural`](https://developer.apple.com/documentation/shadergraph/2d-procedural)

Generate 2D gradients, noise, and other patterns programmatically for your material.

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
