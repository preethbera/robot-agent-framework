"""Type inference, identifier normalization, and dataclass emission for Agent APIs."""

from __future__ import annotations

import base64
import keyword
import re
from typing import Any

from agent_framework.model import PayloadSchema, ScalarType, SchemaKind
from agent_framework.serialization.json import canonical_json


class GenerationError(ValueError):
    """Artifact inconsistency or unsupported static payload conversion."""


def identifier(value: str) -> str:
    """Sanitize any arbitrary string into a valid Python identifier."""
    result = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    if not result or result[0].isdigit():
        result = "value_" + result
    return result + "_" if keyword.iskeyword(result) else result


def unique_names(values: list[str], reserved: set[str] | None = None) -> dict[str, str]:
    """Ensure member names are unique and do not collide with Python keywords or reserved terms."""
    names = {value: identifier(value) for value in values}
    if len(set(names.values())) != len(values) or set(names.values()) & (reserved or set()):
        raise GenerationError("Python member names collide after normalization")
    return names


class Types:
    """Manages Python type strings, dataclass definitions, and encoding/decoding expressions."""

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
                f"{identifier(field)}={self.decode(child, expression + '.' + field, hint + '_' + field)}"
                for field, child in schema["fields"].items()
            ]
            return f"{self.type(schema, hint)}({', '.join(fields)})"
        if kind in {"array", "sequence"}:
            return f"[{self.decode(schema['items'], 'element', hint + '_item')} for element in {expression}]"
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
                if (
                    len(values) > 4
                    and scalar.startswith(("int", "uint"))
                    and list(values) == list(range(min(values), max(values) + 1))
                ):
                    checks.append(f"{min(values)} <= {value} <= {max(values)}")
                else:
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
