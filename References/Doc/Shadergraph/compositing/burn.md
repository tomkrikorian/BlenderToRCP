Source: https://developer.apple.com/documentation/shadergraph/compositing/burn

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Compositing](https://developer.apple.com/documentation/shadergraph/compositing)
* Burn

ShaderGraph Node

# Burn

A blend operation that darkens the foreground layer using the background.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Overview](https://developer.apple.com/documentation/shadergraph/compositing/burn#overview)

1 - (1 - B) / F

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/compositing/burn#Parameter-Types)

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

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/compositing/burn#Parameter-descriptions)

`Foreground`
:   The foreground input. Represented by `F` in the mathmatical equation.

`Background`
:   The background input. Represented by `B` in the mathmatical equation.

`Mix`
:   The weight of the blend effect. The higher the `Mix`, the greater the intensity of the blend operation, and the more the effect is visually apparent. The default value is `1`. Values outside of the range `0-1` produce an undefined effect outside of the node’s intended function.

## [Discussion](https://developer.apple.com/documentation/shadergraph/compositing/burn#Discussion)

The `Burn` node darkens each area in the background based on the darkness of the corresponding area in the foreground, represented by the equation `1 - (1 - B) / F`. Below is an example of a node graph that uses the `Burn` node to darken a brick texture:

![](https://docs-assets.developer.apple.com/published/47249df37324d4d19ad18877480395f9/BurnGraph.png)

Use a [`Noise 2D`](https://developer.apple.com/documentation/shadergraph/2d-procedural/noise-2d) node to generate Perlin noise, and use the output of that texture as the foreground in the `Burn` node. This process darkens the background brick texture according to the procedural pattern. Below, the resulting texture applies to a cube:

![](https://docs-assets.developer.apple.com/published/566f3dfbd55a92bb27315df1e62c5540/BurnMaterial.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/compositing/burn#Nodes)

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

[`Dodge`](https://developer.apple.com/documentation/shadergraph/compositing/dodge)

A blend operation that lightens the background layer depending on the foreground.

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
