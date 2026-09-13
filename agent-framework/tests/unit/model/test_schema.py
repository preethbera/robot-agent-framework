"""Schema shape, graph, and build-time constant validation."""

from typing import cast

import pytest

from agent_framework.model import (
    PayloadSchema,
    ScalarType,
    SchemaKind,
    validate_constant,
    validate_schema,
)


@pytest.mark.parametrize(
    "scalar_type,valid,invalid",
    [
        (ScalarType.BOOL, True, 1),
        (ScalarType.INT8, -128, -129),
        (ScalarType.INT8, 127, 128),
        (ScalarType.INT16, -32768, -32769),
        (ScalarType.INT16, 32767, 32768),
        (ScalarType.INT32, -(2**31), -(2**31) - 1),
        (ScalarType.INT32, 2**31 - 1, 2**31),
        (ScalarType.INT64, -(2**63), -(2**63) - 1),
        (ScalarType.INT64, 2**63 - 1, 2**63),
        (ScalarType.UINT8, 255, 256),
        (ScalarType.UINT16, 65535, 65536),
        (ScalarType.UINT32, 2**32 - 1, 2**32),
        (ScalarType.UINT64, 2**64 - 1, 2**64),
        (ScalarType.UINT8, 0, -1),
        (ScalarType.FLOAT32, 1.5, 3.5e38),
        (ScalarType.FLOAT64, 1.5, float("inf")),
        (ScalarType.FLOAT64, 2, float("nan")),
        (ScalarType.STRING, "robot", b"robot"),
        (ScalarType.BYTES, b"robot", "robot"),
    ],
)
def test_scalar_types_and_representation_bounds(
    scalar_type: ScalarType,
    valid: object,
    invalid: object,
) -> None:
    schema = PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=scalar_type)
    validate_schema(schema)
    validate_constant(schema, valid)
    with pytest.raises(ValueError, match="does not match"):
        validate_constant(schema, invalid)


@pytest.mark.parametrize("scalar_type", [ScalarType.INT32, ScalarType.UINT8, ScalarType.FLOAT64])
def test_boolean_is_not_a_numeric_constant(scalar_type: ScalarType) -> None:
    with pytest.raises(ValueError):
        validate_constant(PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=scalar_type), True)


def test_records_arrays_sequences_and_enums() -> None:
    scalar = PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.INT16)
    schema = PayloadSchema(
        kind=SchemaKind.RECORD,
        fields={
            "position": PayloadSchema(kind=SchemaKind.ARRAY, items=scalar, length=3),
            "samples": PayloadSchema(kind=SchemaKind.SEQUENCE, items=scalar),
            "mode": PayloadSchema(
                kind=SchemaKind.ENUM, scalar_type=ScalarType.STRING, values=("idle", "active")
            ),
        },
        metadata={"description": "Generic sample"},
    )
    validate_constant(schema, {"position": (1, 2, 3), "samples": [], "mode": "idle"})
    for value in (
        {"position": (1, 2), "samples": [], "mode": "idle"},
        {"position": (1, 2, 3), "samples": [2**15], "mode": "idle"},
        {"position": (1, 2, 3), "samples": [], "mode": "unknown"},
        {"position": (1, 2, 3), "samples": "wrong", "mode": "idle"},
        {"position": (1, 2, 3), "mode": "idle"},
        {"position": (1, 2, 3), "samples": [], "mode": "idle", "extra": 0},
    ):
        with pytest.raises(ValueError):
            validate_constant(schema, value)


def test_opaque_payload_is_not_copied_or_inspected() -> None:
    class Opaque:
        def __iter__(self) -> None:
            raise AssertionError("must not inspect opaque payload")

    payload = Opaque()
    validate_constant(PayloadSchema(kind=SchemaKind.OPAQUE), payload)


@pytest.mark.parametrize(
    "schema",
    [
        PayloadSchema(kind=cast(SchemaKind, "unknown")),
        PayloadSchema(kind=SchemaKind.SCALAR),
        PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=cast(ScalarType, "complex")),
        PayloadSchema(kind=SchemaKind.OPAQUE, scalar_type=ScalarType.STRING),
        PayloadSchema(kind=SchemaKind.SEQUENCE),
        PayloadSchema(kind=SchemaKind.ARRAY, items=PayloadSchema(kind=SchemaKind.OPAQUE)),
        PayloadSchema(
            kind=SchemaKind.ARRAY, items=PayloadSchema(kind=SchemaKind.OPAQUE), length=-1
        ),
        PayloadSchema(
            kind=SchemaKind.ARRAY, items=PayloadSchema(kind=SchemaKind.OPAQUE), length=True
        ),
        PayloadSchema(
            kind=SchemaKind.SEQUENCE, items=PayloadSchema(kind=SchemaKind.OPAQUE), length=2
        ),
        PayloadSchema(kind=SchemaKind.OPAQUE, fields={"x": PayloadSchema(kind=SchemaKind.OPAQUE)}),
        PayloadSchema(kind=SchemaKind.OPAQUE, items=PayloadSchema(kind=SchemaKind.OPAQUE)),
        PayloadSchema(kind=SchemaKind.OPAQUE, values=("x",)),
        PayloadSchema(kind=SchemaKind.ENUM, scalar_type=ScalarType.STRING),
        PayloadSchema(kind=SchemaKind.ENUM, scalar_type=ScalarType.STRING, values=("x", "x")),
        PayloadSchema(kind=SchemaKind.ENUM, scalar_type=ScalarType.INT8, values=(128,)),
        PayloadSchema(kind=SchemaKind.RECORD, fields={"": PayloadSchema(kind=SchemaKind.OPAQUE)}),
    ],
)
def test_invalid_schema_shapes_are_rejected(schema: PayloadSchema) -> None:
    with pytest.raises(ValueError):
        validate_schema(schema)


def test_schema_cycles_rejected_but_shared_children_allowed() -> None:
    fields: dict[str, PayloadSchema] = {}
    record = PayloadSchema(kind=SchemaKind.RECORD, fields=fields)
    fields["loop"] = PayloadSchema(kind=SchemaKind.SEQUENCE, items=record)
    with pytest.raises(ValueError, match="cycle"):
        validate_schema(record)
    leaf = PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.STRING)
    validate_schema(PayloadSchema(kind=SchemaKind.RECORD, fields={"left": leaf, "right": leaf}))


def test_deep_schema_does_not_depend_on_python_recursion_limit() -> None:
    schema = PayloadSchema(kind=SchemaKind.OPAQUE)
    for _ in range(2000):
        schema = PayloadSchema(kind=SchemaKind.SEQUENCE, items=schema)
    validate_schema(schema)
