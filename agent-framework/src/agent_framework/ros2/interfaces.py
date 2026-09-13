"""Materialize explicitly requested custom interfaces, never generic wrappers."""

import re
from dataclasses import dataclass

from .errors import RealizationError
from .model import Endpoint, keys, mapping, sequence, text

SECTIONS = {
    "msg": ("message",),
    "srv": ("request", "response"),
    "action": ("goal", "result", "feedback"),
}
SCALARS = {
    "bool",
    "byte",
    "char",
    "float32",
    "float64",
    "int8",
    "uint8",
    "int16",
    "uint16",
    "int32",
    "uint32",
    "int64",
    "uint64",
    "string",
    "wstring",
}


@dataclass(frozen=True, slots=True, kw_only=True)
class CustomInterface:
    interface_type: str
    reason: str
    path: str
    content: str


def parse_custom_interfaces(value: object) -> tuple[CustomInterface, ...]:
    result = []
    seen: set[str] = set()
    for item in sequence(value, "custom_interfaces"):
        data = mapping(item, "custom interface")
        keys(
            data,
            {"interface_type", "reason", "parts"},
            {"interface_type", "reason", "parts"},
            "custom interface",
        )
        interface = text(data["interface_type"], "custom interface type")
        if not re.fullmatch(r"[a-z][a-z0-9_]*/(msg|srv|action)/[A-Z][A-Za-z0-9]*", interface):
            raise RealizationError("invalid custom interface type")
        if interface in seen:
            raise RealizationError(f"duplicate custom interface {interface}")
        seen.add(interface)
        package, kind, name = interface.split("/")
        parts = mapping(data["parts"], "custom interface parts")
        keys(parts, set(SECTIONS[kind]), set(SECTIONS[kind]), "custom interface parts")
        sections = []
        for part in SECTIONS[kind]:
            fields = mapping(parts[part], f"custom interface {part}")
            lines = []
            # Field order is the binding declaration order and affects the ROS interface.
            for field, field_type in fields.items():
                if (
                    not re.fullmatch(r"[a-z][a-z0-9_]*", field)
                    or field.endswith("_")
                    or "__" in field
                ):
                    raise RealizationError("invalid custom interface field name")
                if not isinstance(field_type, str) or field_type not in SCALARS:
                    raise RealizationError(
                        "custom interface generation supports scalar fields only"
                    )
                lines.append(f"{field_type} {field}\n")
            sections.append("".join(lines))
        result.append(
            CustomInterface(
                interface_type=interface,
                reason=text(data["reason"], "custom interface reason"),
                path=f"interfaces/{package}/{kind}/{name}.{kind}",
                content="---\n".join(sections),
            )
        )
    return tuple(sorted(result, key=lambda item: item.interface_type))


def interface_artifacts(
    interfaces: tuple[CustomInterface, ...], endpoints: tuple[Endpoint, ...]
) -> dict[str, str]:
    declared = {item.interface_type: item for item in interfaces}
    required = {item.interface_type for item in endpoints if not item.existing}
    if required != declared.keys():
        raise RealizationError(
            "custom interface declarations must exactly match non-existing interfaces"
        )
    if required & {item.interface_type for item in endpoints if item.existing}:
        raise RealizationError("interface cannot be both existing and generated")
    artifacts = {item.path: item.content for item in interfaces}
    packages = sorted({name.split("/")[0] for name in required})
    for package in packages:
        names = sorted(name for name in required if name.startswith(package + "/"))
        paths = []
        for interface in names:
            _, kind, name = interface.split("/")
            paths.append(f'  "{kind}/{name}.{kind}"\n')
        artifacts[f"interfaces/{package}/CMakeLists.txt"] = (
            f"cmake_minimum_required(VERSION 3.8)\nproject({package})\n"
            "find_package(ament_cmake REQUIRED)\n"
            "find_package(rosidl_default_generators REQUIRED)\n"
            "rosidl_generate_interfaces(${PROJECT_NAME}\n" + "".join(paths) + ")\n"
            "ament_export_dependencies(rosidl_default_runtime)\nament_package()\n"
        )
        artifacts[f"interfaces/{package}/package.xml"] = (
            '<?xml version="1.0"?>\n<package format="3">\n'
            f"  <name>{package}</name>\n  <version>0.1.0</version>\n"
            "  <description>Binding-requested Agent interfaces</description>\n"
            '  <maintainer email="noreply@example.invalid">Agent Framework</maintainer>\n'
            "  <license>Apache-2.0</license>\n"
            "  <buildtool_depend>ament_cmake</buildtool_depend>\n"
            "  <buildtool_depend>rosidl_default_generators</buildtool_depend>\n"
            "  <exec_depend>rosidl_default_runtime</exec_depend>\n"
            "  <member_of_group>rosidl_interface_packages</member_of_group>\n"
            "  <export><build_type>ament_cmake</build_type></export>\n</package>\n"
        )
    return artifacts
