"""Build binding-owned realizations after Agent semantic resolution."""

import os
import tempfile
from copy import deepcopy
from pathlib import Path

from agent_framework.resolution.resolver import Resolution
from agent_framework.serialization.hashing import artifact_hash
from agent_framework.serialization.json import canonical_json, normalize

from .endpoints import apply_override, materialize_endpoint, parse_endpoint_template
from .errors import RealizationError
from .interfaces import CustomInterface, interface_artifacts, parse_custom_interfaces
from .manifest import RealizationManifest, manifest_data
from .mapping import ChannelMapping, parse_mappings
from .model import Endpoint, keys, mapping, sequence

TEMPLATE_KEYS = {
    "endpoints",
    "channel_mappings",
    "custom_interfaces",
    "internal_communication",
    "startup",
    "lifecycle",
}


def resolved_model_data(resolution: Resolution) -> dict[str, object]:
    return {"schema_version": "0.1.0", **mapping(normalize(resolution.agent), "resolved model")}


def build_realization(resolution: Resolution) -> RealizationManifest:
    """Pure build from a resolved Agent; no runtime factories or ROS imports execute."""
    endpoints: dict[str, Endpoint] = {}
    mappings: list[ChannelMapping] = []
    interfaces: dict[str, CustomInterface] = {}
    bindings = []
    overrides = mapping(resolution.definition.ros2_overrides, "ROS2 overrides")
    used_overrides: set[str] = set()
    exposures = {item.alias: item for item in resolution.definition.expose}
    for selected in sorted(resolution.bindings, key=lambda item: item.alias):
        definition = selected.definition
        configuration = deepcopy(
            {**definition.configuration_defaults, **exposures[selected.alias].config}
        )
        try:
            description = (
                definition.configure_ros2(configuration)
                if definition.configure_ros2
                else definition.ros2_template
            )
            # Snapshot declarative data; reject executable/non-finite/cyclic output.
            template = mapping(normalize(description), f"{selected.alias} ROS2 template")
        except (ValueError, TypeError, KeyError) as error:
            raise RealizationError(
                f"{selected.alias}: invalid ROS2 description: {error}"
            ) from error
        keys(template, TEMPLATE_KEYS, {"endpoints", "channel_mappings"}, "ROS2 template")
        local_endpoints: dict[str, Endpoint] = {}
        for item in sequence(template["endpoints"], "endpoints"):
            endpoint_template = parse_endpoint_template(item)
            target = f"{selected.alias}.{endpoint_template.endpoint.id}"
            endpoint = apply_override(endpoint_template, overrides.get(target, {}))
            if target in overrides:
                used_overrides.add(target)
            endpoint = materialize_endpoint(endpoint, resolution.agent.id, selected.alias)
            if endpoint.id in endpoints:
                raise RealizationError(f"duplicate endpoint ID {endpoint.id}")
            endpoints[endpoint.id] = local_endpoints[endpoint.id] = endpoint
        mappings.extend(
            parse_mappings(
                template["channel_mappings"],
                alias=selected.alias,
                channels=selected.semantics.channels,
                endpoints=local_endpoints,
            )
        )
        for interface in parse_custom_interfaces(template.get("custom_interfaces", ())):
            if (
                interface.interface_type in interfaces
                and interfaces[interface.interface_type] != interface
            ):
                raise RealizationError(f"conflicting custom interface {interface.interface_type}")
            interfaces[interface.interface_type] = interface
        bindings.append(
            {
                "id": selected.alias,
                "binding": definition.id,
                "dependencies": sorted(definition.dependencies),
                "configuration": configuration,
                "runtime_mode": definition.runtime_mode.value,
                "runtime_factory": definition.runtime_factory,
                "internal_communication": template.get("internal_communication", []),
                "startup": template.get("startup", []),
                "lifecycle": template.get("lifecycle", []),
            }
        )
    if overrides.keys() - used_overrides:
        raise RealizationError(
            f"unknown ROS2 override targets: {sorted(overrides.keys() - used_overrides)}"
        )
    ordered_endpoints = tuple(endpoints[name] for name in sorted(endpoints))
    ordered_interfaces = tuple(interfaces[name] for name in sorted(interfaces))
    manifest = RealizationManifest(
        agent_id=resolution.agent.id,
        resolved_agent_model_hash=artifact_hash(resolved_model_data(resolution)),
        binding_lock=deepcopy(resolution.binding_lock),
        bindings=tuple(bindings),
        endpoints=ordered_endpoints,
        channel_mappings=tuple(
            sorted(
                mappings,
                key=lambda item: (item.channel, item.endpoint, item.part, item.field or ""),
            )
        ),
        interface_types=tuple(sorted({item.interface_type for item in ordered_endpoints})),
        custom_interfaces=ordered_interfaces,
        custom_interface_artifacts=interface_artifacts(ordered_interfaces, ordered_endpoints),
    )
    canonical_json(manifest_data(manifest))
    return manifest


def artifact_directory(resolution: Resolution, workspace: Path) -> Path:
    identifier = resolution.agent.id
    if (
        not identifier
        or identifier in {".", ".."}
        or any(char in identifier for char in ("/", "\\", "\x00"))
    ):
        raise RealizationError("unsafe Agent artifact directory name")
    root = workspace.resolve()
    directory = root / "build" / "agents" / identifier
    if not directory.resolve().is_relative_to(root / "build"):
        raise RealizationError("artifact directory escapes workspace build tree")
    return directory


def write_realization(resolution: Resolution, workspace: Path) -> Path:
    """Verify persisted M2 inputs, then write custom files and publish the manifest last."""
    directory = artifact_directory(resolution, workspace)
    for name, expected in (
        ("resolved_agent_model.json", resolved_model_data(resolution)),
        ("binding_lock.json", resolution.binding_lock),
    ):
        try:
            content = (directory / name).read_bytes()
        except OSError as error:
            raise RealizationError(f"missing/unreadable M2 artifact {name}") from error
        if content != canonical_json(expected):
            raise RealizationError(f"M2 artifact {name} does not match supplied resolution")
    manifest = build_realization(resolution)
    payloads = {
        name: content.encode("utf-8")
        for name, content in manifest.custom_interface_artifacts.items()
    }
    payloads["ros2_realization.json"] = canonical_json(manifest_data(manifest))
    # Preflight every path before writing anything, including existing symlinks.
    for name in payloads:
        if not (directory / name).resolve().is_relative_to(directory.resolve()):
            raise RealizationError("ROS2 artifact path escapes Agent directory")
    for name, payload in payloads.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return directory / "ros2_realization.json"
