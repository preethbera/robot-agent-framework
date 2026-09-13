"""Explicit validation of the fixed Agent Definition grammar."""

import math
from typing import cast

from agent_framework.model import ConstraintKind, Group, validate_groups

from .errors import DefinitionError
from .model import AgentDefinition, DefinitionConstraint, Exposure


def _mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise DefinitionError(f"{context}: expected a mapping with string keys")
    return cast(dict[str, object], value)


def _keys(value: dict[str, object], allowed: set[str], required: set[str], context: str) -> None:
    if value.keys() - allowed:
        raise DefinitionError(f"{context}: unknown keys {sorted(value.keys() - allowed)}")
    if required - value.keys():
        raise DefinitionError(f"{context}: missing keys {sorted(required - value.keys())}")


def _text(value: object, context: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise DefinitionError(
            f"{context}: expected {'a string' if empty else 'a non-empty string'}"
        )
    return value


def _sequence(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise DefinitionError(f"{context}: expected a list")
    return cast(list[object], value)


def normalize_data(value: object) -> object:
    """Reject cycles/non-JSON values and bound alias expansion before model parsing."""
    active: set[int] = set()
    count = 0

    def visit(item: object, depth: int) -> object:
        nonlocal count
        count += 1
        if count > 100_000 or depth > 64:
            raise DefinitionError("definition exceeds data size/depth limit")
        if item is None or type(item) in (str, bool, int):
            return item
        if isinstance(item, float) and math.isfinite(item):
            return item
        if not isinstance(item, (dict, list)):
            raise DefinitionError("definition must contain finite declarative data only")
        if id(item) in active:
            raise DefinitionError("cyclic YAML aliases are not permitted")
        active.add(id(item))
        try:
            if isinstance(item, dict):
                return {
                    key: visit(child, depth + 1) for key, child in _mapping(item, "data").items()
                }
            return [visit(child, depth + 1) for child in item]
        finally:
            active.remove(id(item))

    return visit(value, 0)


def parse_structure(value: object, source_hash: str) -> AgentDefinition:
    data = _mapping(normalize_data(value), "definition")
    _keys(
        data,
        {"schema_version", "agent", "expose", "groups", "constraints", "ros2"},
        {"schema_version", "agent", "expose"},
        "definition",
    )
    if data["schema_version"] != "0.1.0":
        raise DefinitionError("unsupported Agent Definition schema version; expected 0.1.0")
    agent = _mapping(data["agent"], "agent")
    _keys(agent, {"id", "description"}, {"id", "description"}, "agent")
    identifier = _text(agent["id"], "agent.id")
    if identifier in (".", "..") or any(char in identifier for char in ("/", "\\", "\x00")):
        raise DefinitionError("agent.id must be a safe artifact directory name")
    exposures = []
    for item in _sequence(data["expose"], "expose"):
        exposure = _mapping(item, "expose item")
        _keys(exposure, {"use", "as", "config"}, {"use", "as"}, "expose item")
        exposures.append(
            Exposure(
                use=_text(exposure["use"], "use"),
                alias=_text(exposure["as"], "as"),
                config=_mapping(exposure.get("config", {}), "config"),
            )
        )
    aliases = [item.alias for item in exposures]
    if len(set(aliases)) != len(aliases):
        raise DefinitionError("duplicate exposed alias")
    groups = []
    for item in _sequence(data.get("groups", []), "groups"):
        group = _mapping(item, "group")
        _keys(group, {"id", "description", "members", "subgroups"}, {"id"}, "group")
        groups.append(
            Group(
                id=_text(group["id"], "group.id"),
                description=_text(group.get("description", ""), "group.description", empty=True),
                members=tuple(
                    _text(x, "member") for x in _sequence(group.get("members", []), "members")
                ),
                subgroups=tuple(
                    _text(x, "subgroup") for x in _sequence(group.get("subgroups", []), "subgroups")
                ),
            )
        )
    try:
        validate_groups(tuple(groups), aliases)
    except ValueError as error:
        raise DefinitionError(str(error)) from error
    constraints = []
    for item in _sequence(data.get("constraints", []), "constraints"):
        constraint = _mapping(item, "constraint")
        _keys(
            constraint,
            {"id", "description", "target", "kind", "parameters", "consumer_visible"},
            {"id", "target", "kind", "parameters"},
            "constraint",
        )
        try:
            kind = ConstraintKind(_text(constraint["kind"], "constraint.kind"))
        except ValueError as error:
            raise DefinitionError("invalid constraint kind") from error
        visible = constraint.get("consumer_visible", True)
        if type(visible) is not bool:
            raise DefinitionError("consumer_visible must be a boolean")
        constraints.append(
            DefinitionConstraint(
                id=_text(constraint["id"], "constraint.id"),
                description=_text(
                    constraint.get("description", ""), "constraint.description", empty=True
                ),
                target=_text(constraint["target"], "constraint.target"),
                kind=kind,
                parameters=_mapping(constraint["parameters"], "constraint.parameters"),
                consumer_visible=visible,
            )
        )
    if len({item.id for item in constraints}) != len(constraints):
        raise DefinitionError("duplicate constraint ID")
    ros2 = _mapping(data.get("ros2", {}), "ros2")
    _keys(ros2, {"overrides"}, set(), "ros2")
    return AgentDefinition(
        schema_version="0.1.0",
        id=identifier,
        description=_text(agent["description"], "agent.description", empty=True),
        expose=tuple(exposures),
        groups=tuple(groups),
        constraints=tuple(constraints),
        ros2_overrides=_mapping(ros2.get("overrides", {}), "ros2.overrides"),
        source_hash=source_hash,
    )
