Source: https://developer.apple.com/documentation/shadergraph/realitykit

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* RealityKit

ShaderGraph Node Group

# RealityKit

Add RealityKit surfaces or textures to your material and access and manipulate scene geometry.

## [Overview](https://developer.apple.com/documentation/shadergraph/realitykit#overview)

Incorporate RealityKit-specific content into your graph and modify that content visually. You can use geometry modifiers to change the vertices of your models. You can also create and configure RealityKit surfaces and textures and use them in your graph.

### [Nodes](https://developer.apple.com/documentation/shadergraph/realitykit#Nodes)

[`Unlit Surface (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/unlit-surface-(realitykit))

A surface shader that defines properties for a RealityKit Unlit material.

[`PBR Surface (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/pbr-surface-(realitykit))

A surface shader that defines properties for a RealityKit Physically Based Rendering material.

[`Occlusion Surface (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/occlusion-surface-(realitykit))

A surface shader that defines properties for a RealityKit Occlusion material that does not receive dynamic lighting.

[`Shadow Receiving Occlusion Surface (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/shadow-receiving-occlusion-surface-(realitykit))

A surface shader that defines properties for a RealityKit Occlusion material that receives dynamic lighting.

[`View Direction (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/view-direction-(realitykit))

A vector from a position in the scene to the view reference point.

[`Camera Position (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/camera-position-(realitykit))

The position of the camera in the scene.

[`Geometry Modifier Model To World (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-model-to-world-(realitykit))

The model-to-world transformation Matrix4x4 (Float).

[`Geometry Modifier World To Model (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-world-to-model-(realitykit))

The world-to-model transformation Matrix4x4 (Float).

[`Geometry Modifier Normal To World (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-normal-to-world-(realitykit))

The normal-to-world transformation Matrix3x3 (Float).

[`Geometry Modifier Model To View (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-model-to-view-(realitykit))

The model-to-view transformation Matrix4x4 (Float).

[`Geometry Modifier View To Projection (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-view-to-projection-(realitykit))

The view-to-projection transformation Matrix4x4 (Float).

[`Geometry Modifier Projection To View (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-projection-to-view-(realitykit))

The projection-to-view transformation Matrix4x4 (Float).

[`Geometry Modifier Vertex ID (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-vertex-id-(realitykit))

The integer index of the vertex.

[`Surface Model To World (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-model-to-world-(realitykit))

The model-to-world transformation Matrix4x4 (Float).

[`Surface Model To View (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-model-to-view-(realitykit))

The model-to-view transformation Matrix4x4 (Float).

[`Surface World To View (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-world-to-view-(realitykit))

The world-to-view transformation Matrix4x4 (Float).

[`Surface View To Projection (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-view-to-projection-(realitykit))

The view-to-projection transformation Matrix4x4 (Float).

[`Surface Projection To View (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-projection-to-view-(realitykit))

The projection-to-view transformation Matrix4x4 (Float).

[`Surface Screen Position (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-screen-position-(realitykit))

The coordinates of the currently-processed data in screen space.

[`Surface View Direction (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/surface-view-direction-(realitykit))

A vector from a position in the scene to the view reference point.

[`Environment Radiance (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/environment-radiance-(realitykit))

Returns an environment’s diffuse and specular radiance value based on real-world environment, and an IBL map that is either a developer-provided map or a default map.

[`Hover State (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/hover-state-(realitykit))

Hover State to define custom hover effects.

[`Blurred Background (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/blurred-background-(realitykit))

Returns a sample of the blurred background.

[`Geometry Modifier (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/geometry-modifier-(realitykit))

A function that manipulates the location of a model’s vertices, run once per vertex.

[`Camera Index Switch (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/camera-index-switch-(realitykit))

Render different results for each eye in a stereoscopic render.

[`Image 2D (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-(realitykit))

A texture with RealityKit properties.

[`Image 2D LOD (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-lod-(realitykit))

A texture with RealityKit properties and a explicit level of detail.

[`Image 2D Gradient (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-gradient-(realitykit))

A texture with RealityKit properties and a specified LOD gradient.

[`Image 2D Pixel (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-pixel-(realitykit))

A texture with RealityKit properties and pixel texture coordinates.

[`Image 2D LOD Pixel (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-lod-pixel-(realitykit))

A texture with RealityKit properties, a explicit level of detail, and pixel texture coordinates.

[`Image 2D Gradient Pixel (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-gradient-pixel-(realitykit))

A texture with RealityKit properties, a specified LOD gradient, and pixel texture coordinates.

[`Cube Image (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/cube-image-(realitykit))

A texturecube with RealityKit properties.

[`Cube Image LOD (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/cube-image-lod-(realitykit))

A texturecube with RealityKit properties and a explicit level of detail.

[`Cube Image Gradient (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/cube-image-gradient-(realitykit))

A texturecube with RealityKit properties and a specified LOD gradient.

[`Image 2D Read (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-read-(realitykit))

Direct texture read.

[`Image 3D (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-(realitykit))

A texture with RealityKit properties.

[`Image 3D LOD (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-lod-(realitykit))

A texture with RealityKit properties.

[`Image 3D Gradient (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-gradient-(realitykit))

A texture with RealityKit properties.

[`Image 3D Pixel (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-pixel-(realitykit))

A texture with RealityKit properties.

[`Image 3D LOD Pixel (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-lod-pixel-(realitykit))

A texture with RealityKit properties.

[`Image 3D Gradient Pixel (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-gradient-pixel-(realitykit))

A texture with RealityKit properties.

[`Image 2D Array (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-array-(realitykit))

A texture with RealityKit properties.

[`Image 2D Array LOD (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-array-lod-(realitykit))

A texture with RealityKit properties.

[`Image 2D Array Gradient (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-array-gradient-(realitykit))

A texture with RealityKit properties.

[`Image 2D Array Pixel (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-array-pixel-(realitykit))

A texture with RealityKit properties.

[`Image 2D Array LOD Pixel (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-array-lod-pixel-(realitykit))

A texture with RealityKit properties.

[`Image 2D Array Gradient Pixel (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-array-gradient-pixel-(realitykit))

A texture with RealityKit properties.

[`Image 2D Array Read (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-2d-array-read-(realitykit))

Direct texture read.

[`Image 3D Read (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/image-3d-read-(realitykit))

Direct texture read.

[`Screen-Space X Partial Derivative (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/screen-space-x-partial-derivative-(realitykit))

Returns a high-precision partial derivative of the specified value with respect to the screen space X coordinate.

[`Screen-Space Y Partial Derivative (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/screen-space-y-partial-derivative-(realitykit))

Returns a high-precision partial derivative of the specified value with respect to the screen space Y coordinate.

[`Absolute Derivatives Sum (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/absolute-derivatives-sum-(realitykit))

Returns the sum of the absolute derivatives in X and Y using local differencing for p; that is, fabs(dfdx(p)) + fabs(dfdy(p)).

[`Power Positive (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/power-positive-(realitykit))

Computes X to the power of Y, where X is >= 0.

[`Round Integral (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/round-integral-(realitykit))

Rounds X to integral value using round ties to even rounding mode in floating-point format.

[`Reflection Diffuse (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/reflection-diffuse-(realitykit))

Diffuse component of reflection.

[`Reflection Specular (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/reflection-specular-(realitykit))

Specular component of reflection.

[`Fortran Difference and Minimum (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/fortran-difference-and-minimum-(realitykit))

Returns X – Y if X > Y, or +0 if X <= Y.

[`Is Finite (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/is-finite-(realitykit))

Returns true if the incoming value is finite.

[`Is Infinite (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/is-infinite-(realitykit))

Returns true if the incoming value is infinite.

[`Is Not a Number (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/is-not-a-number-(realitykit))

Returns true if the incoming value is a not a number (NaN).

[`Is Normal (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/is-normal-(realitykit))

Test if the incoming value is a normalized floating-point value.

[`Is Ordered (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/is-ordered-(realitykit))

Test if arguments are ordered.

[`Is Unordered (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/is-unordered-(realitykit))

Test if arguments are unordered.

[`Sign Bit (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/sign-bit-(realitykit))

Tests for sign bit.

### [Subscripts](https://developer.apple.com/documentation/shadergraph/realitykit#Subscripts)

[`Multiply 24 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-24-(realitykit))

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result.

[`Multiply Add 24 (RealityKit)`](https://developer.apple.com/documentation/shadergraph/realitykit/multiply-add-24-(realitykit))

Multiplies two 24-bit integer values X and Y and returns the 32-bit integer result with 32-bit Z value added.

### [Node Categories](https://developer.apple.com/documentation/shadergraph/realitykit#Node-Categories)

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

[`Math`](https://developer.apple.com/documentation/shadergraph/math)

Perform a wide variety of mathematical and transformative operations on data values.

[`Organization`](https://developer.apple.com/documentation/shadergraph/organization)

Modify the visual flow of data within your graph without changing any values.

[`Procedural`](https://developer.apple.com/documentation/shadergraph/procedural)

Add a constant number, vector, matrix, color, string, or other value to your graph.

[`Surface`](https://developer.apple.com/documentation/shadergraph/surface)

Generate a MaterialX preview surface.
