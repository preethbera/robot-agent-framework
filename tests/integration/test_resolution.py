import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from agent_framework.binding.definition import BindingRequirements
from agent_framework.binding.discovery import discover_bindings
from agent_framework.definition.loader import parse_agent_definition
from agent_framework.model import ConstraintKind
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.errors import MandatoryRequirementError, ResolutionError
from agent_framework.resolution.resolver import resolve_agent

SOURCE = """schema_version: '0.1.0'
agent: {id: inspection, description: Test Agent}
expose:
  - {use: test.temperature, as: temperature}
  - {use: test.command, as: command}
  - use: test.stream
    as: lidar
    config: {max_rate_hz: 5, liveness_owner: application}
groups:
  - {id: sensor, members: [temperature, lidar]}
  - {id: all, members: [command], subgroups: [sensor]}
constraints:
  - {id: lower_command_limit, target: command, kind: range, parameters: {max: 80}}
ros2:
  overrides: {temperature: {name: /native/temperature}}
"""


def test_resolution_and_deterministic_artifacts(tmp_path: Path) -> None:
    definition = parse_agent_definition(SOURCE)
    first = resolve_agent(definition)
    paths = write_artifacts(first, tmp_path)
    contents = tuple(path.read_bytes() for path in paths)
    write_artifacts(resolve_agent(definition), tmp_path)
    assert contents == tuple(path.read_bytes() for path in paths)
    model, lock = (json.loads(content) for content in contents)
    assert model["schema_version"] == lock["schema_version"] == "0.1.0"
    assert model["id"] == "inspection"
    assert len(model["properties"]) == 1 and len(model["capabilities"]) == 2
    assert first.agent.metadata["responsibility_ownership"] == {
        "lidar": {"liveness": "application"}
    }
    result = next(channel for channel in first.agent.channels if channel.id == "command.result")
    assert result.correlates_with == "command.request"
    assert lock["bindings"]["test"]["version"] == "0.1.0"
    assert lock["agent_definition_content_hash"] == definition.source_hash
    assert first.definition.ros2_overrides == {"temperature": {"name": "/native/temperature"}}
    assert b"/native/temperature" not in contents[0]
    assert b"ros2_template" not in contents[0] and b"runtime_factory" not in contents[0]
    assert {p.name for p in paths[0].parent.iterdir()} == {
        "resolved_agent_model.json",
        "binding_lock.json",
    }


def test_same_binding_can_be_exposed_twice() -> None:
    definition = parse_agent_definition(
        SOURCE.replace(
            "  - {use: test.temperature, as: temperature}",
            "  - {use: test.temperature, as: temperature}\n  - {use: test.temperature, as: second}",
        )
    )
    resolution = resolve_agent(definition)
    assert {p.id for p in resolution.agent.properties} == {"temperature", "second"}
    assert {"temperature.value", "second.value"} <= {c.id for c in resolution.agent.channels}


def test_binding_owned_liveness_is_hidden() -> None:
    result = resolve_agent(
        parse_agent_definition(
            SOURCE.replace("liveness_owner: application", "liveness_owner: binding")
        )
    )
    assert "lidar.liveness" not in {channel.id for channel in result.agent.channels}
    assert result.agent.metadata["responsibility_ownership"] == {}


@pytest.mark.parametrize(
    "source",
    [
        SOURCE.replace("max_rate_hz: 5", "max_rate_hz: 20"),
        SOURCE.replace("parameters: {max: 80}", "parameters: {max: 200}"),
        SOURCE.replace("parameters: {max: 80}", "parameters: {min: -10}"),
    ],
)
def test_cannot_weaken_mandatory_requirements(source: str) -> None:
    with pytest.raises(MandatoryRequirementError, match="weaken"):
        resolve_agent(parse_agent_definition(source))


def test_mandatory_constraint_survives_omission() -> None:
    definition = parse_agent_definition(
        SOURCE.replace(
            "constraints:\n  - {id: lower_command_limit, target: command, "
            "kind: range, parameters: {max: 80}}\n",
            "",
        )
    )
    resolution = resolve_agent(definition)
    mandatory = next(
        item for item in resolution.agent.constraints if item.id == "command.request_range"
    )
    assert mandatory.parameters == {"min": 0.0, "max": 100.0}


def test_configurable_defaults_are_not_automatically_mandatory() -> None:
    registry = discover_bindings(["test.stream", "test.command", "test.temperature"])
    definitions = dict(registry.definitions)
    definitions["test.stream"] = replace(
        definitions["test.stream"], mandatory_requirements=BindingRequirements()
    )
    with patch(
        "agent_framework.resolution.resolver.discover_bindings",
        return_value=replace(registry, definitions=definitions),
    ):
        result = resolve_agent(
            parse_agent_definition(SOURCE.replace("max_rate_hz: 5", "max_rate_hz: 20"))
        )
    assert next(c for c in result.agent.channels if c.id == "lidar.output").timing is not None


def test_dependency_cycles_fail_before_resolution() -> None:
    registry = discover_bindings(["test.temperature", "test.command", "test.stream"])
    definitions = dict(registry.definitions)
    definitions["test.command"] = replace(
        definitions["test.command"], dependencies=("test.command",)
    )
    with (
        patch(
            "agent_framework.resolution.resolver.discover_bindings",
            return_value=replace(registry, definitions=definitions),
        ),
        pytest.raises(ResolutionError, match="cycle"),
    ):
        resolve_agent(parse_agent_definition(SOURCE))


@pytest.mark.parametrize(
    "source",
    [
        SOURCE.replace("target: command", "target: missing"),
        SOURCE.replace("parameters: {max: 80}", "parameters: {max: 80, field: missing}"),
        SOURCE.replace("parameters: {max: 80}", "parameters: {}"),
        SOURCE.replace("parameters: {max: 80}", "parameters: {min: 90, max: 80}"),
        SOURCE.replace("parameters: {max: 80}", "parameters: {min: 150}"),
        SOURCE.replace("id: lower_command_limit", "id: command.request_range"),
    ],
)
def test_invalid_constraints_are_rejected(source: str) -> None:
    with pytest.raises(ResolutionError):
        resolve_agent(parse_agent_definition(source))


def test_artifact_path_traversal_is_rejected(tmp_path: Path) -> None:
    result = resolve_agent(parse_agent_definition(SOURCE))
    with pytest.raises(ResolutionError, match="unsafe"):
        write_artifacts(replace(result, agent=replace(result.agent, id="../escape")), tmp_path)


def test_build_symlink_escape_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "build").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ResolutionError, match="escapes"):
        write_artifacts(resolve_agent(parse_agent_definition(SOURCE)), workspace)


def test_required_allowed_values_cannot_be_widened() -> None:
    from agent_framework.resolution.validation import require_stricter

    required = next(iter(resolve_agent(parse_agent_definition(SOURCE)).agent.constraints))
    required = replace(required, kind=ConstraintKind.ALLOWED_VALUES, parameters={"values": [1, 2]})
    require_stricter(required, replace(required, parameters={"values": [1]}))
    with pytest.raises(MandatoryRequirementError, match="widened"):
        require_stricter(required, replace(required, parameters={"values": [1, 3]}))
