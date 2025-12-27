Source: https://developer.apple.com/documentation/shadergraph/math/clamp

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Math](https://developer.apple.com/documentation/shadergraph/math)
* Clamp

ShaderGraph Node

# Clamp

Clamps the input per-channel to a specified range.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/math/clamp#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Float |
| `Low` | Float |
| `High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Low` | Vector3f |
| `High` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Vector2f |
| `Low` | Vector2f |
| `High` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Vector4f |
| `Low` | Vector4f |
| `High` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Color4 |
| `Low` | Float |
| `High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Vector3h |
| `Low` | Vector3h |
| `High` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `In` | Half |
| `Low` | Half |
| `High` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `In` | Vector2h |
| `Low` | Vector2h |
| `High` | Vector2h |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `In` | Color3 |
| `Low` | Float |
| `High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Vector3f |
| `Low` | Float |
| `High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Vector2h |
| `Low` | Float |
| `High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `In` | Vector4h |
| `Low` | Vector4h |
| `High` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `In` | Vector3h |
| `Low` | Float |
| `High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `In` | Vector4h |
| `Low` | Float |
| `High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `In` | Color3 |
| `Low` | Color3 |
| `High` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Vector2f |
| `Low` | Float |
| `High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Color4 |
| `Low` | Color4 |
| `High` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Vector4f |
| `Low` | Float |
| `High` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/math/clamp#Parameter-descriptions)

`In`
:   The input to clamp.

`Low`
:   The low end of the clamp range.

`High`
:   The high end of the clamp range.

## [Discussion](https://developer.apple.com/documentation/shadergraph/math/clamp#Discussion)

The `Clamp` node restricts the range of values of an input as defined by the `Low` and `High` parameters passed into the node. The output of the `Clamp` node is the same as the `In` value if it falls within the defined range. Otherwise, the output clamps to the nearest limit, which is either the `Low` or `High` value. Use the `Clamp` node to create more predictable and controlled shader behavior for materials.

### [Nodes](https://developer.apple.com/documentation/shadergraph/math/clamp#Nodes)

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
