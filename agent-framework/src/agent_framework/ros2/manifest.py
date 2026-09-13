"""One deterministic, instance-independent ROS2 build artifact."""

from dataclasses import dataclass

from agent_framework.serialization.json import normalize

from .interfaces import CustomInterface
from .mapping import ChannelMapping
from .model import Endpoint


@dataclass(frozen=True, slots=True, kw_only=True)
class RealizationManifest:
    agent_id: str
    resolved_agent_model_hash: str
    binding_lock: dict[str, object]
    bindings: tuple[dict[str, object], ...]
    endpoints: tuple[Endpoint, ...]
    channel_mappings: tuple[ChannelMapping, ...]
    interface_types: tuple[str, ...]
    custom_interfaces: tuple[CustomInterface, ...]
    custom_interface_artifacts: dict[str, str]
    schema_version: str = "0.1.0"
    namespace_template: str = "{namespace}"
    instance_template: str = "{instance_id}"


def manifest_data(manifest: RealizationManifest) -> dict[str, object]:
    data = normalize(manifest)
    assert isinstance(data, dict)
    data["endpoints"] = [
        {key: value for key, value in endpoint.items() if value is not None}
        for endpoint in data["endpoints"]
    ]
    return data
