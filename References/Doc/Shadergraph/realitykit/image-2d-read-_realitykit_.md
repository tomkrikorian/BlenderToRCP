Source: https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-read-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [RealityKit](https://developer.apple.com/documentation/shadergraph/realitykit)
* Image 2D Read (RealityKit)

ShaderGraph Node

# Image 2D Read (RealityKit)

Direct texture read.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-read-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `Default` | Vector4f |
| `X` | Int32 |
| `Y` | Int32 |
| `Lod` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `Default` | Color4 |
| `X` | Int32 |
| `Y` | Int32 |
| `Lod` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

## [Parameter description](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-read-(realitykit)#Parameter-description)

`File`
:   The image file to use for the texture.

`Default`
:   The default value to use if the ​`File`​ parameter fails to resolve.

`X`
:   The X position of the pixel that the node reads.

Y
:   The Y position of the pixel that the node reads.

`Lod`
:   The specific LOD level that the node samples from.

## [Discussion](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-read-(realitykit)#Discussion)

The `Image 2D Read` node performs a straight read from a 2D texture without a sampler. Use this node if you have a texture that’s just data.

### [Nodes](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-read-(realitykit)#Nodes)

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
