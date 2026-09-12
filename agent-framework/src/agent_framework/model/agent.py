"""Resolved reusable Agent semantics and explicit model graph validation."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from .capability import Capability, validate_capability
from .channel import Channel, validate_channel
from .constraint import Constraint, ConstraintTarget, TargetKind, validate_constraint
from .group import Group, validate_groups
from .property import Property, validate_property
from .schema import SchemaKind, _validate_id


@dataclass(frozen=True, slots=True, kw_only=True)
class Agent:
    """One reusable model, independent of bindings, transport, and runtime identity.

    Channels are stored once; Properties and Capabilities refer to their IDs.
    Container fields are caller-owned build-time data, not deeply frozen values.
    Call validate_agent explicitly after assembling the complete model.
    """

    id: str
    description: str
    properties: tuple[Property, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    channels: tuple[Channel, ...] = ()
    constraints: tuple[Constraint, ...] = ()
    groups: tuple[Group, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


def _index[T: Property | Capability | Channel | Constraint | Group](
    elements: tuple[T, ...], kind: str
) -> dict[str, T]:
    result: dict[str, T] = {}
    for element in elements:
        _validate_id(element.id, kind)
        if element.id in result:
            raise ValueError(f"duplicate {kind} ID {element.id!r}")
        result[element.id] = element
    return result


def _validate_target(
    target: ConstraintTarget,
    agent: Agent,
    properties: Mapping[str, Property],
    capabilities: Mapping[str, Capability],
    channels: Mapping[str, Channel],
    groups: Mapping[str, Group],
) -> None:
    found = {
        TargetKind.AGENT: target.id == agent.id,
        TargetKind.PROPERTY: target.id in properties,
        TargetKind.CAPABILITY: target.id in capabilities,
        TargetKind.CHANNEL: target.id in channels,
        TargetKind.GROUP: target.id in groups,
    }
    if not found[target.kind]:
        raise ValueError(f"unknown constraint target {target.kind.value} {target.id!r}")
    if target.field_path:
        schema = (
            properties[target.id].schema
            if target.kind is TargetKind.PROPERTY
            else channels[target.id].schema
        )
        for name in target.field_path:
            if schema.kind is not SchemaKind.RECORD or name not in schema.fields:
                raise ValueError(f"unknown payload field {name!r} on target {target.id!r}")
            schema = schema.fields[name]


def validate_agent(agent: Agent) -> None:
    """Validate a complete semantic model at build time, without resolving it.

    Errors are explicit ValueErrors. Primitive IDs share a namespace because
    Group members can name either primitive. Other references have typed scopes.
    """
    _validate_id(agent.id, "agent")
    properties = _index(agent.properties, "property")
    capabilities = _index(agent.capabilities, "capability")
    channels = _index(agent.channels, "channel")
    groups = _index(agent.groups, "group")
    _index(agent.constraints, "constraint")
    if properties.keys() & capabilities.keys():
        raise ValueError("Property and Capability IDs must be unambiguous")
    referenced: set[str] = set()
    for prop in agent.properties:
        validate_property(prop)
    for capability in agent.capabilities:
        validate_capability(capability)
    primitives: tuple[Property | Capability, ...] = (*agent.properties, *agent.capabilities)
    for primitive in primitives:
        for reference in primitive.channels:
            if reference not in channels:
                raise ValueError(f"{primitive.id!r}: unknown channel {reference!r}")
            referenced.add(reference)
    for channel in agent.channels:
        validate_channel(channel)
        if channel.id not in referenced:
            raise ValueError(f"channel {channel.id!r} is not associated with a primitive")
        if channel.correlates_with is not None and channel.correlates_with not in channels:
            raise ValueError(
                f"channel {channel.id!r}: unknown correlation {channel.correlates_with!r}"
            )
    validate_groups(agent.groups, properties.keys() | capabilities.keys())
    for constraint in agent.constraints:
        validate_constraint(constraint)
        _validate_target(constraint.target, agent, properties, capabilities, channels, groups)
