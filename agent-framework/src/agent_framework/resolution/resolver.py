"""Agent Definition -> Resolved Agent Model, without ROS2 materialization."""

from dataclasses import dataclass, replace
from importlib.metadata import version

from agent_framework.binding.definition import (
    BindingDefinition,
    BindingSemantics,
    configure_binding,
)
from agent_framework.binding.discovery import discover_bindings
from agent_framework.definition.model import AgentDefinition
from agent_framework.model import Agent, Capability, Constraint, Property, validate_agent

from .errors import ResolutionError
from .merge import canonical_constraint, materialize_constraint, rename_semantics
from .validation import (
    protect_channels,
    protect_constraints,
    validate_constraint_intersections,
    validate_constraint_parameters,
    validate_dependencies,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedBinding:
    alias: str
    definition: BindingDefinition
    semantics: BindingSemantics


@dataclass(frozen=True, slots=True, kw_only=True)
class Resolution:
    agent: Agent
    definition: AgentDefinition
    bindings: tuple[ResolvedBinding, ...]
    binding_lock: dict[str, object]


def resolve_agent(definition: AgentDefinition) -> Resolution:
    if definition.schema_version != "0.1.0":
        raise ResolutionError("unsupported Agent Definition schema version")
    if len({item.alias for item in definition.expose}) != len(definition.expose):
        raise ResolutionError("duplicate exposed alias")
    registry = discover_bindings(item.use for item in definition.expose)
    validate_dependencies(
        {key: value.dependencies for key, value in registry.definitions.items()},
        tuple(item.use for item in definition.expose),
    )
    selected: list[ResolvedBinding] = []
    mandatory: list[Constraint] = []
    properties: list[Property] = []
    capabilities: list[Capability] = []
    for exposure in sorted(definition.expose, key=lambda item: item.alias):
        binding = registry.get(exposure.use)
        semantics = configure_binding(binding, exposure.config)
        protect_channels(binding.mandatory_requirements.channels, binding.default_semantics)
        protect_channels(binding.mandatory_requirements.channels, semantics)
        # Mandatory constraints are always retained, even if a configuration hook omits them.
        merged_constraints = {item.id: item for item in binding.mandatory_requirements.constraints}
        protect_constraints(binding.mandatory_requirements.constraints, semantics.constraints)
        merged_constraints.update({item.id: item for item in semantics.constraints})
        resolved = rename_semantics(
            replace(semantics, constraints=tuple(merged_constraints.values())),
            exposure.alias,
            definition.id,
        )
        required = rename_semantics(
            replace(semantics, constraints=binding.mandatory_requirements.constraints),
            exposure.alias,
            definition.id,
        )
        mandatory.extend(required.constraints)
        if isinstance(resolved.element, Property):
            properties.append(resolved.element)
        else:
            capabilities.append(resolved.element)
        selected.append(
            ResolvedBinding(alias=exposure.alias, definition=binding, semantics=resolved)
        )
    ownership = {
        item.alias: {
            name: owner
            for name, owner in item.semantics.responsibility_ownership.items()
            if owner == "application"
        }
        for item in selected
    }
    agent = Agent(
        id=definition.id,
        description=definition.description,
        properties=tuple(properties),
        capabilities=tuple(capabilities),
        channels=tuple(
            sorted(
                (channel for item in selected for channel in item.semantics.channels),
                key=lambda item: item.id,
            )
        ),
        groups=tuple(sorted(definition.groups, key=lambda item: item.id)),
        metadata={
            "responsibility_ownership": {
                name: owners for name, owners in ownership.items() if owners
            }
        },
    )
    constraints = tuple(
        canonical_constraint(constraint, agent)
        for item in selected
        for constraint in item.semantics.constraints
    )
    required_constraints = tuple(canonical_constraint(item, agent) for item in mandatory)
    requested = tuple(materialize_constraint(item, agent) for item in definition.constraints)
    protect_constraints(required_constraints, constraints + requested)
    for constraint in constraints + requested:
        validate_constraint_parameters(constraint)
    validate_constraint_intersections(constraints + requested)
    # Agent-authored IDs never silently replace binding-provided constraints.
    agent = replace(
        agent, constraints=tuple(sorted(constraints + requested, key=lambda item: item.id))
    )
    try:
        validate_agent(agent)
    except ValueError as error:
        raise ResolutionError(str(error)) from error
    return Resolution(
        agent=agent,
        definition=definition,
        bindings=tuple(selected),
        binding_lock={
            "schema_version": "0.1.0",
            "framework_version": version("agent-framework"),
            "agent_definition_schema_version": definition.schema_version,
            "agent_definition_content_hash": definition.source_hash,
            "bindings": {
                name: {
                    "distribution": record.distribution,
                    "version": record.version,
                    "binding_api_version": record.binding_api_version,
                }
                for name, record in sorted(registry.packages.items())
            },
        },
    )
