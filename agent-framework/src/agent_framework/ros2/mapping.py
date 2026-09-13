"""Validate binding-provided Channel mappings; never infer technology behavior."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from agent_framework.model import Channel, Direction

from .errors import RealizationError
from .model import Endpoint, keys, mapping, sequence, text

PARTS = {
    "topic": {"message"},
    "service": {"request", "response"},
    "action": {"goal", "feedback", "result", "cancel"},
}


@dataclass(frozen=True, slots=True, kw_only=True)
class ChannelMapping:
    channel: str
    endpoint: str
    part: str
    field: str | None = None
    adapter: str | None = None


def parse_mappings(
    value: object, *, alias: str, channels: tuple[Channel, ...], endpoints: Mapping[str, Endpoint]
) -> tuple[ChannelMapping, ...]:
    known = {channel.id: channel for channel in channels}
    result = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for item in sequence(value, "channel_mappings"):
        data = mapping(item, "Channel mapping")
        keys(
            data,
            {"channel", "endpoint", "part", "field", "adapter"},
            {"channel", "endpoint", "part"},
            "Channel mapping",
        )
        channel_id = f"{alias}.{text(data['channel'], 'mapping.channel')}"
        endpoint_id = f"{alias}.{text(data['endpoint'], 'mapping.endpoint')}"
        if channel_id not in known or endpoint_id not in endpoints:
            raise RealizationError(
                f"unknown Channel or endpoint in mapping: {channel_id}, {endpoint_id}"
            )
        part = text(data["part"], "mapping.part")
        endpoint = endpoints[endpoint_id]
        if part not in PARTS[endpoint.kind]:
            raise RealizationError(f"{endpoint_id}: invalid {endpoint.kind} interface part {part}")
        # Roles describe the Agent runtime's ROS connection to the native endpoint.
        sends = (
            endpoint.role == "publisher"
            if endpoint.kind == "topic"
            else (
                (endpoint.role in {"client", "action_client"})
                == (part in {"request", "goal", "cancel"})
            )
        )
        expected = Direction.CONSUMER_TO_AGENT if sends else Direction.AGENT_TO_CONSUMER
        if known[channel_id].direction is not expected:
            raise RealizationError(
                f"{channel_id}: Channel direction contradicts endpoint role/part"
            )
        field = text(data["field"], "mapping.field") if "field" in data else None
        if field is not None and not re.fullmatch(
            r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*", field
        ):
            raise RealizationError("invalid interface field path")
        identity = (channel_id, endpoint_id, part, field)
        if identity in seen:
            raise RealizationError("duplicate Channel mapping")
        seen.add(identity)
        result.append(
            ChannelMapping(
                channel=channel_id,
                endpoint=endpoint_id,
                part=part,
                field=field,
                adapter=text(data["adapter"], "adapter") if "adapter" in data else None,
            )
        )
    unmapped = known.keys() - {item.channel for item in result}
    if unmapped:
        raise RealizationError(f"Channels have no binding ROS2 mapping: {sorted(unmapped)}")
    return tuple(
        sorted(result, key=lambda item: (item.channel, item.endpoint, item.part, item.field or ""))
    )
