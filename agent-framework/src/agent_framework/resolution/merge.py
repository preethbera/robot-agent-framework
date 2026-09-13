"""Rename binding-local semantics and interpret Agent-specific constraints."""

from dataclasses import replace

from agent_framework.binding.definition import BindingSemantics
from agent_framework.definition.model import DefinitionConstraint
from agent_framework.model import (
    Agent,
    Constraint,
    ConstraintTarget,
    Direction,
    SchemaKind,
    TargetKind,
)

from .errors import ResolutionError


def rename_semantics(semantics: BindingSemantics, alias: str, agent_id: str) -> BindingSemantics:
    channels = {channel.id: f"{alias}.{channel.id}" for channel in semantics.channels}

    def target(reference: ConstraintTarget) -> ConstraintTarget:
        if reference.kind is TargetKind.AGENT and reference.id == semantics.element.id:
            return replace(reference, id=agent_id)
        if (
            reference.kind in (TargetKind.PROPERTY, TargetKind.CAPABILITY)
            and reference.id == semantics.element.id
        ):
            return replace(reference, id=alias)
        if reference.kind is TargetKind.CHANNEL and reference.id in channels:
            return replace(reference, id=channels[reference.id])
        raise ResolutionError(f"binding constraint target is outside its semantics: {reference.id}")

    return BindingSemantics(
        element=replace(
            semantics.element,
            id=alias,
            channels=tuple(channels[name] for name in semantics.element.channels),
        ),
        channels=tuple(
            replace(
                channel,
                id=channels[channel.id],
                correlates_with=channels[channel.correlates_with]
                if channel.correlates_with
                else None,
            )
            for channel in semantics.channels
        ),
        constraints=tuple(
            replace(item, id=f"{alias}.{item.id}", target=target(item.target))
            for item in semantics.constraints
        ),
        responsibility_ownership=dict(semantics.responsibility_ownership),
    )


def materialize_constraint(item: DefinitionConstraint, agent: Agent) -> Constraint:
    candidates = [
        ConstraintTarget(kind=kind, id=item.target)
        for kind, identifiers in (
            (TargetKind.AGENT, (agent.id,)),
            (TargetKind.PROPERTY, tuple(x.id for x in agent.properties)),
            (TargetKind.CAPABILITY, tuple(x.id for x in agent.capabilities)),
            (TargetKind.CHANNEL, tuple(x.id for x in agent.channels)),
            (TargetKind.GROUP, tuple(x.id for x in agent.groups)),
        )
        if item.target in identifiers
    ]
    if len(candidates) != 1:
        raise ResolutionError(f"unknown or ambiguous constraint target {item.target!r}")
    constraint = Constraint(
        id=item.id,
        description=item.description,
        target=candidates[0],
        kind=item.kind,
        parameters=dict(item.parameters),
        consumer_visible=item.consumer_visible,
    )
    return canonical_constraint(constraint, agent)


def canonical_constraint(constraint: Constraint, agent: Agent) -> Constraint:
    """Resolve optional payload field to a typed target for validation/comparison."""
    target = constraint.target
    field = constraint.parameters.get("field")
    path = target.field_path
    if field is not None:
        if not isinstance(field, str) or not field:
            raise ResolutionError("constraint field must name a payload field")
        if path and path != (field,):
            raise ResolutionError("conflicting constraint payload field targets")
        path = (field,)
    if target.kind is TargetKind.CAPABILITY and (
        path or constraint.kind.value in ("range", "allowed_values")
    ):
        capability = next(item for item in agent.capabilities if item.id == target.id)
        channels = [item for item in agent.channels if item.id in capability.channels]
        inputs = [item for item in channels if item.direction is Direction.CONSUMER_TO_AGENT]
        channels = inputs or channels
        if path:
            channels = [
                item
                for item in channels
                if item.schema.kind is SchemaKind.RECORD and path[0] in item.schema.fields
            ]
        if len(channels) != 1:
            raise ResolutionError(
                "payload constraint on Capability requires an unambiguous Channel target"
            )
        target = ConstraintTarget(kind=TargetKind.CHANNEL, id=channels[0].id)
    if path and target.kind not in (TargetKind.PROPERTY, TargetKind.CHANNEL):
        raise ResolutionError("payload fields require a Property or Channel target")
    return replace(
        constraint,
        target=replace(target, field_path=path),
        parameters={key: value for key, value in constraint.parameters.items() if key != "field"},
    )
