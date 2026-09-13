"""Declarative ROS2 endpoints; importing descriptions never imports ROS2."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from .errors import RealizationError


@dataclass(frozen=True, slots=True, kw_only=True)
class Endpoint:
    id: str
    kind: str
    interface_type: str
    role: str
    existing: bool
    name: str | None = None
    name_template: str | None = None
    qos: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class EndpointTemplate:
    endpoint: Endpoint
    overridable: tuple[str, ...] = ()
    requirements: Mapping[str, object] = field(default_factory=dict)


def mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise RealizationError(f"{context}: expected a mapping with string keys")
    return dict(cast(Mapping[str, object], value))


def sequence(value: object, context: str) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise RealizationError(f"{context}: expected a sequence")
    return list(value)


def text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RealizationError(f"{context}: expected non-empty text")
    return value


def keys(data: Mapping[str, object], allowed: set[str], required: set[str], context: str) -> None:
    if data.keys() - allowed:
        raise RealizationError(f"{context}: unsupported fields {sorted(data.keys() - allowed)}")
    if required - data.keys():
        raise RealizationError(f"{context}: missing fields {sorted(required - data.keys())}")
