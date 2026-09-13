"""Deployment Specification loading."""

import re
from pathlib import Path

from .errors import DeploymentError
from .model import AgentInstance, DeploymentSpec

MAX_SPEC_BYTES = 1_048_576


def parse_deployment_spec(text: str) -> DeploymentSpec:
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    if len(text.encode("utf-8")) > MAX_SPEC_BYTES:
        raise DeploymentError("Deployment Specification exceeds 1 MiB")
    yaml = YAML(typ="safe", pure=True)
    yaml.version = (1, 2)
    yaml.allow_duplicate_keys = False
    try:
        data = yaml.load(text)
    except YAMLError as error:
        raise DeploymentError(f"invalid Deployment Specification YAML: {error}") from error

    if not isinstance(data, dict):
        raise DeploymentError("Deployment Specification must be a mapping")

    if data.get("schema_version") != "0.1.0":
        raise DeploymentError("unsupported deployment schema version")

    instances_data = data.get("instances", [])
    if not isinstance(instances_data, list):
        raise DeploymentError("instances must be a list")

    instances = []
    seen_ids = set()
    for i, item in enumerate(instances_data):
        if not isinstance(item, dict):
            raise DeploymentError(f"instance at index {i} must be a mapping")
        instance_id = item.get("id")
        if not isinstance(instance_id, str) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", instance_id
        ):
            raise DeploymentError(f"instance at index {i} has invalid or missing id")
        if instance_id in seen_ids:
            raise DeploymentError(f"duplicate instance id: {instance_id}")
        seen_ids.add(instance_id)

        agent_id = item.get("agent")
        if not isinstance(agent_id, str) or not agent_id:
            raise DeploymentError(
                f"instance '{instance_id}' has invalid or missing agent reference"
            )

        if isinstance(item.get("config"), dict):
            namespace = item["config"].get("ros_namespace", "")
        else:
            namespace = ""
        if not isinstance(namespace, str):
            raise DeploymentError(f"instance '{instance_id}' has invalid namespace")

        instances.append(
            AgentInstance(
                id=instance_id,
                agent=agent_id,
                namespace=namespace,
            )
        )

    return DeploymentSpec(schema_version="0.1.0", instances=tuple(instances))


def load_deployment_spec(path: Path) -> DeploymentSpec:
    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_SPEC_BYTES + 1)
        if len(content) > MAX_SPEC_BYTES:
            raise DeploymentError("Deployment Specification exceeds 1 MiB")
        return parse_deployment_spec(content.decode("utf-8"))
    except (OSError, UnicodeError) as error:
        raise DeploymentError(f"cannot read Deployment Specification {path}: {error}") from error
