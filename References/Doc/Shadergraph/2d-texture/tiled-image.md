Source: https://developer.apple.com/documentation/shadergraph/2d-texture/tiled-image

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [2D-Texture](https://developer.apple.com/documentation/shadergraph/2d-texture)
* Tiled Image

ShaderGraph Node

# Tiled Image

Samples data from an image with provisions for offsetting and tiling in UV space.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/2d-texture/tiled-image#Parameter-Types)

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `Default` | Float |
| `Texture Coordinates` | Vector2f |
| `UV Tiling` | Vector2f |
| `UV Offset` | Vector2f |
| `Real World Image Size` | Vector2f |
| `Real World Tile Size` | Vector2f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `Default` | Vector4f |
| `Texture Coordinates` | Vector2f |
| `UV Tiling` | Vector2f |
| `UV Offset` | Vector2f |
| `Real World Image Size` | Vector2f |
| `Real World Tile Size` | Vector2f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `Default` | Color4 |
| `Texture Coordinates` | Vector2f |
| `UV Tiling` | Vector2f |
| `UV Offset` | Vector2f |
| `Real World Image Size` | Vector2f |
| `Real World Tile Size` | Vector2f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `Default` | Vector3f |
| `Texture Coordinates` | Vector2f |
| `UV Tiling` | Vector2f |
| `UV Offset` | Vector2f |
| `Real World Image Size` | Vector2f |
| `Real World Tile Size` | Vector2f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `Default` | Vector2f |
| `Texture Coordinates` | Vector2f |
| `UV Tiling` | Vector2f |
| `UV Offset` | Vector2f |
| `Real World Image Size` | Vector2f |
| `Real World Tile Size` | Vector2f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `Default` | Color3 |
| `Texture Coordinates` | Vector2f |
| `UV Tiling` | Vector2f |
| `UV Offset` | Vector2f |
| `Real World Image Size` | Vector2f |
| `Real World Tile Size` | Vector2f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `File` | AssetPath |
| `Default` | Half |
| `Texture Coordinates` | Vector2f |
| `UV Tiling` | Vector2f |
| `UV Offset` | Vector2f |
| `Real World Image Size` | Vector2f |
| `Real World Tile Size` | Vector2f |
| `Filter Type` | String |

| Output | Type |
| --- | --- |
| `Out` | Half |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/2d-texture/tiled-image#Parameter-descriptions)

`File`
:   The image file to use for the texture.

`Default`
:   A default value to use if the ​file​ reference fails to resolve.

`Texture Coordinates`
:   The 2D coordinate at which the data is read for mapping the texture onto a surface. The default uses the current UV coordinates, in which U is the horizontal axis and V is the vertical axis.

`UV Tiling`
:   The tiling rate for the given image along the U and V axes. The tiling rate is mathematically equivalent to multiplying the incoming texture coordinates by the given vector value. The rate controls how often the `File` repeats in the texture.

`UV Offset`
:   The offset for the given image along the U and V axes. The offset is mathematically equivalent to subtracting the given vector value from the incoming texture coordinates.

`Real World Image Size`
:   The real-world size represented by the ​file​ image.

`Real World Tile Size`
:   The real-world size of a single square `0-1` UV tile.

`Filter Type`
:   The type of texture filtering to use.

## [Discussion](https://developer.apple.com/documentation/shadergraph/2d-texture/tiled-image#Discussion)

The `Tiled Image` material node maps a texture onto a surface with a repeating tiled pattern. It allows you to specify a texture image and control its tiling and real-world size properties.

The `UV Tiling` parameter repeats the given file input to produce an image. The `Real World Image Size` parameter determines the image’s size. The resulting image is then applied to a single square 0-1 UV tile. The `Real World Tile Size` parameter determines the size of this tile. The size of the tile and the size of the image may differ. If the image size is larger than the tile it wants to be applied to, the resulting texture only shows part of the image. If the size of the tile is larger than the image, the image repeats in the resulting texture.

Note

If your goal is to repeat the image, use the `UV Tiling` parameter. While you can create a repeating texture by using the `Real World Image Size` and `Real World Tile Size` parameters, use the size parameters to model real-world dimensions of the image and the surface that it’s applied to.

Below is an example of a simple node graph that uses the Tiled Image node:

![nil](https://docs-assets.developer.apple.com/published/b1e7815b71b078c16fab9f0895dff0c2/TiledImage1.png)

If the `UV Tiling` parameter is `(2,2)`, the pattern repeats twice horizontally and twice vertically:

![nil](https://docs-assets.developer.apple.com/published/4852a827f845f57e396ff75ac1dad7b8/TiledImage2.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/2d-texture/tiled-image#Nodes)

[`Image`](https://developer.apple.com/documentation/shadergraph/2d-texture/image)

A texture referencing a 2D image file.

[`UV Texture`](https://developer.apple.com/documentation/shadergraph/2d-texture/uv-texture)

A MaterialX version of USD UV Texture reader.

[`Transform 2D`](https://developer.apple.com/documentation/shadergraph/2d-texture/transform-2d)

A node that applies an affine transformation to a 2d input.
