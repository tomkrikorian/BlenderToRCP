Source: https://developer.apple.com/documentation/shadergraph/compositing/dodge

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Compositing](https://developer.apple.com/documentation/shadergraph/compositing)
* Dodge

ShaderGraph Node

# Dodge

A blend operation that lightens the background layer depending on the foreground.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Overview](https://developer.apple.com/documentation/shadergraph/compositing/dodge#overview)

B / (1 - F)

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/compositing/dodge#Parameter-Types)

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
| `Foreground` | Color4 |
| `Background` | Color4 |
| `Mix` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

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

## [Parameter Description](https://developer.apple.com/documentation/shadergraph/compositing/dodge#Parameter-Description)

`Foreground`
:   The foreground input. Represented by `F` in the mathmatical equation.

`Background`
:   The background input. Represented by `B` in the mathmatical equation.

`Mix`
:   The weight of the blend operation. The higher the `Mix`, the greater the intensity of the blend operation, and the more the effect is visually apparent. The default value is `1`. Values outside of the range `0-1` produce an undefined effect outside of the node’s intended function.

## [Discussion](https://developer.apple.com/documentation/shadergraph/compositing/dodge#Discussion)

The Dodge node lightens each area in the background based on the lightness of the corresponding area in the foreground, represented by the equation `B / (1 - F)`. Below is an example of a simple node graph that uses the the dodge node to lighten a brick texture:

![](https://docs-assets.developer.apple.com/published/4aa9b8b032d8716a4316e8c991c36f25/DodgeGraph.png)

Use a [`Noise 2D`](https://developer.apple.com/documentation/shadergraph/2d-procedural/noise-2d) node to generate Perlin noise, and use the output of that texture as the foreground in the dodge node. This process causes the background brick texture to lighten according to the procedural pattern. Below, the resulting texture applies to a cube:

![](https://docs-assets.developer.apple.com/published/3f99d156c5fbb66084cdaecc9ea0b4ec/DodgeMaterial.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/compositing/dodge#Nodes)

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

[`Screen`](https://developer.apple.com/documentation/shadergraph/compositing/screen)

A blend operation that lightens areas that are darker than white.

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
