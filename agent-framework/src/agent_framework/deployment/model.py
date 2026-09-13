"""Deployment Specification types."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentInstance:
    id: str
    agent: str
    namespace: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class DeploymentSpec:
    schema_version: str
    instances: tuple[AgentInstance, ...] = ()
