Source: https://developer.apple.com/documentation/shadergraph/logic/xor-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Logic](https://developer.apple.com/documentation/shadergraph/logic)
* XOR (RealityKit)

ShaderGraph Node

# XOR (RealityKit)

Returns true if only one of the inputs is true.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/logic/xor-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `In 1` | Bool |
| `In 2` | Bool |

| Output | Type |
| --- | --- |
| `Out` | Bool |

## [Discussion](https://developer.apple.com/documentation/shadergraph/logic/xor-(realitykit)#Discussion)

This node mimics the logical `Xor` operator, as shown in the table below:

| In1 | In2 | Out |
| --- | --- | --- |
| True | True | False |
| True | False | True |
| False | True | True |
| False | False | False |

### [Nodes](https://developer.apple.com/documentation/shadergraph/logic/xor-(realitykit)#Nodes)

[`If Greater`](https://developer.apple.com/documentation/shadergraph/logic/if-greater)

Outputs True Result or False Result depending on whether value1 > value2.

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

[`Not (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/not-(realitykit))

Returns !input.

[`Select (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/select-(realitykit))

Selects B if conditional is true, A if false.

[`Multiply Add 24 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-add-24-(realitykit))

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result with 32-bit Z value added.

[`Multiply 24 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-24-(realitykit))

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result.
