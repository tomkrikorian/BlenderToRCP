Source: https://developer.apple.com/documentation/shadergraph/math/place-2d

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [Math](https://developer.apple.com/documentation/shadergraph/math)
* Place 2D

ShaderGraph Node

# Place 2D

Transforms UV texture coordinates for 2D texture placement.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/math/place-2d#Parameter-Types)

| Input | Type |
| --- | --- |
| `Texture Coordinates` | Vector2f |
| `Pivot` | Vector2f |
| `Scale` | Vector2f |
| `Rotate` | Float |
| `Offset` | Vector2f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/math/place-2d#Parameter-descriptions)

`Texture Coordinates`
:   The input texture coordinates to transform. The default value is the current surface texture coordinates with an index of `0`.

`Pivot`
:   The pivot point for scaling and rotating the texture coordinates. The node subtracts this value from U and V before it applies the scale or rotation. The node then adds this value back later.

`Scale`
:   The value by which to scale the texture coordinates. The node divides the U and V coordinates by this value. The default is `(1,1)`.

`Rotate`
:   The number of degrees to rotate the texture coordinates. A postive value rotates the texture coordinates by that many degrees counterclockwise and the resulting image clockwise. A negative value rotates the texture coordinates by that many degrees clockwise and the resulting image counterclockwise. The default value is `0`.

`Offset`
:   The value to offset the position of the texture coordinates. The node subtracts this value from the texture coordinates after scaling and rotating it, and adding back the pivot. The default is `(0,0)`.

## [Discussion](https://developer.apple.com/documentation/shadergraph/math/place-2d#Discussion)

Use the `Place 2D` node to transform texture coordinates and apply these basic transformations to textures. Below is an example of a simple node graph that uses the `Place 2D` node to transform texture coordinates before passing them to an image node:

![](https://docs-assets.developer.apple.com/published/9eedcf2c05258008ef6543a7b5d1d075/Place2dGraph.png)

The incoming texture coordinates transform in three ways; they are:

* scaled down to half the size
* rotated 180 degrees
* offset by `0.5` in both the U and V directions. For the scale and rotation, the pivot point is set to `(0.5, 0.5)`. Because texture coordinates generally range from `(0-1)`, this means the scale and rotation are done from the center point of the image.

Below is the original image and the texture with the transformation applied:

![](https://docs-assets.developer.apple.com/published/78717aea759b374d62a6c56468ba269e/Place2dMaterial1.png)

Original Image

![](https://docs-assets.developer.apple.com/published/efc54695250fd8a7151a87eab115b4f3/Place2dMaterial2.png)

Image after transformations

### [Nodes](https://developer.apple.com/documentation/shadergraph/math/place-2d#Nodes)

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
