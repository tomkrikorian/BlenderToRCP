Source: https://developer.apple.com/documentation/shadergraph/geometric/normal

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Geometric](https://developer.apple.com/documentation/shadergraph/geometric)
* Normal

ShaderGraph Node

# Normal

The geometric normal of the currently-processed data in a given coordinate space.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/geometric/normal#Parameter-Types)

| Input | Type |
| --- | --- |
| `Space` | String |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

## [Parameter description](https://developer.apple.com/documentation/shadergraph/geometric/normal#Parameter-description)

`Space`
:   The coordinate space in which the shader defines the normal vector. The default value is `object`.

## [Discussion](https://developer.apple.com/documentation/shadergraph/geometric/normal#Discussion)

Valid values for the `Space` parameter include the following:

* `model`: The local coordinate space before the shader applies any local deformations or global transforms to the geometry.
* `object`: The local coordinate space after the shader applies local deformations but before it applies global transforms to the geometry.
* `world`: The global coordinate space after the shader applies both local deformations and global transforms to the geometry.

### [Nodes](https://developer.apple.com/documentation/shadergraph/geometric/normal#Nodes)

[`Position`](https://developer.apple.com/documentation/shadergraph/geometric/position)

The coordinates of the currently-processed data in a given coordinate space.

[`Tangent`](https://developer.apple.com/documentation/shadergraph/geometric/tangent)

The geometric tangent of the currently-processed data in a given coordinate space.

[`Bitangent`](https://developer.apple.com/documentation/shadergraph/geometric/bitangent)

The geometric bitangent vector of the currently-processed data in a given coordinate space.

[`Texture Coordinates`](https://developer.apple.com/documentation/shadergraph/geometric/texture-coordinates)

The 2D or 3D texture coordinates of the currently-processed data.

[`Geometry Color`](https://developer.apple.com/documentation/shadergraph/geometric/geometry-color)

The color associated with the geometry at the currently-processed geometric position, typically defined by vertex color.

[`Geometric Property`](https://developer.apple.com/documentation/shadergraph/geometric/geometric-property)

The value of the specified geometric property (defined using ) of the currently-bound geometry.

[`Reflect (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit))

Reflects a vector about another vector.

[`Refract (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit))

Refracts a vector using a given normal and index of refraction (eta).
