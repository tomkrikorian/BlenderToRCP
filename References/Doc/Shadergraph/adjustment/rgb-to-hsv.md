Source: https://developer.apple.com/documentation/shadergraph/adjustment/rgb-to-hsv

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Adjustment](https://developer.apple.com/documentation/shadergraph/adjustment)
* RGB to HSV

ShaderGraph Node

# RGB to HSV

Converts a color from RGB to HSV space.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/adjustment/rgb-to-hsv#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

### [Nodes](https://developer.apple.com/documentation/shadergraph/adjustment/rgb-to-hsv#Nodes)

[`Remap`](https://developer.apple.com/documentation/shadergraph/adjustment/remap)

Linearly remaps incoming values from one range to another.

[`Smooth Step`](https://developer.apple.com/documentation/shadergraph/adjustment/smooth-step)

Outputs a smooth remapping from low-high to 0-1.

[`Luminance`](https://developer.apple.com/documentation/shadergraph/adjustment/luminance)

Outputs a grayscale value containing the luminance of the incoming RGB color in all color channels.

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
