"""Properties describe the Agent itself or its components, not sensor output."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from .schema import PayloadSchema, _validate_id, _validate_ids, validate_constant, validate_schema


class _Absent(Enum):
    VALUE = "absent"


CONSTANT_ABSENT = _Absent.VALUE


@dataclass(frozen=True, slots=True, kw_only=True)
class Property:
    """A Property references Agent channel IDs; absence differs from any constant.

    Writable Property Channels describe state/configuration updates. Requests to
    perform functions, including sensor acquisition, belong to Capabilities.
    """

    id: str
    description: str
    schema: PayloadSchema
    channels: tuple[str, ...] = ()
    constant_value: object = CONSTANT_ABSENT
    metadata: Mapping[str, object] = field(default_factory=dict)


def validate_property(prop: Property) -> None:
    _validate_id(prop.id, "property")
    _validate_ids(prop.channels, f"property {prop.id!r} channels")
    validate_schema(prop.schema)
    if prop.constant_value is CONSTANT_ABSENT:
        if not prop.channels:
            raise ValueError(f"dynamic property {prop.id!r} requires a channel")
    else:
        validate_constant(prop.schema, prop.constant_value)
