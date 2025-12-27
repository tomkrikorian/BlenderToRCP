"""
USDZ packager

Creates USDZ files as stored (uncompressed) ZIP archives.
"""

import os
import zipfile
from pathlib import Path
from typing import Optional, List

from .. import prefs as addon_prefs

def create_usdz(usd_path: str, output_path: str, settings, context, diagnostics=None):
    """Create USDZ file from USD stage
    
    Args:
        usd_path: Path to USD file
        output_path: Path to output USDZ file
        settings: Export settings
        context: Blender context
        diagnostics: ExportDiagnostics instance
    """
    # Check for external usdzip tool first
    import bpy
    prefs = addon_prefs.get_preferences(context)
    usdzip_path = prefs.usdzip_path if prefs and hasattr(prefs, 'usdzip_path') else None
    
    if usdzip_path and os.path.exists(usdzip_path):
        # Use external tool
        create_usdz_with_tool(usd_path, output_path, usdzip_path)
    else:
        # Use Python fallback
        create_usdz_python(usd_path, output_path, settings, diagnostics)


def create_usdz_with_tool(usd_path: str, output_path: str, usdzip_path: str):
    """Create USDZ using external usdzip tool"""
    import subprocess
    
    try:
        result = subprocess.run(
            [usdzip_path, output_path, usd_path],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"USDZ created using usdzip: {output_path}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"usdzip failed: {e.stderr}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to run usdzip: {e}") from e


def create_usdz_python(usd_path: str, output_path: str, settings, diagnostics=None):
    """Create USDZ using Python ZIP (stored, uncompressed)"""
    usd_file = Path(usd_path)
    usd_dir = usd_file.parent
    
    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create ZIP archive with no compression (stored)
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_STORED) as usdz:
        # Add main USD file at root
        usd_arcname = usd_file.name
        usdz.write(usd_path, usd_arcname)
        
        # Add textures directory if it exists
        textures_dir = usd_dir / "textures"
        if textures_dir.exists():
            for texture_file in textures_dir.rglob("*"):
                if texture_file.is_file():
                    # Preserve relative path structure
                    arcname = texture_file.relative_to(usd_dir)
                    usdz.write(str(texture_file), str(arcname))

        # Add staged assets directory if it exists
        assets_dir = usd_dir / "assets"
        if assets_dir.exists():
            for asset_file in assets_dir.rglob("*"):
                if asset_file.is_file():
                    arcname = asset_file.relative_to(usd_dir)
                    usdz.write(str(asset_file), str(arcname))
        
        # Add any other referenced assets
        # (This is a simplified implementation - full version would parse USD for all asset references)
    
    print(f"USDZ created: {output_path}")
    
    if diagnostics:
        diagnostics.add_warning("USDZ packaged using Python fallback (stored ZIP)")


def validate_usdz(usdz_path: str) -> bool:
    """Validate USDZ file structure
    
    Args:
        usdz_path: Path to USDZ file
        
    Returns:
        True if valid, False otherwise
    """
    try:
        with zipfile.ZipFile(usdz_path, 'r') as usdz:
            # Check for at least one USD file at root
            root_files = [f for f in usdz.namelist() if '/' not in f or f.count('/') == 1]
            usd_files = [f for f in root_files if f.endswith(('.usd', '.usda', '.usdc'))]
            
            if not usd_files:
                return False
            
            # Check that main USD file is readable
            main_usd = usd_files[0]
            try:
                usdz.read(main_usd)
            except Exception:
                return False
            
            return True
    except Exception:
        return False
