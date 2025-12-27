Source: https://developer.apple.com/documentation/shadergraph

Framework

# ShaderGraph

Create custom materials and effects for 3D content in Reality Composer Pro.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 15.0+tvOS 26.0+visionOS 1.0+

## [Overview](https://developer.apple.com/documentation/shadergraph#Overview)

Create complex materials and effects with Shader Graph, a node-based material editor within Reality Composer Pro. The editor presents an interface in which you can build out node graphs to achieve various visual effects.

With the control Shader Graph provides over materials, you can create effects that might otherwise require writing Metal shaders. The nodes represent either a value or operation, and have inputs and outputs you can connect to build a material. They serve the same purpose as a variable, constant, or function in Metal. Multiple versions of a node tweak the inputs and outputs it can receive, similar to overloads of a function.

![](https://docs-assets.developer.apple.com/published/9d613c8625c7195c13461b29b95ef35a/HomePageMaterial1.png)

Build your material using the nodes that achieve your desired visual and geometric effects, and apply these materials to entities within your Reality Composer Pro scene.

## [Interoperability](https://developer.apple.com/documentation/shadergraph#Interoperability)

Shader Graph uses MaterialX 1.38 conventions to improve interoperability with content creation applications that can read and author MaterialX within USD files.

Shader Graph also includes several nodes that are unique to RealityKit. Some of these nodes are available as standard MaterialX definitions that you can use within your content creation workflow. To download these definitions, see [MaterialX definitions](https://developer.apple.com/augmented-reality/realitykit/files/MaterialX-definitions.zip).

### [Node Categories](https://developer.apple.com/documentation/shadergraph#Node-Categories)

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

[`Procedural`](https://developer.apple.com/documentation/shadergraph/procedural)

Add a constant number, vector, matrix, color, string, or other value to your graph.

[`RealityKit`](https://developer.apple.com/documentation/shadergraph/realitykit)

Add RealityKit surfaces or textures to your material and access and manipulate scene geometry.

[`Surface`](https://developer.apple.com/documentation/shadergraph/surface)

Generate a MaterialX preview surface.
