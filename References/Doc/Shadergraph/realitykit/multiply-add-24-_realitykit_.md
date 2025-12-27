Source: https://developer.apple.com/documentation/shadergraph/realitykit/multiply-add-24-(realitykit)

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [RealityKit](https://developer.apple.com/documentation/shadergraph/realitykit)
* Multiply Add 24 (RealityKit)

ShaderGraph Node

# Multiply Add 24 (RealityKit)

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result with 32-bit Z value added.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Overview](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-add-24-(realitykit)#overview)

X and Y are 32-bit integers but only the low 24 bits perform the multiplication

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-add-24-(realitykit)#Parameter-Types)

| Input | Type |
| --- | --- |
| `X` | Int32 |
| `Y` | Int32 |
| `Z` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Int32 |

### [Nodes](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-add-24-(realitykit)#Nodes)

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

[`XOR (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/xor-(realitykit))

Returns true if only one of the inputs is true.

[`Not (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/not-(realitykit))

Returns !input.

[`Select (RealityKit)`](https://developer.apple.com/documentation/shadergraph/logic/select-(realitykit))

Selects B if conditional is true, A if false.

[`Multiply 24 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-24-(realitykit))

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result.
