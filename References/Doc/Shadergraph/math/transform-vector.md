Source: https://developer.apple.com/documentation/shadergraph/math/transform-vector

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Math](https://developer.apple.com/documentation/shadergraph/math)
* Transform Vector

ShaderGraph Node

# Transform Vector

Transforms a vector3 from one space to another.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/math/transform-vector#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Fromspace` | String |
| `Tospace` | String |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/math/transform-vector#Parameter-descriptions)

`In`
:   The normal vector to transform.

`Fromspace`
:   The space from which to transform the `In` vector.

`Tospace`
:   The space to which to transform the `In` vector.

## [Discussion](https://developer.apple.com/documentation/shadergraph/math/transform-vector#Discussion)

The following spaces are valid values for the `Fromspace` and `Tospace` parameters:

* `model`: The local coordinate space in relation to the model.
* `object`: The coordinate space in relation to the object.
* `world`: The global coordinate in relation to the world as a whole.

### [Nodes](https://developer.apple.com/documentation/shadergraph/math/transform-vector#Nodes)

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
