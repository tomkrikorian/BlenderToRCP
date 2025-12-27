Source: https://developer.apple.com/documentation/shadergraph/realitykit/environment-radiance-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [RealityKit](https://developer.apple.com/documentation/shadergraph/realitykit)
* Environment Radiance (RealityKit)

ShaderGraph Node

# Environment Radiance (RealityKit)

Returns an environment’s diffuse and specular radiance value based on real-world environment, and an IBL map that is either a developer-provided map or a default map.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/realitykit/environment-radiance-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `Base Color` | Color3 |
| `Roughness` | Half |
| `Specular` | Half |
| `Metallic` | Half |
| `Normal` | Vector3f |

| Output | Type |
| --- | --- |
| `Diffuse Radiance` | Color3 |
| `Specular Radiance` | Color3 |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/realitykit/environment-radiance-(realitykit)#Parameter-descriptions)

`Base Color`
:   The base display color of the surface. The color under pure white light.

`Roughness`
:   The level of roughness of the surface. This value ranges between `0` and `1.0`, with `0` representing a perfectly specular surface and `1.0` representing maximum roughness. The default value is `0`.

`Specular`
:   The level of specular reflections that occur on the surface.

`Metallic`
:   The indicator if a surface is metallic or not. Set this value to `1` for metallic surfaces and `0` for nonmetallic surfaces. The default value is `0.0`.

`Normal`
:   The surface normal vector. The default value is `(0,0,0)`.

## [Discussion:](https://developer.apple.com/documentation/shadergraph/realitykit/environment-radiance-(realitykit)#Discussion)

The Environment Radiance node has two outputs:

`Diffuse Radiance`
:   The diffuse radiance of the surface. Refers to light absorbed by the surface and then re-emitted in all directions.

`Specular Radiance`
:   The specular radiance of the surface. Refers to light reflected off of the surface.

### [Nodes](https://developer.apple.com/documentation/shadergraph/realitykit/environment-radiance-(realitykit)#Nodes)

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
