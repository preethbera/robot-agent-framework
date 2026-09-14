import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from agent_framework.definition.model import AgentDefinition, Exposure
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import Resolution, resolve_agent
from agent_framework.ros2 import (
    RealizationError,
    build_realization,
    manifest_data,
    write_realization,
)
from agent_framework.serialization.json import canonical_json

TOPIC: dict[str, object] = {
    "endpoints": [
        {
            "id": "native",
            "kind": "topic",
            "role": "subscriber",
            "interface_type": "std_msgs/msg/Float64",
            "name_template": "/{namespace}/{instance_id}/{binding_instance_id}/temperature",
            "existing": True,
            "overridable": ["name", "qos.depth"],
            "qos": {"history": "keep_last", "depth": 5},
        }
    ],
    "channel_mappings": [
        {"channel": "value", "endpoint": "native", "part": "message", "field": "data"}
    ],
    "internal_communication": [{"description": "native transport"}],
    "startup": ["connect"],
    "lifecycle": ["disconnect"],
}


def resolution(
    template: dict[str, object] | None = None, overrides: dict[str, object] | None = None
) -> Resolution:
    result = resolve_agent(
        AgentDefinition(
            schema_version="0.1.0",
            id="test_agent",
            description="",
            expose=(Exposure(use="test.temperature", alias="temperature"),),
            ros2_overrides=overrides or {},
        )
    )
    selected = result.bindings[0]
    return replace(
        result,
        bindings=(
            replace(
                selected,
                definition=replace(
                    selected.definition,
                    ros2_template=deepcopy(TOPIC if template is None else template),
                ),
            ),
        ),
    )


def test_manifest_contains_provenance_and_binding_requirements() -> None:
    result = resolution()
    before = canonical_json(result.agent)
    manifest = build_realization(result)
    assert manifest.schema_version == "0.1.0"
    assert manifest.interface_types == ("std_msgs/msg/Float64",)
    assert manifest.custom_interface_artifacts == {}
    assert manifest.bindings[0]["startup"] == ["connect"]
    assert manifest.bindings[0]["lifecycle"] == ["disconnect"]
    assert manifest.bindings[0]["internal_communication"] == [{"description": "native transport"}]
    assert manifest.bindings[0]["runtime_factory"] is None
    assert manifest.bindings[0]["dependencies"] == []
    assert manifest.binding_lock["bindings"] == result.binding_lock["bindings"]
    assert manifest.channel_mappings[0].channel == "temperature.value"
    assert canonical_json(result.agent) == before
    assert "name" not in manifest_data(manifest)["endpoints"][0]  # type: ignore[index]


@pytest.mark.parametrize("target", ["temperature", "unknown.native", "temperature.unknown"])
def test_unknown_override_target(target: str) -> None:
    with pytest.raises(RealizationError, match="unknown ROS2 override targets"):
        build_realization(resolution(overrides={target: {"name": "/changed"}}))


def test_deterministic_writer_checks_m2_inputs(tmp_path: Path) -> None:
    result = resolution(overrides={"temperature.native": {"name": "/native/value"}})
    with pytest.raises(RealizationError, match="M2 artifact"):
        write_realization(result, tmp_path)
    write_artifacts(result, tmp_path)
    path = write_realization(result, tmp_path)
    first = path.read_bytes()
    assert write_realization(result, tmp_path).read_bytes() == first
    assert json.loads(first)["endpoints"][0]["name"] == "/native/value"
    assert path == tmp_path / "build/agents/test_agent/ros2_realization.json"
    assert sorted(item.name for item in path.parent.iterdir()) == [
        "binding_lock.json",
        "resolved_agent_model.json",
        "ros2_realization.json",
    ]
    (path.parent / "resolved_agent_model.json").write_text("{}")
    with pytest.raises(RealizationError, match="does not match"):
        write_realization(result, tmp_path)
    assert path.read_bytes() == first


def test_bad_override_writes_no_manifest(tmp_path: Path) -> None:
    result = resolution(overrides={"temperature.native": {"kind": "action"}})
    write_artifacts(result, tmp_path)
    with pytest.raises(RealizationError):
        write_realization(result, tmp_path)
    assert not (tmp_path / "build/agents/test_agent/ros2_realization.json").exists()


@pytest.mark.parametrize(
    "change", [{"unexpected": []}, {"endpoints": []}, {"channel_mappings": []}]
)
def test_bad_template_rejected(change: dict[str, object]) -> None:
    with pytest.raises(RealizationError):
        build_realization(resolution({**TOPIC, **change}))


def test_duplicate_endpoint_rejected() -> None:
    template = deepcopy(TOPIC)
    template["endpoints"] = [*template["endpoints"], *template["endpoints"]]  # type: ignore[misc]
    with pytest.raises(RealizationError, match="duplicate endpoint"):
        build_realization(resolution(template))


def test_configured_description_hook_runs_at_build_only() -> None:
    calls = []
    result = resolution()
    selected = result.bindings[0]

    def configure(configuration: object) -> dict[str, object]:
        calls.append(configuration)
        return deepcopy(TOPIC)

    result = replace(
        result,
        bindings=(
            replace(selected, definition=replace(selected.definition, configure_ros2=configure)),
        ),
    )
    assert calls == []
    assert build_realization(result).endpoints
    assert calls == [{}]


def test_writer_path_escape_rejected(tmp_path: Path) -> None:
    result = resolution()
    with pytest.raises(RealizationError, match="unsafe"):
        write_realization(replace(result, agent=replace(result.agent, id="../outside")), tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "build").symlink_to(outside, target_is_directory=True)
    with pytest.raises(RealizationError, match="escapes"):
        write_realization(result, tmp_path)


def test_manifest_symlink_escape_rejected(tmp_path: Path) -> None:
    result = resolution()
    model, _ = write_artifacts(result, tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("untouched")
    (model.parent / "ros2_realization.json").symlink_to(outside)
    with pytest.raises(RealizationError, match="escapes"):
        write_realization(result, tmp_path)
    assert outside.read_text() == "untouched"
