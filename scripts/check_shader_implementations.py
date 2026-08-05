#!/usr/bin/env python3
"""Report materials whose MaterialX nodes RealityKit cannot build a shader for.

Reality Composer Pro reports these as

    GEN RESOURCE: tm_material object id: ... - Resource generation failed.
    Error: Couldn't find compiled shader graph buffer!

with no indication of *which* material. This finds them.

A nodedef can resolve in RealityKit's nodedef store and still have no compiled
Metal function behind it - every `ND_swizzle_*` is exactly that. The graph then
builds and has no shader. Neither `realitytool compile` nor
`usdchecker --arkit --strict` notices, because RCP compiles through
ShaderGraph.framework and realitytool does not link libtm-* at all.

Usage:

    python3 scripts/check_shader_implementations.py <file-or-directory>...

Scans .usda / .usdc / .usdz. Exits 1 if anything would fail.
"""

from __future__ import annotations

import argparse
import bisect
import re
import subprocess
import sys
import zipfile
from pathlib import Path

METAL_LIBRARIES = {
    "1.38": "/Applications/RealityComposerPro.app/Contents/SystemFrameworks/"
    "ShaderGraph.framework/Versions/A/Resources/MaterialX-1.38-apple.metallib",
    "1.39": "/Applications/RealityComposerPro.app/Contents/SystemFrameworks/"
    "ShaderGraph.framework/Versions/A/Resources/MaterialX-1.39.4-apple.metallib",
}
COMMON_LIBRARY = (
    "/Applications/RealityComposerPro.app/Contents/SystemFrameworks/"
    "ShaderGraph.framework/Versions/A/Resources/MaterialX-Common.metallib"
)

_MATERIALX_XML = (
    "/Applications/RealityComposerPro.app/Contents/SystemFrameworks/"
    "ShaderGraph.framework/Versions/A/Resources/MaterialX"
)

#: Per-version MaterialX definition trees, plus Apple's shared overrides.
XML_TREES = {
    "1.38": (f"{_MATERIALX_XML}/MaterialX-1.38", f"{_MATERIALX_XML}/Apple"),
    "1.39": (f"{_MATERIALX_XML}/MaterialX-1.39.4", f"{_MATERIALX_XML}/Apple"),
}

#: Node families the engine implements outside both the Metal libraries and the
#: MaterialX XML. Texture sampling, UV lookup and the surface constructors are
#: wired by the renderer.
#: Verified by exports that render correctly while using every one of them.
ENGINE_PROVIDED = (
    "ND_image_",
    "ND_tiledimage_",
    "ND_triplanarprojection_",
    "ND_place2d_",
    "ND_texcoord_",
    "ND_geompropvalue_",
    "ND_UsdUVTexture",
    "ND_UsdPrimvarReader",
    "ND_UsdPreviewSurface",
    "ND_surfacematerial",
)

_MATERIAL = re.compile(r'def Material "([^"]+)"')
_NODE_ID = re.compile(r'info:id\s*=\s*"(ND_[A-Za-z0-9_]+)"')


def implemented_symbols(version: str) -> tuple[str, ...]:
    """Every ND_ symbol in the libraries this version binds.

    Returned sorted, and matched by *prefix*: Apple's symbols carry codegen
    suffixes (ND_geomcolor_color4_<hash>), so an exact-name test reports every
    node as missing.
    """
    symbols: set[str] = set()
    for library in (METAL_LIBRARIES[version], COMMON_LIBRARY):
        if not Path(library).exists():
            continue
        out = subprocess.run(
            ["strings", "-a", library], capture_output=True, text=True, check=False
        ).stdout
        symbols.update(re.findall(r"^(ND_[A-Za-z0-9_]+)", out, re.M))
    return tuple(sorted(symbols))


