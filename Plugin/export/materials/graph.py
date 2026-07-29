"""
MaterialX graph construction for RealityKit shaders.

Builds node graphs that reference RealityKit nodedefs.
"""

from typing import Any, Dict, List, Optional

from ...manifest.materialx_nodes import select_node_def_for_node


RCP3_PBR2_NODEDEF = "ND_realitykit_pbr_surfaceshader_2_0"
OPENPBR_1_1_NODEDEF = "ND_open_pbr_surface_surfaceshader"
PORTABLE_REALITYKIT_PBR_NODEDEF = "ND_realitykit_pbr_surfaceshader"

_PROFILE_PORTABLE = "realitykit_portable"
_PROFILE_RCP3 = "realitykit_pbr2"
_PROFILE_OPENPBR = "openpbr_1_1"

PBR2_EXPERIMENTAL_RUNTIME_WARNING = (
    "RealityKit PBR Surface 2 is experimental. Mandatory strict USD/USDZ "
    "validation remains enabled for this profile."
)

_COLOR_TEXTURE_INPUTS = {
    "color",
    "baseColor",
    "emissiveColor",
    "subsurfaceColor",
    "sheenColor",
    "specularColor",
    "base_color",
    "emission_color",
    "subsurface_color",
    "fuzz_color",
    "specular_color",
    "coat_color",
}


def material_profile_runtime_warnings(surface_profile: str) -> tuple[str, ...]:
    """Return user-facing compatibility warnings for an explicit profile."""
    requested = (surface_profile or _PROFILE_PORTABLE).strip().lower()
    if requested == _PROFILE_RCP3:
        return (PBR2_EXPERIMENTAL_RUNTIME_WARNING,)
    return ()


