Source: https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Geometric](https://developer.apple.com/documentation/shadergraph/geometric)
* Refract (RealityKit)

ShaderGraph Node

# Refract (RealityKit)

Refracts a vector using a given normal and index of refraction (eta).

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Normal` | Vector3f |
| `Eta` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit)#Parameter-descriptions)

`In`
:   The vector to refract.

`Normal`
:   The normal of the surface from which the `In` vector refracts.

`Eta`
:   The index of refraction.

## [Discussion](https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit)#Discussion)

`Out High`
:   The high end value of the output range; the default is `1.0`.

Note

The vectors passed as the `In` and `Normal` parameters must both already be normalized to achieve the desired output.

### [Nodes](https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit)#Nodes)

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

[`Geometric Property`](https://developer.apple.com/documentation/shadergraph/geometric/geometric-property)

The value of the specified geometric property (defined using ) of the currently-bound geometry.

[`Reflect (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit))

Reflects a vector about another vector.
