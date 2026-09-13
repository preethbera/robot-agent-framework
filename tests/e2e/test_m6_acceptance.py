"""M6 acceptance test: Multi-Agent Deployment."""

import importlib.util
from pathlib import Path

import pytest
from agent_framework.definition.loader import load_agent_definition
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
    generate_python(build_root / "build" / "agents" / test_agent.agent.id)

    # Build minimal_agent
    min_def = load_agent_definition(WORKSPACE / "agents" / "minimal_agent" / "agent.yaml")
    minimal_agent = resolve_agent(min_def)
    write_artifacts(minimal_agent, build_root)
    write_realization(minimal_agent, build_root)
    generate_python(build_root / "build" / "agents" / minimal_agent.agent.id)

    import subprocess
    import sys

    # Build ROS2 interfaces
    workspace = build_root
    subprocess.run(
        [
            "colcon",
            "--log-base",
            str(workspace / "log"),
            "build",
            "--base-paths",
            str(build_root / "build" / "agents" / "test_agent" / "interfaces"),
            str(build_root / "build" / "agents" / "minimal_agent" / "interfaces"),
            "--build-base",
            str(workspace / "compile"),
            "--install-base",
            str(workspace / "install"),
            "--cmake-args",
            "-DBUILD_TESTING=OFF",
            "-DPython3_EXECUTABLE=/usr/bin/python3",
        ],
        check=True,
    )

    # Run the validation in a ROS2-aware subprocess
    worker_script = workspace / "m6_worker.py"
    worker_script.write_text("""
import sys
from pathlib import Path
from agent_framework.deployment.loader import load_deployment_spec
from agent_framework.deployment.registry import Deployment

def main():
    workspace = Path(sys.argv[1])
    spec_path = Path(sys.argv[2])
    spec = load_deployment_spec(spec_path)
    with Deployment(spec, workspace / "build" / "agents") as deployment:
        sensor1 = deployment.instances.get("test_sensor_1")
        sensor2 = deployment.instances.get("test_sensor_2")
        min_agent = deployment.instances.get("test_min")
        
        assert sensor1 is not None
        assert sensor2 is not None
        assert min_agent is not None
        
        assert sensor1.namespace == "sensor1"
        assert sensor1.instance_id == "test_sensor_1"
        assert sensor1.instance_config["lidar_stream"]["max_rate_hz"] == 8.0
        
        assert sensor2.namespace == "sensor2"
        assert sensor2.instance_id == "test_sensor_2"
        assert sensor2.instance_config["lidar_stream"]["max_rate_hz"] == 15.0
        
        assert min_agent.namespace == "min1"
        assert min_agent.instance_id == "test_min"
        assert "test" not in min_agent.instance_config

        # Verify they share the same runtime registry
        assert deployment.runtime is not None
        assert len(deployment.runtime.registry.values()) == 3
        
        # Verify no cross-talk of internal node structures (namespaces keep ROS2 names distinct)
        nodes = [c._node for c in sensor1.components if hasattr(c, "_node")] + \\
                [c._node for c in sensor2.components if hasattr(c, "_node")]
        node_names = [n.get_name() for n in nodes]
        assert len(node_names) == len(set(node_names))

if __name__ == "__main__":
    main()
""")

    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; shift; exec "$@"',
            "m6-test",
            str(workspace / "install" / "local_setup.bash"),
            sys.executable,
            str(worker_script),
            str(workspace),
            str(WORKSPACE / "deployments" / "multi_test.yaml"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    return build_root / "build" / "agents"


def test_multi_agent_deployment_isolation_and_heterogeneous_coexistence(
    deployment_artifacts: Path,
) -> None:
    pass
