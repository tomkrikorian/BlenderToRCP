"""
Export diagnostics and reporting
"""

import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


class ExportDiagnostics:
    """Collects and reports export diagnostics"""
    
    def __init__(self):
        """Initialize diagnostics"""
        self.data = {
            'timestamp': datetime.now().isoformat(),
            'materials': {
                'converted': 0,
                'failed': 0,
                'warnings': [],
            },
            'textures': {
                'copied': 0,
                'converted': 0,
                'failed': [],
            },
            'nodes': {
                'fallback_used': [],
                'ktx_required': [],
                'omitted': [],
            },
            'animations': {
                'enabled': False,
                'fps': None,
                'total_frames': None,
                'segments': [],
                'targets': [],
            },
            'errors': [],
            'warnings': [],
        }
    
    def add_material_converted(self, material_name: str):
        """Record a successfully converted material"""
        self.data['materials']['converted'] += 1
    
    def add_material_failed(self, material_name: str, reason: str):
        """Record a failed material conversion"""
        self.data['materials']['failed'] += 1
        self.data['materials']['warnings'].append({
            'material': material_name,
            'reason': reason,
        })
        self.add_error(f"Material conversion failed: {material_name} ({reason})")
    
    def add_texture_copied(self, texture_path: str):
        """Record a copied texture"""
        self.data['textures']['copied'] += 1
    
    def add_texture_converted(self, texture_path: str):
        """Record a converted texture"""
        self.data['textures']['converted'] += 1
    
    def add_texture_failed(self, texture_path: str, reason: str):
        """Record a failed texture operation"""
        self.data['textures']['failed'].append({
            'texture': texture_path,
            'reason': reason,
        })
        self.add_error(f"Texture operation failed: {texture_path} ({reason})")
    
    def add_fallback_node(self, node_name: str, material_name: str):
        """Record use of a fallback node"""
        self.data['nodes']['fallback_used'].append({
            'node': node_name,
            'material': material_name,
        })
        self.add_error(f"Fallback node used: {node_name} (material {material_name})")
    
    def add_ktx_required_node(self, node_name: str, material_name: str):
        """Record use of a KTX-required node"""
        self.data['nodes']['ktx_required'].append({
            'node': node_name,
            'material': material_name,
        })
        self.add_error(f"KTX-required node used: {node_name} (material {material_name})")
    
    def add_omitted_node(self, node_name: str, material_name: str):
        """Record use of an omitted node (e.g., GeometryModifier)"""
        self.data['nodes']['omitted'].append({
            'node': node_name,
            'material': material_name,
        })
        self.add_error(f"Omitted node used: {node_name} (material {material_name})")
    
    def add_error(self, error: str):
        """Add an error message"""
        self.data['errors'].append(error)
    
    def add_warning(self, warning: str):
        """Add a warning message"""
        self.data['warnings'].append(warning)

    def set_animation_schedule(self, fps: int, total_frames: int, segments: list, targets: list):
        """Record animation schedule and targets."""
        self.data['animations']['enabled'] = True
        self.data['animations']['fps'] = fps
        self.data['animations']['total_frames'] = total_frames
        self.data['animations']['segments'] = segments
        self.data['animations']['targets'] = targets
    
    def to_dict(self) -> Dict[str, Any]:
        """Get diagnostics as dictionary"""
        return self.data.copy()
    
    def to_json(self, indent: int = 2) -> str:
        """Get diagnostics as JSON string"""
        return json.dumps(self.data, indent=indent)
    
    def save(self, filepath: Path):
        """Save diagnostics to JSON file"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_summary(self) -> str:
        """Get a human-readable summary"""
        lines = [
            "Export Diagnostics Summary",
            "=" * 40,
            f"Materials converted: {self.data['materials']['converted']}",
            f"Materials failed: {self.data['materials']['failed']}",
            f"Textures copied: {self.data['textures']['copied']}",
            f"Textures converted: {self.data['textures']['converted']}",
        ]
        
        if self.data['nodes']['fallback_used']:
            lines.append(f"Fallback nodes used: {len(self.data['nodes']['fallback_used'])}")
        
        if self.data['nodes']['ktx_required']:
            lines.append(f"KTX-required nodes: {len(self.data['nodes']['ktx_required'])}")
        
        if self.data['nodes']['omitted']:
            lines.append(f"Omitted nodes: {len(self.data['nodes']['omitted'])}")
        
        if self.data['errors']:
            lines.append(f"Errors: {len(self.data['errors'])}")
        
        if self.data['warnings']:
            lines.append(f"Warnings: {len(self.data['warnings'])}")
        
        return "\n".join(lines)
