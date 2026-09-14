from dataclasses import replace

import pytest
from agent_framework.model import PayloadSchema, Property, ScalarType, SchemaKind
from agent_framework.serialization.hashing import artifact_hash, content_hash
from agent_framework.serialization.json import canonical_json


def test_canonical_order_and_hashes() -> None:
    assert canonical_json({"b": 2, "a": [True, None]}) == b'{"a":[true,null],"b":2}\n'
    assert artifact_hash({"a": 1, "b": 2}) == artifact_hash({"b": 2, "a": 1})
    assert (
        content_hash(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_missing_constant_differs_from_explicit_none_and_bytes() -> None:
    prop = Property(id="p", description="", schema=PayloadSchema(kind=SchemaKind.OPAQUE))
    assert b"constant_value" not in canonical_json(prop)
    assert b'"constant_value":null' in canonical_json(replace(prop, constant_value=None))
    assert b'"constant_value":"YWJj"' in canonical_json(
        replace(
            prop,
            constant_value=b"abc",
            schema=PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.BYTES),
        )
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object(), {1: "bad"}, {1, 2}])
def test_non_deterministic_or_unsupported_values_fail(value: object) -> None:
    with pytest.raises(ValueError):
        canonical_json(value)


def test_cycles_fail() -> None:
    value: list[object] = []
    value.append(value)
    with pytest.raises(ValueError, match="cyclic"):
        canonical_json(value)
