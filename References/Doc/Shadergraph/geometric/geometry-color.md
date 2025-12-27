Source: https://developer.apple.com/documentation/shadergraph/geometric/geometry-color

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Geometric](https://developer.apple.com/documentation/shadergraph/geometric)
* Geometry Color

ShaderGraph Node

# Geometry Color

The color associated with the geometry at the currently-processed geometric position, typically defined by vertex color.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/geometric/geometry-color#Parameter-Types)

| Input | Type |
| --- | --- |
| `Index` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Index` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Index` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

## [Parameter description](https://developer.apple.com/documentation/shadergraph/geometric/geometry-color#Parameter-description)

`Index`
:   The index of the color the node references. The default value is `0`.

### [Nodes](https://developer.apple.com/documentation/shadergraph/geometric/geometry-color#Nodes)

[`Position`](https://developer.apple.com/documentation/shadergraph/geometric/position)

The coordinates of the currently-processed data in a given coordinate space.

[`Normal`](https://developer.apple.com/documentation/shadergraph/geometric/normal)

The geometric normal of the currently-processed data in a given coordinate space.

[`Tangent`](https://developer.apple.com/documentation/shadergraph/geometric/tangent)

The geometric tangent of the currently-processed data in a given coordinate space.

[`Bitangent`](https://developer.apple.com/documentation/shadergraph/geometric/bitangent)

The geometric bitangent vector of the currently-processed data in a given coordinate space.

[`Texture Coordinates`](https://developer.apple.com/documentation/shadergraph/geometric/texture-coordinates)

The 2D or 3D texture coordinates of the currently-processed data.

[`Geometric Property`](https://developer.apple.com/documentation/shadergraph/geometric/geometric-property)

The value of the specified geometric property (defined using ) of the currently-bound geometry.

[`Reflect (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit))

Reflects a vector about another vector.

[`Refract (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit))

Refracts a vector using a given normal and index of refraction (eta).
