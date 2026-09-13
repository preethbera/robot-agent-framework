"""Validate endpoint defaults, names, and instance-independent templates."""

import re
from string import Formatter

from .errors import RealizationError
from .model import Endpoint, keys, mapping, text
from .qos import parse_qos

ROLES = {
    "topic": {"publisher", "subscriber"},
    "service": {"client", "server"},
    "action": {"action_client", "action_server"},
}
INTERFACE_KINDS = {"topic": "msg", "service": "srv", "action": "action"}
TEMPLATE_FIELDS = {"agent_id", "binding_instance_id", "namespace", "instance_id"}


def validate_name(name: str, *, template: bool = False) -> None:
    candidate = name
    if template:
        try:
            parts = list(Formatter().parse(name))
        except ValueError as error:
            raise RealizationError("invalid endpoint name template") from error
        for _, field, spec, conversion in parts:
            if field is not None and (field not in TEMPLATE_FIELDS or spec or conversion):
                raise RealizationError(f"unsupported endpoint template field {field!r}")
        candidate = name.format_map(dict.fromkeys(TEMPLATE_FIELDS, "token"))
    if candidate.startswith("~/"):
        candidate = candidate[2:]
    elif candidate.startswith("/"):
        candidate = candidate[1:]
    if not candidate or any(
        not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token) for token in candidate.split("/")
    ):
        raise RealizationError(f"invalid ROS2 endpoint name {name!r}")


def parse_endpoint(value: object) -> Endpoint:
    data = mapping(value, "endpoint")
    required = {"id", "kind", "interface_type", "role", "existing"}
    keys(data, required | {"name", "name_template", "qos"}, required, "endpoint")
    identifier = text(data["id"], "endpoint.id")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise RealizationError("endpoint.id must be a local identifier without dots")
    kind = text(data["kind"], "endpoint.kind")
    role = text(data["role"], "endpoint.role")
    if kind not in ROLES or role not in ROLES[kind]:
        raise RealizationError("invalid endpoint kind/role combination")
    interface = text(data["interface_type"], "endpoint.interface_type")
    if not re.fullmatch(rf"[a-z][a-z0-9_]*/{INTERFACE_KINDS[kind]}/[A-Z][A-Za-z0-9]*", interface):
        raise RealizationError("interface_type must match package/msg|srv|action/Type and kind")
    existing = data["existing"]
    if type(existing) is not bool:
        raise RealizationError("endpoint.existing must be a boolean")
    if ("name" in data) == ("name_template" in data):
        raise RealizationError("endpoint requires exactly one of name or name_template")
    field = "name" if "name" in data else "name_template"
    name = text(data[field], f"endpoint.{field}")
    validate_name(name, template=field == "name_template")
    return Endpoint(
        id=identifier,
        kind=kind,
        interface_type=interface,
        role=role,
        existing=existing,
        name=name if field == "name" else None,
        name_template=name if field == "name_template" else None,
        qos=parse_qos(data["qos"]) if "qos" in data else None,
    )
