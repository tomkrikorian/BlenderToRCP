Source: https://developer.apple.com/documentation/shadergraph/math/normal-map

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Math](https://developer.apple.com/documentation/shadergraph/math)
* Normal Map

ShaderGraph Node

# Normal Map

Transforms a normal vector from object or tangent space into world space.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/math/normal-map#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Space` | String |
| `Scale` | Float |
| `Normal` | Vector3f |
| `Tangent` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Space` | String |
| `Scale` | Vector2f |
| `Normal` | Vector3f |
| `Tangent` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/math/normal-map#Parameter-descriptions)

`In`
:   The input vector to be transformed; the default is `(0.5, 0.5, 1.0)`.

`Space`
:   The space from which the node transforms the normal vector. The value can either be `object` or `tangent`. The default value is `tangent`.

`Scale`
:   A scalar multiplier for the input vector before the node transforms it. The default value is `1.0`.

`Normal`
:   The surface normal vector. The default value is the current surface normal of world space.

`Tangent`
:   The surface tangent vector. The default value is the current tangent vector of world space.

### [Nodes](https://developer.apple.com/documentation/shadergraph/math/normal-map#Nodes)

[`Add`](https://developer.apple.com/documentation/shadergraph/math/add)

Adds two values.

[`Subtract`](https://developer.apple.com/documentation/shadergraph/math/subtract)

Subtracts two values.

[`Multiply`](https://developer.apple.com/documentation/shadergraph/math/multiply)

Multiplies two values.

[`Divide`](https://developer.apple.com/documentation/shadergraph/math/divide)

Divides two values.

[`Modulo`](https://developer.apple.com/documentation/shadergraph/math/modulo)

Outputs the remaining fraction after dividing the input by a value and subtracting the integer portion.

[`Abs`](https://developer.apple.com/documentation/shadergraph/math/abs)

Outputs the per-channel absolute value of the input.

[`Floor`](https://developer.apple.com/documentation/shadergraph/math/floor)

Outputs the nearest integer value, per-channel, less than or equal to the incoming values.

[`Ceiling`](https://developer.apple.com/documentation/shadergraph/math/ceiling)

Outputs the nearest integer value, per-channel, greater than or equal to the incoming values.

[`Power`](https://developer.apple.com/documentation/shadergraph/math/power)

Raises the incoming value to an exponent.

[`Sin`](https://developer.apple.com/documentation/shadergraph/math/sin)

The sine of the incoming value in radians.

[`Cos`](https://developer.apple.com/documentation/shadergraph/math/cos)

The cosine of the incoming value in radians.

[`Tan`](https://developer.apple.com/documentation/shadergraph/math/tan)

The tangent of the incoming value in radians.

[`Asin`](https://developer.apple.com/documentation/shadergraph/math/asin)

The arcsine of the incoming value in radians.

[`Acos`](https://developer.apple.com/documentation/shadergraph/math/acos)

The arccosine of the incoming value in radians.

[`Atan2`](https://developer.apple.com/documentation/shadergraph/math/atan2)

The arctangent of the expression (iny/inx) in radians.
