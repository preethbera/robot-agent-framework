"""Deployment Specification types."""

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentInstance:
    id: str
    agent: str
    namespace: str = ""
    instance_configuration: Mapping[str, Mapping[str, object]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class DeploymentEnvironment:
    target: str = "simulation"
    run_dir: str = "runs/latest"
    bindings: Mapping[str, Mapping[str, object]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class DeploymentSpec:
    schema_version: str
    instances: tuple[AgentInstance, ...] = ()
    environment: DeploymentEnvironment = field(default_factory=DeploymentEnvironment)
