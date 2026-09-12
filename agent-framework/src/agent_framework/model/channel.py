"""Unidirectional logical Channels, independent of ROS2 endpoints and QoS."""

from dataclasses import dataclass
from enum import StrEnum

from .schema import PayloadSchema, _validate_id, _validate_nonnegative, validate_schema


class Direction(StrEnum):
    CONSUMER_TO_AGENT = "consumer_to_agent"
    AGENT_TO_CONSUMER = "agent_to_consumer"


class Cardinality(StrEnum):
    SINGLE = "single"
    STREAM = "stream"


class Lifetime(StrEnum):
    PERSISTENT = "persistent"
    INVOCATION = "invocation"
    SESSION = "session"


class Purpose(StrEnum):
    VALUE = "value"
    INPUT = "input"
    OUTPUT = "output"
    ACKNOWLEDGEMENT = "acknowledgement"
    FEEDBACK = "feedback"
    RESULT = "result"
    CANCELLATION = "cancellation"
    LIVENESS = "liveness"
    STATUS = "status"


class Reliability(StrEnum):
    RELIABLE = "reliable"
    BEST_EFFORT = "best_effort"


class Ordering(StrEnum):
    ORDERED = "ordered"
    UNORDERED = "unordered"


@dataclass(frozen=True, slots=True, kw_only=True)
class Timing:
    min_rate_hz: float | None = None
    max_rate_hz: float | None = None
    max_gap_s: float | None = None
    max_latency_s: float | None = None
    max_age_s: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Delivery:
    reliability: Reliability
    ordering: Ordering


@dataclass(frozen=True, slots=True, kw_only=True)
class Channel:
    id: str
    direction: Direction
    schema: PayloadSchema
    cardinality: Cardinality
    lifetime: Lifetime
    purpose: Purpose
    correlates_with: str | None = None
    timing: Timing | None = None
    delivery: Delivery | None = None


def validate_channel(channel: Channel) -> None:
    """Validate local semantics; Agent validation checks correlation references."""
    _validate_id(channel.id, "channel")
    for value, enum_type in (
        (channel.direction, Direction),
        (channel.cardinality, Cardinality),
        (channel.lifetime, Lifetime),
        (channel.purpose, Purpose),
    ):
        if not isinstance(value, enum_type):
            raise ValueError(f"channel {channel.id!r}: invalid {enum_type.__name__}")
    validate_schema(channel.schema)
    if channel.correlates_with is not None:
        _validate_id(channel.correlates_with, "correlates_with")
        if channel.correlates_with == channel.id:
            raise ValueError(f"channel {channel.id!r} cannot correlate with itself")
    if channel.timing is not None:
        timing = channel.timing
        for name, number in (
            ("min_rate_hz", timing.min_rate_hz),
            ("max_rate_hz", timing.max_rate_hz),
            ("max_gap_s", timing.max_gap_s),
            ("max_latency_s", timing.max_latency_s),
            ("max_age_s", timing.max_age_s),
        ):
            _validate_nonnegative(number, f"channel {channel.id!r} timing.{name}")
        if (
            timing.min_rate_hz is not None
            and timing.max_rate_hz is not None
            and timing.min_rate_hz > timing.max_rate_hz
        ):
            raise ValueError("min_rate_hz cannot exceed max_rate_hz")
    if channel.delivery is not None:
        if not isinstance(channel.delivery.reliability, Reliability):
            raise ValueError("invalid delivery reliability")
        if not isinstance(channel.delivery.ordering, Ordering):
            raise ValueError("invalid delivery ordering")
