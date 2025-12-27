Source: https://developer.apple.com/documentation/shadergraph/application/time-(float)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Application](https://developer.apple.com/documentation/shadergraph/application)
* Time (float)

ShaderGraph Node

# Time (float)

The current time in seconds.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/application/time-(float)#Parameter-Types)

| Output | Type |
| --- | --- |
| `Out` | Float |

## [Discussion](https://developer.apple.com/documentation/shadergraph/application/time-(float)#Discussion)

The `Time` node outputs a float that represents the current time in seconds. When applied or connected to other nodes, this value changes constantly, allowing for dynamic materials. Below is an example of a simple node graph that causes an image texture to scroll in real time:

![](https://docs-assets.developer.apple.com/published/cff64c2ca64dd8e94442e51f2b648d9f/TimeGraph.png)

Adding Time to the incoming texture coordinates horizontal component causes the texture to “scroll” along the horizontal plane. Below, the resulting texture applies to a cube:

Video with custom controls.

[](https://docs-assets.developer.apple.com/published/bd4860116b4c9b6263157a59cd41f1cf/TimeMaterialVideo.mov)

 [Play](#)

### [Nodes](https://developer.apple.com/documentation/shadergraph/application/time-(float)#Nodes)

[`Up Direction`](https://developer.apple.com/documentation/shadergraph/application/up-direction)

The direction of the up vector.
