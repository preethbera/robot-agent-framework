"""Deterministic build-artifact JSON; no serialization in the message hot path."""

import base64
import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum

from agent_framework.model import CONSTANT_ABSENT, Property


def normalize(value: object) -> object:
    """Normalize dataclasses/containers; bytes use base64 in their typed payload slot."""
    active: set[int] = set()

    def visit(item: object) -> object:
        if item is None or isinstance(item, (str, bool, int)):
            return item
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("artifact numbers must be finite")
            return item
        if isinstance(item, bytes):
            return base64.b64encode(item).decode("ascii")
        if isinstance(item, Enum):
            return visit(item.value)
        if id(item) in active:
            raise ValueError("cyclic artifact data")
        active.add(id(item))
        try:
            if is_dataclass(item) and not isinstance(item, type):
                return {
                    member.name: visit(getattr(item, member.name))
                    for member in fields(item)
                    if not (
                        isinstance(item, Property)
                        and member.name == "constant_value"
                        and item.constant_value is CONSTANT_ABSENT
                    )
                }
            if isinstance(item, Mapping):
                if any(not isinstance(key, str) for key in item):
                    raise ValueError("artifact mapping keys must be strings")
                return {key: visit(child) for key, child in item.items()}
            if isinstance(item, (tuple, list)):
                return [visit(child) for child in item]
            raise ValueError(f"unsupported artifact value type: {type(item).__name__}")
        finally:
            active.remove(id(item))

    try:
        return visit(value)
    except RecursionError as error:
        raise ValueError("artifact data exceeds supported nesting depth") from error


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            normalize(value),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
