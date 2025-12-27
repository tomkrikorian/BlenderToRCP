Source: https://developer.apple.com/documentation/shadergraph/material

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* Material

ShaderGraph Node Group

# Material

Encapsulate a set of shader graph nodes into a single module.

## [Overview](https://developer.apple.com/documentation/shadergraph/material#overview)

`Material` nodes help you divide your graph into subsets of nodes, each with distinct inputs and outputs. A [`Node Graph`](https://developer.apple.com/documentation/shadergraph/material/node-graph) appears as a single node within your main graph. Editing that node hides the main graph and gives you an empty space that you fill with additional nodes. Use that space to build a specific portion of your main graph, and use the [`Node Graph`](https://developer.apple.com/documentation/shadergraph/material/node-graph) to define the inputs and outputs to that separate space.

### [Nodes](https://developer.apple.com/documentation/shadergraph/material#Nodes)

[`Node Graph`](https://developer.apple.com/documentation/shadergraph/material/node-graph)

A node that can contain shading nodes and other node graphs.

### [Node Categories](https://developer.apple.com/documentation/shadergraph/material#Node-Categories)

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
