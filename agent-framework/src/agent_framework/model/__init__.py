"""Technology-independent Agent semantic types and explicit build-time checks."""

from .agent import Agent, validate_agent
from .capability import Capability, Execution, validate_capability
from .channel import (
    Cardinality,
    Channel,
    Delivery,
    Direction,
    Lifetime,
    Ordering,
    Purpose,
    Reliability,
    Timing,
    validate_channel,
)
from .constraint import (
    Constraint,
    ConstraintKind,
    ConstraintTarget,
    TargetKind,
    validate_constraint,
)
from .group import Group, validate_group, validate_groups
from .property import CONSTANT_ABSENT, Property, validate_property
from .schema import PayloadSchema, ScalarType, SchemaKind, validate_constant, validate_schema

__all__ = [
    "CONSTANT_ABSENT",
    "Agent",
    "Capability",
    "Cardinality",
    "Channel",
    "Constraint",
    "ConstraintKind",
    "ConstraintTarget",
    "Delivery",
    "Direction",
    "Execution",
    "Group",
    "Lifetime",
    "Ordering",
    "PayloadSchema",
    "Property",
    "Purpose",
    "Reliability",
    "ScalarType",
    "SchemaKind",
    "TargetKind",
    "Timing",
    "validate_agent",
    "validate_capability",
    "validate_channel",
    "validate_constant",
    "validate_constraint",
    "validate_group",
    "validate_groups",
    "validate_property",
    "validate_schema",
]
