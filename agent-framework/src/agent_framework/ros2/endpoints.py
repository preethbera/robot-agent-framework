"""Validate endpoint defaults, names, and instance-independent templates."""

import re
from collections.abc import Mapping
from dataclasses import replace
from string import Formatter

from .errors import RealizationError
from .model import Endpoint, EndpointTemplate, keys, mapping, sequence, text
from .qos import QOS_FIELDS, parse_qos

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


def parse_endpoint_template(value: object) -> EndpointTemplate:
    data = mapping(value, "endpoint template")
    overridable = tuple(
        text(item, "overridable field")
        for item in sequence(data.pop("overridable", ()), "overridable")
    )
    permitted = {"name", *(f"qos.{field}" for field in QOS_FIELDS)}
    if set(overridable) - permitted or len(set(overridable)) != len(overridable):
        raise RealizationError("unsupported or duplicate overridable field")
    requirements = mapping(data.pop("requirements", {}), "endpoint requirements")
    keys(requirements, {"name", "qos"}, set(), "endpoint requirements")
    if "name" in requirements:
        validate_name(text(requirements["name"], "required name"), template=True)
    if "qos" in requirements:
        requirements["qos"] = parse_qos(requirements["qos"], partial=True)
    template = EndpointTemplate(
        endpoint=parse_endpoint(data), overridable=overridable, requirements=requirements
    )
    check_requirements(template.endpoint, requirements)
    return template


def check_requirements(endpoint: Endpoint, requirements: Mapping[str, object]) -> None:
    if "name" in requirements and requirements["name"] != (endpoint.name or endpoint.name_template):
        raise RealizationError(f"{endpoint.id}: mandatory name requirement violated")
    for field, value in mapping(requirements.get("qos", {}), "required qos").items():
        if (endpoint.qos or {}).get(field) != value:
            raise RealizationError(f"{endpoint.id}: mandatory qos.{field} requirement violated")


def apply_override(template: EndpointTemplate, value: object) -> Endpoint:
    override = mapping(value, "endpoint override")
    keys(override, {"name", "qos"}, set(), "endpoint override")
    changed = set(override) - {"qos"}
    qos = parse_qos(override["qos"], partial=True) if "qos" in override else {}
    changed.update(f"qos.{field}" for field in qos)
    if changed - set(template.overridable):
        raise RealizationError(
            f"endpoint override not permitted: {sorted(changed - set(template.overridable))}"
        )
    endpoint = template.endpoint
    if "name" in override:
        name = text(override["name"], "override name")
        validate_name(name)
        endpoint = replace(endpoint, name=name, name_template=None)
    if "qos" in override:
        endpoint = replace(endpoint, qos=parse_qos({**(endpoint.qos or {}), **qos}))
    check_requirements(endpoint, template.requirements)
    return endpoint


def materialize_endpoint(endpoint: Endpoint, agent_id: str, binding_instance_id: str) -> Endpoint:
    name_template = endpoint.name_template
    if name_template is not None:
        name_template = name_template.replace("{agent_id}", agent_id).replace(
            "{binding_instance_id}", binding_instance_id
        )
        validate_name(name_template, template=True)
        endpoint = replace(endpoint, name_template=name_template)
        if "{" not in name_template:
            endpoint = replace(endpoint, name=name_template, name_template=None)
    return replace(endpoint, id=f"{binding_instance_id}.{endpoint.id}")
