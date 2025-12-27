Source: https://developer.apple.com/documentation/shadergraph/realitykit/camera-index-switch-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [RealityKit](https://developer.apple.com/documentation/shadergraph/realitykit)
* Camera Index Switch (RealityKit)

ShaderGraph Node

# Camera Index Switch (RealityKit)

Render different results for each eye in a stereoscopic render.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/realitykit/camera-index-switch-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `Mono` | Int32 |
| `Left` | Int32 |
| `Right` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Int32 |

| Input | Type |
| --- | --- |
| `Mono` | Float |
| `Left` | Float |
| `Right` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Mono` | Vector4h |
| `Left` | Vector4h |
| `Right` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `Mono` | Vector2f |
| `Left` | Vector2f |
| `Right` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `Mono` | Vector4f |
| `Left` | Vector4f |
| `Right` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `Mono` | Color3 |
| `Left` | Color3 |
| `Right` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Mono` | Vector3h |
| `Left` | Vector3h |
| `Right` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `Mono` | Half |
| `Left` | Half |
| `Right` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `Mono` | Vector3f |
| `Left` | Vector3f |
| `Right` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `Mono` | Color4 |
| `Left` | Color4 |
| `Right` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `Mono` | Vector2h |
| `Left` | Vector2h |
| `Right` | Vector2h |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/realitykit/camera-index-switch-(realitykit)#Parameter-descriptions)

`Mono`
:   The value to return if using a single renderer.

`Left`
:   The value to return if seeing the texture through the left eye of a stereoscopic render.

`Right`
:   The value to return if seeing the texture through the right eye of a stereoscopic render.

## [Discussion](https://developer.apple.com/documentation/shadergraph/realitykit/camera-index-switch-(realitykit)#Discussion)

Use the `Camera Index Switch` node to render stereoscopic images. On most devices, this node returns its `Mono` input parameter. On Apple Vision Pro, this node outputs either `Left` or `Right`, depending on which eye the texture renders through.

### [Nodes](https://developer.apple.com/documentation/shadergraph/realitykit/camera-index-switch-(realitykit)#Nodes)

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
