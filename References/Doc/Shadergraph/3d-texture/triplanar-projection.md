Source: https://developer.apple.com/documentation/shadergraph/3d-texture/triplanar-projection

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [3D-Texture](https://developer.apple.com/documentation/shadergraph/3d-texture)
* Triplanar Projection

ShaderGraph Node

# Triplanar Projection

Samples data from three images and projects each along its respective coordinate axis and blends them by geometric normal.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/3d-texture/triplanar-projection#Parameter-Types)

| Input | Type |
| --- | --- |
| `File X` | AssetPath |
| `File Y` | AssetPath |
| `File Z` | AssetPath |
| `Default` | Float |
| `Position` | Vector3f |
| `Normal` | Vector3f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `File X` | AssetPath |
| `File Y` | AssetPath |
| `File Z` | AssetPath |
| `Default` | Vector2f |
| `Position` | Vector3f |
| `Normal` | Vector3f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `File X` | AssetPath |
| `File Y` | AssetPath |
| `File Z` | AssetPath |
| `Default` | Color3 |
| `Position` | Vector3f |
| `Normal` | Vector3f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `File X` | AssetPath |
| `File Y` | AssetPath |
| `File Z` | AssetPath |
| `Default` | Vector3f |
| `Position` | Vector3f |
| `Normal` | Vector3f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `File X` | AssetPath |
| `File Y` | AssetPath |
| `File Z` | AssetPath |
| `Default` | Color4 |
| `Position` | Vector3f |
| `Normal` | Vector3f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `File X` | AssetPath |
| `File Y` | AssetPath |
| `File Z` | AssetPath |
| `Default` | Vector4f |
| `Position` | Vector3f |
| `Normal` | Vector3f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

## [Parameter description](https://developer.apple.com/documentation/shadergraph/3d-texture/triplanar-projection#Parameter-description)

`File X`
:   The image file to project from the positive X direction toward the origin.

`File Y`
:   The image file to project from the positive Y direction toward the origin.

`File Z`
:   The image file to project from the positive Z direction toward the origin.

`Default`
:   The default value the node uses if any of the ​file​ references fail to resolve.

`Position`
:   The 3D coordinates at which the node reads data for mapping the texture onto a surface. The default uses the current 3D object-space coordinates.

`Normal`
:   The 3D normal vector the node uses for blending; the default is the current object-space surface normal.

`Filter Type`
:   The type of texture filtering the node uses; the default is `linear`.

## [Discussion](https://developer.apple.com/documentation/shadergraph/3d-texture/triplanar-projection#Discussion)

Use the `Triplanar Projection` node to blend three different images together based on the vector normal of each point on the object. Areas of the object that are parallel with a coordinate axis cause the node to fully show the respective image. Areas of the object between the coordinate axis cause the node to render a mix of the images based on how close the normal is to each of the axis. The closer the normal is to the normal of a coordinate axis the strong the respective image is in the blend. Below is an example of a simple node graph that uses the `Triplanar Projection` node to blend the same grass image in the X and Y directions, and a tile texture in the Z direction:

![](https://docs-assets.developer.apple.com/published/6eb46ff8978c7668db66854d9c28a713/TriplanarGraph.png)

Below, the resulting texture applies to a sphere:

![](https://docs-assets.developer.apple.com/published/1117a45d6a0935576157ebc4b3f41684/TriplanarMaterial.png)
