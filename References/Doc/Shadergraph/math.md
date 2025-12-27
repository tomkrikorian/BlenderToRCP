Source: https://developer.apple.com/documentation/shadergraph/math

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* Math

ShaderGraph Node Group

# Math

Perform a wide variety of mathematical and transformative operations on data values.

## [Overview](https://developer.apple.com/documentation/shadergraph/math#overview)

Include `Math` nodes in your graph to perform typical mathematical operations on data values. A wide range of nodes are available, supporting basic arithmetic, trigonometry, logs, exponents, dot and cross products, and more. Some nodes operate on specific data types of values, but most operate on a wide range of data types, including numbers, colors, and vectors.

### [Nodes](https://developer.apple.com/documentation/shadergraph/math#Nodes)

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

[`Square Root`](https://developer.apple.com/documentation/shadergraph/math/square-root)

The square root of the incoming value.

[`Natural Log`](https://developer.apple.com/documentation/shadergraph/math/natural-log)

The natural log of the input.

[`Exp`](https://developer.apple.com/documentation/shadergraph/math/exp)

Outputs ‘e’ to the power of the input.

[`Sign`](https://developer.apple.com/documentation/shadergraph/math/sign)

The per-channel sign of the input value: -1 for negative, +1 for positive, 0 for zero.

[`Clamp`](https://developer.apple.com/documentation/shadergraph/math/clamp)

Clamps the input per-channel to a specified range.

[`Min`](https://developer.apple.com/documentation/shadergraph/math/min)

Outputs the minimum of two incoming values.

[`Max`](https://developer.apple.com/documentation/shadergraph/math/max)

Outputs the maximum of two incoming values.

[`Normalize`](https://developer.apple.com/documentation/shadergraph/math/normalize)

Outputs a normalized vector.

[`Magnitude`](https://developer.apple.com/documentation/shadergraph/math/magnitude)

Outputs the float magnitude of a vector.

[`Dot Product`](https://developer.apple.com/documentation/shadergraph/math/dot-product)

Outputs the dot product of two vectors.

[`Cross Product`](https://developer.apple.com/documentation/shadergraph/math/cross-product)

Calculates the cross product vector of 2 input vectors.

[`Transform Point`](https://developer.apple.com/documentation/shadergraph/math/transform-point)

Transforms a coordinate from one space to another.

[`Transform Vector`](https://developer.apple.com/documentation/shadergraph/math/transform-vector)

Transforms a vector3 from one space to another.

[`Transform Normal`](https://developer.apple.com/documentation/shadergraph/math/transform-normal)

Transforms a normal from one space to another.

[`Transform Matrix`](https://developer.apple.com/documentation/shadergraph/math/transform-matrix)

Transforms a vector by a matrix.

[`Transpose`](https://developer.apple.com/documentation/shadergraph/math/transpose)

Outputs the tranpose of a matrix.

[`Determinant`](https://developer.apple.com/documentation/shadergraph/math/determinant)

Outputs the float determinant of a matrix.

[`Invert Matrix`](https://developer.apple.com/documentation/shadergraph/math/invert-matrix)

Outputs the inverse of a matrix.

[`Rotate 2D`](https://developer.apple.com/documentation/shadergraph/math/rotate-2d)

Rotates a Vector2 (Float) about the origin in 2D.

[`Rotate 3D`](https://developer.apple.com/documentation/shadergraph/math/rotate-3d)

Rotates a Vector3 (Float) about a specified unit axis vector.

[`Place 2D`](https://developer.apple.com/documentation/shadergraph/math/place-2d)

Transforms UV texture coordinates for 2D texture placement.

[`Round`](https://developer.apple.com/documentation/shadergraph/math/round)

Rounds to the nearest integer value, per-channel.

[`Safe Power`](https://developer.apple.com/documentation/shadergraph/math/safe-power)

Raises the incoming value to an exponent and assigns the sign of the base to the output.

[`Normal Map`](https://developer.apple.com/documentation/shadergraph/math/normal-map)

Transforms a normal vector from object or tangent space into world space.

[`Fractional (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/fractional-(realitykit))

Returns the fractional part of a floating point number.

[`One Minus (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/one-minus-(realitykit))

Outputs one minus the input.

[`Normal Map Decode`](https://developer.apple.com/documentation/shadergraph/math/normal-map-decode)

Remaps a normal’s value from [0,1] to [-1,1] by applying 2x-1.

[`Max3 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/max3-(realitykit))

Outputs the maximum of three incoming values.

[`Min3 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/min3-(realitykit))

Outputs the minimum of three incoming values.

[`Fractional (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/fractional-(realitykit))

Returns the fractional part of a floating point number.

[`Inverse Hyperbolic Cos`](https://developer.apple.com/documentation/shadergraph/math/inverse-hyperbolic-cos)

The inverse hyperbolic cosine of the incoming value in radians.

[`Inverse Hyperbolic Sin`](https://developer.apple.com/documentation/shadergraph/math/inverse-hyperbolic-sin)

The inverse hyperbolic sine of the incoming value in radians.

[`Atan`](https://developer.apple.com/documentation/shadergraph/math/atan)

The arctangent of the incoming value in radians.

[`Inverse Hyperbolic Tan`](https://developer.apple.com/documentation/shadergraph/math/inverse-hyperbolic-tan)

The hyperbolic arc tangent of the incoming value in radians.

[`Copy Sign (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/copy-sign-(realitykit))

Return x with its sign changed to match the sign of y.

[`Hyperbolic Cos`](https://developer.apple.com/documentation/shadergraph/math/hyperbolic-cos)

The hyperbolic cosine of the incoming value in radians.

[`Cos Pi (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/cos-pi-(realitykit))

Compute cos(πX).

[`Exponential 2 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/exponential-2-(realitykit))

Exponential Base 2 of X.

[`Exponential 10 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/exponential-10-(realitykit))

Exponential Base 10 of X.

### [Subscripts](https://developer.apple.com/documentation/shadergraph/math#Subscripts)

[`Distance (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/distance-(realitykit))

Returns the distance between X and Y.

[`Distance Square (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/distance-square-(realitykit))

Returns the square of the distance between X and Y.

[`Fused Multiply-Add (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/fused-multiply-add-(realitykit))

Returns (A \* B) + C.

[`Hyperbolic Sin`](https://developer.apple.com/documentation/shadergraph/math/hyperbolic-sin)

The hyperbolic sine of the incoming value in radians.

[`Hyperbolic Tan`](https://developer.apple.com/documentation/shadergraph/math/hyperbolic-tan)

The hyperbolic tangent of the incoming value in radians.

[`Log 10`](https://developer.apple.com/documentation/shadergraph/math/log-10)

The log base 10 of the input.

[`Log 2`](https://developer.apple.com/documentation/shadergraph/math/log-2)

The log base 2 of the input.

[`Magnitude Square (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/magnitude-square-(realitykit))

Outputs the float magnitude of a vector, squared.

[`Median3 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/median3-(realitykit))

Returns the middle value of three incoming values.

[`Modulo (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/modulo-(realitykit))

Outputs the remaining fraction after dividing the input by a value and subtracting the integer portion.

[`Reciprocal Square Root (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/reciprocal-square-root-(realitykit))

Computes inverse square root of X.

[`Sin Pi (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/sin-pi-(realitykit))

Compute sin(πX).

[`Tan Pi (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/tan-pi-(realitykit))

Compute tan(πX).

[`Truncate (RealityKit)`](https://developer.apple.com/documentation/shadergraph/math/truncate-(realitykit))

Rounds X to integral value using the round-toward-zero rounding mode.

### [Node Categories](https://developer.apple.com/documentation/shadergraph/math#Node-Categories)

[`2D-Procedural`](https://developer.apple.com/documentation/shadergraph/2d-procedural)

Generate 2D gradients, noise, and other patterns programmatically for your material.

[`2D-Texture`](https://developer.apple.com/documentation/shadergraph/2d-texture)

Load and configure 2D texture files.

[`3D-Procedural`](https://developer.apple.com/documentation/shadergraph/3d-procedural)

Generate 3D noise patterns programmatically for your material.

[`3D-Texture`](https://developer.apple.com/documentation/shadergraph/3d-texture)

Project multiple 2D images onto a surface to create a 3D texture.

[`Adjustment`](https://developer.apple.com/documentation/shadergraph/adjustment)

Modify or convert values, or ranges of values, from one form to another.

[`Application`](https://developer.apple.com/documentation/shadergraph/application)

Get system values such as the current time or the direction of the up vector.

[`Compositing`](https://developer.apple.com/documentation/shadergraph/compositing)

Generate a single output from the combination of multiple data values.

[`Data`](https://developer.apple.com/documentation/shadergraph/data)

Convert data values to different formats, or manipulate individual elements within a data structure.

[`Geometric`](https://developer.apple.com/documentation/shadergraph/geometric)

Access scene geometry while your graph runs.

[`Logic`](https://developer.apple.com/documentation/shadergraph/logic)

Perform Boolean operations and other logical comparisons on data values.

[`Material`](https://developer.apple.com/documentation/shadergraph/material)

Encapsulate a set of shader graph nodes into a single module.

[`Organization`](https://developer.apple.com/documentation/shadergraph/organization)

Modify the visual flow of data within your graph without changing any values.

[`Procedural`](https://developer.apple.com/documentation/shadergraph/procedural)

Add a constant number, vector, matrix, color, string, or other value to your graph.

[`RealityKit`](https://developer.apple.com/documentation/shadergraph/realitykit)

Add RealityKit surfaces or textures to your material and access and manipulate scene geometry.

[`Surface`](https://developer.apple.com/documentation/shadergraph/surface)

Generate a MaterialX preview surface.
