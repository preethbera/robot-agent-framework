"""Run generated application APIs over real ROS2 in the canonical environment."""

import ast
import importlib.util
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from agent_framework.binding.definition import RuntimeMode
from agent_framework.definition.loader import load_agent_definition
from agent_framework.definition.model import AgentDefinition, Exposure
from agent_framework.generation.python import generate_python
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import write_realization

WORKSPACE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def built_agents(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[tuple[Path, ...], Path]:
    if importlib.util.find_spec("rclpy") is None:
        pytest.skip("ROS2 acceptance runs in the canonical Jazzy container")
    workspace = tmp_path_factory.mktemp("m4-ros")
    definition = load_agent_definition(WORKSPACE / "agents/test_agent/agent.yaml")
    resolution = resolve_agent(definition)
    model, _ = write_artifacts(resolution, workspace)
    write_realization(resolution, workspace)
    first = generate_python(model.parent).parent
    resolution = resolve_agent(replace(definition, id="codebacked_agent"))
    resolution = replace(
        resolution,
        bindings=tuple(
            replace(
                selected,
                definition=replace(
                    selected.definition,
                    runtime_mode=RuntimeMode.CODE_BACKED,
                    runtime_factory="agent_binding_test.runtime:create_component",
                ),
            )
            for selected in resolution.bindings
        ),
    )
    model, _ = write_artifacts(resolution, workspace)
    write_realization(resolution, workspace)
    second = generate_python(model.parent).parent
    result = subprocess.run(
        [
            "colcon",
            "--log-base",
            str(workspace / "log"),
            "build",
            "--base-paths",
            str(model.parent / "interfaces"),
            "--build-base",
            str(workspace / "compile"),
            "--install-base",
            str(workspace / "install"),
            "--cmake-args",
            "-DBUILD_TESTING=OFF",
            "-DPython3_EXECUTABLE=/usr/bin/python3",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    packages = [first, second]
    for binding, name in (
        ("test.action", "action_agent"),
        ("test.action_server", "action_server_agent"),
        ("test.command_server", "command_server_agent"),
    ):
        spec = AgentDefinition(
            schema_version="0.1.0",
            id=name,
            description="Protocol fixture",
            expose=(
                Exposure(
                    use=binding,
                    alias="command" if binding == "test.command_server" else "task",
                ),
            ),
        )
        resolved = resolve_agent(spec)
        path, _ = write_artifacts(resolved, workspace)
        write_realization(resolved, workspace)
        packages.append(generate_python(path.parent).parent)
    return tuple(packages), workspace / "install/local_setup.bash"


@pytest.mark.parametrize("mode", ["direct", "factories", "protocols"])
def test_real_ros2_acceptance(
    built_agents: tuple[tuple[Path, ...], Path], mode: str
) -> None:
    packages, setup = built_agents
    environment = dict(os.environ)
    environment["ROS_LOCALHOST_ONLY"] = "1"
    # Arguments, rather than interpolated shell text, carry paths through ROS setup.
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; shift; exec "$@"',
            "m4-test",
            str(setup),
            sys.executable,
            str(WORKSPACE / "tests/e2e/m4_ros_worker.py"),
            mode,
            *(str(path) for path in packages),
        ],
        cwd=WORKSPACE,
        env=environment,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_application_import_boundary() -> None:
    source = (WORKSPACE / "tests/e2e/m4_application.py").read_text()
    tree = ast.parse(source)
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert imports == {"agent_test_agent", "time"}
