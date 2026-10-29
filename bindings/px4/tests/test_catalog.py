import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_binding_px4 import get_bindings
from agent_binding_px4.catalog import ack_status
from agent_binding_px4.commands import (
    camera_trigger_parameters,
    gimbal_parameters,
    orbit_parameters,
    reposition_parameters,
    speed_parameters,
    takeoff_parameters,
)
from agent_binding_px4.properties import armed_state, flight_mode
from agent_framework.binding.definition import validate_binding
from agent_framework.definition.model import AgentDefinition, Exposure
from agent_framework.generation.python import generate_python
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import write_realization


def test_catalog_and_generated_pipeline(tmp_path: Path) -> None:
    package = get_bindings()
    assert len(package.definitions) == 24
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
    assert armed_state(1) == "disarmed"
    assert armed_state(2) == "armed"
    assert armed_state(99) == "unknown"
    assert flight_mode(14) == "offboard"
    assert flight_mode(21) == "orbit"
    assert flight_mode(99) == "unknown"


def test_orbit_encoding_and_limits() -> None:
    value = SimpleNamespace(
        radius_m=10.0,
        speed_m_s=2.0,
        latitude_deg=47.0,
        longitude_deg=8.0,
        altitude_m=500.0,
    )
    assert orbit_parameters(value) == (10.0, 2.0, 0.0, 0.0, 47.0, 8.0, 500.0)
    value.radius_m = 0.0
    with pytest.raises(ValueError, match="radius"):
        orbit_parameters(value)
    value.radius_m = float("nan")
    with pytest.raises(ValueError, match="finite"):
        orbit_parameters(value)


def test_flight_and_navigation_parameter_encoders() -> None:
    # Takeoff
    takeoff_val = SimpleNamespace(altitude_m=15.0)
    params = takeoff_parameters(takeoff_val)
    assert params[6] == 15.0
    with pytest.raises(ValueError, match="positive and finite"):
        takeoff_parameters(SimpleNamespace(altitude_m=-5.0))

    # Reposition
    repo_val = SimpleNamespace(
        latitude_deg=47.397,
        longitude_deg=8.545,
        altitude_m=488.0,
        ground_speed_m_s=5.0,
        yaw_deg=0.5,
    )
    r_params = reposition_parameters(repo_val)
    assert r_params == (5.0, 0.0, 0.0, 0.5, 47.397, 8.545, 488.0)
    with pytest.raises(ValueError, match="latitude/longitude"):
        reposition_parameters(SimpleNamespace(latitude_deg=100.0, longitude_deg=0.0, altitude_m=10.0))

    # Cruise speed
    s_params = speed_parameters(SimpleNamespace(speed_m_s=12.5))
    assert s_params == (1.0, 12.5, -1.0, 0.0, 0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="positive"):
        speed_parameters(SimpleNamespace(speed_m_s=-1.0))

    # Gimbal
    g_params = gimbal_parameters(SimpleNamespace(pitch_deg=-30.0, roll_deg=0.0, yaw_deg=45.0))
    assert g_params == (-30.0, 0.0, 45.0, 0.0, 0.0, 0.0, 2.0)
    with pytest.raises(ValueError, match="finite"):
        gimbal_parameters(SimpleNamespace(pitch_deg=float("nan"), roll_deg=0.0, yaw_deg=0.0))

    # Camera trigger
    c_params = camera_trigger_parameters(SimpleNamespace(interval_s=2.0, count=10.0))
    assert c_params == (0.0, 2.0, 10.0, 0.0, 0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="interval"):
        camera_trigger_parameters(SimpleNamespace(interval_s=-1.0, count=1.0))


def test_ack_status_codes() -> None:
    assert ack_status(0) == "accepted"
    assert ack_status(1) == "temporarily_rejected"
    assert ack_status(2) == "denied"
    assert ack_status(99) == "unknown"
