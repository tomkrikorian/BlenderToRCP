Source: https://developer.apple.com/documentation/shadergraph/logic/if-greater

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Logic](https://developer.apple.com/documentation/shadergraph/logic)
* If Greater

ShaderGraph Node

# If Greater

Outputs True Result or False Result depending on whether value1 > value2.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/logic/if-greater#Parameter-Types)

| Input | Type |
| --- | --- |
| `Value1` | Float |
| `Value2` | Float |
| `True Result` | Float |
| `False Result` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `In 1` | Vector2h |
| `In 2` | Vector2h |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `True Result` | Float |
| `False Result` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Value1` | Float |
| `Value2` | Float |
| `In 1` | Vector3h |
| `In 2` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `True Result` | Vector2f |
| `False Result` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `Value1` | Float |
| `Value2` | Float |
| `True Result` | Vector4f |
| `False Result` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `Value1` | Float |
| `Value2` | Float |
| `In 1` | Vector4h |
| `In 2` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `In 1` | Vector4h |
| `In 2` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `Value1` | Float |
| `Value2` | Float |
| `True Result` | Color3 |
| `False Result` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `True Result` | Vector4f |
| `False Result` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `In 1` | Half |
| `In 2` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `Value1` | Float |
| `Value2` | Float |
| `True Result` | Vector3f |
| `False Result` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `In 1` | Vector3h |
| `In 2` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `True Result` | Color4 |
| `False Result` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `Value1` | Half |
| `Value2` | Half |
| `In 1` | Half |
| `In 2` | Half |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `Value1` | Float |
| `Value2` | Float |
| `True Result` | Vector2f |
| `False Result` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `Value1` | Float |
| `Value2` | Float |
| `True Result` | Color4 |
| `False Result` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `True Result` | Color3 |
| `False Result` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Value1` | Int32 |
| `Value2` | Int32 |
| `True Result` | Vector3f |
| `False Result` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `Value1` | Float |
| `Value2` | Float |
| `In 1` | Vector2h |
| `In 2` | Vector2h |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/logic/if-greater#Parameter-descriptions)

`Value1`
:   The first value to compare.

`Value2`
:   The second value to compare.

`True Result`
:   The output of the node if the `Value1` input parameter is greater than the `Value2` input parameter.

`False Result`
:   The output of the node if the `Value1` input parameter isn’t greater than the `Value2` input parameter.

### [Nodes](https://developer.apple.com/documentation/shadergraph/logic/if-greater#Nodes)

[`If Greater Or Equal`](https://developer.apple.com/documentation/shadergraph/logic/if-greater-or-equal)

Outputs True Result or False Result depending on whether value1 >= value2.

[`If Equal`](https://developer.apple.com/documentation/shadergraph/logic/if-equal)

Outputs True Result or False Result depending on whether value1 == value2.

[`Switch`](https://developer.apple.com/documentation/shadergraph/logic/switch)

Outputs the value from one of ten input streams, according to a selector .

[`And (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/and-(realitykit))

Boolean operation in1 && in2.

[`Or (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/or-(realitykit))

Boolean operation in1 || in2.

[`XOR (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/xor-(realitykit))

Returns true if only one of the inputs is true.

[`Not (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/not-(realitykit))

Returns !input.

[`Select (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/select-(realitykit))

Selects B if conditional is true, A if false.

[`Multiply Add 24 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-add-24-(realitykit))

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result with 32-bit Z value added.

[`Multiply 24 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-24-(realitykit))

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result.
