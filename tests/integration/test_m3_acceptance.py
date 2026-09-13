"""M3 acceptance using the installed external M2 test binding."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from agent_framework.binding.definition import RuntimeMode
from agent_framework.definition.loader import load_agent_definition, parse_agent_definition
from agent_framework.definition.model import AgentDefinition, Exposure
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import (
    RealizationError,
    build_realization,
    manifest_data,
    write_realization,
)
from agent_framework.serialization.json import canonical_json

WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "agents/test_agent/agent.yaml"


def test_complete_m3_realization(tmp_path: Path) -> None:
    resolution = resolve_agent(load_agent_definition(SOURCE))
    m2_paths = write_artifacts(resolution, tmp_path)
    m2_contents = [path.read_bytes() for path in m2_paths]
    path = write_realization(resolution, tmp_path)
    manifest = json.loads(path.read_bytes())
    endpoints = {item["id"]: item for item in manifest["endpoints"]}
    mappings = {item["channel"]: item for item in manifest["channel_mappings"]}
    assert manifest["schema_version"] == "0.1.0"
    assert manifest["binding_lock"]["bindings"]["test"]["version"] == "0.1.0"
    # Direct Property reads native transport without a generic republishing hop.
    temperature = endpoints["temperature.value"]
    assert temperature["kind"] == "topic" and temperature["role"] == "subscriber"
    assert temperature["interface_type"] == "std_msgs/msg/Float64" and temperature["existing"]
    assert temperature["name_template"] == "/native/{instance_id}/temperature"
    assert mappings["temperature.value"]["field"] == "data"
    # The two invocation Channels share a single request/response service.
    assert endpoints["command.command"]["kind"] == "service"
    assert mappings["command.request"]["endpoint"] == mappings["command.result"]["endpoint"]
    assert mappings["command.request"]["part"] == "request"
    assert mappings["command.result"]["part"] == "response"
    # A sensing Capability maps its stream and application liveness to two endpoints.
    assert endpoints["lidar_stream.output"]["role"] == "subscriber"
    assert endpoints["lidar_stream.liveness"]["role"] == "publisher"
    assert (
        mappings["lidar_stream.output"]["endpoint"] != mappings["lidar_stream.liveness"]["endpoint"]
    )
    assert len(endpoints) == 4 and len(mappings) == 5
    assert endpoints["lidar_stream.output"]["qos"]["reliability"] == "best_effort"
    # Only the incompatible numeric service payload requires a custom interface.
    artifacts = manifest["custom_interface_artifacts"]
    assert len(artifacts) == 3
    assert artifacts["interfaces/agent_binding_test_interfaces/srv/Command.srv"] == (
        "float64 value\n---\nfloat64 result\n"
    )
    for relative, content in artifacts.items():
        assert (path.parent / relative).read_text() == content
    assert [item.read_bytes() for item in m2_paths] == m2_contents
    assert not list(path.parent.rglob("*.py"))
    assert canonical_json(manifest) == path.read_bytes()


def test_valid_agent_overrides_and_binding_requirement_rejection() -> None:
    source = SOURCE.read_text().replace(
        "overrides: {}",
        "overrides:\n    temperature.value:\n      name: /native/temperature\n"
        "      qos: {depth: 20}",
    )
    manifest = build_realization(resolve_agent(parse_agent_definition(source)))
    temperature = next(item for item in manifest.endpoints if item.id == "temperature.value")
    assert temperature.name == "/native/temperature" and temperature.qos is not None
    assert temperature.qos["depth"] == 20 and temperature.qos["durability"] == "volatile"
    source = SOURCE.read_text().replace(
        "overrides: {}", "overrides:\n    command.command:\n      qos: {reliability: best_effort}"
    )
    with pytest.raises(RealizationError, match="mandatory qos.reliability"):
        build_realization(resolve_agent(parse_agent_definition(source)))


@pytest.mark.parametrize(
    "override",
    [
        {"temperature": {"name": "/x"}},
        {"missing.value": {"name": "/x"}},
        {"temperature.missing": {"name": "/x"}},
        {"temperature.value": {"kind": "service"}},
        {"temperature.value": {"interface_type": "std_msgs/msg/String"}},
        {"temperature.value": {"qos": {"unsupported": 1}}},
        {"temperature.value": {"qos": {"depth": -1}}},
        {"temperature.value": {"qos": {"durability": "transient_local"}}},
    ],
)
def test_invalid_override_acceptance(override: dict[str, object], tmp_path: Path) -> None:
    definition = replace(load_agent_definition(SOURCE), ros2_overrides=override)
    resolution = resolve_agent(definition)
    write_artifacts(resolution, tmp_path)
    with pytest.raises(RealizationError):
        write_realization(resolution, tmp_path)
    assert not (tmp_path / "build/agents/test_agent/ros2_realization.json").exists()
    assert not (tmp_path / "build/agents/test_agent/interfaces").exists()


def test_binding_owned_liveness_and_existing_interfaces_only(tmp_path: Path) -> None:
    definition = AgentDefinition(
        schema_version="0.1.0",
        id="native_only",
        description="",
        expose=(
            Exposure(use="test.temperature", alias="temperature"),
            Exposure(use="test.stream", alias="sensor"),
        ),
    )
    resolution = resolve_agent(definition)
    write_artifacts(resolution, tmp_path)
    manifest = json.loads(write_realization(resolution, tmp_path).read_bytes())
    assert len(manifest["endpoints"]) == 2
    assert manifest["custom_interface_artifacts"] == {} and manifest["custom_interfaces"] == []
    assert all(item["existing"] for item in manifest["endpoints"])
    assert not (tmp_path / "build/agents/native_only/interfaces").exists()
    sensor = next(item for item in manifest["bindings"] if item["id"] == "sensor")
    assert sensor["internal_communication"] == [
        {"owner": "binding", "responsibility": "liveness", "max_gap_s": 0.5}
    ]


def test_two_instances_share_custom_type_but_have_distinct_ids() -> None:
    definition = AgentDefinition(
        schema_version="0.1.0",
        id="two",
        description="",
        expose=(
            Exposure(use="test.command", alias="first"),
            Exposure(use="test.command", alias="second"),
        ),
        ros2_overrides={"first.command": {"name": "/first"}, "second.command": {"name": "/second"}},
    )
    manifest = build_realization(resolve_agent(definition))
    assert [item.id for item in manifest.endpoints] == ["first.command", "second.command"]
    assert len(manifest.custom_interfaces) == 1
    reverse = replace(definition, expose=tuple(reversed(definition.expose)))
    assert canonical_json(manifest_data(manifest)) == canonical_json(
        manifest_data(build_realization(resolve_agent(reverse)))
    )


def test_runtime_factory_adapters_and_sequence_preserved_without_execution() -> None:
    resolution = resolve_agent(
        AgentDefinition(
            schema_version="0.1.0",
            id="metadata",
            description="",
            expose=(Exposure(use="test.temperature", alias="temperature"),),
        )
    )
    selected = resolution.bindings[0]
    template = deepcopy(dict(selected.definition.ros2_template))
    template["channel_mappings"] = [
        {
            "channel": "value",
            "endpoint": "value",
            "part": "message",
            "field": "data",
            "adapter": "unimportable_binding:convert",
        }
    ]
    template["startup"] = ["z_first", "a_second"]
    selected = replace(
        selected,
        definition=replace(
            selected.definition,
            runtime_mode=RuntimeMode.CODE_BACKED,
            runtime_factory="unimportable_binding:create",
            ros2_template=template,
        ),
    )
    manifest = build_realization(replace(resolution, bindings=(selected,)))
    assert manifest.bindings[0]["runtime_factory"] == "unimportable_binding:create"
    assert manifest.bindings[0]["startup"] == ["z_first", "a_second"]
    assert manifest.channel_mappings[0].adapter == "unimportable_binding:convert"
    assert "unimportable_binding" not in sys.modules


def test_fresh_process_manifest_and_custom_artifacts_are_identical(tmp_path: Path) -> None:
    program = """
import sys
from pathlib import Path
from agent_framework.definition.loader import load_agent_definition
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.ros2 import write_realization
resolution = resolve_agent(load_agent_definition(Path(sys.argv[1])))
write_artifacts(resolution, Path(sys.argv[2]))
write_realization(resolution, Path(sys.argv[2]))
for name in ('rclpy', 'pydantic', 'std_msgs', 'agent_binding_test_interfaces'):
    assert name not in sys.modules
"""
    outputs = [tmp_path / "first", tmp_path / "second"]
    for output, seed in zip(outputs, ["1", "987654"], strict=True):
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", program, str(SOURCE), str(output)],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
    first = {
        path.relative_to(outputs[0]): path.read_bytes()
        for path in outputs[0].rglob("*")
        if path.is_file()
    }
    second = {
        path.relative_to(outputs[1]): path.read_bytes()
        for path in outputs[1].rglob("*")
        if path.is_file()
    }
    assert first == second