def xml_implemented(version: str) -> frozenset[str]:
    """Nodedefs expanded from a nodegraph rather than compiled to Metal.

    470 nodedefs are expanded from a ``<nodegraph nodedef="...">`` at compile
    time and never get a Metal symbol of their own - ``ND_normal_map_decode``
    and ``ND_separate4_color4`` are two. Judging on the metallib alone reports
    every one of them as broken.

    Deliberately only ``<nodegraph>``, not ``<implementation>``: an
    implementation element names a Metal function that may not be in the
    shipped library, which is precisely the failure this script exists to find.
    """
    found: set[str] = set()
    pattern = re.compile(r'<nodegraph\b[^>]*\bnodedef="(ND_[A-Za-z0-9_]+)"')
    for root in XML_TREES.get(version, ()):
        base = Path(root)
        if not base.is_dir():
            continue
        for path in base.rglob("*.mtlx"):
            found.update(pattern.findall(path.read_text(encoding="utf-8", errors="replace")))
    return frozenset(found)


def _is_implemented(nodedef: str, implemented) -> bool:
    symbols, xml = implemented
    if nodedef in xml:
        return True
    index = bisect.bisect_left(symbols, nodedef)
    return index < len(symbols) and symbols[index].startswith(nodedef)


def layer_text(path: Path) -> str:
    """The layer as text, converting binary crate and usdz on the way."""
    if path.suffix == ".usdz":
        with zipfile.ZipFile(path) as archive:
            inner = next(
                (n for n in archive.namelist() if n.endswith((".usdc", ".usda"))), None
            )
            if inner is None:
                return ""
            data = archive.read(inner)
            if inner.endswith(".usda"):
                return data.decode("utf-8", "replace")
        return _usdcat(path)
    if path.suffix == ".usdc":
        return _usdcat(path)
    return path.read_text(encoding="utf-8", errors="replace")


def _usdcat(path: Path) -> str:
    for tool in ("/usr/bin/usdcat", "usdcat"):
        finished = subprocess.run(
            [tool, "--flatten", str(path)], capture_output=True, text=True, check=False
        )
        if finished.returncode == 0:
            return finished.stdout
    return ""


def declared_version(text: str) -> str:
    match = re.search(r'config:mtlx:version\s*=\s*"([0-9.]+)"', text)
    if not match:
        return "1.38"  # RealityKit's own fallback for an unrecognised version
    return "1.39" if match.group(1).startswith("1.39") else "1.38"


def scan(path: Path, symbols_by_version: dict) -> list[tuple[str, str, str]]:
    """Return (material, nodedef, reason) for each unbuildable material."""
    text = layer_text(path)
    if not text:
        return []
    implemented = symbols_by_version[declared_version(text)]

    findings = []
    boundaries = [(m.start(), m.group(1)) for m in _MATERIAL.finditer(text)]
    boundaries.append((len(text), ""))
    for index in range(len(boundaries) - 1):
        start, name = boundaries[index]
        body = text[start : boundaries[index + 1][0]]
        for nodedef in sorted(set(_NODE_ID.findall(body))):
            if nodedef.startswith(ENGINE_PROVIDED):
                continue
            if not _is_implemented(nodedef, implemented):
                findings.append(
                    (name, nodedef, "no Metal symbol and no nodegraph expansion")
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    if not Path(METAL_LIBRARIES["1.38"]).exists():
        print("Reality Composer Pro is not installed here.", file=sys.stderr)
        return 2
    symbols_by_version = {
        v: (implemented_symbols(v), xml_implemented(v)) for v in METAL_LIBRARIES
    }

    targets: list[Path] = []
    for path in args.paths:
        if path.is_dir():
            for suffix in ("*.usda", "*.usdc", "*.usdz"):
                # is_file(): a texture staging directory is legitimately named
                # <layer>.usda, and rglob matches directories too.
                targets.extend(sorted(p for p in path.rglob(suffix) if p.is_file()))
        else:
            targets.append(path)

    total = 0
    for target in targets:
        findings = scan(target, symbols_by_version)
        if not findings:
            continue
        print(f"\n{target}")
        for material, nodedef, reason in findings:
            total += 1
            print(f"  {material or '<root>'}: {nodedef} - {reason}")

    if total:
        print(
            f"\n{total} material/node pair(s) would fail with "
            '"Couldn\'t find compiled shader graph buffer".'
        )
        return 1
    print(f"Checked {len(targets)} layer(s); every material can build a shader.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
