Source: https://developer.apple.com/documentation/shadergraph/compositing/disjoint-over

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Compositing](https://developer.apple.com/documentation/shadergraph/compositing)
* Disjoint Over

ShaderGraph Node

# Disjoint Over

A merge operation that layers foreground over background color, but assumes no overlap in partially transparent areas covered by both.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/compositing/disjoint-over#Parameter-Types)

| Input | Type |
| --- | --- |
| `Foreground` | Color4 |
| `Background` | Color4 |
| `Mix` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/compositing/disjoint-over#Parameter-descriptions)

`Foreground`
:   The `color4` foreground input. `F` represents the RGB component of this parameter. `f` represents the alpha component of this parameter.

`Background`
:   The `color4` background input. `B` represents the RGB component of this parameter. `b`represents the alpha component of this parameter.

`Mix`
:   The weight of the blend operation. The higher the value of `Mix`, the more apparent the effect of the blend operation. The default value is `1`. Values outside of the range `0-1` produce an undefined effect outside of the node’s intended function.

## [Discussion](https://developer.apple.com/documentation/shadergraph/compositing/disjoint-over#Discussion)

The Disjoint Over node performs one of two mixes based on the alpha channels of the foreground and background inputs. If `f+b<=1`, then the RGB component of the output is `F+B`. If `f+b>1`, then the RGB component of the output is `F+b(1-f)/b`. The alpha component of the output for this node is always the smaller value between `f+b` or 1. Below is a simple node graph that uses the Disjoint Over node to blend a tile and rock texture:

![](https://docs-assets.developer.apple.com/published/eca8c920080f8f96111adac027da05b0/DisjointOverGraph.png)

The graph remaps the alpha of the rock texture from a range of `0-1` to a range of `-1-2` in order to show more of the effect of both possible modes of the blend. Below are the two original images and their resulting blended texture applied to a cube:

![](https://docs-assets.developer.apple.com/published/38a805b0af11b84168f3f67209e89e9b/DisjointOverMaterial1.png)

Foreground

![](https://docs-assets.developer.apple.com/published/12a56b955ca2c7eaf5c644f2ae3b9464/DisjointOverMaterial2.png)

Background

![](https://docs-assets.developer.apple.com/published/c81d51bd455f4890ce12bcdfa39e05a9/DisjointOverMaterial3.png)

Blended texture

### [Nodes](https://developer.apple.com/documentation/shadergraph/compositing/disjoint-over#Nodes)

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

[`Screen`](https://developer.apple.com/documentation/shadergraph/compositing/screen)

A blend operation that lightens areas that are darker than white.

[`Overlay`](https://developer.apple.com/documentation/shadergraph/compositing/overlay)

A blend operation that multiplies dark areas and screens light areas.

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
