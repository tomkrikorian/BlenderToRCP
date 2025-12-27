Source: https://developer.apple.com/documentation/shadergraph/2d-procedural/split-vertical

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [2D-Procedural](https://developer.apple.com/documentation/shadergraph/2d-procedural)
* Split Vertical

ShaderGraph Node

# Split Vertical

A top-to-bottom split matte, split at a specified V value.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/2d-procedural/split-vertical#Parameter-Types)

| Input | Type |
| --- | --- |
| `Top` | Float |
| `Bottom` | Float |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Top` | Vector4h |
| `Bottom` | Vector4h |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `Top` | Vector4f |
| `Bottom` | Vector4f |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `Top` | Half |
| `Bottom` | Half |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `Top` | Vector2h |
| `Bottom` | Vector2h |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `Top` | Color4 |
| `Bottom` | Color4 |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `Top` | Vector2f |
| `Bottom` | Vector2f |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `Top` | Vector3h |
| `Bottom` | Vector3h |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `Top` | Color3 |
| `Bottom` | Color3 |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Top` | Vector3f |
| `Bottom` | Vector3f |
| `Center` | Float |
| `Texture Coordinates` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

## [Parameter description](https://developer.apple.com/documentation/shadergraph/2d-procedural/split-vertical#Parameter-description)

`Top`
:   The value of the left side of the split.

`Bottom`
:   The value of the right side of the split.

`Center`
:   The *V* value at which the output is split. Everything above this value will be equal to the `Top` input; everything below this value will be equal to the `Bottom` input. This parameter ranges between `0` and `1`.

`Texture Coordinates`
:   The 2D coordinate at which the data is read in order to map the texture onto a surface. The default uses the current *UV* coordinates, in which *U* is the horizontal axis and *V* is the vertical axis.

## [Discussion](https://developer.apple.com/documentation/shadergraph/2d-procedural/split-vertical#Discussion)

This node creates two distinct regions along the vertical axis. The value of the `Center` input determines the regions. A value of `0` establishes the center at the top-most, position causing the output to always be equal to the `Top` input. A value of `1` establishes the center at the bottom-most position. Below is a an example of a simple node graph that uses `Split Vertical` to create a split color:

![](https://docs-assets.developer.apple.com/published/4c238efca001e7e1d912c0d1b322cfd9/SplitVerticalGraph.png)

By editing the center value, you change the texture to show a larger top or bottom region. The image below shows the resulting textures:

![](https://docs-assets.developer.apple.com/published/e93fc156dba3409fa1a0c50ceaeda4f9/SplitVerticalMaterial1.png)

![](https://docs-assets.developer.apple.com/published/eb2b01bf5242b137759ce179b7770b48/SplitVerticalMaterial2.png)

![](https://docs-assets.developer.apple.com/published/85cd9f6ac19824561fa752a94d234455/SplitVerticalMaterial3.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/2d-procedural/split-vertical#Nodes)

[`Ramp Horizontal`](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-horizontal)

A left-to-right linear value ramp (gradient) generator.

[`Ramp Vertical`](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-vertical)

A top-to-bottom linear value ramp (gradient) generator.

[`Ramp 4 Corners`](https://developer.apple.com/documentation/shadergraph/2d-procedural/ramp-4-corners)

A four-point linear value ramp (gradient) generator.

[`Split Horizontal`](https://developer.apple.com/documentation/shadergraph/2d-procedural/split-horizontal)

A left-to-right split matte, split at a specified U value.

[`Noise 2D`](https://developer.apple.com/documentation/shadergraph/2d-procedural/noise-2d)

A 2D Perlin noise generator.

[`Cellular Noise 2D`](https://developer.apple.com/documentation/shadergraph/2d-procedural/cellular-noise-2d)

A 2D cellular noise generator.

[`Worley Noise 2D`](https://developer.apple.com/documentation/shadergraph/2d-procedural/worley-noise-2d)

A 2D Worley noise generator.
