Source: https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-gradient-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [RealityKit](https://developer.apple.com/documentation/shadergraph/realitykit)
* Image 3D Gradient (RealityKit)

ShaderGraph Node

# Image 3D Gradient (RealityKit)

A texture with RealityKit properties.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+visionOS 1.0+

## [Overview](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-gradient-(realitykit)#overview)

Level of detail gradient

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-gradient-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `U Wrap Mode` | String |
| `V Wrap Mode` | String |
| `W Wrap Mode` | String |
| `Border Color` | String |
| `Mag Filter` | String |
| `Min Filter` | String |
| `Mip Filter` | String |
| `Max Anisotropy` | Int32 |
| `Max Lod Clamp` | Float |
| `Min Lod Clamp` | Float |
| `Default` | Vector4f |
| `Texture Coordinates` | Vector3f |
| `Dynamic Min Lod Clamp` | Float |
| `Gradient3D D Pdx` | Vector3f |
| `Gradient3D D Pdy` | Vector3f |
| `Offset` | Integer3 |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `U Wrap Mode` | String |
| `V Wrap Mode` | String |
| `W Wrap Mode` | String |
| `Border Color` | String |
| `Mag Filter` | String |
| `Min Filter` | String |
| `Mip Filter` | String |
| `Max Anisotropy` | Int32 |
| `Max Lod Clamp` | Float |
| `Min Lod Clamp` | Float |
| `Default` | Color3 |
| `Texture Coordinates` | Vector3f |
| `Dynamic Min Lod Clamp` | Float |
| `Gradient3D D Pdx` | Vector3f |
| `Gradient3D D Pdy` | Vector3f |
| `Offset` | Integer3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `U Wrap Mode` | String |
| `V Wrap Mode` | String |
| `W Wrap Mode` | String |
| `Border Color` | String |
| `Mag Filter` | String |
| `Min Filter` | String |
| `Mip Filter` | String |
| `Max Anisotropy` | Int32 |
| `Max Lod Clamp` | Float |
| `Min Lod Clamp` | Float |
| `Default` | Color4 |
| `Texture Coordinates` | Vector3f |
| `Dynamic Min Lod Clamp` | Float |
| `Gradient3D D Pdx` | Vector3f |
| `Gradient3D D Pdy` | Vector3f |
| `Offset` | Integer3 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

Important

This node requires a device with a [`MTLGPUFamily.apple6`](https://developer.apple.com/documentation/Metal/MTLGPUFamily/apple6) or later GPU and may not be available on certain devices. To determine GPU feature support at runtime, see [Detecting GPU features and Metal software versions](https://developer.apple.com/documentation/Metal/detecting-gpu-features-and-metal-software-versions).

### [Nodes](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-gradient-(realitykit)#Nodes)

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
