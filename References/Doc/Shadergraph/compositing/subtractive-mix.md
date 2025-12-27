Source: https://developer.apple.com/documentation/shadergraph/compositing/subtractive-mix

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Compositing](https://developer.apple.com/documentation/shadergraph/compositing)
* Subtractive Mix

ShaderGraph Node

# Subtractive Mix

Subtracts foreground from background values.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Overview](https://developer.apple.com/documentation/shadergraph/compositing/subtractive-mix#overview)

B - F

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/compositing/subtractive-mix#Parameter-Types)

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
| `Foreground` | Color3 |
| `Background` | Color3 |
| `Mix` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Foreground` | Half |
| `Background` | Half |
| `Mix` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/compositing/subtractive-mix#Parameter-descriptions)

`Foreground`
:   The foreground input, represented by `F` in the mathematical equation.

`Background`
:   The background input, represented by `B` in the mathematical equation.

`Mix`
:   The weight of the blend effect. The higher the `Mix`, the greater the intensity of the blend operation, and the more the effect is visually apparent. The default value is `1`. Values outside of the range `0-1` produce an undefined effect outside of the node’s intended function.

## [Discussion](https://developer.apple.com/documentation/shadergraph/compositing/subtractive-mix#Discussion)

The `Subtractive Mix` node subtracts two inputs and uses the `Mix` input to determine the weight of the foreground in the blend, represented by the equation `B - F`. Higher values closer to `1` output a more intense subtractive mix, while lower values closer to `0` dim the effect.

Below is an example of a simple node graph that uses the subtractive mix node to blend two images into a single material:

![](https://docs-assets.developer.apple.com/published/0b2cb1c29296c2d895fde15bce065e41/SubtractiveMixGraph.png)

Below are two images and the resulting blended texture applied to a cube:

![](https://docs-assets.developer.apple.com/published/d9c4946e10d4cea53d216d891a402e72/MixMaterial1.png)

Foreground

![](https://docs-assets.developer.apple.com/published/894072a80859e854d9facc19ef5e6577/BrickTexture.png)

Background

![](https://docs-assets.developer.apple.com/published/fca33a7dff83ead7e54cef9ff64f0775/SubtractiveMixMaterial.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/compositing/subtractive-mix#Nodes)

[`Premultiply`](https://developer.apple.com/documentation/shadergraph/compositing/premultiply)

Multiplies the RGB channels of the input by the alpha channel.

[`Unpremultiply`](https://developer.apple.com/documentation/shadergraph/compositing/unpremultiply)

Divides the RGB channels of the input by the alpha channel.

[`Additive Mix`](https://developer.apple.com/documentation/shadergraph/compositing/additive-mix)

Adds foreground and background values.

[`Difference`](https://developer.apple.com/documentation/shadergraph/compositing/difference)

Outputs the distance between foreground and background values.

[`Burn`](https://developer.apple.com/documentation/shadergraph/compositing/burn)

A blend operation that darkens the foreground layer using the background.

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
