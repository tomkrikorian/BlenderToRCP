Source: https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [RealityKit](https://developer.apple.com/documentation/shadergraph/realitykit)
* Geometry Modifier (RealityKit)

ShaderGraph Node

# Geometry Modifier (RealityKit)

A function that manipulates the location of a model’s vertices, run once per vertex.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `Model Position Offset` | Vector3f |
| `Color` | Color4 |
| `Normal` | Vector3f |
| `Bitangent` | Vector3f |
| `Uv0` | Vector2f |
| `Uv1` | Vector2f |
| `Uv2` | Vector4f |
| `Uv3` | Vector4f |
| `Uv4` | Vector4f |
| `Uv5` | Vector4f |
| `Uv6` | Vector4f |
| `Uv7` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Token |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-(realitykit)#Parameter-descriptions)

`Model Position Offset`
:   The offset to each vertices model position.

`Color`
:   The color of each vertex.

`Normal`
:   The normal vector for each vertex.

`Bitangent`
:   The bitangent vector for each vertex.

`Uv0`
:   A set of texture coordinates for each vertex.

`Uv1`
:   A set of texture coordinates for each vertex.

`User Attribute`
:   A user-defined attribute to apply to each vertex of the object.

`User Attribute Half4 0`
:   A user-defined attribute the node attaches to each vertex of the object.

`User Attribute Half4 1`
:   A user-defined attribute the node attaches to each vertex of the object.

`User Attribute Half4 2`
:   A user-defined attribute the node attaches to each vertex of the object.

`User Attribute Half4 3`
:   A user-defined attribute the node attaches to each vertex of the object.

`User Attribute Half2 0`
:   A user-defined attribute the node attaches to each vertex of the object.

`User Attribute Half2 1`
:   A user-defined attribute the node attaches to each vertex of the object.

# [Discussion](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-(realitykit)#Discussion)

The Geometry Modifier node can be used to cause a material to affect the geometry of any object to which it’s applied, in addition to the objects texture. Connect the output of the Geometry modifier node to the `Custom Geometry Modifier` output of your material. Below is an example of a simple node graph that uses the Geometry Modifier node to alter the *Y* model positions of vertices.

![](https://docs-assets.developer.apple.com/published/00136a30e1f473e17c13809511e24380/GeometryModifierGraph.png)

Use the Noise 2D node to procedurally generate an amount to offset the *Y* position of each vertex. You can also use the noise to add shadows to the texture in order to show the change in model position more clearly. Below, the resulting material applies to a plane.

![](https://docs-assets.developer.apple.com/published/4a79a93ee45909df54677e2f4490b485/GeometryModifierMaterial1.png)

Object before modifier

![](https://docs-assets.developer.apple.com/published/6372214cee3c7c81eb2f6c578db4c62c/GeometryModifierMaterial2.png)

Object after modifier

### [Nodes](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-(realitykit)#Nodes)

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
