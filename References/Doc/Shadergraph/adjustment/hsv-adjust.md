Source: https://developer.apple.com/documentation/shadergraph/adjustment/hsv-adjust

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Adjustment](https://developer.apple.com/documentation/shadergraph/adjustment)
* HSV Adjust

ShaderGraph Node

# HSV Adjust

Adjusts the hue, saturation and value of an RGB color by a vector .

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/adjustment/hsv-adjust#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Color3 |
| `Amount` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Color4 |
| `Amount` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/adjustment/hsv-adjust#Parameter-descriptions)

`In`
:   The input color the node adjusts.

`Amount`
:   The adjustment of the HSV. The default value is `(0,1,1)`, which causes no change.

## [Discussion](https://developer.apple.com/documentation/shadergraph/adjustment/hsv-adjust#Discussion)

The HSV Adjust node adjusts the hue, saturation, and value of the color passed to the `In` parameter. The node performs this adjustment by adding the first value of the `Amount` vector to the hue, multiplying the saturation by the second value of the `Amount` vector, and multiplying that value by the third value of the `Amount` vector. When adjusting the hue, a positive value rotates the hue in the direction of red to green to blue. A value of 1 represents an entire rotation, and results in no change.

Note

This node never changes the alpha of a `color4`.

### [Nodes](https://developer.apple.com/documentation/shadergraph/adjustment/hsv-adjust#Nodes)

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

[`Saturate`](https://developer.apple.com/documentation/shadergraph/adjustment/saturate)

Adjusts the saturation of a color.

[`Step (RealityKit)`](https://developer.apple.com/documentation/shadergraph/adjustment/step-(realitykit))

Outputs a 1 or a 0 depending on whether the input is greater than or less than the edge value.
