Source: https://developer.apple.com/documentation/shadergraph/data/primvar-reader

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Data](https://developer.apple.com/documentation/shadergraph/data)
* Primvar Reader

ShaderGraph Node

# Primvar Reader

A node that provides the ability for shading networks to consume data defined on geometry.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/data/primvar-reader#Parameter-Types)

| Input | Type |
| --- | --- |
| `Varname` | String |
| `Fallback` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Int32 |

| Input | Type |
| --- | --- |
| `Varname` | String |
| `Fallback` | Float |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Varname` | String |
| `Fallback` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `Varname` | String |
| `Fallback` | Bool |

| Output | Type |
| --- | --- |
| `Out` | Bool |

| Input | Type |
| --- | --- |
| `Varname` | String |
| `Fallback` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `Varname` | String |
| `Fallback` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

### [Nodes](https://developer.apple.com/documentation/shadergraph/data/primvar-reader#Nodes)

[`Convert`](https://developer.apple.com/documentation/shadergraph/data/convert)

Converts a stream from one data type to another.

[`Swizzle`](https://developer.apple.com/documentation/shadergraph/data/swizzle)

Performs an arbitrary permutation of the channels of the input stream, returning a new stream of the specified type.

[`Combine 2`](https://developer.apple.com/documentation/shadergraph/data/combine-2)

Combines the channels from two streams into two channels of a single output stream of a compatible type.

[`Combine 3`](https://developer.apple.com/documentation/shadergraph/data/combine-3)

Combines the channels from three streams into three channels of a single output stream of a compatible type.

[`Combine 4`](https://developer.apple.com/documentation/shadergraph/data/combine-4)

Combines the channels from four streams into four channels of a single output stream of a compatible type.

[`Extract`](https://developer.apple.com/documentation/shadergraph/data/extract)

Generates a float stream from one channel of a color​N o​r vector​N ​stream.

[`Separate 2`](https://developer.apple.com/documentation/shadergraph/data/separate-2)

Outputs each of the channels of a vector2 or integer2 as individual float or integer outputs.

[`Separate 3`](https://developer.apple.com/documentation/shadergraph/data/separate-3)

Outputs each of the channels of a color3, vector3, or integer3 as individual float or integer outputs.

[`Separate 4`](https://developer.apple.com/documentation/shadergraph/data/separate-4)

Outputs each of the channels of a color4, vector4, or integer4 as individual float or integer outputs.
