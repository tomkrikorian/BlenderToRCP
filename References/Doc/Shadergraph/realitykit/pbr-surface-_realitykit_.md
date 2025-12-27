Source: https://developer.apple.com/documentation/shadergraph/realitykit/pbr-surface-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [RealityKit](https://developer.apple.com/documentation/shadergraph/realitykit)
* PBR Surface (RealityKit)

ShaderGraph Node

# PBR Surface (RealityKit)

A surface shader that defines properties for a RealityKit Physically Based Rendering material.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/realitykit/pbr-surface-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `Base Color` | Color3 |
| `Emissive Color` | Color3 |
| `Normal` | Vector3f |
| `Roughness` | Float |
| `Metallic` | Float |
| `Ambient Occlusion` | Float |
| `Specular` | Float |
| `Opacity` | Float |
| `Opacity Threshold` | Float |
| `Clearcoat` | Float |
| `Clearcoat Roughness` | Float |
| `Clearcoat Normal` | Vector3f |
| `Has Premultiplied Alpha` | Bool |

| Output | Type |
| --- | --- |
| `Out` | Token |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/realitykit/pbr-surface-(realitykit)#Parameter-descriptions)

`Base Color`
:   The base display color of the surface. The color of an object under pure white light.

`Emissive Color`
:   The self-illumination color of the surface. The color the surface displays as if it’s self-lit.

`Normal`
:   The normal vector in tangent space. The default is `(0,0,1)`.

`Roughness`
:   The level of roughness of the surface. This value ranges between `0` and `1.0`, with `0` outputting a perfectly specular surface and `1.0` indicating maximum roughness. The default is `0.5`.

`Metallic`
:   Indicates whether a surface is metallic. Set this value to `1` for metallic surfaces, and to `0` for nonmetallic surfaces. The default is `0.0`.

`Ambient Occlusion`
:   The degree of ambient lighting that the surface receives. This value simulates soft shadows and subtle shading.

`Specular`
:   The brightness of the specular highlight of the material.

`Opacity`
:   The level of opaqueness of the surface. If the value of this parameter is `1.0`, the surface is fully opaque. If the value is less than `1.0`, the surface appears translucent. If the value is `0`, the surface is completely transparent. The default is `1.0`.

`Opacity Threshold`
:   The threshold for whether a portion of the surface renders based on its opacity level. A value of `0.0` means that no additional masking occurs. If the value is greater than `0.0`, the node renders only areas of the surface with an `Opacity` value greater than the value of this parameter. This parameter can be turned on or off. The default value is `0.0`.

`Clearcoat`
:   A second clear reflective layer on the surface. This property produces a glossy finish. The default is `0.0`.

`Clearcoat Roughness`
:   The level of roughness of the surfaces clearcoat layer. The default is `0.01`.

`Has Premultiplied Alpha`
:   A Boolean value to let the node know if input parameters have a premultiplied alpha.

## [Discussion](https://developer.apple.com/documentation/shadergraph/realitykit/pbr-surface-(realitykit)#Discussion)

The PBR Surface node produces a custom surface based on its input parameters. Connect the output of the PBR Surface node to the `Custom Surface` output of your material.

Below is an example material that uses only the `PBR Surface` node to produce a gold-like texture and apply it to a sphere:

![](https://docs-assets.developer.apple.com/published/14dabad45a3dba0f7dda8ee7f112d394/PBRSurfaceMaterial.png)

![](https://docs-assets.developer.apple.com/published/69fa8b7feb6eb1d35d69f0d13155dea9/PBRSurfaceInputs.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/realitykit/pbr-surface-(realitykit)#Nodes)

[`Unlit Surface (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/unlit-surface-(realitykit))

A surface shader that defines properties for a RealityKit Unlit material.

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

[`Surface World To View (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-world-to-view-(realitykit))

The world-to-view transformation Matrix4x4 (Float).
