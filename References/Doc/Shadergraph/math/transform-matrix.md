Source: https://developer.apple.com/documentation/shadergraph/math/transform-matrix

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Math](https://developer.apple.com/documentation/shadergraph/math)
* Transform Matrix

ShaderGraph Node

# Transform Matrix

Transforms a vector by a matrix.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/math/transform-matrix#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Vector2f |
| `Mat` | Matrix3x3f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Vector4f |
| `Mat` | Matrix4x4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Vector2f |
| `Mat` | Matrix2x2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Mat` | Matrix4x4f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Mat` | Matrix3x3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/math/transform-matrix#Parameter-descriptions)

`In`
:   The vector to transform. This node appends an addtional component onto the `In` vector with a value of `1.0` to make the vector match the dimensions of the `Mat` matrix. This additional compenent is removed after the transformation completes.

`Mat`
:   The matrix by which to transform the `In` vector; the default is the identity matrix.

### [Nodes](https://developer.apple.com/documentation/shadergraph/math/transform-matrix#Nodes)

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
