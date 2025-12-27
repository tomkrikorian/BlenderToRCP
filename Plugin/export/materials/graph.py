"""
MaterialX graph construction for RealityKit shaders.

Builds node graphs that reference RealityKit nodedefs.
"""

from typing import Any, Dict, List, Optional

from ...manifest.materialx_nodes import select_node_def_for_node


class MaterialXGraphBuilder:
    """Build MaterialX graphs for RealityKit-compatible materials."""

    def __init__(self, manifest: Dict[str, Any], diagnostics=None):
        """Initialize the graph builder.

        Args:
            manifest: MaterialX node manifest.
            diagnostics: Optional ExportDiagnostics instance.
        """
        self.manifest = manifest
        self.diagnostics = diagnostics
        self.node_counter = 0

    def build_pbr_material(self, material_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build a PBR MaterialX graph.

        Args:
            material_data: Material data extracted from Blender.

        Returns:
            MaterialX graph structure.
        """
        graph = {
            'nodes': [],
            'connections': [],
            'output': None,
        }

        pbr_node_id = 'realitykit_pbr_surfaceshader'
        pbr_node_def = self._find_node_def(pbr_node_id)

        if not pbr_node_def:
            raise ValueError(f"PBR node definition not found: {pbr_node_id}")

        pbr_node = self._create_node(
            node_id=pbr_node_id,
            node_name='pbr_surfaceshader',
            inputs=self._map_pbr_inputs(material_data),
        )
        graph['nodes'].append(pbr_node)
        self._apply_graph_inputs(graph, pbr_node['name'], material_data.get('input_graphs', {}))
        graph['output'] = pbr_node['name']

        return graph

    def build_unlit_material(self, material_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build an Unlit MaterialX graph.

        Args:
            material_data: Material data extracted from Blender.

        Returns:
            MaterialX graph structure.
        """
        graph = {
            'nodes': [],
            'connections': [],
            'output': None,
        }

        unlit_node_id = 'realitykit_unlit_surfaceshader'
        unlit_node_def = self._find_node_def(unlit_node_id)

        if not unlit_node_def:
            raise ValueError(f"Unlit node definition not found: {unlit_node_id}")

        unlit_node = self._create_node(
            node_id=unlit_node_id,
            node_name='unlit_surfaceshader',
            inputs=self._map_unlit_inputs(material_data),
        )
        graph['nodes'].append(unlit_node)
        self._apply_graph_inputs(graph, unlit_node['name'], material_data.get('input_graphs', {}))
        graph['output'] = unlit_node['name']

        return graph

    def build_rk_material(self, node_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Build a MaterialX graph from a RealityKit node id and inputs."""
        graph = {
            'nodes': [],
            'connections': [],
            'output': None,
        }

        node_def = self._find_node_def(node_id)
        if not node_def:
            raise ValueError(f"RealityKit node definition not found: {node_id}")

        rk_node = self._create_node(
            node_id=node_id,
            node_name=f"rk_{node_id}",
            inputs=inputs,
        )
        graph['nodes'].append(rk_node)
        graph['output'] = rk_node['name']

        return graph

    def build_rk_graph(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        """Pass through a pre-built RealityKit node graph."""
        if not graph or not graph.get('nodes'):
            raise ValueError("RealityKit graph is empty")
        for node in graph.get('nodes', []):
            node_id = node.get('node_id')
            if not node_id:
                raise ValueError("RealityKit graph node missing node_id")
            if not self._find_node_def(node_id):
                raise ValueError(f"RealityKit node definition not found: {node_id}")
        return graph

    def _find_node_def(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Find a node definition in the manifest."""
        node_def = select_node_def_for_node(self.manifest, node_id)
        if not node_def and isinstance(node_id, str) and node_id.startswith("ND_"):
            node_def = self.manifest.get("nodes", {}).get(node_id)
        return node_def

    def _create_node(self, node_id: str, node_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new node payload with a unique name."""
        self.node_counter += 1
        unique_name = f"{node_name}_{self.node_counter}"

        return {
            'name': unique_name,
            'node_id': node_id,
            'type': 'nodedef',
            'inputs': inputs,
        }

    def _apply_graph_inputs(
        self,
        graph: Dict[str, Any],
        target_node: str,
        graph_inputs: Dict[str, Any],
    ) -> None:
        """Attach expression graphs to inputs on a target node."""
        if not graph_inputs:
            return
        for input_name, expr in graph_inputs.items():
            connection = self._inject_expression(graph, expr, f"{target_node}_{input_name}")
            if not connection:
                continue
            graph['connections'].append(
                {
                    "from_node": connection["node"],
                    "from_output": connection.get("output") or "out",
                    "to_node": target_node,
                    "to_input": input_name,
                }
            )

    def _inject_expression(
        self,
        graph: Dict[str, Any],
        expr: Any,
        name_hint: str,
    ) -> Optional[Dict[str, Any]]:
        """Convert an expression spec into graph nodes/connections."""
        if not isinstance(expr, dict):
            return None
        kind = expr.get("kind")
        if kind == "constant" or kind == "texture":
            return None
        if kind != "node":
            return None

        node_id = expr.get("node_id")
        if not node_id:
            return None

        inputs: Dict[str, Any] = {}
        node = self._create_node(node_id=node_id, node_name=name_hint, inputs=inputs)
        graph['nodes'].append(node)
        node_name = node["name"]

        for input_name, input_expr in (expr.get("inputs") or {}).items():
            if isinstance(input_expr, dict) and input_expr.get("kind") == "node":
                child = self._inject_expression(graph, input_expr, f"{name_hint}_{input_name}")
                if child:
                    graph['connections'].append(
                        {
                            "from_node": child["node"],
                            "from_output": child.get("output") or "out",
                            "to_node": node_name,
                            "to_input": input_name,
                        }
                    )
                continue

            value = self._expression_to_value(input_expr)
            if value is not None:
                node["inputs"][input_name] = value

        return {"node": node_name, "output": expr.get("output") or "out"}

    def _expression_to_value(self, expr: Any) -> Optional[Any]:
        if not isinstance(expr, dict):
            return expr
        kind = expr.get("kind")
        if kind == "constant":
            return expr.get("value")
        if kind == "texture":
            return self._texture_spec_from_expr(expr)
        if kind == "node":
            return None
        return None

    def _texture_spec_from_expr(self, expr: Dict[str, Any]) -> Dict[str, Any]:
        return self._create_texture_input(
            expr.get("path"),
            expr.get("output_type") or "color3",
            channel=expr.get("channel", "rgb"),
            texcoord=expr.get("texcoord") or expr.get("uv_map"),
            mapping=expr.get("mapping"),
            colorspace=expr.get("colorspace"),
            alpha_mode=expr.get("alpha_mode"),
            scale=expr.get("scale"),
        )

    def _map_pbr_inputs(self, material_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Blender Principled BSDF inputs to RealityKit PBR inputs."""
        inputs: Dict[str, Any] = {}

        if 'base_color_texture' in material_data:
            inputs['baseColor'] = self._create_texture_input(
                material_data['base_color_texture'],
                'color3',
                texcoord=material_data.get('base_color_texture_texcoord'),
                mapping=material_data.get('base_color_texture_mapping'),
                colorspace=material_data.get('base_color_texture_colorspace'),
                alpha_mode=material_data.get('base_color_texture_alpha_mode'),
            )
        elif 'base_color' in material_data:
            inputs['baseColor'] = self._convert_color(material_data['base_color'])

        if 'metallic_texture' in material_data:
            inputs['metallic'] = self._create_texture_input(
                material_data['metallic_texture'],
                'float',
                channel=material_data.get('metallic_texture_channel', 'r'),
                texcoord=material_data.get('metallic_texture_texcoord'),
                mapping=material_data.get('metallic_texture_mapping'),
                colorspace=material_data.get('metallic_texture_colorspace'),
                alpha_mode=material_data.get('metallic_texture_alpha_mode'),
            )
        elif 'metallic' in material_data:
            inputs['metallic'] = material_data['metallic']

        if 'roughness_texture' in material_data:
            inputs['roughness'] = self._create_texture_input(
                material_data['roughness_texture'],
                'float',
                channel=material_data.get('roughness_texture_channel', 'g'),
                texcoord=material_data.get('roughness_texture_texcoord'),
                mapping=material_data.get('roughness_texture_mapping'),
                colorspace=material_data.get('roughness_texture_colorspace'),
                alpha_mode=material_data.get('roughness_texture_alpha_mode'),
            )
        elif 'roughness' in material_data:
            inputs['roughness'] = material_data['roughness']

        if 'normal_texture' in material_data:
            inputs['normal'] = self._create_normal_input(
                material_data['normal_texture'],
                texcoord=material_data.get('normal_texture_texcoord'),
                mapping=material_data.get('normal_texture_mapping'),
                colorspace=material_data.get('normal_texture_colorspace'),
                alpha_mode=material_data.get('normal_texture_alpha_mode'),
                scale=material_data.get('normal_texture_scale'),
                space=material_data.get('normal_texture_space'),
            )

        if 'emission_texture' in material_data:
            emission_strength = material_data.get('emission_strength')
            if emission_strength is not None and abs(emission_strength - 1.0) < 1e-4:
                emission_strength = None
            inputs['emissiveColor'] = self._create_texture_input(
                material_data['emission_texture'],
                'color3',
                texcoord=material_data.get('emission_texture_texcoord'),
                mapping=material_data.get('emission_texture_mapping'),
                colorspace=material_data.get('emission_texture_colorspace'),
                alpha_mode=material_data.get('emission_texture_alpha_mode'),
                scale=emission_strength,
            )
        elif 'emission_color' in material_data:
            inputs['emissiveColor'] = self._convert_color(material_data['emission_color'])
        elif 'emission_strength' in material_data and material_data['emission_strength'] > 0:
            base_color = material_data.get('base_color', [1.0, 1.0, 1.0])
            strength = material_data['emission_strength']
            inputs['emissiveColor'] = [c * strength for c in base_color]

        blend_method = material_data.get('blend_method', 'OPAQUE')

        if blend_method != 'OPAQUE' and 'alpha_texture' in material_data:
            inputs['opacity'] = self._create_texture_input(
                material_data['alpha_texture'],
                'float',
                channel=material_data.get('alpha_texture_channel', 'a'),
                texcoord=material_data.get('alpha_texture_texcoord'),
                mapping=material_data.get('alpha_texture_mapping'),
                colorspace=material_data.get('alpha_texture_colorspace'),
                alpha_mode=material_data.get('alpha_texture_alpha_mode'),
            )
        elif blend_method != 'OPAQUE' and 'alpha' in material_data:
            inputs['opacity'] = material_data['alpha']

        if 'alpha_threshold' in material_data:
            inputs['opacityThreshold'] = material_data['alpha_threshold']

        if 'ao_texture' in material_data:
            inputs['ambientOcclusion'] = self._create_texture_input(
                material_data['ao_texture'],
                'float',
                channel=material_data.get('ao_texture_channel', 'r'),
                texcoord=material_data.get('ao_texture_texcoord'),
                mapping=material_data.get('ao_texture_mapping'),
                colorspace=material_data.get('ao_texture_colorspace'),
                alpha_mode=material_data.get('ao_texture_alpha_mode'),
            )

        if 'clearcoat' in material_data:
            inputs['clearcoat'] = material_data['clearcoat']
            if 'clearcoat_roughness' in material_data:
                inputs['clearcoatRoughness'] = material_data['clearcoat_roughness']
            if 'clearcoat_normal_texture' in material_data:
                inputs['clearcoatNormal'] = self._create_normal_input(
                    material_data['clearcoat_normal_texture'],
                    texcoord=material_data.get('clearcoat_normal_texture_texcoord'),
                    mapping=material_data.get('clearcoat_normal_texture_mapping'),
                    colorspace=material_data.get('clearcoat_normal_texture_colorspace'),
                    alpha_mode=material_data.get('clearcoat_normal_texture_alpha_mode'),
                    scale=material_data.get('clearcoat_normal_texture_scale'),
                    space=material_data.get('clearcoat_normal_texture_space'),
                )

        if 'specular' in material_data:
            inputs['specular'] = material_data['specular']
        else:
            inputs['specular'] = 0.5

        if material_data.get('has_premultiplied_alpha'):
            inputs['hasPremultipliedAlpha'] = True

        return inputs

    def _map_unlit_inputs(self, material_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Blender material inputs to RealityKit Unlit inputs."""
        inputs: Dict[str, Any] = {}

        if 'base_color_texture' in material_data:
            inputs['color'] = self._create_texture_input(
                material_data['base_color_texture'],
                'color3',
                texcoord=material_data.get('base_color_texture_texcoord'),
                mapping=material_data.get('base_color_texture_mapping'),
                colorspace=material_data.get('base_color_texture_colorspace'),
                alpha_mode=material_data.get('base_color_texture_alpha_mode'),
            )
        elif 'base_color' in material_data:
            inputs['color'] = self._convert_color(material_data['base_color'])

        blend_method = material_data.get('blend_method', 'OPAQUE')

        if blend_method != 'OPAQUE' and 'alpha_texture' in material_data:
            inputs['opacity'] = self._create_texture_input(
                material_data['alpha_texture'],
                'float',
                channel=material_data.get('alpha_texture_channel', 'a'),
                texcoord=material_data.get('alpha_texture_texcoord'),
                mapping=material_data.get('alpha_texture_mapping'),
                colorspace=material_data.get('alpha_texture_colorspace'),
                alpha_mode=material_data.get('alpha_texture_alpha_mode'),
            )
        elif blend_method != 'OPAQUE' and 'alpha' in material_data:
            inputs['opacity'] = material_data['alpha']

        if 'alpha_threshold' in material_data:
            inputs['opacityThreshold'] = material_data['alpha_threshold']

        if material_data.get('has_premultiplied_alpha'):
            inputs['hasPremultipliedAlpha'] = True

        return inputs

    def _convert_color(self, color: Any) -> List[float]:
        """Convert a color value to a 3-float list."""
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            return [float(color[0]), float(color[1]), float(color[2])]
        return [1.0, 1.0, 1.0]

    def _create_texture_input(
        self,
        texture_path: str,
        output_type: str,
        channel: str = 'rgb',
        texcoord: Optional[str] = None,
        mapping: Optional[Dict[str, Any]] = None,
        colorspace: Optional[str] = None,
        alpha_mode: Optional[str] = None,
        scale: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Create a texture reference for the USD post-process stage."""
        spec = {
            'type': 'texture',
            'path': texture_path,
            'output_type': output_type,
            'channel': channel,
        }
        if texcoord:
            spec['texcoord'] = texcoord
        if mapping:
            spec['mapping'] = mapping
        if colorspace:
            spec['colorspace'] = colorspace
        if alpha_mode:
            spec['alpha_mode'] = alpha_mode
        if scale is not None:
            spec['scale'] = scale
        return spec

    def _create_normal_input(
        self,
        texture_path: str,
        texcoord: Optional[str] = None,
        mapping: Optional[Dict[str, Any]] = None,
        colorspace: Optional[str] = None,
        alpha_mode: Optional[str] = None,
        scale: Optional[float] = None,
        space: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a normal map reference for the USD post-process stage."""
        spec = {
            'type': 'normal_texture',
            'path': texture_path,
            'output_type': 'vector3',
        }
        if texcoord:
            spec['texcoord'] = texcoord
        if mapping:
            spec['mapping'] = mapping
        if colorspace:
            spec['colorspace'] = colorspace
        if alpha_mode:
            spec['alpha_mode'] = alpha_mode
        if scale is not None:
            spec['scale'] = scale
        if space:
            spec['space'] = space
        return spec
