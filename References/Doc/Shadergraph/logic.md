Source: https://developer.apple.com/documentation/shadergraph/logic

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* Logic

ShaderGraph Node Group

# Logic

Perform Boolean operations and other logical comparisons on data values.

## [Overview](https://developer.apple.com/documentation/shadergraph/logic#overview)

Use Logic nodes to facilitate decision trees and other logic-based choices within your graph. You can perform comparisons for equality or to determine if one value is larger than another. You can also perform logic operations on Boolean values.

### [Nodes](https://developer.apple.com/documentation/shadergraph/logic#Nodes)

[`If Greater`](https://developer.apple.com/documentation/shadergraph/logic/if-greater)

Outputs True Result or False Result depending on whether value1 > value2.

[`If Greater Or Equal`](https://developer.apple.com/documentation/shadergraph/logic/if-greater-or-equal)

Outputs True Result or False Result depending on whether value1 >= value2.

[`If Equal`](https://developer.apple.com/documentation/shadergraph/logic/if-equal)

Outputs True Result or False Result depending on whether value1 == value2.

[`Switch`](https://developer.apple.com/documentation/shadergraph/logic/switch)

Outputs the value from one of ten input streams, according to a selector .

[`And (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/and-(realitykit))

Boolean operation in1 && in2.

[`Or (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/or-(realitykit))

Boolean operation in1 || in2.

[`XOR (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/xor-(realitykit))

Returns true if only one of the inputs is true.

[`Not (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/not-(realitykit))

Returns !input.

[`Select (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/select-(realitykit))

Selects B if conditional is true, A if false.

[`Multiply Add 24 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-add-24-(realitykit))

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result with 32-bit Z value added.

[`Multiply 24 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-24-(realitykit))

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result.

### [Node Categories](https://developer.apple.com/documentation/shadergraph/logic#Node-Categories)

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
