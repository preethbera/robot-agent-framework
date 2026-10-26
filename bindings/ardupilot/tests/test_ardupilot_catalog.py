from pathlib import Path

import pytest
from agent_binding_ardupilot import get_bindings
from agent_binding_ardupilot.properties import armed_state, flight_mode
from agent_framework.binding.definition import validate_binding
from agent_framework.definition.model import AgentDefinition, Exposure
from agent_framework.generation.python import generate_python
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import write_realization


def test_catalog_and_generated_pipeline(tmp_path: Path) -> None:
    package = get_bindings()
    assert len(package.definitions) == 14
    for definition in package.definitions:
        validate_binding(definition)
    model = AgentDefinition(
        schema_version="0.1.0",
        id="ardupilot_test",
        description="ArduPilot test",
        expose=tuple(
            Exposure(use=d.id, alias=d.id.removeprefix("ardupilot.").replace(".", "_"))
            for d in package.definitions
        ),
    )
    resolved = resolve_agent(model)
    artifact, _ = write_artifacts(resolved, tmp_path)
    manifest = write_realization(resolved, tmp_path)
    assert manifest is not None
    path = generate_python(artifact.parent)
    source = (path / "__init__.py").read_text()
    compile(source, str(path), "exec")
    assert "import ardupilot_msgs" not in source and "import rclpy" not in source


def test_state_names() -> None:
    assert armed_state(True) == "armed"
    assert armed_state(False) == "disarmed"
    assert flight_mode(4) == "guided"
    assert flight_mode(9) == "land"
    assert flight_mode(6) == "rtl"
    assert flight_mode(5) == "loiter"
    assert flight_mode(0) == "stabilize"
    assert flight_mode(99) == "unknown"

