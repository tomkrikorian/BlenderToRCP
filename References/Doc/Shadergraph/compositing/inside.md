Source: https://developer.apple.com/documentation/shadergraph/compositing/inside

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Compositing](https://developer.apple.com/documentation/shadergraph/compositing)
* Inside

ShaderGraph Node

# Inside

Multiplies a mask to all channels of the input.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/compositing/inside#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Float |
| `Mask` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `In` | Half |
| `Mask` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `In` | Color3 |
| `Mask` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Color4 |
| `Mask` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/compositing/inside#Parameter-descriptions)

`In`
:   The input value to which the mask applies.

`Mask`
:   The value by which the input is multiplied.

## [Discussion](https://developer.apple.com/documentation/shadergraph/compositing/inside#Discussion)

Below is an example of a simple node graph that uses the Inside node to apply a mask to a brick texture:

![](https://docs-assets.developer.apple.com/published/ddd60aabdacdc1bd721a5ddb67b271c7/InsideGraph.png)

Below, the resulting texture applies to a cube.

![](https://docs-assets.developer.apple.com/published/22d385b227fa57a9a3f445794e022e8e/InsideMaterial1.png)

Mask

![](https://docs-assets.developer.apple.com/published/b8a12d9ac1244a778a30d88ebfe67b03/InsideMaterial2.png)

Input

![](https://docs-assets.developer.apple.com/published/2855885be1ac1bb941d84e14a9c96c1c/InsideMaterial3.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/compositing/inside#Nodes)

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

[`Matte`](https://developer.apple.com/documentation/shadergraph/compositing/matte)

A merge operation that layers premultiplied foreground over background.

[`Out`](https://developer.apple.com/documentation/shadergraph/compositing/out)

Outputs areas of foreground that do not overlap with background.

[`Over`](https://developer.apple.com/documentation/shadergraph/compositing/over)

A merge operation that layers foreground over background, using the alpha of the foreground.
