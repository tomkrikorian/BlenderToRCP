"""Build-pinned primitives for Reality Composer Pro ``.import`` records.

Reality Composer Pro 3 serializes its asset database as a small text language
plus binary buffers.  This module contains only contracts measured against RCP
3.0 build ``80.0.1.500.1``:

* a fail-closed parser for the text record language;
* a deterministic renderer for generated records; and
* the MurmurHash64A content hash used in ordinary ``.tm_buffers`` filenames.

The optimized geometry cache uses a separate derived-data validity hash.  That
hash is intentionally not guessed here.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Union

RCP_VERSION = "3.0"
RCP_BUILD = "80.0.1.500.1"

_MURMUR_MULTIPLIER = 0xC6A4A7935BD1E995
_MURMUR_SHIFT = 47
_U64_MASK = (1 << 64) - 1


class ImportFormatError(ValueError):
    """Raised when input is outside the measured build-80 text contract."""


@dataclass(frozen=True)
class Field:
    name: str
    value: Value


@dataclass(frozen=True)
class ObjectValue:
    fields: tuple[Field, ...]

    def values(self, name: str) -> tuple[Value, ...]:
        return tuple(field.value for field in self.fields if field.name == name)

    def require_one(self, name: str) -> Value:
        values = self.values(name)
        if len(values) != 1:
            raise ImportFormatError(
                f"expected exactly one {name!r} field, found {len(values)}"
            )
        return values[0]


@dataclass(frozen=True)
class ListValue:
    values: tuple[Value, ...]


Scalar = Union[str, int, float, bool]  # noqa: UP007 -- Python 3.9 compatibility
Value = Union[Scalar, ObjectValue, ListValue]  # noqa: UP007


def murmur_hash64a(data: bytes, *, seed: int = 0) -> int:
    """Return RCP build-80's unsigned 64-bit content hash for ``data``.

    This is MurmurHash64A with the seed and constants observed in the shipped
    CoreRealityTools binary. RCP prints the result with ``%llx``: lowercase and
    NOT zero-padded, so a value whose leading nibble is zero has 15 digits.
    """

    multiplier = _MURMUR_MULTIPLIER
    # RCP truncates the length to 32 bits before the initial mix (`mov w9, w1`).
    value = ((((len(data) & 0xFFFFFFFF) * multiplier) & _U64_MASK) ^ seed) & _U64_MASK
    whole_words = len(data) // 8

    for index in range(whole_words):
        offset = index * 8
        word = int.from_bytes(data[offset : offset + 8], "little")
        word = (word * multiplier) & _U64_MASK
        word ^= word >> _MURMUR_SHIFT
        word = (word * multiplier) & _U64_MASK
        value ^= word
        value = (value * multiplier) & _U64_MASK

    tail = data[whole_words * 8 :]
    for index, byte in enumerate(tail):
        value ^= byte << (index * 8)
    if tail:
        value = (value * multiplier) & _U64_MASK

    value ^= value >> _MURMUR_SHIFT
    value = (value * multiplier) & _U64_MASK
    value ^= value >> _MURMUR_SHIFT
    return value


def buffer_content_hash(data: bytes) -> str:
    """Return the lowercase suffix used for ordinary build-80 buffers.

    RCP formats the value with ``%llx``, which is not zero-padded: a hash
    whose leading nibble is zero is written with 15 digits, not 16.
    """

    return f"{murmur_hash64a(data):x}"


def geometry_buffer_names(payloads: "Sequence[bytes]") -> list[str]:
    """Filename hash suffixes for ``geometry/<name>.tm_buffers`` payloads.

    Geometry payloads are not content-addressed individually. RCP chains the
    non-empty slots in ascending order, feeding each result in as the next
    seed, then names slot 0 with the chain value and slot ``i`` with
    ``murmur(pack(chain, i))``. ``payloads`` must be given in slot order,
    where the slot number is the ``index:`` on the matching entry of
    ``input_geometry.buffers`` (absent means 0).
    """

    chain = 0
    for data in payloads:
        if data:
            chain = murmur_hash64a(data, seed=chain)
    return [
        f"{chain:x}"
        if index == 0
        else f"{murmur_hash64a(struct.pack('<QQ', chain, index)):x}"
        for index, _ in enumerate(payloads)
    ]


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.offset = 0

    def parse(self) -> ObjectValue:
        fields = self._fields(until=None)
        self._skip_space()
        if self.offset != len(self.text):
            self._error("unexpected trailing data")
        return ObjectValue(tuple(fields))

    def _fields(self, *, until: str | None) -> list[Field]:
        fields: list[Field] = []
        while True:
            self._skip_space()
            if until is not None and self._peek() == until:
                self.offset += 1
                return fields
            if self.offset >= len(self.text):
                if until is not None:
                    self._error(f"expected {until!r}")
                return fields
            name = self._field_name()
            self._skip_horizontal_space()
            self._expect(":")
            self._skip_horizontal_space()
            fields.append(Field(name, self._value()))

    def _field_name(self) -> str:
        if self._peek() == '"':
            return self._string()
        return self._identifier()

    def _value(self) -> Value:
        character = self._peek()
        if character == '"':
            return self._string()
        if character == "{":
            self.offset += 1
            return ObjectValue(tuple(self._fields(until="}")))
        if character == "[":
            self.offset += 1
            return self._list()
        if character in "-+0123456789.":
            return self._number()
        token = self._identifier()
        if token == "true":
            return True
        if token == "false":
            return False
        self._error(f"unsupported bare value {token!r}")

    def _list(self) -> ListValue:
        values: list[Value] = []
        while True:
            self._skip_space()
            if self._peek() == "]":
                self.offset += 1
                return ListValue(tuple(values))
            if self.offset >= len(self.text):
                self._error("expected ']'")
            values.append(self._value())

    def _identifier(self) -> str:
        start = self.offset
        if not (self._peek().isalpha() or self._peek() == "_"):
            self._error("expected identifier")
        self.offset += 1
        while self._peek().isalnum() or self._peek() == "_":
            self.offset += 1
        return self.text[start : self.offset]

    def _string(self) -> str:
        self._expect('"')
        characters: list[str] = []
        while self.offset < len(self.text):
            character = self.text[self.offset]
            self.offset += 1
            if character == '"':
                return "".join(characters)
            if character != "\\":
                characters.append(character)
                continue
            if self.offset >= len(self.text):
                self._error("unterminated string escape")
            escaped = self.text[self.offset]
            self.offset += 1
            escapes = {
                '"': '"',
                "\\": "\\",
                "n": "\n",
                "r": "\r",
                "t": "\t",
            }
            if escaped not in escapes:
                self._error(f"unsupported string escape \\{escaped}")
            characters.append(escapes[escaped])
        self._error("unterminated string")

    def _number(self) -> int | float:
        start = self.offset
        allowed = frozenset("+-0123456789.eE")
        while self._peek() in allowed:
            self.offset += 1
        token = self.text[start : self.offset]
        try:
            if any(character in token for character in ".eE"):
                return float(token)
            return int(token)
        except ValueError:
            self._error(f"invalid number {token!r}")

    def _skip_horizontal_space(self) -> None:
        while self.offset < len(self.text) and self._peek() in " \t":
            self.offset += 1

    def _skip_space(self) -> None:
        while self.offset < len(self.text) and self._peek() in " \t\r\n":
            self.offset += 1

    def _peek(self) -> str:
        if self.offset >= len(self.text):
            return ""
        return self.text[self.offset]

    def _expect(self, character: str) -> None:
        if self._peek() != character:
            self._error(f"expected {character!r}")
        self.offset += 1

    def _error(self, message: str) -> None:
        line = self.text.count("\n", 0, self.offset) + 1
        last_newline = self.text.rfind("\n", 0, self.offset)
        column = self.offset - last_newline
        raise ImportFormatError(f"{message} at line {line}, column {column}")


def parse_record(text: str) -> ObjectValue:
    """Parse one UTF-8-decoded RCP record and reject unknown syntax."""

    return _Parser(text).parse()


def _quote(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _render_value(value: Value, *, depth: int) -> str:
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, ObjectValue):
        if not value.fields:
            return "{\n" + ("\t" * depth) + "}"
        body = _render_fields(value.fields, depth=depth + 1)
        return "{\n" + body + ("\t" * depth) + "}"
    if isinstance(value, ListValue):
        if not value.values:
            return "[\n" + ("\t" * depth) + "]"
        indent = "\t" * (depth + 1)
        body = "".join(
            indent + _render_value(item, depth=depth + 1) + "\n"
            for item in value.values
        )
        return "[\n" + body + ("\t" * depth) + "]"
    raise TypeError(f"unsupported RCP value {type(value)!r}")


def _render_fields(fields: tuple[Field, ...], *, depth: int) -> str:
    indent = "\t" * depth
    return "".join(
        f"{indent}{_render_field_name(field.name)}: "
        f"{_render_value(field.value, depth=depth)}\n"
        for field in fields
    )


def _render_field_name(name: str) -> str:
    if name and (name[0].isalpha() or name[0] == "_") and all(
        character.isalnum() or character == "_" for character in name[1:]
    ):
        return name
    return _quote(name)


def render_record(record: ObjectValue) -> str:
    """Render a record using the build-80 tab/newline convention."""

    return _render_fields(record.fields, depth=0)
