"""Typed binding declarations, with technology descriptions kept outside semantics."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum

from agent_framework.model import (
    Agent,
    Capability,
    Channel,
    Constraint,
    PayloadSchema,
    Property,
    SchemaKind,
    validate_agent,
    validate_channel,
    validate_constant,
    validate_constraint,
    validate_schema,
)

from .errors import BindingError


class Primitive(StrEnum):
    PROPERTY = "property"
    CAPABILITY = "capability"


class RuntimeMode(StrEnum):
    DIRECT = "direct"
    CODE_BACKED = "code_backed"


@dataclass(frozen=True, slots=True, kw_only=True)
class BindingSemantics:
    element: Property | Capability
    channels: tuple[Channel, ...] = ()
    constraints: tuple[Constraint, ...] = ()
    responsibility_ownership: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class BindingRequirements:
    """Mandatory constraints and Channels, distinct from configurable defaults."""

    constraints: tuple[Constraint, ...] = ()
    channels: tuple[Channel, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class BindingDefinition:
    id: str
    description: str
    primitive: Primitive
    default_semantics: BindingSemantics
    mandatory_requirements: BindingRequirements = field(default_factory=BindingRequirements)
    configuration_schema: PayloadSchema = field(
        default_factory=lambda: PayloadSchema(kind=SchemaKind.RECORD)
    )
    configuration_defaults: Mapping[str, object] = field(default_factory=dict)
    instance_configuration_schema: PayloadSchema = field(
        default_factory=lambda: PayloadSchema(kind=SchemaKind.RECORD)
    )
    dependencies: tuple[str, ...] = ()
    ros2_template: Mapping[str, object] = field(default_factory=dict)
    configure_ros2: Callable[[Mapping[str, object]], Mapping[str, object]] | None = None
    runtime_mode: RuntimeMode = RuntimeMode.DIRECT
    runtime_factory: str | None = None
    configure: Callable[[Mapping[str, object]], BindingSemantics] | None = None


def validate_semantics(semantics: BindingSemantics) -> None:
    element = semantics.element
    validate_agent(
        Agent(
            id=element.id,
            description=element.description,
            properties=(element,) if isinstance(element, Property) else (),
            capabilities=(element,) if isinstance(element, Capability) else (),
            channels=semantics.channels,
            constraints=semantics.constraints,
        )
    )
    for name, owner in semantics.responsibility_ownership.items():
        if not name or owner not in ("binding", "application"):
            raise BindingError("responsibility ownership must name binding or application")


def validate_binding(definition: BindingDefinition) -> None:
    if len(definition.id.split(".")) < 2 or any(not part for part in definition.id.split(".")):
        raise BindingError("binding IDs must be namespace-qualified")
    expected = (
        Primitive.PROPERTY
        if isinstance(definition.default_semantics.element, Property)
        else Primitive.CAPABILITY
    )
    if definition.primitive is not expected:
        raise BindingError(f"{definition.id}: primitive does not match default semantics")
    if not isinstance(definition.runtime_mode, RuntimeMode):
        raise BindingError("invalid binding runtime mode")
    if definition.runtime_mode is RuntimeMode.CODE_BACKED and not definition.runtime_factory:
        raise BindingError("code-backed bindings require a runtime factory reference")
    if definition.runtime_mode is RuntimeMode.DIRECT and definition.runtime_factory is not None:
        raise BindingError("direct bindings do not use a runtime factory")
    if definition.configuration_schema.kind is not SchemaKind.RECORD:
        raise BindingError("binding configuration must be a record")
    if definition.instance_configuration_schema.kind is not SchemaKind.RECORD:
        raise BindingError("instance configuration must be a record")
    validate_schema(definition.instance_configuration_schema)
    validate_semantics(definition.default_semantics)
    validate_schema(definition.configuration_schema)
    for channel in definition.mandatory_requirements.channels:
        validate_channel(channel)
    for constraint in definition.mandatory_requirements.constraints:
        validate_constraint(constraint)
    if len(set(definition.dependencies)) != len(definition.dependencies):
        raise BindingError("duplicate binding dependency")


def configure_binding(
    definition: BindingDefinition, configuration: Mapping[str, object]
) -> BindingSemantics:
    """Validate only this binding's declared configuration before calling its hook.

    Mandatory requirements are checked by the resolver against both the baseline
    and the configured semantics; a hook cannot authorize weakening them.
    """
    values = deepcopy({**definition.configuration_defaults, **configuration})
    try:
        validate_constant(definition.configuration_schema, values)
        if definition.configure is None:
            if values:
                raise BindingError("configured binding requires a configuration hook")
            result = definition.default_semantics
        else:
            result = definition.configure(values)
        validate_semantics(result)
        if type(result.element) is not type(definition.default_semantics.element):
            raise BindingError("configuration cannot change the binding primitive")
        return result
    except (ValueError, TypeError, KeyError) as error:
        raise BindingError(f"{definition.id}: invalid configuration: {error}") from error
