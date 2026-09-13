"""Parsed Agent Definition types preserving the documented external grammar."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from agent_framework.model import ConstraintKind, Group


@dataclass(frozen=True, slots=True, kw_only=True)
class Exposure:
    use: str
    alias: str
    config: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class DefinitionConstraint:
    id: str
    description: str
    target: str
    kind: ConstraintKind
    parameters: Mapping[str, object]
    consumer_visible: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentDefinition:
    schema_version: str
    id: str
    description: str
    expose: tuple[Exposure, ...]
    groups: tuple[Group, ...] = ()
    constraints: tuple[DefinitionConstraint, ...] = ()
    ros2_overrides: Mapping[str, object] = field(default_factory=dict)
    source_hash: str = ""
