"""M6 acceptance test: Multi-Agent Deployment."""

import importlib.util
from pathlib import Path

import pytest
from agent_framework.definition.loader import load_agent_definition
from agent_framework.deployment.loader import load_deployment_spec
from agent_framework.deployment.registry import Deployment
from agent_framework.generation.python import generate_python
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import write_realization

WORKSPACE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def deployment_artifacts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if importlib.util.find_spec("rclpy") is None:
        pytest.skip("ROS2 not available")
        
    build_root = tmp_path_factory.mktemp("build")
    
    # Build test_agent
    agent_def = load_agent_definition(WORKSPACE / "agents" / "test_agent" / "agent.yaml")
    test_agent = resolve_agent(agent_def)
    write_artifacts(test_agent, build_root)
    write_realization(test_agent, build_root)
    generate_python(build_root / test_agent.agent.id)

    # Build minimal_agent
    min_def = load_agent_definition(WORKSPACE / "agents" / "minimal_agent" / "agent.yaml")
    minimal_agent = resolve_agent(min_def)
    write_artifacts(minimal_agent, build_root)
    write_realization(minimal_agent, build_root)
    generate_python(build_root / minimal_agent.agent.id)

    return build_root


def test_multi_agent_deployment_isolation_and_heterogeneous_coexistence(
    deployment_artifacts: Path,
) -> None:
    spec = load_deployment_spec(WORKSPACE / "deployments" / "multi_test.yaml")
    
    # The Deployment context manager instantiates the shared runtime and all instances.
    with Deployment(spec, deployment_artifacts) as deployment:
        from typing import Any
        sensor1: Any = deployment["test_sensor_1"]
        sensor2: Any = deployment["test_sensor_2"]
        min_agent: Any = deployment["test_min"]
        
        # Verify instances have expected configurations
        assert sensor1.namespace == "sensor1"
        assert sensor1.instance_id == "test_sensor_1"
        assert sensor1.instance_config["test"]["calibration_offset"] == 1.5
        
        assert sensor2.namespace == "sensor2"
        assert sensor2.instance_id == "test_sensor_2"
        assert sensor2.instance_config["test"]["calibration_offset"] == 2.5
        
        assert min_agent.namespace == "min1"
        assert min_agent.instance_id == "test_min"
        
        # Verify isolation: each agent has distinct properties/state
        # They should not share property value buffers.
        sensor1.emit("temperature.value", 21.0)
        sensor2.emit("temperature.value", 22.0)
        min_agent.emit("temperature.value", 23.0)
        
        assert sensor1.temperature.get(timeout=0) == 21.0
        assert sensor2.temperature.get(timeout=0) == 22.0
        assert min_agent.temperature.get(timeout=0) == 23.0

        # Verify they share the same runtime registry
        assert deployment.runtime is not None
        assert len(deployment.runtime.registry.values()) == 3
        
        # Verify no cross-talk of internal node structures (namespaces keep ROS2 names distinct)
        nodes = [c._node for c in sensor1.components if hasattr(c, "_node")] + \
                [c._node for c in sensor2.components if hasattr(c, "_node")]
        node_names = [n.get_name() for n in nodes]
        assert len(node_names) == len(set(node_names))
