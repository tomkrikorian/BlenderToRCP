Source: https://developer.apple.com/documentation/shadergraph/compositing/screen

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Compositing](https://developer.apple.com/documentation/shadergraph/compositing)
* Screen

ShaderGraph Node

# Screen

A blend operation that lightens areas that are darker than white.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Overview](https://developer.apple.com/documentation/shadergraph/compositing/screen#overview)

1 - (1 - F)(1 - B)

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/compositing/screen#Parameter-Types)

| Input | Type |
| --- | --- |
| `Foreground` | Float |
| `Background` | Float |
| `Mix` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Foreground` | Half |
| `Background` | Half |
| `Mix` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `Foreground` | Color3 |
| `Background` | Color3 |
| `Mix` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Foreground` | Color4 |
| `Background` | Color4 |
| `Mix` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/compositing/screen#Parameter-descriptions)

`Foreground`
:   The foreground input, represented by `F` in the mathematical equation.

`Background`
:   The background input, represented by `B` in the mathematical equation.

`Mix`
:   The weight of the blend operation. The higher the value of `Mix`, the more apparent the effect of the blend operation. The default value is `1`. Values outside of the range `0-1` produce an undefined effect outside of the node’s intended function.

## [Discussion](https://developer.apple.com/documentation/shadergraph/compositing/screen#Discussion)

The `Screen` node inverts the color values of both the foreground and background and multiplies those values together. Then the node inverts the colors again, as represented by the equation: `1 - (1 - F)(1 - B)`. The resulting visual effect is always equally bright or brighter than the original textures. Below is an example of a simple node graph that uses the `Screen` node to blend two images together into a single material:

![](https://docs-assets.developer.apple.com/published/28a0a55b18ecac5972bd5ed2e21eebeb/ScreenGraph.png)

Below are two images and their resulting blended texture applied to a cube:

![](https://docs-assets.developer.apple.com/published/7aee9efa7c8a8a4e7b0e64887d4b54f2/ScreenMaterial2.png)

Foreground

![](https://docs-assets.developer.apple.com/published/8a7108508e5cad0fbc50f6d6bdc4a006/ScreenMaterial1.png)

Background

![](https://docs-assets.developer.apple.com/published/5a84eb39e40779bc1d9fb68d07252bf4/ScreenMaterial3.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/compositing/screen#Nodes)

[`Premultiply`](https://developer.apple.com/documentation/shadergraph/compositing/premultiply)

Multiplies the RGB channels of the input by the alpha channel.

[`Unpremultiply`](https://developer.apple.com/documentation/shadergraph/compositing/unpremultiply)

Divides the RGB channels of the input by the alpha channel.

[`Additive Mix`](https://developer.apple.com/documentation/shadergraph/compositing/additive-mix)

Adds foreground and background values.

[`Subtractive Mix`](https://developer.apple.com/documentation/shadergraph/compositing/subtractive-mix)

Subtracts foreground from background values.

[`Difference`](https://developer.apple.com/documentation/shadergraph/compositing/difference)

Outputs the distance between foreground and background values.

[`Burn`](https://developer.apple.com/documentation/shadergraph/compositing/burn)

A blend operation that darkens the foreground layer using the background.

[`Dodge`](https://developer.apple.com/documentation/shadergraph/compositing/dodge)

A blend operation that lightens the background layer depending on the foreground.

[`Overlay`](https://developer.apple.com/documentation/shadergraph/compositing/overlay)

A blend operation that multiplies dark areas and screens light areas.

[`Disjoint Over`](https://developer.apple.com/documentation/shadergraph/compositing/disjoint-over)

A merge operation that layers foreground over background color, but assumes no overlap in partially transparent areas covered by both.

[`In`](https://developer.apple.com/documentation/shadergraph/compositing/in)

Outputs areas of foreground that overlap with the alpha of background.

[`Mask`](https://developer.apple.com/documentation/shadergraph/compositing/mask)

Outputs areas of background that overlap with the alpha of foreground.

[`Matte`](https://developer.apple.com/documentation/shadergraph/compositing/matte)

A merge operation that layers premultiplied foreground over background.

[`Out`](https://developer.apple.com/documentation/shadergraph/compositing/out)

Outputs areas of foreground that do not overlap with background.

[`Over`](https://developer.apple.com/documentation/shadergraph/compositing/over)

A merge operation that layers foreground over background, using the alpha of the foreground.

[`Inside`](https://developer.apple.com/documentation/shadergraph/compositing/inside)

Multiplies a mask to all channels of the input.
