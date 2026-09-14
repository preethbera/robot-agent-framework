"""Agent instance creation from deployment specs."""

import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from agent_framework.generation.python import identifier
from agent_framework.runtime.agent import AgentRuntime, SharedServices

from .errors import DeploymentError
from .model import AgentInstance


class AgentFactory(Protocol):
    def __call__(
        self,
        *,
        instance_id: str,
        namespace: str,
        runtime: SharedServices | None,
        instance_configuration: Mapping[str, Mapping[str, object]],
    ) -> AgentRuntime: ...


def create_instance(
    instance: AgentInstance,
    build_root: Path,
    runtime: SharedServices | None = None,
    agent_type: AgentFactory | None = None,
) -> AgentRuntime:
    """Create an AgentRuntime for the given instance using its generated Python API."""
    if agent_type is not None:
        return agent_type(
            instance_id=instance.id,
            namespace=instance.namespace,
            runtime=runtime,
            instance_configuration=instance.instance_configuration,
        )
    package_name = "agent_" + identifier(instance.agent)
    package_path = build_root / instance.agent / "python" / package_name

    if not package_path.resolve().is_relative_to(build_root.resolve()):
        raise DeploymentError("generated package escapes build root")
    if not package_path.is_dir():
        raise DeploymentError(
            f"generated Python API not found for agent '{instance.agent}' at {package_path}"
        )

    # Generated packages are self-contained. Register only while executing (dataclasses
    # inspect their module), then remove the unique private name even on failure.
    name = "_agent_build_" + uuid4().hex
    spec = importlib.util.spec_from_file_location(name, package_path / "__init__.py")
    if spec is None or spec.loader is None:
        raise DeploymentError(f"cannot load generated API at {package_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except Exception as error:
        raise DeploymentError(f"failed to load generated API: {error}") from error
    finally:
        sys.modules.pop(name, None)

    agent_cls = getattr(module, "Agent", None)
    if agent_cls is None:
        raise DeploymentError(f"generated module for '{instance.agent}' is missing the Agent class")

    try:
        from typing import cast

        return cast(
            AgentRuntime,
            agent_cls(
                instance_id=instance.id,
                namespace=instance.namespace,
                runtime=runtime,
                instance_configuration=instance.instance_configuration,
            ),
        )
    except Exception as error:
        raise DeploymentError(f"failed to instantiate agent '{instance.id}': {error}") from error
