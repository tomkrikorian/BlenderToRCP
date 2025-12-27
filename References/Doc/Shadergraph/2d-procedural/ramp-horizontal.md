Source: https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-horizontal

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [2D-Procedural](https://developer.apple.com/documentation/shadergraph/2d-procedural)
* Ramp Horizontal

ShaderGraph Node

# Ramp Horizontal

A left-to-right linear value ramp (gradient) generator.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-horizontal#Parameter-Types)

| Input | Type |
| --- | --- |
| `Left` | Float |
| `Right` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Left` | Vector4f |
| `Right` | Vector4f |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `Left` | Vector2h |
| `Right` | Vector2h |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `Left` | Vector4h |
| `Right` | Vector4h |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `Left` | Vector3f |
| `Right` | Vector3f |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `Left` | Vector2f |
| `Right` | Vector2f |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `Left` | Color4 |
| `Right` | Color4 |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `Left` | Color3 |
| `Right` | Color3 |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Left` | Half |
| `Right` | Half |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `Left` | Vector3h |
| `Right` | Vector3h |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-horizontal#Parameter-descriptions)

`Left`
:   The left value of the interpolation.

`Right`
:   The right value of the interpolation.

`Texture Coordinates`
:   The 2D coordinate at which the data is read in order to map the texture onto a surface. The default is to use the current UV coordinates, in which U is the horizontal axis and V is the vertical axis.

## [Discussion](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-horizontal#Discussion)

This node uses interpolation to create a horizontal ramp or gradient from two values. Any point within the output ramp is a mix of the two values. A given point is more similar to the value that its horizontal position is closer to. Below is a an example of a simple node graph that uses `Ramp Horizontal` to create a color gradient:

![](https://docs-assets.developer.apple.com/published/262f1f12dc34a4ffc9d1065f449f1c8c/RampHorizontalGraph.png)

The image below shows the resulting texture, along with the color values on either side:

![](https://docs-assets.developer.apple.com/published/be3386c09c6ce3c9d3076223b98fea13/RampHorizontalMaterial.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-horizontal#Nodes)

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
