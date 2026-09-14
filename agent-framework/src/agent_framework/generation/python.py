"""Static typed Python API generation from the two finalized build artifacts."""

from __future__ import annotations

import ast
import base64
import json
import keyword
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from agent_framework.model import PayloadSchema, ScalarType, SchemaKind, validate_schema
from agent_framework.runtime.agent import AgentRuntime
from agent_framework.serialization.hashing import content_hash
from agent_framework.serialization.json import canonical_json


class GenerationError(ValueError):
    """Artifact inconsistency or unsupported static payload conversion."""


def identifier(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    if not result or result[0].isdigit():
        result = "value_" + result
    return result + "_" if keyword.iskeyword(result) else result


def unique_names(values: list[str], reserved: set[str] | None = None) -> dict[str, str]:
    names = {value: identifier(value) for value in values}
    if len(set(names.values())) != len(values) or set(names.values()) & (reserved or set()):
        raise GenerationError("Python member names collide after normalization")
    return names


class Types:
    def __init__(self) -> None:
        self.definitions: list[str] = []
        self.names: dict[bytes, str] = {}

    def type(self, schema: dict[str, Any], hint: str) -> str:
        kind = schema["kind"]
        if kind in {"scalar", "enum"}:
            scalar = schema["scalar_type"]
            if scalar == "bool":
                return "bool"
            if scalar.startswith(("int", "uint")):
                return "int"
            return {"float32": "float", "float64": "float", "string": "str", "bytes": "bytes"}[
                scalar
            ]
        if kind in {"array", "sequence"}:
            return f"list[{self.type(schema['items'], hint + '_item')}]"
        if kind == "opaque":
            return "object"
        if kind != "record":
            raise GenerationError(f"unsupported payload schema kind {kind!r}")
        key = canonical_json(schema)
        if key in self.names:
            return self.names[key]
        name = "Payload_" + identifier(hint)
        if name in self.names.values():
            raise GenerationError("generated payload type name collision")
        self.names[key] = name
        fields = schema["fields"]
        names = unique_names(list(fields))
        members = [
            f"    {names[field]}: {self.type(child, hint + '_' + field)}"
            for field, child in fields.items()
        ]
        self.definitions.append(
            "@dataclass(frozen=True, slots=True)\nclass "
            + name
            + ":\n"
            + ("\n".join(members) or "    pass")
            + "\n"
        )
        return name

    def decode(self, schema: dict[str, Any], expression: str, hint: str) -> str:
        kind = schema["kind"]
        if kind in {"scalar", "enum"}:
            return f"{self.type(schema, hint)}({expression})"
        if kind == "record":
            if any(
                not field.isidentifier() or keyword.iskeyword(field) for field in schema["fields"]
            ):
                raise GenerationError(
                    "native record fields require Python identifiers or a binding adapter"
                )
            fields = [
                f"{identifier(field)}={self.decode(child, expression + '.' + field, hint + '_' + field)}"  # noqa: E501
                for field, child in schema["fields"].items()
            ]
            return f"{self.type(schema, hint)}({', '.join(fields)})"
        if kind in {"array", "sequence"}:
            return f"[{self.decode(schema['items'], 'element', hint + '_item')} for element in {expression}]"  # noqa: E501
        raise GenerationError("opaque transport payloads require an explicit binding adapter")

    def encode(self, schema: dict[str, Any], target: str, value: str, hint: str) -> list[str]:
        kind = schema["kind"]
        if kind == "record":
            if any(
                not field.isidentifier() or keyword.iskeyword(field) for field in schema["fields"]
            ):
                raise GenerationError(
                    "native record fields require Python identifiers or a binding adapter"
                )
            return [
                line
                for field, child in schema["fields"].items()
                for line in self.encode(
                    child, target + "." + field, value + "." + identifier(field), hint + "_" + field
                )
            ]
        if kind == "opaque" or (
            kind in {"sequence", "array"} and schema["items"]["kind"] not in {"scalar", "enum"}
        ):
            raise GenerationError(
                "structured collection/opaque writes require an explicit binding adapter"
            )
        if target == "message":
            raise GenerationError("a scalar mapping must select a ROS message field")
        if kind in {"scalar", "enum"} and schema["scalar_type"] in {"float32", "float64"}:
            value = f"float({value})"
        return [f"{target} = {value}"]

    def validate(
        self,
        schema: dict[str, Any],
        value: str,
        hint: str,
        depth: int = 0,
        *,
        mapping_record: bool = False,
    ) -> list[str]:
        kind = schema["kind"]
        checks = []
        children: list[str] = []
        if kind in {"scalar", "enum"}:
            scalar = schema["scalar_type"]
            if scalar in {"float32", "float64"}:
                limit = 3.4028234663852886e38 if scalar == "float32" else 1.7976931348623157e308
                checks.append(
                    f"type({value}) in (int, float) and -{limit!r} <= {value} <= {limit!r}"
                )
            elif scalar.startswith(("int", "uint")):
                signed = scalar.startswith("int")
                bits = int(scalar.removeprefix("int" if signed else "uint"))
                lower, upper = (
                    (-(1 << (bits - 1)) if signed else 0),
                    (1 << (bits - int(signed))) - 1,
                )
                checks.append(f"type({value}) is int and {lower} <= {value} <= {upper}")
            else:
                checks.append(f"isinstance({value}, {self.type(schema, hint)})")
            if kind == "enum":
                values = schema["values"]
                if scalar == "bytes":
                    values = [base64.b64decode(item) for item in values]
                checks.append(f"{value} in {values!r}")
        elif kind == "record":
            if mapping_record:
                checks.append(f"isinstance({value}, Mapping)")
                checks.append(f"not ({value}.keys() - set({tuple(sorted(schema['fields']))!r}))")
            else:
                checks.append(f"isinstance({value}, {self.type(schema, hint)})")
            for field, child in schema["fields"].items():
                if mapping_record:
                    children.append(f"if {field!r} in {value}:")
                    children.extend(
                        "    " + line
                        for line in self.validate(
                            child,
                            f"{value}[{field!r}]",
                            hint + "_" + field,
                            depth,
                            mapping_record=True,
                        )
                    )
                else:
                    children.extend(
                        self.validate(
                            child, f"{value}.{identifier(field)}", hint + "_" + field, depth
                        )
                    )
        elif kind in {"array", "sequence"}:
            checks.append(f"isinstance({value}, list)")
            if kind == "array":
                checks.append(f"len({value}) == {schema['length']}")
            variable = f"element_{depth}"
            children.append(f"for {variable} in {value}:")
            children.extend(
                "    " + line
                for line in self.validate(
                    schema["items"],
                    variable,
                    hint + "_item",
                    depth + 1,
                    mapping_record=mapping_record,
                )
            )
        lines = [
            line
            for check in checks
            for line in (f"if not ({check}):", "    raise ValueError('invalid Channel payload')")
        ]
        return lines + children or ["pass"]

    def constant(self, schema: dict[str, Any], value: Any, hint: str) -> str:
        kind = schema["kind"]
        if kind == "record":
            args = [
                f"{identifier(field)}={self.constant(child, value[field], hint + '_' + field)}"
                for field, child in schema["fields"].items()
            ]
            return f"{self.type(schema, hint)}({', '.join(args)})"
        if kind in {"sequence", "array"}:
            return (
                "["
                + ", ".join(
                    self.constant(schema["items"], child, hint + "_item") for child in value
                )
                + "]"
            )
        if schema.get("scalar_type") == "bytes":
            return repr(base64.b64decode(value))
        return repr(value)


def schema_from_data(data: dict[str, Any]) -> PayloadSchema:
    scalar = ScalarType(data["scalar_type"]) if data.get("scalar_type") is not None else None
    values = tuple(data.get("values", ()))
    if scalar is ScalarType.BYTES:
        values = tuple(base64.b64decode(value, validate=True) for value in values)
    return PayloadSchema(
        kind=SchemaKind(data["kind"]),
        scalar_type=scalar,
        fields={name: schema_from_data(child) for name, child in data.get("fields", {}).items()},
        items=schema_from_data(data["items"]) if data.get("items") is not None else None,
        length=data.get("length"),
        values=values,
        metadata=data.get("metadata", {}),
    )


def load_artifacts(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
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
            f"ChannelSpec({name!r}, {owners[name]!r}, {channel['direction']!r}, {channel['purpose']!r}, {name in property_channels!r}, _validate_{index})"  # noqa: E501
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
            f"Codec({item['channel']!r}, {item['endpoint']!r}, {item['part']!r}, _encode_{index}, _decode_{index}, {adapter!r})"  # noqa: E501
        )
    handles = []
    assignments = []
    for capability in model["capabilities"]:
        name = capability["id"]
        cls = "Capability_" + public[name]
        handle = cls + "Handle"
        local = unique_names([channel for channel in capability["channels"]])
        # Expose binding-local Channel names while preserving exact IDs in generated calls.
        local = {channel: identifier(channel.removeprefix(name + ".")) for channel in local}
        if len(set(local.values())) != len(local) or set(local.values()) & {"close", "_operation"}:
            raise GenerationError("Capability Channel names collide")
        members = []
        for channel_id, member in local.items():
            typ = channel_types[channel_id]
            if channels[channel_id]["direction"] == "consumer_to_agent":
                members.append(
                    f"        self.{member}: InputChannel[{typ}] = InputChannel(lambda value: operation.send({channel_id!r}, value))"  # noqa: E501
                )
            else:
                members.append(
                    f"        self.{member}: OutputChannel[{typ}] = OutputChannel(lambda timeout: cast({typ}, operation.read({channel_id!r}, timeout)), operation.buffers[{channel_id!r}].statistics)"  # noqa: E501
                )
        base = "Session" if capability["execution"] == "session" else "Invocation"
        handles.append(
            f"class {handle}({base}):\n    def __init__(self, operation: Operation) -> None:\n        super().__init__(operation)\n"  # noqa: E501
            + "\n".join(members)
            + "\n"
        )
        timeout = "float | None = None" if base == "Session" else "float = 5.0"
        code = f"class {cls}(Capability):\n    def start(self, *, capacity: int = 16, timeout: {timeout}) -> {handle}:\n        return {handle}(self._agent.begin({name!r}, capacity=capacity, timeout=timeout))\n"  # noqa: E501
        inputs = [
            channel for channel in local if channels[channel]["direction"] == "consumer_to_agent"
        ]
        results = [
            channel
            for channel in local
            if channels[channel]["purpose"] == "result"
            and channels[channel]["direction"] == "agent_to_consumer"
        ]
        if base == "Invocation" and len(inputs) == len(results) == 1:
            input_id, result_id = inputs[0], results[0]
            code += (
                f"\n    def invoke(self, value: {channel_types[input_id]}, *, timeout: float = 5.0) -> {channel_types[result_id]}:\n"  # noqa: E501
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
            f"BindingSpec({binding['id']!r}, {binding['configuration']!r}, {relevant!r}, {binding['runtime_factory']!r}, {validator})"  # noqa: E501
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
from agent_framework.runtime.capability import Capability
from agent_framework.runtime.channel import InputChannel, OutputChannel
from agent_framework.runtime.errors import AgentError as AgentError, FailureCode as FailureCode
from agent_framework.runtime.invocation import Invocation
from agent_framework.runtime.property import PropertyValue
from agent_framework.runtime.session import Session
'''
    plan = (
        "_SPEC = AgentSpec(\n"
        + f"    {model['id']!r},\n    ("
        + ",".join(plans)
        + ("," if plans else "")
        + "),\n    ("
        + ",".join(codecs)
        + ("," if codecs else "")
        + "),\n    ("
        + ",".join(bindings)
        + ("," if bindings else "")
        + "),\n"
        + f"    {tuple(manifest['endpoints'])!r},\n    {metadata!r},\n)\n"
    )
    agent = (
        "class Agent(AgentRuntime):\n"
        + f"    metadata = {metadata!r}\n"
        + "    def __init__(self, *, instance_id: str, namespace: str = '', runtime: SharedServices | None = None, instance_configuration: Mapping[str, Mapping[str, object]] | None = None) -> None:\n"  # noqa: E501
        "        super().__init__(_SPEC, instance_id=instance_id, namespace=namespace, runtime=runtime, instance_configuration=instance_configuration)\n"  # noqa: E501
         + "\n".join(assignments) + "\n"
    )
    return "\n\n".join([header, *types.definitions, *functions, plan, *handles, agent])


def generate_python(directory: Path) -> Path:
    """Generate only from matching M2/M3 artifacts in an Agent build directory."""
    model, manifest = load_artifacts(directory)
    try:
        source = render(model, manifest)
        ast.parse(source)
    except (KeyError, TypeError, SyntaxError) as error:
        raise GenerationError(f"cannot generate Python API: {error}") from error
    package = directory / "python" / ("agent_" + identifier(model["id"]))
    if not package.resolve().is_relative_to(directory.resolve()):
        raise GenerationError("Python output path escapes Agent build directory")
    package.mkdir(parents=True, exist_ok=True)
    for name, content in (("__init__.py", source), ("py.typed", "")):
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=package, mode="w", encoding="utf-8", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            os.replace(temporary, package / name)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return package
