"""Technology-independent payload descriptions and build-time validation.

These Python structures are internal semantic types, not a serialized schema
format. Validation is explicit and must not run in per-message runtime paths.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class SchemaKind(StrEnum):
    SCALAR = "scalar"
    RECORD = "record"
    ARRAY = "array"
    SEQUENCE = "sequence"
    ENUM = "enum"
    OPAQUE = "opaque"


class ScalarType(StrEnum):
    BOOL = "bool"
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    STRING = "string"
    BYTES = "bytes"


type ScalarValue = bool | int | float | str | bytes


@dataclass(frozen=True, slots=True, kw_only=True)
class PayloadSchema:
    """Describe a payload without depending on transport-specific classes.

    Scalars and enums specify scalar_type; enums also specify values. Records
    map field names to schemas. Arrays have items and a fixed length; sequences
    have items and variable length. Opaque schemas leave representation to later
    stages. Semantic annotations (unit, frame, meaning, bounds, description)
    belong in metadata. No wire-format grammar is defined here.
    """

    kind: SchemaKind
    scalar_type: ScalarType | None = None
    fields: Mapping[str, PayloadSchema] = field(default_factory=dict)
    items: PayloadSchema | None = None
    length: int | None = None
    values: tuple[ScalarValue, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


def _validate_id(value: str, context: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: expected a non-empty identifier")


def _validate_ids(values: tuple[str, ...], context: str) -> None:
    seen: set[str] = set()
    for value in values:
        _validate_id(value, context)
        if value in seen:
            raise ValueError(f"{context}: duplicate reference {value!r}")
        seen.add(value)


def _validate_scalar(scalar_type: ScalarType, value: object) -> None:
    if scalar_type is ScalarType.BOOL:
        valid = type(value) is bool
    elif scalar_type is ScalarType.STRING:
        valid = isinstance(value, str)
    elif scalar_type is ScalarType.BYTES:
        valid = isinstance(value, bytes)
    elif scalar_type in (ScalarType.FLOAT32, ScalarType.FLOAT64):
        limit = (
            3.4028234663852886e38 if scalar_type is ScalarType.FLOAT32 else 1.7976931348623157e308
        )
        valid = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and -limit <= value <= limit
        )
    else:
        signed = scalar_type.value.startswith("int")
        bits = int(scalar_type.value.removeprefix("int" if signed else "uint"))
        minimum = -(1 << (bits - 1)) if signed else 0
        maximum = (1 << (bits - int(signed))) - 1
        valid = type(value) is int and minimum <= value <= maximum
    if not valid:
        raise ValueError(f"constant/enum value does not match {scalar_type.value}")


def validate_schema(schema: PayloadSchema) -> None:
    """Reject inconsistent or cyclic schemas; shared child schemas are valid.

    The iterative traversal visits each schema once and does not copy payloads.
    """
    active: set[int] = set()
    complete: set[int] = set()
    pending = [(schema, False)]
    while pending:
        current, leaving = pending.pop()
        identity = id(current)
        if leaving:
            active.remove(identity)
            complete.add(identity)
            continue
        if identity in active:
            raise ValueError("payload schema cycle")
        if identity in complete:
            continue
        if not isinstance(current.kind, SchemaKind):
            raise ValueError("invalid schema kind")
        scalar = current.kind in (SchemaKind.SCALAR, SchemaKind.ENUM)
        if scalar != (current.scalar_type is not None):
            raise ValueError("only scalar and enum schemas require scalar_type")
        if scalar and not isinstance(current.scalar_type, ScalarType):
            raise ValueError("invalid scalar type")
        if current.kind is not SchemaKind.RECORD and current.fields:
            raise ValueError("only record schemas have fields")
        collection = current.kind in (SchemaKind.ARRAY, SchemaKind.SEQUENCE)
        if collection != (current.items is not None):
            raise ValueError("only array and sequence schemas require items")
        if current.kind is SchemaKind.ARRAY:
            if type(current.length) is not int or current.length < 0:
                raise ValueError("array length must be a non-negative integer")
        elif current.length is not None:
            raise ValueError("only array schemas have a fixed length")
        if current.kind is SchemaKind.ENUM:
            if not current.values:
                raise ValueError("enum schema must have values")
            assert current.scalar_type is not None
            for value in current.values:
                _validate_scalar(current.scalar_type, value)
            if len(set(current.values)) != len(current.values):
                raise ValueError("duplicate enum value")
        elif current.values:
            raise ValueError("only enum schemas have values")
        active.add(identity)
        pending.append((current, True))
        for name, child in current.fields.items():
            _validate_id(name, "record field")
            pending.append((child, False))
        if current.items is not None:
            pending.append((current.items, False))


def validate_constant(schema: PayloadSchema, value: object) -> None:
    """Validate a contract-static value at build time, never at message receipt."""
    validate_schema(schema)
    pending = [(schema, value)]
    while pending:
        current, item = pending.pop()
        if current.kind in (SchemaKind.SCALAR, SchemaKind.ENUM):
            assert current.scalar_type is not None
            _validate_scalar(current.scalar_type, item)
            if current.kind is SchemaKind.ENUM and item not in current.values:
                raise ValueError("constant is not an enum value")
        elif current.kind is SchemaKind.RECORD:
            if not isinstance(item, Mapping) or set(item) != set(current.fields):
                raise ValueError("constant must contain exactly the record fields")
            pending.extend((child, item[name]) for name, child in current.fields.items())
        elif current.kind in (SchemaKind.ARRAY, SchemaKind.SEQUENCE):
            if not isinstance(item, (list, tuple)):
                raise ValueError("array/sequence constant must be a list or tuple")
            if current.kind is SchemaKind.ARRAY and len(item) != current.length:
                raise ValueError("constant does not match array length")
            assert current.items is not None
            pending.extend((current.items, element) for element in item)
        # Opaque values are intentionally not inspected or copied here.


def _validate_nonnegative(value: float | None, context: str) -> None:
    if value is not None and (isinstance(value, bool) or not math.isfinite(value) or value < 0):
        raise ValueError(f"{context}: expected a finite non-negative number")
