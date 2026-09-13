import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_binding_px4 import get_bindings
from agent_binding_px4.commands import orbit_parameters
from agent_binding_px4.properties import armed_state, flight_mode
from agent_framework.binding.definition import validate_binding
from agent_framework.definition.model import AgentDefinition, Exposure
from agent_framework.generation.python import generate_python
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import write_realization


def test_catalog_and_generated_pipeline(tmp_path: Path) -> None:
    package = get_bindings()
    assert len(package.definitions) == 10
    for definition in package.definitions:
        validate_binding(definition)
    model = AgentDefinition(
        schema_version="0.1.0",
        id="px4_test",
        description="PX4 test",
        expose=tuple(
            Exposure(use=d.id, alias=d.id.removeprefix("px4.").replace(".", "_"))
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
    assert "import px4_msgs" not in source and "import rclpy" not in source
    assert all(not name.startswith("px4_msgs") for name in sys.modules)


def test_state_names() -> None:
    assert armed_state("1") == "disarmed"
    assert armed_state("2") == "armed"
    assert armed_state("99") == "unknown"
    assert flight_mode("14") == "offboard"
    assert flight_mode("21") == "orbit"
    assert flight_mode("99") == "unknown"


def test_orbit_encoding_and_limits() -> None:
    value = SimpleNamespace(
        radius_m=10.0, speed_m_s=2.0, latitude_deg=47.0, longitude_deg=8.0, altitude_m=500.0
    )
    assert orbit_parameters(value) == (10.0, 2.0, 0.0, 0.0, 47.0, 8.0, 500.0)
    value.radius_m = 0.0
    with pytest.raises(ValueError, match="radius"):
        orbit_parameters(value)
    value.radius_m = float("nan")
    with pytest.raises(ValueError, match="finite"):
        orbit_parameters(value)
