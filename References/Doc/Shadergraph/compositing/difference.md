Source: https://developer.apple.com/documentation/shadergraph/compositing/difference

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Compositing](https://developer.apple.com/documentation/shadergraph/compositing)
* Difference

ShaderGraph Node

# Difference

Outputs the distance between foreground and background values.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Overview](https://developer.apple.com/documentation/shadergraph/compositing/difference#overview)

abs(B - F)

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/compositing/difference#Parameter-Types)

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

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/compositing/difference#Parameter-descriptions)

`Foreground`
:   The foreground input. Represented by `F` in the mathmatical equation.

`Background`
:   The background input. Represented by `B` in the mathmatical equation.

`Mix`
:   The weight of the blend effect. The higher the `Mix`, the greater the intensity of the blend operation, and the more the effect is visually apparent. The default value is `1`. Values outside of the range `0-1` produce an undefined effect outside of the node’s intended function.

## [Discussion](https://developer.apple.com/documentation/shadergraph/compositing/difference#Discussion)

The `Difference` node subtracts two inputs and takes the absolute value of the result, represented by the equation `abs(B - F)`. It uses the `Mix` input to determine the weight of the foreground in the blend. Higher values closer to `1` output a more intense difference, while lower values closer to `0` dim the effect. Below is an example of a node graph that uses the difference node to blend two images together into a single material:

![](https://docs-assets.developer.apple.com/published/df0b2a945ff0248fd2850cac564a8a26/DifferenceGraph.png)

Below are two images and the resulting blended texture applied to a cube.

![](https://docs-assets.developer.apple.com/published/d9c4946e10d4cea53d216d891a402e72/MixMaterial1.png)

Foreground

![](https://docs-assets.developer.apple.com/published/894072a80859e854d9facc19ef5e6577/BrickTexture.png)

Background

![](https://docs-assets.developer.apple.com/published/262c61aaa1f893b613b75080338aaad7/DifferenceMaterial.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/compositing/difference#Nodes)

[`Premultiply`](https://developer.apple.com/documentation/shadergraph/compositing/premultiply)

Multiplies the RGB channels of the input by the alpha channel.

[`Unpremultiply`](https://developer.apple.com/documentation/shadergraph/compositing/unpremultiply)

Divides the RGB channels of the input by the alpha channel.

[`Additive Mix`](https://developer.apple.com/documentation/shadergraph/compositing/additive-mix)

Adds foreground and background values.

[`Subtractive Mix`](https://developer.apple.com/documentation/shadergraph/compositing/subtractive-mix)

Subtracts foreground from background values.

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
