Source: https://developer.apple.com/documentation/shadergraph/data/convert

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Data](https://developer.apple.com/documentation/shadergraph/data)
* Convert

ShaderGraph Node

# Convert

Converts a stream from one data type to another.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/data/convert#Parameter-Types)

| Input | Type |
| --- | --- |
| `In` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2h |

| Input | Type |
| --- | --- |
| `In` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `In` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Vector3h |

| Input | Type |
| --- | --- |
| `In` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `In` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Half |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `In` | Color4 |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Bool |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `In` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Vector4h |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Half |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `In` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Float |

| Output | Type |
| --- | --- |
| `Out` | Int32 |

| Input | Type |
| --- | --- |
| `In` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Half |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Color3 |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Int32 |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `In` | Float |

| Output | Type |
| --- | --- |
| `Out` | Half |

| Input | Type |
| --- | --- |
| `In` | Half |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Half |

| Output | Type |
| --- | --- |
| `Out` | Int32 |

| Input | Type |
| --- | --- |
| `In` | Vector2h |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector4h |

| Input | Type |
| --- | --- |
| `In` | Vector4f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Half |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Bool |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `In` | Vector3h |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `In` | Float |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `In` | Float |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `In` | Half |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `In` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `In` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

## [Discussion](https://developer.apple.com/documentation/shadergraph/data/convert#Discussion)

The `Convert` node takes data of one type and outputs it in another form. The supported type conversions are shown above with the various convert node types. The `Convert` node handles data types in the following ways:

* When converting a `float` to a `color` or `vector`, the `Convert` node copies the `float` to all channels of the `color` or `vector`.
* When converting a `color3` to a `color4`, the `Convert` node sets the output alpha to `1.0`
* When converting a `color4` to a `color3`, the `Convert` node drops the alpha channel.
* When converting a `boolean` or `integer` to a `float`, the output is either `1.0` or `0.0`.
* When converting a `vector2` to `vector3` or a `vector3` to a `vector4`, the `Convert` nodes populates the additional channel with a value of `1.0`
* When converting a `vector4` to a `vector3`, or a `vector3` to a `vector2`, drop the last channel.

### [Nodes](https://developer.apple.com/documentation/shadergraph/data/convert#Nodes)

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

[`Primvar Reader`](https://developer.apple.com/documentation/shadergraph/data/primvar-reader)

A node that provides the ability for shading networks to consume data defined on geometry.
