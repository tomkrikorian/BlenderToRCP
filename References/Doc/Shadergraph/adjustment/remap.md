Source: https://developer.apple.com/documentation/shadergraph/adjustment/remap

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Adjustment](https://developer.apple.com/documentation/shadergraph/adjustment)
* Remap

ShaderGraph Node

# Remap

Linearly remaps incoming values from one range to another.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/adjustment/remap#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Float |
| `In Low` | Float |
| `In High` | Float |
| `Out Low` | Float |
| `Out High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `In` | Color4 |
| `In Low` | Color4 |
| `In High` | Color4 |
| `Out Low` | Color4 |
| `Out High` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Vector3h |
| `In Low` | Vector3h |
| `In High` | Vector3h |
| `Out Low` | Vector3h |
| `Out High` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `In Low` | Vector3f |
| `In High` | Vector3f |
| `Out Low` | Vector3f |
| `Out High` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Half |
| `In Low` | Half |
| `In High` | Half |
| `Out Low` | Half |
| `Out High` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `In` | Vector2f |
| `In Low` | Float |
| `In High` | Float |
| `Out Low` | Float |
| `Out High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Vector4h |
| `In Low` | Float |
| `In High` | Float |
| `Out Low` | Float |
| `Out High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `In` | Vector4f |
| `In Low` | Float |
| `In High` | Float |
| `Out Low` | Float |
| `Out High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Vector2f |
| `In Low` | Vector2f |
| `In High` | Vector2f |
| `Out Low` | Vector2f |
| `Out High` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Vector2h |
| `In Low` | Vector2h |
| `In High` | Vector2h |
| `Out Low` | Vector2h |
| `Out High` | Vector2h |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `In` | Vector3h |
| `In Low` | Float |
| `In High` | Float |
| `Out Low` | Float |
| `Out High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `In Low` | Float |
| `In High` | Float |
| `Out Low` | Float |
| `Out High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Vector4f |
| `In Low` | Vector4f |
| `In High` | Vector4f |
| `Out Low` | Vector4f |
| `Out High` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Vector2h |
| `In Low` | Float |
| `In High` | Float |
| `Out Low` | Float |
| `Out High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `In` | Color3 |
| `In Low` | Float |
| `In High` | Float |
| `Out Low` | Float |
| `Out High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Color3 |
| `In Low` | Color3 |
| `In High` | Color3 |
| `Out Low` | Color3 |
| `Out High` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Vector4h |
| `In Low` | Vector4h |
| `In High` | Vector4h |
| `Out Low` | Vector4h |
| `Out High` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `In` | Color4 |
| `In Low` | Float |
| `In High` | Float |
| `Out Low` | Float |
| `Out High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/adjustment/remap#Parameter-descriptions)

`In`
:   The input value to remap.

`In Low`
:   The low end value of the input range; the default is `0.0`.

`In High`
:   The high end value of the input range; the default is `1.0`.

`Out Low`
:   The low end value of the output range; the default is `0.0`.

`Out High`
:   The high end value of the output range. The default value is `1.0`.

### [Nodes](https://developer.apple.com/documentation/shadergraph/adjustment/remap#Nodes)

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
