"""Parser for Reality Composer Pro's shipped Truth-schema type index.

RCP's ``.import`` text format is the serialized form of "The Truth", the data
model of the Our Machinery engine the app is built on (CoreRealityTools
carries ``the_truth.c``/``the_truth_migration.c`` build paths). The app ships
its complete schema as a plain-ASCII index of every Truth type:

    Contents/Resources/rcp_app_data.bundle/Contents/Resources/data/core/
        __type_index.tm_meta

963 types on the pinned build (3.0, 80.0.1.500.1), each with its property
names, property kinds (string / uint32_t / subobject / subobject_set /
reference / reference_set / buffer ...) and defaults. Subobject and reference
properties carry a ``type_hash`` naming their target type; measured across
the whole file, every such hash is ``murmur64a(type_name, seed=0)`` — the
sole nonmember is ``8944e0b1cefd4756`` = murmur64a("tm_anything"), the
engine's wildcard target.

This makes the index the authoritative contract our generator and the
structural inspector were previously reverse-measuring from sample packages:
anything they write or accept can be validated against it directly.

The file uses The Machinery's text object notation, the same grammar as the
``.tm_*`` records themselves: ``key: value`` pairs without separators,
``[ ... ]`` arrays of whitespace-separated values, ``{ ... }`` objects, and
double-quoted strings with backslash escapes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "DEFAULT_TYPE_INDEX_PATH",
    "ANYTHING_TYPE_HASH",
    "TruthType",
    "parse_type_index",
    "load_type_index",
]

DEFAULT_TYPE_INDEX_PATH = Path(
    "/Applications/RealityComposerPro.app/Contents/Resources/"
    "rcp_app_data.bundle/Contents/Resources/data/core/__type_index.tm_meta"
)

#: murmur64a("tm_anything") — the engine's wildcard target for properties
#: that may reference any Truth type.
ANYTHING_TYPE_HASH = "8944e0b1cefd4756"

_TOKEN_RE = re.compile(r'"(?:[^"\\]|\\.)*"|[\[\]{}:]|[^\s\[\]{}:"]+')


@dataclass(frozen=True)
class TruthType:
    """One schema entry: a Truth type and its declared properties."""

    name: str
    #: property name -> raw property object ({"name", "type", "type_hash"?, ...})
    properties: dict = field(default_factory=dict)
    #: the full raw entry, including defaults
    raw: dict = field(default_factory=dict)

    def property_kind(self, property_name: str) -> str | None:
        entry = self.properties.get(property_name)
        return entry.get("type") if entry else None

    def property_target_hash(self, property_name: str) -> str | None:
        entry = self.properties.get(property_name)
        return entry.get("type_hash") if entry else None


class _Parser:
    def __init__(self, text: str):
        self._tokens = _TOKEN_RE.findall(text)
        self._pos = 0

    def parse(self):
        value = self._value()
        if self._pos != len(self._tokens):
            raise ValueError(
                f"trailing tokens after top-level value at index {self._pos}"
            )
        return value

    def _value(self):
        token = self._tokens[self._pos]
        if token == "[":
            self._pos += 1
            items = []
            while self._tokens[self._pos] != "]":
                items.append(self._value())
            self._pos += 1
            return items
        if token == "{":
            self._pos += 1
            entries = {}
            while self._tokens[self._pos] != "}":
                key = self._tokens[self._pos]
                if key.startswith('"'):
                    key = _unquote(key)
                self._pos += 1
                if self._tokens[self._pos] != ":":
                    raise ValueError(f"expected ':' after key {key!r}")
                self._pos += 1
                entries[key] = self._value()
            self._pos += 1
            return entries
        self._pos += 1
        if token.startswith('"'):
            return _unquote(token)
        return token


def _unquote(token: str) -> str:
    return token[1:-1].replace('\\"', '"').replace("\\\\", "\\")


def parse_type_index(text: str) -> dict[str, TruthType]:
    """Parse the index text into ``{type_name: TruthType}``."""
    entries = _Parser(text).parse()
    if not isinstance(entries, list):
        raise ValueError("type index must be a top-level array")
    types: dict[str, TruthType] = {}
    for entry in entries:
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"type entry without a name: {entry!r:.120}")
        properties = {
            prop["name"]: prop
            for prop in entry.get("properties", [])
            if isinstance(prop, dict) and "name" in prop
        }
        types[name] = TruthType(name=name, properties=properties, raw=entry)
    return types


def load_type_index(path: Path | None = None) -> dict[str, TruthType]:
    """Load and parse the installed app's type index."""
    index_path = Path(path) if path else DEFAULT_TYPE_INDEX_PATH
    return parse_type_index(index_path.read_text(encoding="utf-8"))
