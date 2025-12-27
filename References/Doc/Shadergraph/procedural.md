Source: https://developer.apple.com/documentation/shadergraph/procedural

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* Procedural

ShaderGraph Node Group

# Procedural

Add a constant number, vector, matrix, color, string, or other value to your graph.

## [Overview](https://developer.apple.com/documentation/shadergraph/procedural#overview)

Use Procedural nodes to manage constant values within your graph. Configure a Procedural node with a constant value in the Reality Composer Pro inspector, and use it as an input to other nodes. You can also use the input side of the node to store values from other parts of your graph.

### [Nodes](https://developer.apple.com/documentation/shadergraph/procedural#Nodes)

[`Float`](https://developer.apple.com/documentation/shadergraph/procedural/float)

A constant floating-point numeric value.

[`Color3 (Float)`](https://developer.apple.com/documentation/shadergraph/procedural/color3-(float))

A constant Color3 (Float) value.

[`Color4 (Float)`](https://developer.apple.com/documentation/shadergraph/procedural/color4-(float))

A constant Color4 (Float) value.

[`Vector2 (Float)`](https://developer.apple.com/documentation/shadergraph/procedural/vector2-(float))

A constant Vector2 (Float) value.

[`Vector3 (Float)`](https://developer.apple.com/documentation/shadergraph/procedural/vector3-(float))

A constant Vector3 (Float) value.

[`Vector4 (Float)`](https://developer.apple.com/documentation/shadergraph/procedural/vector4-(float))

A constant Vector4 (Float) value.

[`Boolean`](https://developer.apple.com/documentation/shadergraph/procedural/boolean)

A constant boolean (true/false) value.

[`Integer`](https://developer.apple.com/documentation/shadergraph/procedural/integer)

A constant integer numeric value.

[`Matrix3x3 (Float)`](https://developer.apple.com/documentation/shadergraph/procedural/matrix3x3-(float))

A constant Matrix3x3 (Float) value.

[`Matrix4x4 (Float)`](https://developer.apple.com/documentation/shadergraph/procedural/matrix4x4-(float))

A constant Matrix4x4 (Float) value.

[`String`](https://developer.apple.com/documentation/shadergraph/procedural/string)

A constant string (text) value.

[`Image File`](https://developer.apple.com/documentation/shadergraph/procedural/image-file)

A constant path refering to an arbitrary image file on disk.

[`Half`](https://developer.apple.com/documentation/shadergraph/procedural/half)

A constant half-precision floating-point numeric value.

[`Vector2 (Half)`](https://developer.apple.com/documentation/shadergraph/procedural/vector2-(half))

A constant half-precision floating-point Vector2 numeric value.

[`Vector3 (Half)`](https://developer.apple.com/documentation/shadergraph/procedural/vector3-(half))

A constant half-precision floating-point Vector3 numeric value.

[`Vector4 (Half)`](https://developer.apple.com/documentation/shadergraph/procedural/vector4-(half))

A constant half-precision floating-point Vector4 numeric value.

[`Matrix2x2 (Float)`](https://developer.apple.com/documentation/shadergraph/procedural/matrix2x2-(float))

A constant Matrix2x2 (Float) value.

[`Integer2`](https://developer.apple.com/documentation/shadergraph/procedural/integer2)

A constant Integer2 value.

[`Integer3`](https://developer.apple.com/documentation/shadergraph/procedural/integer3)

A constant Integer3 value.

[`Integer4`](https://developer.apple.com/documentation/shadergraph/procedural/integer4)

A constant Integer4 value.

### [Node Categories](https://developer.apple.com/documentation/shadergraph/procedural#Node-Categories)

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

[`RealityKit`](https://developer.apple.com/documentation/shadergraph/realitykit)

Add RealityKit surfaces or textures to your material and access and manipulate scene geometry.

[`Surface`](https://developer.apple.com/documentation/shadergraph/surface)

Generate a MaterialX preview surface.
