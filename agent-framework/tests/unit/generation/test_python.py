import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from agent_framework.definition.loader import load_agent_definition
from agent_framework.generation.python import GenerationError, generate_python
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import write_realization
from agent_framework.runtime.agent import AgentRuntime, BindingSpec, Component, Operation
from agent_framework.runtime.registry import Registry
from agent_framework.serialization.hashing import content_hash
from agent_framework.serialization.json import canonical_json

WORKSPACE = Path(__file__).resolve().parents[4]


@pytest.fixture
def artifacts(tmp_path: Path) -> Path:
    result = resolve_agent(load_agent_definition(WORKSPACE / "agents/test_agent/agent.yaml"))
    path, _ = write_artifacts(result, tmp_path)
    write_realization(result, tmp_path)
    return path.parent


def load_generated(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("generated_test", path / "__init__.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Services:
    def __init__(self) -> None:
        self.registry: Registry[AgentRuntime] = Registry()

    def create_component(self, agent: AgentRuntime, binding: BindingSpec) -> Component:
        class LocalComponent:
            def start(self) -> None:
                if binding.id == "command":

                    def send(value: object, operation: Operation) -> None:
                        agent.emit("command.result", value, operation)

                    agent.register("command.request", send)
                elif binding.id == "lidar_stream":
                    agent.register("lidar_stream.liveness", lambda value, operation: None)

            def close(self) -> None:
                pass

        return LocalComponent()

    def close(self) -> None:
        pass


def test_typed_generated_api_and_static_codec(artifacts: Path) -> None:
    package = generate_python(artifacts)
    first = (package / "__init__.py").read_bytes()
    assert generate_python(artifacts) == package
    assert (package / "__init__.py").read_bytes() == first
    assert (package / "py.typed").exists()
    module = load_generated(package)
    with module.Agent(instance_id="test", runtime=Services()) as agent:
        agent.emit("temperature.value", 21.5)
        assert agent.temperature.get(timeout=0) == 21.5
        assert agent.command.invoke(42.0) == 42.0
        with pytest.raises(Exception, match="constraint"):
            agent.command.invoke(81.0)
        with agent.lidar_stream.start(capacity=2) as session:
            agent.emit("lidar_stream.output", 3.0)
            assert session.output.read(timeout=0) == 3.0
            session.liveness.send(1.0)
    codec = next(item for item in module._SPEC.codecs if item.channel == "temperature.value")
    assert codec.decode(SimpleNamespace(data=8.0)) == 8.0
    assert b"rclpy" not in first and b"px4" not in first
    assert b"value: float" in first


@pytest.mark.parametrize("name", ["ros2_realization.json", "resolved_agent_model.json"])
def test_both_artifacts_required(artifacts: Path, name: str) -> None:
    (artifacts / name).unlink()
    with pytest.raises(GenerationError, match="inputs"):
        generate_python(artifacts)
    assert not (artifacts / "python").exists()


def test_stale_manifest_and_custom_artifacts_rejected(artifacts: Path) -> None:
    model = artifacts / "resolved_agent_model.json"
    model.write_bytes(model.read_bytes() + b" ")
    with pytest.raises(GenerationError, match="does not match"):
        generate_python(artifacts)
    model.write_bytes(model.read_bytes()[:-1])
    (artifacts / "interfaces/agent_binding_test_interfaces/srv/Command.srv").write_text("wrong")
    with pytest.raises(GenerationError, match="custom interface"):
        generate_python(artifacts)


def test_record_sequence_constant_generation(artifacts: Path) -> None:
    model = json.loads((artifacts / "resolved_agent_model.json").read_bytes())
    scalar = model["properties"][0]["schema"]
    record = {
        "kind": "record",
        "fields": {"x": scalar, "samples": {"kind": "sequence", "items": scalar}},
        "metadata": {},
    }
    model["properties"].append(
        {
            "id": "calibration",
            "schema": record,
            "channels": [],
            "constant_value": {"x": 2.0, "samples": [1.0, 3.0]},
        }
    )
    data = canonical_json(model)
    (artifacts / "resolved_agent_model.json").write_bytes(data)
    manifest = json.loads((artifacts / "ros2_realization.json").read_bytes())
    manifest["resolved_agent_model_hash"] = content_hash(data)
    (artifacts / "ros2_realization.json").write_bytes(canonical_json(manifest))
    module = load_generated(generate_python(artifacts))
    with module.Agent(instance_id="record", runtime=Services()) as agent:
        assert agent.calibration.get().samples == [1.0, 3.0]
        assert agent.calibration.get().x == 2.0


def test_output_directory_symlink_rejected(artifacts: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (artifacts / "python").symlink_to(outside, target_is_directory=True)
    with pytest.raises(GenerationError, match="escapes"):
        generate_python(artifacts)
    assert not list(outside.iterdir())


@pytest.mark.parametrize("invalid", ["schema", "member"])
def test_invalid_generation_contract_rejected(artifacts: Path, invalid: str) -> None:
    model = json.loads((artifacts / "resolved_agent_model.json").read_bytes())
    if invalid == "schema":
        model["channels"][0]["schema"] = {
            "kind": "array",
            "length": -1,
            "items": {"kind": "scalar", "scalar_type": "float64"},
        }
    else:
        model["properties"].append(
            {"id": "close", "schema": model["properties"][0]["schema"], "channels": []}
        )
    data = canonical_json(model)
    (artifacts / "resolved_agent_model.json").write_bytes(data)
    manifest = json.loads((artifacts / "ros2_realization.json").read_bytes())
    manifest["resolved_agent_model_hash"] = content_hash(data)
    (artifacts / "ros2_realization.json").write_bytes(canonical_json(manifest))
    with pytest.raises(GenerationError):
        generate_python(artifacts)
    assert not (artifacts / "python").exists()


def test_generated_writable_property(artifacts: Path) -> None:
    from copy import deepcopy

    model = json.loads((artifacts / "resolved_agent_model.json").read_bytes())
    manifest = json.loads((artifacts / "ros2_realization.json").read_bytes())
    channel = deepcopy(
        next(item for item in model["channels"] if item["id"] == "temperature.value")
    )
    channel.update(id="temperature.update", direction="consumer_to_agent")
    model["channels"].append(channel)
    model["properties"][0]["channels"].append("temperature.update")
    endpoint = deepcopy(
        next(item for item in manifest["endpoints"] if item["id"] == "temperature.value")
    )
    endpoint.update(id="temperature.update", role="publisher")
    manifest["endpoints"].append(endpoint)
    manifest["channel_mappings"].append(
        {
            "channel": "temperature.update",
            "endpoint": "temperature.update",
            "part": "message",
            "field": "data",
            "adapter": None,
        }
    )
    data = canonical_json(model)
    (artifacts / "resolved_agent_model.json").write_bytes(data)
    manifest["resolved_agent_model_hash"] = content_hash(data)
    (artifacts / "ros2_realization.json").write_bytes(canonical_json(manifest))
    module = load_generated(generate_python(artifacts))

    class WritableServices(Services):
        def create_component(self, agent: AgentRuntime, binding: BindingSpec) -> Component:
            if binding.id == "temperature":
                agent.register(
                    "temperature.update",
                    lambda value, operation: agent.emit("temperature.value", value),
                )
            return super().create_component(agent, binding)

    with module.Agent(instance_id="writable", runtime=WritableServices()) as agent:
        agent.temperature.set(12.5)
        assert agent.temperature.get(timeout=0) == 12.5
