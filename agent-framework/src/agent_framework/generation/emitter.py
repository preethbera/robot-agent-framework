"""Artifact loading, contract validation, and Python source emission for Agent APIs."""

from __future__ import annotations

import json
import keyword
from pathlib import Path
from typing import Any

from agent_framework.model import validate_schema
from agent_framework.runtime.agent import AgentRuntime
from agent_framework.serialization.hashing import content_hash
from agent_framework.serialization.json import canonical_json

from .schema_types import (
    GenerationError,
    Types,
    identifier,
    schema_from_data,
    unique_names,
)


def load_artifacts(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate the resolved agent model and ROS2 realization artifacts."""
    try:
        model_bytes = (directory / "resolved_agent_model.json").read_bytes()
        model = json.loads(model_bytes)
        manifest = json.loads((directory / "ros2_realization.json").read_bytes())
        if model["schema_version"] != "0.1.0" or manifest["schema_version"] != "0.1.0":
            raise GenerationError("unsupported artifact schema version")
        if (
            model["id"] != manifest["agent_id"]
            or content_hash(model_bytes) != manifest["resolved_agent_model_hash"]
        ):
            raise GenerationError("ROS2 realization does not match the resolved Agent Model")
        if manifest["binding_lock"]["framework_version"] != "0.1.0":
            raise GenerationError("unsupported framework version")
        for relative, content in manifest["custom_interface_artifacts"].items():
            path = directory / relative
            if (
                not path.resolve().is_relative_to(directory.resolve())
                or path.read_text() != content
            ):
                raise GenerationError(
                    "custom interface artifact is missing or differs from realization"
                )
        if len({item["id"] for item in manifest["endpoints"]}) != len(manifest["endpoints"]):
            raise GenerationError("duplicate finalized endpoint")
        known = {item["id"] for item in model["channels"]}
        endpoints = {item["id"] for item in manifest["endpoints"]}
        if {item["channel"] for item in manifest["channel_mappings"]} != known:
            raise GenerationError("finalized Channel mappings do not cover the resolved model")
        if any(item["endpoint"] not in endpoints for item in manifest["channel_mappings"]):
            raise GenerationError("unknown finalized endpoint in Channel mapping")
        canonical_json(model)
        canonical_json(manifest)
        for item in (*model["properties"], *model["channels"]):
            validate_schema(schema_from_data(item["schema"]))
        return model, manifest
    except GenerationError:
        raise
    except (OSError, KeyError, TypeError, ValueError, AttributeError, RecursionError) as error:
        raise GenerationError(f"invalid or missing generation inputs: {error}") from error


def render(model: dict[str, Any], manifest: dict[str, Any]) -> str:
    """Render typed Python API module source from finalized artifacts."""
    types = Types()
    primitives = [*model["properties"], *model["capabilities"]]
    public = unique_names(
        [item["id"] for item in primitives],
        {
            "close",
            "ready",
            "closed",
            "runtime",
            "spec",
            "instance_id",
            "namespace",
            "metadata",
            "constraints",
            "lock",
            "active",
            "senders",
            "channel_specs",
            "properties",
            "components",
            "openers",
            "_owns_runtime",
            "_failure",
        }
        | set(dir(AgentRuntime)),
    )
    channels = {item["id"]: item for item in model["channels"]}
    channel_types = {name: types.type(item["schema"], name) for name, item in channels.items()}
    owners = {channel: item["id"] for item in primitives for channel in item["channels"]}
    property_channels = {channel for item in model["properties"] for channel in item["channels"]}
    functions: list[str] = []
    plans: list[str] = []

    for index, (name, channel) in enumerate(channels.items()):
        lines = types.validate(channel["schema"], "value", name)
        for constraint in model["constraints"]:
            target = constraint["target"]
            if not (
                (target["kind"] == "channel" and target["id"] == name)
                or (target["kind"] == "property" and target["id"] == owners[name])
            ):
                continue
            value = "value" + "".join("." + identifier(part) for part in target["field_path"])
            parameters = constraint["parameters"]
            if constraint["kind"] == "range":
                for bound, operator in (("min", "<"), ("max", ">")):
                    if bound in parameters:
                        lines += [
                            f"if {value} {operator} {parameters[bound]!r}:",
                            "    raise ValueError('Channel constraint violated')",
                        ]
            elif constraint["kind"] == "allowed_values":
                lines += [
                    f"if {value} not in {parameters['values']!r}:",
                    "    raise ValueError('Channel constraint violated')",
                ]
        functions.append(
            f"def _validate_{index}(value: Any) -> None:\n"
            + "\n".join("    " + line for line in lines)
            + "\n"
        )
        plans.append(
            f"ChannelSpec({name!r}, {owners[name]!r}, {channel['direction']!r}, {channel['purpose']!r}, {name in property_channels!r}, _validate_{index})"
        )

    codecs = []
    for index, item in enumerate(manifest["channel_mappings"]):
        channel = channels[item["channel"]]
        expression = "message" + ("." + item["field"] if item.get("field") else "")
        if item.get("field") and any(
            not part.isidentifier() or keyword.iskeyword(part) for part in item["field"].split(".")
        ):
            raise GenerationError("invalid mapped Python field path")
        adapter = item.get("adapter")
        decode = (
            expression if adapter else types.decode(channel["schema"], expression, channel["id"])
        )
        if channel["direction"] == "consumer_to_agent":
            encode = (
                [f"{expression} = value"]
                if adapter
                else types.encode(channel["schema"], expression, "value", channel["id"])
            )
        else:
            encode = ["raise RuntimeError('outbound encoder requested for an inbound Channel')"]
        functions.append(f"def _decode_{index}(message: Any) -> Any:\n    return {decode}\n")
        functions.append(
            f"def _encode_{index}(message: Any, value: Any) -> None:\n"
            + "\n".join("    " + line for line in (encode or ["pass"]))
            + "\n"
        )
        codecs.append(
            f"Codec({item['channel']!r}, {item['endpoint']!r}, {item['part']!r}, _encode_{index}, _decode_{index}, {adapter!r})"
        )

    handles = []
    assignments = []
    for capability in model["capabilities"]:
        name = capability["id"]
        cls = "Capability_" + public[name]
        handle = cls + "Handle"
        local = unique_names([channel for channel in capability["channels"]])
        local = {channel: identifier(channel.removeprefix(name + ".")) for channel in local}
        if len(set(local.values())) != len(local) or set(local.values()) & {"close", "_operation"}:
            raise GenerationError("Capability Channel names collide")
        members = []
        methods = []
        for channel_id, member in local.items():
            typ = channel_types[channel_id]
            if channels[channel_id]["direction"] == "consumer_to_agent":
                members.append(
                    f"        self.{member}: InputChannel[{typ}] = InputChannel(lambda value: operation.send({channel_id!r}, value))"
                )
                ch_schema = channels[channel_id]["schema"]
                if ch_schema["kind"] == "record" and ch_schema.get("fields"):
                    fields = ch_schema["fields"]
                    f_params = [
                        f"{identifier(f)}: {types.type(c, channel_id + '_' + f)}"
                        for f, c in fields.items()
                    ]
                    f_args = [f"{identifier(f)}={identifier(f)}" for f in fields]
                    methods.append(
                        f"\n    def send_{member}(self, *, {', '.join(f_params)}) -> None:\n"
                        f"        self.{member}.send({typ}({', '.join(f_args)}))\n"
                    )
            else:
                members.append(
                    f"        self.{member}: OutputChannel[{typ}] = OutputChannel(lambda timeout: cast({typ}, operation.read({channel_id!r}, timeout)), operation.buffers[{channel_id!r}].statistics)"
                )
        base = "Session" if capability["execution"] == "session" else "Invocation"
        handles.append(
            f"class {handle}({base}):\n    def __init__(self, operation: Operation) -> None:\n        super().__init__(operation)\n"
            + "\n".join(members)
            + "\n"
            + "".join(methods)
        )
        timeout = "float | None = None" if base == "Session" else "float = 5.0"
        code = f"class {cls}(Capability):\n    def start(self, *, capacity: int = 16, timeout: {timeout}) -> {handle}:\n        return {handle}(self._agent.begin({name!r}, capacity=capacity, timeout=timeout))\n"
        inputs = [
            channel for channel in local if channels[channel]["direction"] == "consumer_to_agent"
        ]
        results = [
            channel
            for channel in local
            if channels[channel]["purpose"] == "result"
            and channels[channel]["direction"] == "agent_to_consumer"
        ]
        acks = [
            channel
            for channel in local
            if channels[channel]["purpose"] == "acknowledgement"
            and channels[channel]["direction"] == "agent_to_consumer"
        ]
        if base == "Session":
            code += (
                f"\n    def __call__(self, *, capacity: int = 16, timeout: {timeout}) -> {handle}:\n"
                f"        return self.start(capacity=capacity, timeout=timeout)\n"
            )
        elif base == "Invocation" and len(inputs) == 1:
            input_id = inputs[0]
            input_schema = channels[input_id]["schema"]
            ret_type = (
                channel_types[results[0]]
                if results
                else (channel_types[acks[0]] if acks else "None")
            )
            read_channel = results[0] if results else (acks[0] if acks else None)
            read_stmt = (
                f"            return call.{local[read_channel]}.read(timeout)\n"
                if read_channel
                else ""
            )

            if input_schema["kind"] == "record" and not input_schema.get("fields"):
                code += (
                    f"\n    def __call__(self, *, timeout: float = 5.0) -> {ret_type}:\n"
                    f"        with self.start(timeout=timeout) as call:\n"
                    f"            call.{local[input_id]}.send({channel_types[input_id]}())\n"
                    f"{read_stmt}"
                )
            elif input_schema["kind"] == "record" and input_schema.get("fields"):
                fields = input_schema["fields"]
                field_params = [
                    f"{identifier(f)}: {types.type(ch, input_id + '_' + f)}"
                    for f, ch in fields.items()
                ]
                field_args = [f"{identifier(f)}={identifier(f)}" for f in fields]
                code += (
                    f"\n    def __call__(self, *, {', '.join(field_params)}, timeout: float = 5.0) -> {ret_type}:\n"
                    f"        with self.start(timeout=timeout) as call:\n"
                    f"            call.{local[input_id]}.send({channel_types[input_id]}({', '.join(field_args)}))\n"
                    f"{read_stmt}"
                )
            else:
                code += (
                    f"\n    def __call__(self, value: {channel_types[input_id]}, *, timeout: float = 5.0) -> {ret_type}:\n"
                    f"        with self.start(timeout=timeout) as call:\n"
                    f"            call.{local[input_id]}.send(value)\n"
                    f"{read_stmt}"
                )
        if base == "Invocation" and len(inputs) == len(results) == 1:
            input_id, result_id = inputs[0], results[0]
            code += (
                f"\n    def invoke(self, value: {channel_types[input_id]}, *, timeout: float = 5.0) -> {channel_types[result_id]}:\n"
                "        with self.start(timeout=timeout) as call:\n"
                f"            call.{local[input_id]}.send(value)\n"
                f"            return call.{local[result_id]}.read(timeout)\n"
            )
        handles.append(code)
        assignments.append(f"        self.{public[name]} = {cls}(self)")

    for prop in model["properties"]:
        name = prop["id"]
        typ = types.type(prop["schema"], name)
        if "constant_value" in prop:
            expression = types.constant(prop["schema"], prop["constant_value"], name)
        else:
            incoming = [
                channel
                for channel in prop["channels"]
                if channels[channel]["direction"] == "agent_to_consumer"
            ]
            if len(incoming) != 1:
                raise GenerationError("Property get requires exactly one value Channel")
            expression = f"cast({typ}, self.read_property({incoming[0]!r}, timeout))"
        outgoing = [
            channel
            for channel in prop["channels"]
            if channels[channel]["direction"] == "consumer_to_agent"
        ]
        if len(outgoing) > 1:
            raise GenerationError("Property set requires at most one update Channel")
        writer = f", lambda value: self.write_property({outgoing[0]!r}, value)" if outgoing else ""
        assignments.append(
            f"        self.{public[name]}: PropertyValue[{typ}] = "
            f"PropertyValue(lambda timeout: {expression}{writer})"
        )

    def _clean_schema(s: Any) -> Any:
        if not isinstance(s, dict):
            return s
        res = dict(s)
        if res.get("kind") == "enum" and len(res.get("values", ())) > 4:
            vals = res["values"]
            if res.get("scalar_type", "").startswith(("int", "uint")) and list(vals) == list(
                range(min(vals), max(vals) + 1)
            ):
                res["values"] = []
        if "fields" in res and isinstance(res["fields"], dict):
            res["fields"] = {k: _clean_schema(v) for k, v in res["fields"].items()}
        return res

    bindings: list[str] = []
    for binding in manifest["bindings"]:
        relevant = {
            **binding,
            "endpoints": [
                item
                for item in manifest["endpoints"]
                if item["id"].rsplit(".", 1)[0] == binding["id"]
            ],
            "channel_mappings": [
                item
                for item in manifest["channel_mappings"]
                if owners[item["channel"]] == binding["id"]
            ],
        }
        if "instance_configuration_schema" in relevant:
            relevant["instance_configuration_schema"] = _clean_schema(
                relevant["instance_configuration_schema"]
            )
        validator = f"_instance_{len(bindings)}"
        schema = binding.get("instance_configuration_schema", {"kind": "record", "fields": {}})
        validation = [
            line.replace("invalid Channel payload", "invalid instance configuration")
            for line in types.validate(schema, "values", validator, mapping_record=True)
        ]
        functions.append(
            f"def {validator}(values: Mapping[str, object]) -> None:\n"
            + "\n".join("    " + line for line in validation)
        )
        bindings.append(
            f"BindingSpec({binding['id']!r}, {binding['configuration']!r}, {relevant!r}, {binding['runtime_factory']!r}, {validator})"
        )

    metadata = {key: model[key] for key in ("description", "metadata", "groups", "constraints")}
    header = '''"""Generated Agent API, version 0.1.0. Do not edit."""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, cast
from agent_framework.runtime.agent import (
    AgentRuntime, AgentSpec, BindingSpec, ChannelSpec, Codec, Operation, SharedServices,
)
from agent_framework.runtime.agent import create_runtime as Runtime
from agent_framework.runtime.channel import InputChannel, OutputChannel
from agent_framework.runtime.errors import AgentError, FailureCode
from agent_framework.runtime.handles import Capability, Invocation, PropertyValue, Session
'''
    plan = (
        "_SPEC = AgentSpec(\n"
        + f"    {model['id']!r},\n"
        + "    (\n        "
        + ",\n        ".join(plans)
        + (",\n    " if plans else "")
        + "),\n"
        + "    (\n        "
        + ",\n        ".join(codecs)
        + (",\n    " if codecs else "")
        + "),\n"
        + "    (\n        "
        + ",\n        ".join(bindings)
        + (",\n    " if bindings else "")
        + "),\n"
        + f"    {tuple(manifest['endpoints'])!r},\n    {metadata!r},\n)\n"
    )
    agent = (
        "class Agent(AgentRuntime):\n"
        + f"    metadata = {metadata!r}\n"
        + "    def __init__(self, *, instance_id: str, namespace: str = '', runtime: SharedServices | None = None, instance_configuration: Mapping[str, Mapping[str, object]] | None = None) -> None:\n"
        "        super().__init__(_SPEC, instance_id=instance_id, namespace=namespace, runtime=runtime, instance_configuration=instance_configuration)\n"
        + "\n".join(assignments) + "\n"
    )
    return "\n\n".join([header, *types.definitions, *functions, plan, *handles, agent])
