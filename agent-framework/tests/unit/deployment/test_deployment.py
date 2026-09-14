import pytest
from agent_framework.deployment.errors import DeploymentError
from agent_framework.deployment.loader import parse_deployment_spec


def test_parse_valid_deployment_spec() -> None:
    yaml = """
schema_version: "0.1.0"
instances:
  - id: inst1
    agent: test_agent
    config:
      ros_namespace: "ns1"
  - id: inst2
    agent: minimal_agent
"""
    spec = parse_deployment_spec(yaml)
    assert spec.schema_version == "0.1.0"
    assert len(spec.instances) == 2

    assert spec.instances[0].id == "inst1"
    assert spec.instances[0].agent == "test_agent"
    assert spec.instances[0].namespace == "ns1"

    assert spec.instances[1].id == "inst2"
    assert spec.instances[1].agent == "minimal_agent"
    assert spec.instances[1].namespace == ""


def test_parse_invalid_schema_version() -> None:
    yaml = """
schema_version: "0.2.0"
instances: []
"""
    with pytest.raises(DeploymentError, match="unsupported deployment schema version"):
        parse_deployment_spec(yaml)


def test_parse_duplicate_instance_id() -> None:
    yaml = """
schema_version: "0.1.0"
instances:
  - id: dup
    agent: agent1
  - id: dup
    agent: agent2
"""
    with pytest.raises(DeploymentError, match="duplicate instance id"):
        parse_deployment_spec(yaml)


def test_parse_invalid_instance_id() -> None:
    yaml = """
schema_version: "0.1.0"
instances:
  - id: 1invalid
    agent: agent1
"""
    with pytest.raises(DeploymentError, match="invalid or missing id"):
        parse_deployment_spec(yaml)


def test_parse_missing_agent() -> None:
    yaml = """
schema_version: "0.1.0"
instances:
  - id: valid_id
"""
    with pytest.raises(DeploymentError, match="invalid or missing agent reference"):
        parse_deployment_spec(yaml)


@pytest.mark.parametrize("config", ["[]", "{unknown: 1}", "{bindings: []}", "{bindings: {arm: 2}}"])
def test_invalid_instance_configuration(config: str) -> None:
    with pytest.raises(DeploymentError):
        parse_deployment_spec(
            f"schema_version: '0.1.0'\ninstances:\n- id: a\n  agent: a\n  config: {config}\n"
        )


def test_binding_instance_configuration_preserved() -> None:
    spec = parse_deployment_spec("""schema_version: '0.1.0'
instances:
- id: a
  agent: px4_agent
  config:
    bindings:
      arm: {target_system: 2}
""")
    assert spec.instances[0].instance_configuration == {"arm": {"target_system": 2}}
