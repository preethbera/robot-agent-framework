"""Deployment runtime coordinator."""

from contextlib import suppress
from pathlib import Path
from typing import Self

from agent_framework.runtime.agent import AgentRuntime, SharedServices
from agent_framework.runtime.agent import create_runtime as create_shared_runtime

from .errors import DeploymentError
from .instances import create_instance
from .model import DeploymentSpec


class Deployment:
    """Manages the lifecycle of a set of agent instances sharing a runtime."""

    def __init__(
        self, spec: DeploymentSpec, build_root: Path, runtime: SharedServices | None = None
    ) -> None:
        self.spec = spec
        self._owns_runtime = runtime is None
        self.runtime: SharedServices | None = None
        
        try:
            self.runtime = runtime if runtime is not None else create_shared_runtime()
            self.instances: dict[str, AgentRuntime] = {}
            for instance_spec in spec.instances:
                self.instances[instance_spec.id] = create_instance(
                    instance_spec, build_root, self.runtime
                )
        except Exception as error:
            with suppress(Exception):
                self.close()
            raise DeploymentError(f"Deployment startup failed: {error}") from error

    def __getitem__(self, instance_id: str) -> AgentRuntime:
        try:
            return self.instances[instance_id]
        except KeyError:
            raise KeyError(f"unknown instance id: {instance_id}") from None

    def close(self) -> None:
        failures = []
        if hasattr(self, "instances"):
            for instance in self.instances.values():
                try:
                    instance.close()
                except Exception as error:
                    failures.append(error)
            self.instances.clear()
            
        if self._owns_runtime and self.runtime is not None:
            try:
                self.runtime.close()
            except Exception as error:
                failures.append(error)
            self.runtime = None
            
        if failures:
            raise DeploymentError("Deployment cleanup failed") from failures[0]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
