Source: https://developer.apple.com/documentation/shadergraph/adjustment/contrast

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Adjustment](https://developer.apple.com/documentation/shadergraph/adjustment)
* Contrast

ShaderGraph Node

# Contrast

Increases or decreases contrast of values using a linear slope multiplier.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/adjustment/contrast#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Float |
| `Amount` | Float |
| `Pivot` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Amount` | Float |
| `Pivot` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Vector2f |
| `Amount` | Vector2f |
| `Pivot` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Color4 |
| `Amount` | Color4 |
| `Pivot` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Vector4f |
| `Amount` | Vector4f |
| `Pivot` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Vector3h |
| `Amount` | Half |
| `Pivot` | Half |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `In` | Color4 |
| `Amount` | Float |
| `Pivot` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Half |
| `Amount` | Half |
| `Pivot` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `In` | Vector3h |
| `Amount` | Vector3h |
| `Pivot` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `In` | Vector2f |
| `Amount` | Float |
| `Pivot` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Vector4h |
| `Amount` | Half |
| `Pivot` | Half |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Amount` | Vector3f |
| `Pivot` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Vector2h |
| `Amount` | Vector2h |
| `Pivot` | Vector2h |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `In` | Vector4h |
| `Amount` | Vector4h |
| `Pivot` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `In` | Color3 |
| `Amount` | Float |
| `Pivot` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Vector2h |
| `Amount` | Half |
| `Pivot` | Half |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `In` | Vector4f |
| `Amount` | Float |
| `Pivot` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Color3 |
| `Amount` | Color3 |
| `Pivot` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/adjustment/contrast#Parameter-descriptions)

`In`
:   The input value to modify.

`Amount`
:   The linear slope multiplier that increases or decreases the contrast. A value between `0.0` and `1.0` decreases the contrast of the `In` parameter, while a value greater than `1.0` increases it.

`Pivot`
:   The center value of the contrast adjustment. As contrast increases, values of the `In` parameter get further away from this value. As contrast decreases, values of the `In` parameter get closer to this value.

## [Discussion](https://developer.apple.com/documentation/shadergraph/adjustment/contrast#Discussion)

Below is an example of a node graph that uses the `Contrast` node to make a black and white arrow texture more gray and closer in color.

![](https://docs-assets.developer.apple.com/published/b875b7e718e1101dcab31f42da00ba66/ContrastGraph.png)

Below, the resulting texture applies to a cube:

![](https://docs-assets.developer.apple.com/published/b5031fa1f42bfc35c8ab51be05d66b6d/ContrastMaterial.png)

In the image above, the value of `Pivot` is `0.2`, which represents a dark gray. Because the value of `Amount` is also `0.2`, the contrast of the input decreases while the color value of the texture moves closer to the `Pivot` input. As a result, the output texture of the node becomes a gray version of the original black and white arrow texture.

### [Nodes](https://developer.apple.com/documentation/shadergraph/adjustment/contrast#Nodes)

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

[`Range`](https://developer.apple.com/documentation/shadergraph/adjustment/range)

Remaps incoming values from one range to another.

[`HSV Adjust`](https://developer.apple.com/documentation/shadergraph/adjustment/hsv-adjust)

Adjusts the hue, saturation and value of an RGB color by a vector .

[`Saturate`](https://developer.apple.com/documentation/shadergraph/adjustment/saturate)

Adjusts the saturation of a color.

[`Step (RealityKit)`](https://developer.apple.com/documentation/shadergraph/adjustment/step-(realitykit))

Outputs a 1 or a 0 depending on whether the input is greater than or less than the edge value.
