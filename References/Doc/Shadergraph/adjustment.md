Source: https://developer.apple.com/documentation/shadergraph/adjustment

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* Adjustment

ShaderGraph Node Group

# Adjustment

Modify or convert values, or ranges of values, from one form to another.

## [Overview](https://developer.apple.com/documentation/shadergraph/adjustment#overview)

Use Adjustment nodes to adjust color values, convert between different color formats, or map input values to a different set of outputs based on rules you specify. For example, you might use these nodes to adapt the output from one node to match the expected input for another node.

### [Nodes](https://developer.apple.com/documentation/shadergraph/adjustment#Nodes)

[`Remap`](https://developer.apple.com/documentation/shadergraph/adjustment/remap)

Linearly remaps incoming values from one range to another.

[`Smooth Step`](https://developer.apple.com/documentation/shadergraph/adjustment/smooth-step)

Outputs a smooth remapping from low-high to 0-1.

[`Luminance`](https://developer.apple.com/documentation/shadergraph/adjustment/luminance)

Outputs a grayscale value containing the luminance of the incoming RGB color in all color channels.

[`RGB to HSV`](https://developer.apple.com/documentation/shadergraph/adjustment/rgb-to-hsv)

Converts a color from RGB to HSV space.

[`HSV to RGB`](https://developer.apple.com/documentation/shadergraph/adjustment/hsv-to-rgb)

Converts a color from HSV to RGB space.

[`Contrast`](https://developer.apple.com/documentation/shadergraph/adjustment/contrast)

Increases or decreases contrast of values using a linear slope multiplier.

[`Range`](https://developer.apple.com/documentation/shadergraph/adjustment/range)

Remaps incoming values from one range to another.

[`HSV Adjust`](https://developer.apple.com/documentation/shadergraph/adjustment/hsv-adjust)

Adjusts the hue, saturation and value of an RGB color by a vector .

[`Saturate`](https://developer.apple.com/documentation/shadergraph/adjustment/saturate)

Adjusts the saturation of a color.

[`Step (RealityKit)`](https://developer.apple.com/documentation/shadergraph/adjustment/step-(realitykit))

Outputs a 1 or a 0 depending on whether the input is greater than or less than the edge value.

### [Node Categories](https://developer.apple.com/documentation/shadergraph/adjustment#Node-Categories)

[`2D-Procedural`](https://developer.apple.com/documentation/shadergraph/2d-procedural)

Generate 2D gradients, noise, and other patterns programmatically for your material.

[`2D-Texture`](https://developer.apple.com/documentation/shadergraph/2d-texture)

Load and configure 2D texture files.

[`3D-Procedural`](https://developer.apple.com/documentation/shadergraph/3d-procedural)

Generate 3D noise patterns programmatically for your material.

[`3D-Texture`](https://developer.apple.com/documentation/shadergraph/3d-texture)

Project multiple 2D images onto a surface to create a 3D texture.

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
