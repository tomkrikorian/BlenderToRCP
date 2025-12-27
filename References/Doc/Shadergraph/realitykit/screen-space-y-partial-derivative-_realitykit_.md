Source: https://developer.apple.com/documentation/shadergraph/realitykit/screen-space-y-partial-derivative-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [RealityKit](https://developer.apple.com/documentation/shadergraph/realitykit)
* Screen-Space Y Partial Derivative (RealityKit)

ShaderGraph Node

# Screen-Space Y Partial Derivative (RealityKit)

Returns a high-precision partial derivative of the specified value with respect to the screen space Y coordinate.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/realitykit/screen-space-y-partial-derivative-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `P` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `P` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `P` | Vector2h |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `P` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `P` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `P` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `P` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `P` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

### [Nodes](https://developer.apple.com/documentation/shadergraph/realitykit/screen-space-y-partial-derivative-(realitykit)#Nodes)

[`Unlit Surface (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/unlit-surface-(realitykit))

A surface shader that defines properties for a RealityKit Unlit material.

[`PBR Surface (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/pbr-surface-(realitykit))

A surface shader that defines properties for a RealityKit Physically Based Rendering material.

[`Occlusion Surface (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/occlusion-surface-(realitykit))

A surface shader that defines properties for a RealityKit Occlusion material that does not receive dynamic lighting.

[`Shadow Receiving Occlusion Surface (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/shadow-receiving-occlusion-surface-(realitykit))

A surface shader that defines properties for a RealityKit Occlusion material that receives dynamic lighting.

[`View Direction (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/view-direction-(realitykit))

A vector from a position in the scene to the view reference point.

[`Camera Position (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/camera-position-(realitykit))

The position of the camera in the scene.

[`Geometry Modifier Model To World (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-model-to-world-(realitykit))

The model-to-world transformation Matrix4x4 (Float).

[`Geometry Modifier World To Model (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-world-to-model-(realitykit))

The world-to-model transformation Matrix4x4 (Float).

[`Geometry Modifier Normal To World (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-normal-to-world-(realitykit))

The normal-to-world transformation Matrix3x3 (Float).

[`Geometry Modifier Model To View (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-model-to-view-(realitykit))

The model-to-view transformation Matrix4x4 (Float).

[`Geometry Modifier View To Projection (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-view-to-projection-(realitykit))

The view-to-projection transformation Matrix4x4 (Float).

[`Geometry Modifier Projection To View (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-projection-to-view-(realitykit))

The projection-to-view transformation Matrix4x4 (Float).

[`Geometry Modifier Vertex ID (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-vertex-id-(realitykit))

The integer index of the vertex.

[`Surface Model To World (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-model-to-world-(realitykit))

The model-to-world transformation Matrix4x4 (Float).

[`Surface Model To View (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-model-to-view-(realitykit))

The model-to-view transformation Matrix4x4 (Float).