class MaterialXGraphBuilder:
    """Build MaterialX graphs for RealityKit-compatible materials."""

    def __init__(
        self,
        manifest: Dict[str, Any],
        diagnostics=None,
        surface_profile: str = _PROFILE_PORTABLE,
    ):
        """Initialize the graph builder.

        Args:
            manifest: MaterialX node manifest.
            diagnostics: Optional ExportDiagnostics instance.
        """
        self.manifest = manifest
        self.diagnostics = diagnostics
        self.node_counter = 0
        self.surface_profile = surface_profile

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

        pbr_node_id, profile, materialx_version = self._select_surface_profile()
        pbr_node_def = self._find_node_def(pbr_node_id)

        if not pbr_node_def:
            raise ValueError(f"PBR node definition not found: {pbr_node_id}")

        pbr_inputs = self._map_pbr_inputs(material_data, profile)
        pbr_node = self._create_node(
            node_id=pbr_node_id,
            node_name='pbr_surfaceshader',
            inputs=pbr_inputs,
        )
        graph['nodes'].append(pbr_node)
        profile_graphs = self._profile_input_graphs(
            material_data.get('input_graphs', {}),
            profile,
            material_data,
        )
        if (
            profile == _PROFILE_OPENPBR
            and 'emission_color' in profile_graphs
            and 'emission_luminance' not in pbr_node['inputs']
        ):
            pbr_node['inputs']['emission_luminance'] = 1.0

        if profile == _PROFILE_OPENPBR:
            weight_name, color_name, base_name = (
                'subsurface_weight',
                'subsurface_color',
                'base_color',
            )
        else:
            weight_name, color_name, base_name = (
                'subsurfaceWeight',
                'subsurfaceColor',
                'baseColor',
            )
        has_subsurface = weight_name in pbr_inputs or weight_name in profile_graphs
        if has_subsurface and color_name not in pbr_inputs and color_name not in profile_graphs:
            if base_name in profile_graphs:
                profile_graphs = dict(profile_graphs)
                profile_graphs[color_name] = profile_graphs[base_name]
            elif base_name in pbr_inputs:
                pbr_node['inputs'][color_name] = pbr_inputs[base_name]
        self._apply_graph_inputs(
            graph,
            pbr_node['name'],
            profile_graphs,
        )
        graph['output'] = pbr_node['name']
        graph['surface_profile'] = profile
        graph['materialx_version'] = materialx_version

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
        # Filter, don't pass through. input_graphs is keyed for the PBR surface
        # (roughness, metallic, _emissionColor, ...); the unlit surface exposes
        # none of those. Authoring them anyway produced a shader prim carrying
        # inputs the nodedef does not declare - author.py records an error for
        # each but does not raise, so the rewrite never rolled back and the
        # export died later with an opaque diagnostics-gate message.
        self._apply_graph_inputs(
            graph,
            unlit_node['name'],
            self._unlit_input_graphs(
                material_data.get('input_graphs', {}), unlit_node_def
            ),
        )
        graph['output'] = unlit_node['name']
        graph['surface_profile'] = "realitykit_unlit"
        graph['materialx_version'] = "1.38"

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
        graph['surface_profile'] = "realitykit_custom"
        graph['materialx_version'] = self.manifest.get('metadata', {}).get(
            'materialx_version',
            '1.39',
        )

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
        graph = dict(graph)
        graph.setdefault('surface_profile', "realitykit_custom")
        graph.setdefault(
            'materialx_version',
            self.manifest.get('metadata', {}).get('materialx_version', '1.39'),
        )
        return graph

    def _find_node_def(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Find a node definition in the manifest."""
        node_def = select_node_def_for_node(self.manifest, node_id)
        if not node_def and isinstance(node_id, str) and node_id.startswith("ND_"):
            node_def = self.manifest.get("nodes", {}).get(node_id)
        return node_def

    def _declared_input_names(self, node_def: Optional[Dict[str, Any]]) -> set:
        """Return the input names a nodedef actually declares."""
        return {
            entry.get('name')
            for entry in ((node_def or {}).get('inputs') or [])
            if entry.get('name')
        }

    def _select_surface_profile(self):
        """Select an explicit, versioned surface contract.

        The verified RealityKit PBR graph remains the shipping default.
        PBR2 and OpenPBR are explicit, capability-gated enrichments until
        their complete export and runtime contracts are validated.
        """
        requested = (self.surface_profile or _PROFILE_PORTABLE).strip().lower()
        has_portable = bool(
            self.manifest.get("nodes", {}).get(PORTABLE_REALITYKIT_PBR_NODEDEF)
        )
        has_pbr2 = bool(self.manifest.get("nodes", {}).get(RCP3_PBR2_NODEDEF))
        has_openpbr = bool(self.manifest.get("nodes", {}).get(OPENPBR_1_1_NODEDEF))

        if requested == _PROFILE_PORTABLE:
            if not has_portable:
                raise ValueError("Portable RealityKit PBR nodedef is not available")
            return PORTABLE_REALITYKIT_PBR_NODEDEF, _PROFILE_PORTABLE, "1.38"
        if requested == _PROFILE_OPENPBR:
            if not has_openpbr:
                raise ValueError("OpenPBR 1.1 nodedef is not available in the MaterialX manifest")
            return OPENPBR_1_1_NODEDEF, _PROFILE_OPENPBR, "1.39"
        if requested != _PROFILE_RCP3:
            raise ValueError(f"Unknown MaterialX surface profile: {self.surface_profile}")
        if has_pbr2:
            return RCP3_PBR2_NODEDEF, _PROFILE_RCP3, "1.38"
        raise ValueError(
            "RealityKit PBR Surface 2 was explicitly selected but its exact OS 27 nodedef "
            "is unavailable; refusing to switch shading models silently"
        )

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
        target = next(
            (node for node in graph.get('nodes', []) if node.get('name') == target_node),
            None,
        )
        for input_name, expr in graph_inputs.items():
            texture_role = "color" if input_name in _COLOR_TEXTURE_INPUTS else "data"
            if isinstance(expr, dict) and expr.get("kind") in {"constant", "texture"}:
                value = self._expression_to_value(expr, texture_role=texture_role)
                if target is not None and value is not None:
                    target.setdefault('inputs', {})[input_name] = value
                continue
            connection = self._inject_expression(
                graph,
                expr,
                f"{target_node}_{input_name}",
                texture_role=texture_role,
            )
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
        texture_role: Optional[str] = None,
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
                child = self._inject_expression(
                    graph,
                    input_expr,
                    f"{name_hint}_{input_name}",
                    texture_role=texture_role,
                )
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

            value = self._expression_to_value(input_expr, texture_role=texture_role)
            if value is not None:
                node["inputs"][input_name] = value

        return {"node": node_name, "output": expr.get("output") or "out"}

    def _expression_to_value(
        self,
        expr: Any,
        texture_role: Optional[str] = None,
    ) -> Optional[Any]:
        if not isinstance(expr, dict):
            return expr
        kind = expr.get("kind")
        if kind == "constant":
            return expr.get("value")
        if kind == "texture":
            return self._texture_spec_from_expr(expr, texture_role=texture_role)
        if kind == "node":
            return None
        return None

    def _texture_spec_from_expr(
        self,
        expr: Dict[str, Any],
        texture_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._create_texture_input(
            expr.get("path"),
            expr.get("output_type") or "color3",
            channel=expr.get("channel", "rgb"),
            texcoord=expr.get("texcoord") or expr.get("uv_map"),
            mapping=expr.get("mapping"),
            colorspace=expr.get("colorspace"),
            alpha_mode=expr.get("alpha_mode"),
            scale=expr.get("scale"),
            texture_role=expr.get("colorspace_role") or texture_role,
            normal_decode=expr.get("normal_decode"),
        )

    def _map_pbr_inputs(
        self,
        material_data: Dict[str, Any],
        profile: str = _PROFILE_RCP3,
    ) -> Dict[str, Any]:
        """Map Blender Principled BSDF inputs to RealityKit PBR inputs."""
        if profile == _PROFILE_OPENPBR:
            return self._map_openpbr_inputs(material_data)
        if profile == _PROFILE_PORTABLE:
            return self._map_realitykit_portable_inputs(material_data)
        return self._map_realitykit_pbr2_inputs(material_data)

    def _map_realitykit_pbr2_inputs(self, material_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Blender Principled BSDF inputs to RealityKit PBR Surface 2."""
        inputs: Dict[str, Any] = {}

        if 'base_color_texture' in material_data:
            inputs['baseColor'] = self._create_texture_input(
                material_data['base_color_texture'],
                'color3',
                texcoord=material_data.get('base_color_texture_texcoord'),
                mapping=material_data.get('base_color_texture_mapping'),
                colorspace=material_data.get('base_color_texture_colorspace'),
                alpha_mode=material_data.get('base_color_texture_alpha_mode'),
                texture_role='color',
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
                texture_role='data',
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
                texture_role='data',
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
                texture_role='color',
            )
        elif 'emission_color' in material_data:
            strength = float(material_data.get('emission_strength', 1.0))
            inputs['emissiveColor'] = [
                component * strength
                for component in self._convert_color(material_data['emission_color'])
            ]

        is_transparent = material_data.get('is_transparent', False)

        if is_transparent and 'alpha_texture' in material_data:
            inputs['opacity'] = self._create_texture_input(
                material_data['alpha_texture'],
                'float',
                channel=material_data.get('alpha_texture_channel', 'a'),
                texcoord=material_data.get('alpha_texture_texcoord'),
                mapping=material_data.get('alpha_texture_mapping'),
                colorspace=material_data.get('alpha_texture_colorspace'),
                alpha_mode=material_data.get('alpha_texture_alpha_mode'),
                texture_role='data',
            )
        elif is_transparent and 'alpha' in material_data:
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
                texture_role='data',
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

        # RealityKit PBR Surface 2 / Blender 5.2 Principled additions.
        pbr2_fields = {
            'diffuse_roughness': 'baseDiffuseRoughness',
            'subsurface_weight': 'subsurfaceWeight',
            'subsurface_radius': 'subsurfaceRadius',
            'subsurface_radius_scale': 'subsurfaceRadiusScale',
            'subsurface_anisotropy': 'subsurfaceScatterAnisotropy',
            'sheen_color': 'sheenColor',
            'clearcoat_ior': 'clearcoatIOR',
            'clearcoat_anisotropy': 'clearcoatAnisotropyLevel',
            'clearcoat_anisotropy_rotation': 'clearcoatAnisotropyAngle',
            'ior': 'specularIOR',
            'anisotropic': 'specularAnisotropyLevel',
            'anisotropic_rotation': 'specularAnisotropyAngle',
            'specular_tint': 'specularColor',
            'specular_weight': 'specularWeight',
        }
        for source_name, target_name in pbr2_fields.items():
            if source_name in material_data:
                value = material_data[source_name]
                if target_name in {'subsurfaceRadiusScale', 'sheenColor', 'specularColor'}:
                    value = self._convert_color(value)
                inputs[target_name] = value

        if 'subsurfaceWeight' in inputs:
            if 'baseColor' in inputs and 'subsurfaceColor' not in inputs:
                inputs['subsurfaceColor'] = inputs['baseColor']
            elif 'base_color' in material_data and 'subsurfaceColor' not in inputs:
                inputs['subsurfaceColor'] = self._convert_color(material_data['base_color'])

        if material_data.get('has_premultiplied_alpha'):
            inputs['hasPremultipliedAlpha'] = True

        return inputs

    def _map_realitykit_portable_inputs(self, material_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return the beta-safe RealityKit PBR v1 subset used for shipping."""
        pbr2 = self._map_realitykit_pbr2_inputs(material_data)
        supported = {
            'baseColor',
            'emissiveColor',
            'normal',
            'roughness',
            'metallic',
            'ambientOcclusion',
            'specular',
            'opacity',
            'opacityThreshold',
            'clearcoat',
            'clearcoatRoughness',
            'clearcoatNormal',
            'hasPremultipliedAlpha',
        }
        return {name: value for name, value in pbr2.items() if name in supported}

    def _map_openpbr_inputs(self, material_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map the same Principled payload to the explicit OpenPBR 1.1 fallback."""
        pbr2 = self._map_realitykit_pbr2_inputs(material_data)
        result: Dict[str, Any] = {'base_weight': 1.0}
        rename = {
            'baseColor': 'base_color',
            'baseDiffuseRoughness': 'base_diffuse_roughness',
            'metallic': 'base_metalness',
            'roughness': 'specular_roughness',
            'specularIOR': 'specular_ior',
            'specularAnisotropyLevel': 'specular_roughness_anisotropy',
            'specularColor': 'specular_color',
            'specularWeight': 'specular_weight',
            'normal': 'geometry_normal',
            'opacity': 'geometry_opacity',
            'clearcoat': 'coat_weight',
            'clearcoatRoughness': 'coat_roughness',
            'clearcoatNormal': 'geometry_coat_normal',
            'clearcoatIOR': 'coat_ior',
            'clearcoatAnisotropyLevel': 'coat_roughness_anisotropy',
            'subsurfaceWeight': 'subsurface_weight',
            'subsurfaceColor': 'subsurface_color',
            'subsurfaceRadius': 'subsurface_radius',
            'subsurfaceRadiusScale': 'subsurface_radius_scale',
            'subsurfaceScatterAnisotropy': 'subsurface_scatter_anisotropy',
            'emissiveColor': 'emission_color',
        }
        for source_name, target_name in rename.items():
            if source_name in pbr2:
                value = pbr2[source_name]
                if source_name in {'normal', 'clearcoatNormal'} and isinstance(value, dict):
                    value = dict(value)
                    if (value.get('space') or 'tangent').strip().lower() not in {
                        '',
                        'tangent',
                    }:
                        raise ValueError(
                            "OpenPBR geometry normals require a tangent-space normal map; "
                            "bake object-space normals before export"
                        )
                    value['normal_decode'] = 'materialx'
                result[target_name] = value

        if 'emissiveColor' in pbr2:
            # The extracted emissive color already contains Blender's strength.
            result['emission_luminance'] = 1.0
        if 'sheen_weight' in material_data:
            result['fuzz_weight'] = material_data['sheen_weight']
        if 'sheen_tint' in material_data:
            result['fuzz_color'] = self._convert_color(material_data['sheen_tint'])
        if 'sheen_roughness' in material_data:
            result['fuzz_roughness'] = material_data['sheen_roughness']
        if 'clearcoat_tint' in material_data:
            result['coat_color'] = self._convert_color(material_data['clearcoat_tint'])

        self._report_openpbr_omissions(pbr2, rename, result)
        return result

    def _report_openpbr_omissions(
        self,
        pbr2: Dict[str, Any],
        rename: Dict[str, str],
        result: Dict[str, Any],
    ) -> None:
        """Refuse or report every PBR2 input OpenPBR 1.1 cannot carry.

        The rename table is a whitelist, so anything missing from it used to
        disappear without a trace. What survives the surface is decided by the
        nodedef rather than a second hard-coded list so the two cannot drift.
        """
        # A cutout threshold only exists because the scene set
        # blender_to_rcp_alpha_cutout_threshold; the exporter never infers one.
        # OpenPBR has no clip, so carrying on would quietly ship alpha blending
        # in place of the rendering model that was explicitly asked for.
        if 'opacityThreshold' in pbr2:
            raise ValueError(
                "OpenPBR 1.1 has no alpha-cutout input; clear "
                "blender_to_rcp_alpha_cutout_threshold or export this material "
                "with a RealityKit PBR profile"
            )

        # specular and sheenColor are absent from the rename table but are not
        # lost: extraction always pairs them with the values this method routes
        # to specular_weight and the fuzz_* trio. Confirm the substitute was
        # actually authored rather than trusting that pairing.
        carried_under_another_name = {
            'specular': 'specular_weight',
            'sheenColor': 'fuzz_weight',
        }
        declared = self._declared_input_names(
            self._find_node_def(OPENPBR_1_1_NODEDEF)
        )
        omitted = sorted(
            name
            for name in pbr2
            if carried_under_another_name.get(name) not in result
            and rename.get(name, name) not in declared
        )
        if omitted and self.diagnostics:
            self.diagnostics.add_warning(
                "OpenPBR 1.1 material profile omitted inputs the OpenPBR surface "
                "does not expose: " + ", ".join(omitted)
            )

    def _profile_input_graphs(
        self,
        graph_inputs: Dict[str, Any],
        profile: str,
        material_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        material_data = material_data or {}
        graph_inputs = dict(graph_inputs or {})
        emission_color = graph_inputs.pop('_emissionColor', None)
        emission_strength = graph_inputs.pop('_emissionStrength', None)
        sheen_weight = graph_inputs.pop('_sheenWeight', None)
        sheen_tint = graph_inputs.pop('_sheenTint', None)
        sheen_roughness = graph_inputs.pop('_sheenRoughness', None)
        specular_level = graph_inputs.pop('_specularLevel', None)

        if emission_color is not None or emission_strength is not None:
            color_expr = emission_color or self._emission_expr_from_material_data(material_data)
            strength_expr = emission_strength or {
                'kind': 'constant',
                'value': float(material_data.get('emission_strength', 1.0)),
            }
            graph_inputs['emissiveColor'] = self._scaled_color_expr(
                color_expr,
                strength_expr,
            )

        if profile == _PROFILE_RCP3:
            if sheen_weight is not None or sheen_tint is not None:
                weight_expr = sheen_weight or {
                    'kind': 'constant',
                    'value': material_data.get('sheen_weight', 0.0),
                }
                tint_expr = sheen_tint or {
                    'kind': 'constant',
                    'value': material_data.get('sheen_tint', [1.0, 1.0, 1.0]),
                }
                weight_color = {
                    'kind': 'node',
                    'node_id': self._nodedef_for_graph('combine3', 'color3'),
                    'inputs': {'in1': weight_expr, 'in2': weight_expr, 'in3': weight_expr},
                }
                graph_inputs['sheenColor'] = {
                    'kind': 'node',
                    'node_id': self._nodedef_for_graph('multiply', 'color3'),
                    'inputs': {'in1': tint_expr, 'in2': weight_color},
                }
            if sheen_roughness is not None and self.diagnostics:
                self.diagnostics.add_warning(
                    "RealityKit PBR Surface 2 has no sheen roughness input; bake this control "
                    "or select OpenPBR 1.1."
                )
            if specular_level is not None:
                graph_inputs['specular'] = specular_level
                graph_inputs['specularWeight'] = self._scaled_float_expr(specular_level, 2.0)
            return graph_inputs

        if profile == _PROFILE_OPENPBR:
            if sheen_weight is not None:
                graph_inputs['fuzz_weight'] = sheen_weight
            if sheen_tint is not None:
                graph_inputs['fuzz_color'] = sheen_tint
            if sheen_roughness is not None:
                graph_inputs['fuzz_roughness'] = sheen_roughness
            if specular_level is not None:
                graph_inputs['specular_weight'] = self._scaled_float_expr(specular_level, 2.0)

        if profile == _PROFILE_PORTABLE:
            if specular_level is not None:
                graph_inputs['specular'] = specular_level
            supported = {
                'baseColor',
                'emissiveColor',
                'normal',
                'roughness',
                'metallic',
                'specular',
                'opacity',
                'clearcoat',
                'clearcoatRoughness',
                'clearcoatNormal',
            }
            if (
                sheen_weight is not None
                or sheen_tint is not None
                or sheen_roughness is not None
            ) and self.diagnostics:
                self.diagnostics.add_warning(
                    "Portable RealityKit material profile omitted linked sheen controls."
                )
            omitted = sorted(set(graph_inputs) - supported)
            if omitted and self.diagnostics:
                self.diagnostics.add_warning(
                    "Portable RealityKit material profile omitted PBR2-only inputs: "
                    + ", ".join(omitted)
                )
            return {name: expr for name, expr in graph_inputs.items() if name in supported}
        if profile != _PROFILE_OPENPBR:
            return graph_inputs
        rename = {
            'baseColor': 'base_color',
            'baseDiffuseRoughness': 'base_diffuse_roughness',
            'metallic': 'base_metalness',
            'roughness': 'specular_roughness',
            'specularIOR': 'specular_ior',
            'specularAnisotropyLevel': 'specular_roughness_anisotropy',
            'specularColor': 'specular_color',
            'specularWeight': 'specular_weight',
            'normal': 'geometry_normal',
            'opacity': 'geometry_opacity',
            'clearcoat': 'coat_weight',
            'clearcoatRoughness': 'coat_roughness',
            'clearcoatNormal': 'geometry_coat_normal',
            'clearcoatIOR': 'coat_ior',
            'subsurfaceWeight': 'subsurface_weight',
            'subsurfaceColor': 'subsurface_color',
            'subsurfaceRadius': 'subsurface_radius',
            'subsurfaceRadiusScale': 'subsurface_radius_scale',
            'subsurfaceScatterAnisotropy': 'subsurface_scatter_anisotropy',
            'emissiveColor': 'emission_color',
        }
        # Filter against the nodedef for the same reason the unlit surface
        # does: a rename table that misses a key passes it through verbatim, and
        # authoring an input OpenPBR does not declare only surfaces later as an
        # opaque diagnostics-gate failure. A linked Anisotropic Rotation is one
        # such key - OpenPBR 1.1 has no anisotropy angle at all.
        declared = self._declared_input_names(
            self._find_node_def(OPENPBR_1_1_NODEDEF)
        )
        mapped: Dict[str, Any] = {}
        omitted = []
        for name, expr in graph_inputs.items():
            target = rename.get(name, name)
            if target in declared:
                mapped[target] = expr
            else:
                omitted.append(name)
        if omitted and self.diagnostics:
            self.diagnostics.add_warning(
                "OpenPBR 1.1 material profile omitted linked inputs the OpenPBR "
                "surface does not expose: " + ", ".join(sorted(omitted))
            )
        for normal_name in ('geometry_normal', 'geometry_coat_normal'):
            if normal_name in mapped:
                mapped[normal_name] = self._with_normal_decode(
                    mapped[normal_name],
                    "materialx",
                )
        return mapped

    def _nodedef_for_graph(self, node_name: str, output_type: str) -> str:
        from ...manifest.materialx_nodes import select_nodedef_name_for_node

        return select_nodedef_name_for_node(
            self.manifest,
            node_name,
            output_type=output_type,
        ) or f"ND_{node_name}_{output_type}"

    def _scaled_float_expr(self, expr: Dict[str, Any], scale: float) -> Dict[str, Any]:
        return {
            'kind': 'node',
            'node_id': self._nodedef_for_graph('multiply', 'float'),
            'inputs': {
                'in1': expr,
                'in2': {'kind': 'constant', 'value': float(scale)},
            },
        }

    def _scaled_color_expr(
        self,
        color_expr: Dict[str, Any],
        strength_expr: Dict[str, Any],
    ) -> Dict[str, Any]:
        if strength_expr.get('kind') == 'constant':
            strength = float(strength_expr.get('value', 1.0))
            if abs(strength - 1.0) <= 1e-6:
                return color_expr
            if color_expr.get('kind') == 'texture':
                result = dict(color_expr)
                result['scale'] = float(result.get('scale', 1.0)) * strength
                return result
        strength_color = {
            'kind': 'node',
            'node_id': self._nodedef_for_graph('combine3', 'color3'),
            'inputs': {
                'in1': strength_expr,
                'in2': strength_expr,
                'in3': strength_expr,
            },
        }
        return {
            'kind': 'node',
            'node_id': self._nodedef_for_graph('multiply', 'color3'),
            'inputs': {'in1': color_expr, 'in2': strength_color},
        }

    def _emission_expr_from_material_data(
        self,
        material_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        path = material_data.get('emission_texture')
        if path:
            result = {
                'kind': 'texture',
                'path': path,
                'output_type': 'color3',
                'channel': material_data.get('emission_texture_channel', 'rgb'),
                'colorspace_role': 'color',
            }
            for source_suffix, target_name in (
                ('texcoord', 'uv_map'),
                ('mapping', 'mapping'),
                ('colorspace', 'colorspace'),
                ('alpha_mode', 'alpha_mode'),
            ):
                value = material_data.get(f'emission_texture_{source_suffix}')
                if value is not None:
                    result[target_name] = value
            return result
        return {
            'kind': 'constant',
            'value': self._convert_color(material_data.get('emission_color', [0.0, 0.0, 0.0])),
        }

    def _with_normal_decode(self, expr: Any, decode: str) -> Any:
        if not isinstance(expr, dict):
            return expr
        result = dict(expr)
        if result.get('kind') == 'texture':
            if (result.get('space') or 'tangent').strip().lower() not in {'', 'tangent'}:
                raise ValueError(
                    "OpenPBR geometry normals require a tangent-space normal map; "
                    "bake object-space normals before export"
                )
            result['normal_decode'] = decode
            return result
        if result.get('kind') == 'node':
            result['inputs'] = {
                name: self._with_normal_decode(value, decode)
                for name, value in (result.get('inputs') or {}).items()
            }
        return result

    def _unlit_input_graphs(
        self,
        input_graphs: Dict[str, Any],
        unlit_node_def: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Keep only graph inputs the unlit surface actually declares.

        The supported set is read from the nodedef rather than hard-coded so it
        cannot drift from the manifest. ``baseColor`` is the one name that
        differs between the PBR and unlit surfaces.
        """
        if not input_graphs:
            return {}

        supported = self._declared_input_names(unlit_node_def)
        rename = {'baseColor': 'color'}

        kept: Dict[str, Any] = {}
        omitted = []
        for name, expression in input_graphs.items():
            target = rename.get(name, name)
            if target in supported:
                kept[target] = expression
            else:
                omitted.append(name)

        if omitted and self.diagnostics:
            self.diagnostics.add_warning(
                "Unlit material profile omitted inputs the unlit surface does "
                "not expose: " + ", ".join(sorted(omitted))
            )
        return kept

    def _map_unlit_inputs(self, material_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map Blender material inputs to RealityKit Unlit inputs."""
        inputs: Dict[str, Any] = {}

        if 'base_color_texture' in material_data:
            color_scale = material_data.get('base_color_texture_scale')
            if color_scale is None:
                color_scale = material_data.get('emission_strength')
            inputs['color'] = self._create_texture_input(
                material_data['base_color_texture'],
                'color3',
                texcoord=material_data.get('base_color_texture_texcoord'),
                mapping=material_data.get('base_color_texture_mapping'),
                colorspace=material_data.get('base_color_texture_colorspace'),
                alpha_mode=material_data.get('base_color_texture_alpha_mode'),
                scale=color_scale,
                texture_role='color',
            )
        elif 'base_color' in material_data:
            inputs['color'] = self._convert_color(material_data['base_color'])

        is_transparent = material_data.get('is_transparent', False)

        if is_transparent and 'alpha_texture' in material_data:
            inputs['opacity'] = self._create_texture_input(
                material_data['alpha_texture'],
                'float',
                channel=material_data.get('alpha_texture_channel', 'a'),
                texcoord=material_data.get('alpha_texture_texcoord'),
                mapping=material_data.get('alpha_texture_mapping'),
                colorspace=material_data.get('alpha_texture_colorspace'),
                alpha_mode=material_data.get('alpha_texture_alpha_mode'),
                texture_role='data',
            )
        elif is_transparent and 'alpha' in material_data:
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
        texture_role: Optional[str] = None,
        normal_decode: Optional[str] = None,
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
        if texture_role:
            spec['colorspace_role'] = texture_role
        if normal_decode:
            spec['normal_decode'] = normal_decode
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
            'colorspace_role': 'data',
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
