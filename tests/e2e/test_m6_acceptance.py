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


def test_multi_agent_deployment_isolation_and_heterogeneous_coexistence(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
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
    worker_script = WORKSPACE / "tests/e2e/m6_worker.py"

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
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
