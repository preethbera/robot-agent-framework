"""Machine-readable valid-use limitations; no expression evaluation."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from .schema import _validate_id


class ConstraintKind(StrEnum):
    RANGE = "range"
    ALLOWED_VALUES = "allowed_values"
    PRECONDITION = "precondition"
    MUTUAL_EXCLUSION = "mutual_exclusion"


class TargetKind(StrEnum):
    AGENT = "agent"
    GROUP = "group"
    PROPERTY = "property"
    CAPABILITY = "capability"
    CHANNEL = "channel"


@dataclass(frozen=True, slots=True, kw_only=True)
class ConstraintTarget:
    """Internal typed reference, not an Agent Definition wire-format grammar.

    A non-empty field_path targets nested record fields of a Property or Channel
    payload. Tuple components are literal field names, not an expression language.
    """

    kind: TargetKind
    id: str
    field_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Constraint:
    id: str
    description: str
    target: ConstraintTarget
    kind: ConstraintKind
    parameters: Mapping[str, object]
    consumer_visible: bool


def validate_constraint(constraint: Constraint) -> None:
    """Check structure; Agent validation checks that the target exists.

    Parameter interpretation is not specified by M1. Preserve it as declarative
    data rather than inventing precondition or mutual-exclusion expression syntax.
    """
    _validate_id(constraint.id, "constraint")
    if not isinstance(constraint.kind, ConstraintKind):
        raise ValueError(f"constraint {constraint.id!r}: invalid kind")
    target = constraint.target
    if not isinstance(target.kind, TargetKind):
        raise ValueError(f"constraint {constraint.id!r}: invalid target kind")
    _validate_id(target.id, "constraint target")
    if target.field_path and target.kind not in (TargetKind.PROPERTY, TargetKind.CHANNEL):
        raise ValueError("payload field targets require a Property or Channel")
    for component in target.field_path:
        _validate_id(component, "payload field")
    if type(constraint.consumer_visible) is not bool:
        raise ValueError("consumer_visible must be a boolean")
