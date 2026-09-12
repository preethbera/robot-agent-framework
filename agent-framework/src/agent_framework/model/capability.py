"""Capabilities describe functions, including actuation, sensing, and perception."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from .schema import _validate_id, _validate_ids


class Execution(StrEnum):
    INVOCATION = "invocation"
    SESSION = "session"


@dataclass(frozen=True, slots=True, kw_only=True)
class Capability:
    """A function with references to any required Channels in its Agent.

    A sensing session may expose only output Channels, without a consumer input.
    """

    id: str
    description: str
    execution: Execution
    channels: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


def validate_capability(capability: Capability) -> None:
    _validate_id(capability.id, "capability")
    if not isinstance(capability.execution, Execution):
        raise ValueError(f"capability {capability.id!r}: invalid execution")
    _validate_ids(capability.channels, f"capability {capability.id!r} channels")
