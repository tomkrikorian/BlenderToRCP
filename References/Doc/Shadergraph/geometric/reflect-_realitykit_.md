Source: https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Geometric](https://developer.apple.com/documentation/shadergraph/geometric)
* Reflect (RealityKit)

ShaderGraph Node

# Reflect (RealityKit)

Reflects a vector about another vector.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Normal` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit)#Parameter-descriptions)

`In`
:   The input vector to reflect.

`Normal`
:   The vector that the `In` vector will be reflected with reference to.

## [Discussion](https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit)#Discussion)

The `Reflect` node reflects the `In` vector by taking into account the surface orientation determined by the `Normal` vector. The `Reflect` node normalizes the `Normal` vector, then calculates the reflection direction using the formula, `In - 2 * dot(Normal, In) * Normal`. In this equation, `dot()` represents the dot product of the two vectors.

### [Nodes](https://developer.apple.com/documentation/shadergraph/geometric/reflect-(realitykit)#Nodes)

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

[`Refract (RealityKit)`](https://developer.apple.com/documentation/shadergraph/geometric/refract-(realitykit))

Refracts a vector using a given normal and index of refraction (eta).
