Source: https://developer.apple.com/documentation/shadergraph/compositing/matte

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Compositing](https://developer.apple.com/documentation/shadergraph/compositing)
* Matte

ShaderGraph Node

# Matte

A merge operation that layers premultiplied foreground over background.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/compositing/matte#Parameter-Types)

| Input | Type |
| --- | --- |
| `Foreground` | Color4 |
| `Background` | Color4 |
| `Mix` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/compositing/matte#Parameter-descriptions)

`Foreground`
:   The `color4` foreground input. `F` represents the RGB component of this parameter. `f` represents the alpha component of this parameter.

`Background`
:   The `color4` background input. `B` represents the RGB component of this parameter. `b`represents the alpha component of this parameter.

`Mix`
:   The weight of the blend operation. The higher the value of `Mix`, the more apparent the effect of the blend operation. The default value is `1`. Values outside of the range `0-1` produce an undefined effect outside of the node’s intended function.

## [Discussion](https://developer.apple.com/documentation/shadergraph/compositing/matte#Discussion)

The Matte node determines its output using the alpha channels of the foreground and background inputs. The RGB component of the output is `Ff+B(1-f)` and the alpha component of the output is `f+b(1-f)`. Below is a simple node graph that uses the In node to blend a wood and rock texture.

![](https://docs-assets.developer.apple.com/published/c9896f648bad20c84ad337c69fac5ca0/MatteGraph.png)

Below are the two original images, the image representation of the alpha of the foreground, and the resulting blended texture applied to a cube.

![](https://docs-assets.developer.apple.com/published/aeaf3eaedbb1788dd10bf6b091c35397/MaskMaterial1.png)

Foreground

![](https://docs-assets.developer.apple.com/published/c5085a56de96794b0a52e09d7596a2d4/MaskMaterialAlpha.png)

Foreground Alpha

![](https://docs-assets.developer.apple.com/published/12a56b955ca2c7eaf5c644f2ae3b9464/DisjointOverMaterial2.png)

Background

![](https://docs-assets.developer.apple.com/published/8ae875713c6e485fd5cfa686168f841e/MatteMaterial.png)

Blended texture

### [Nodes](https://developer.apple.com/documentation/shadergraph/compositing/matte#Nodes)

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

[`Disjoint Over`](https://developer.apple.com/documentation/shadergraph/compositing/disjoint-over)

A merge operation that layers foreground over background color, but assumes no overlap in partially transparent areas covered by both.

[`In`](https://developer.apple.com/documentation/shadergraph/compositing/in)

Outputs areas of foreground that overlap with the alpha of background.

[`Mask`](https://developer.apple.com/documentation/shadergraph/compositing/mask)

Outputs areas of background that overlap with the alpha of foreground.

[`Out`](https://developer.apple.com/documentation/shadergraph/compositing/out)

Outputs areas of foreground that do not overlap with background.

[`Over`](https://developer.apple.com/documentation/shadergraph/compositing/over)

A merge operation that layers foreground over background, using the alpha of the foreground.

[`Inside`](https://developer.apple.com/documentation/shadergraph/compositing/inside)

Multiplies a mask to all channels of the input.
