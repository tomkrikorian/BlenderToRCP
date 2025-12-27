Source: https://developer.apple.com/documentation/shadergraph/adjustment/step-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Adjustment](https://developer.apple.com/documentation/shadergraph/adjustment)
* Step (RealityKit)

ShaderGraph Node

# Step (RealityKit)

Outputs a 1 or a 0 depending on whether the input is greater than or less than the edge value.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Overview](https://developer.apple.com/documentation/shadergraph/adjustment/step-(realitykit)#overview)

0 if X < Edge, otherwise it returns 1.0

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/adjustment/step-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Float |
| `Edge` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `In` | Vector3h |
| `Edge` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `In` | Half |
| `Edge` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `In` | Vector4h |
| `Edge` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `In` | Vector2f |
| `Edge` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Color4 |
| `Edge` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Edge` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Color3 |
| `Edge` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Vector4f |
| `Edge` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Vector2h |
| `Edge` | Vector2h |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/adjustment/step-(realitykit)#Parameter-descriptions)

`In`
:   The input value.

`Edge`
:   The deciding value to which to compare the input.

## [Discussion](https://developer.apple.com/documentation/shadergraph/adjustment/step-(realitykit)#Discussion)

The Step node takes the `In` value and compares it to the `Edge` parameter. If the value is less than `Edge`, the node returns `0`. Otherwise, it returns `1`.

### [Nodes](https://developer.apple.com/documentation/shadergraph/adjustment/step-(realitykit)#Nodes)

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
