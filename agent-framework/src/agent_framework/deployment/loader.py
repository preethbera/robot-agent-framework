"""Deployment Specification loading."""

import re
from pathlib import Path

from .errors import DeploymentError
from .model import AgentInstance, DeploymentEnvironment, DeploymentSpec

MAX_SPEC_BYTES = 1_048_576


def parse_deployment_spec(text: str) -> DeploymentSpec:
    try:
        from ruamel.yaml import YAML
        from ruamel.yaml.error import YAMLError

        yaml_loader = YAML(typ="safe", pure=True)
        yaml_loader.version = (1, 2)
        yaml_loader.allow_duplicate_keys = False
        try:
            data = yaml_loader.load(text)
        except YAMLError as error:
            raise DeploymentError(f"invalid Deployment Specification YAML: {error}") from error
    except ModuleNotFoundError:
        import yaml

        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise DeploymentError(f"invalid Deployment Specification YAML: {error}") from error

    if not isinstance(data, dict):
        raise DeploymentError("Deployment Specification must be a mapping")

    if data.keys() - {"schema_version", "instances", "environment"}:
        raise DeploymentError("unknown deployment fields")
    if data.get("schema_version") != "0.1.0":
        raise DeploymentError("unsupported deployment schema version")

    env_data = data.get("environment")
    env = DeploymentEnvironment()
    if env_data is not None:
        if not isinstance(env_data, dict):
            raise DeploymentError("environment must be a mapping")
        if env_data.keys() - {"target", "run_dir", "bindings"}:
            raise DeploymentError("unknown environment fields")
        target = env_data.get("target", "simulation")
        if not isinstance(target, str):
            raise DeploymentError("environment.target must be a string")
        run_dir = env_data.get("run_dir", "runs/latest")
        if not isinstance(run_dir, str):
            raise DeploymentError("environment.run_dir must be a string")
        bindings = env_data.get("bindings", {})
        if not isinstance(bindings, dict):
            raise DeploymentError("environment.bindings must be a mapping")
        env = DeploymentEnvironment(
            target=target,
            run_dir=run_dir,
            bindings=bindings,
        )

    instances_data = data.get("instances", [])
    if not isinstance(instances_data, list):
        raise DeploymentError("instances must be a list")

    instances = []
    seen_ids = set()
    for i, item in enumerate(instances_data):
        if not isinstance(item, dict):
            raise DeploymentError(f"instance at index {i} must be a mapping")
        if item.keys() - {"id", "agent", "config"}:
            raise DeploymentError("unknown instance fields")
        instance_id = item.get("id")
        if not isinstance(instance_id, str) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", instance_id
        ):
            raise DeploymentError(f"instance at index {i} has invalid or missing id")
        if instance_id in seen_ids:
            raise DeploymentError(f"duplicate instance id: {instance_id}")
        seen_ids.add(instance_id)

        agent_id = item.get("agent")
        if not isinstance(agent_id, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", agent_id):
            raise DeploymentError(
                f"instance '{instance_id}' has invalid or missing agent reference"
            )

        config = item.get("config", {})
        if not isinstance(config, dict) or config.keys() - {"ros_namespace", "bindings"}:
            raise DeploymentError("invalid or unknown instance config fields")
        bindings = config.get("bindings", {})
        if not isinstance(bindings, dict) or any(
            not isinstance(key, str) or not isinstance(value, dict)
            for key, value in bindings.items()
        ):
            raise DeploymentError("config.bindings must map binding aliases to parameters")
        namespace = config.get("ros_namespace", "")
        if not isinstance(namespace, str):
            raise DeploymentError(f"instance '{instance_id}' has invalid namespace")

        instances.append(
            AgentInstance(
                id=instance_id,
                agent=agent_id,
                namespace=namespace,
                instance_configuration=bindings,
            )
        )

    return DeploymentSpec(
        schema_version="0.1.0",
        instances=tuple(instances),
        environment=env,
    )


def load_deployment_spec(path: Path) -> DeploymentSpec:
    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_SPEC_BYTES + 1)
        if len(content) > MAX_SPEC_BYTES:
            raise DeploymentError("Deployment Specification exceeds 1 MiB")
        return parse_deployment_spec(content.decode("utf-8"))
    except (OSError, UnicodeError) as error:
        raise DeploymentError(f"cannot read Deployment Specification {path}: {error}") from error
