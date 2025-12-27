Source: https://developer.apple.com/documentation/shadergraph/geometric/geometric-property

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Geometric](https://developer.apple.com/documentation/shadergraph/geometric)
* Geometric Property

ShaderGraph Node

# Geometric Property

The value of the specified geometric property (defined using ) of the currently-bound geometry.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/geometric/geometric-property#Parameter-Types)

| Input | Type |
| --- | --- |
| `Geomprop` | String |
| `Default` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Geomprop` | String |
| `Default` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `Geomprop` | String |
| `Default` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `Geomprop` | String |
| `Default` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Geomprop` | String |
| `Default` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/geometric/geometric-property#Parameter-descriptions)

`Geomprop`
:   The name of the geometric property to be read.

`Default`
:   The value the node returns if it’s unable to read the geometric property.

## [Discussion](https://developer.apple.com/documentation/shadergraph/geometric/geometric-property#Discussion)

The Geometric Property node attempts to return the value of the geometric property with the name defined by the `Geomprop` parameter. If that property doesn’t exist or there’s an error retrieving the property’s value, the node outputs the value of the `Default` parameter.

Note

The type of this node must be the same as the type of the geometric property you’re attempting to reference.

### [Nodes](https://developer.apple.com/documentation/shadergraph/geometric/geometric-property#Nodes)

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

[`Geometry Color`](https://developer.apple.com/documentation/shadergraph/geometric/geometry-color)

The color associated with the geometry at the currently-processed geometric position, typically defined by vertex color.

[`Reflect (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit))

Reflects a vector about another vector.

[`Refract (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit))

Refracts a vector using a given normal and index of refraction (eta).
