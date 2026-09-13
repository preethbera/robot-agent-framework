"""Agent instance creation from deployment specs."""

import importlib.util
import sys
from pathlib import Path

from agent_framework.generation.python import identifier
from agent_framework.runtime.agent import AgentRuntime, SharedServices

from .errors import DeploymentError
from .model import AgentInstance


def create_instance(
    instance: AgentInstance,
    build_root: Path,
    runtime: SharedServices | None = None,
) -> AgentRuntime:
    """Create an AgentRuntime for the given instance using its generated Python API."""
    package_name = "agent_" + identifier(instance.agent)
    package_path = build_root / instance.agent / "python" / package_name
    
    if not package_path.is_dir():
        raise DeploymentError(
            f"generated Python API not found for agent '{instance.agent}' at {package_path}"
        )

    # Add the python directory to sys.path if not already there so the package can be imported
    python_dir = str(build_root / instance.agent / "python")
    if python_dir not in sys.path:
        sys.path.insert(0, python_dir)

    try:
        module = importlib.import_module(package_name)
    except Exception as error:
        raise DeploymentError(
            f"failed to import generated API for agent '{instance.agent}': {error}"
        ) from error

    agent_cls = getattr(module, "Agent", None)
    if agent_cls is None:
        raise DeploymentError(
            f"generated module for '{instance.agent}' is missing the Agent class"
        )
        
    try:
        from typing import cast
        return cast(AgentRuntime, agent_cls(
            instance_id=instance.id,
            namespace=instance.namespace,
            runtime=runtime,
        ))
    except Exception as error:
        raise DeploymentError(f"failed to instantiate agent '{instance.id}': {error}") from error
