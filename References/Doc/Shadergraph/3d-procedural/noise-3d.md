Source: https://developer.apple.com/documentation/shadergraph/3d-procedural/noise-3d

* [ShaderGraph](https://developer.apple.com/documentation/shadergraph)
* [3D-Procedural](https://developer.apple.com/documentation/shadergraph/3d-procedural)
* Noise 3D

ShaderGraph Node

# Noise 3D

A 3D Perlin noise generator.

iOS 17.0+iPadOS 17.0+Mac Catalyst 17.0+macOS 14.0+tvOS 26.0+visionOS 1.0+

## [Parameter Types](https://developer.apple.com/documentation/shadergraph/3d-procedural/noise-3d#Parameter-Types)

| Input | Type |
| --- | --- |
| `Amplitude` | Float |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Float |

| Input | Type |
| --- | --- |
| `Amplitude` | Float |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `Amplitude` | Float |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Amplitude` | Vector3f |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector3f |

| Input | Type |
| --- | --- |
| `Amplitude` | Vector3f |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Color3 |

| Input | Type |
| --- | --- |
| `Amplitude` | Float |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `Amplitude` | Float |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

| Input | Type |
| --- | --- |
| `Amplitude` | Float |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `Amplitude` | Vector2f |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector2f |

| Input | Type |
| --- | --- |
| `Amplitude` | Vector4f |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Color4 |

| Input | Type |
| --- | --- |
| `Amplitude` | Vector4f |
| `Pivot` | Float |
| `Position` | Vector3f |

| Output | Type |
| --- | --- |
| `Out` | Vector4f |

## [Parameter descriptions](https://developer.apple.com/documentation/shadergraph/3d-procedural/noise-3d#Parameter-descriptions)

`Amplitude`
:   The intensity of the generated noise. The higher the amplitude, the more pronounced the variations of the noise pattern.

`Pivot`
:   The neutral value of the noise. This value is the noise’s minimum value, added to the output after the node multipliess the output by the amplitude.

`Position`
:   The 3D coordinates at which the data is read in order to map the texture onto a surface. The default uses the current 3D object-space coordinates.

## [Discussion](https://developer.apple.com/documentation/shadergraph/3d-procedural/noise-3d#Discussion)

The Noise 3D shader node procedurally generates Perlin noise patterns you can use to add texture and variation to materials. All noise values that are procedurally generated are numbers between `0` and `1` before the amplitude and pivot are applied. Because this node generates noise in 3D, the texture doesn’t repeat in the Z direction, but rather continues as depth changes. Below is an example of a simple node graph that uses the Noise 3D node to generate a black and white pattern procedurally:

![](https://docs-assets.developer.apple.com/published/b8c62b146b40ba2082029f77b5a5af71/Noise3dGraph.png)

Multiply the incoming position with a constant float. The float changes the frequency of the generated noise to a higher number that corresponds with the pattern repeating more often. Below, the resulting texture applies to a cube:

![](https://docs-assets.developer.apple.com/published/b6f5f45d5a71fedd0f03b2c4ee7f1a0d/Noise3dMaterial.png)

### [Nodes](https://developer.apple.com/documentation/shadergraph/3d-procedural/noise-3d#Nodes)

[`Fractal Noise 3D`](https://developer.apple.com/documentation/shadergraph/3d-procedural/fractal-noise-3d)

Zero-centered 3D fractal noise created by summing several octaves of 3D Perlin noise.

[`Cellular Noise 3D`](https://developer.apple.com/documentation/shadergraph/3d-procedural/cellular-noise-3d)

A 3D cellular noise generator.

[`Worley Noise 3D`](https://developer.apple.com/documentation/shadergraph/3d-procedural/worley-noise-3d)

A 3D Worley noise generator.
