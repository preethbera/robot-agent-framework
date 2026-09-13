"""Extensible command descriptors and native parameter encoders (PX4 v1.16.2)."""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from agent_framework.binding.definition import (
    BindingDefinition,
    BindingSemantics,
    Primitive,
    RuntimeMode,
)
from agent_framework.model import (
    Capability,
    Cardinality,
    Channel,
    Direction,
    Execution,
    Lifetime,
    PayloadSchema,
    Purpose,
    SchemaKind,
)

from .catalog import (
    CONFIG,
    DEFAULTS,
    EMPTY,
    NUMBER,
    STRING,
    endpoint,
    mapping,
    validate_config,
)


@dataclass(frozen=True)
class Command:
    name: str
    command: int
    schema: PayloadSchema
    parameters: Callable[[Any], tuple[float, ...]]


def orbit_parameters(value: Any) -> tuple[float, ...]:
    values = (
        value.radius_m,
        value.speed_m_s,
        value.latitude_deg,
        value.longitude_deg,
        value.altitude_m,
    )
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Orbit parameters must be finite")
    if not 1 <= abs(value.radius_m) <= 1000 or not 0 < value.speed_m_s <= 10:
        raise ValueError("Orbit radius must be 1..1000 m, speed in (0, 10] m/s")
    if not -90 <= value.latitude_deg <= 90 or not -180 <= value.longitude_deg <= 180:
        raise ValueError("Invalid orbit latitude/longitude")
    return (
        value.radius_m,
        value.speed_m_s,
        0.0,
        0.0,
        value.latitude_deg,
        value.longitude_deg,
        value.altitude_m,
    )


COMMANDS = (
    Command("arm", 400, EMPTY, lambda value: (1.0, 0.0)),
    Command("disarm", 400, EMPTY, lambda value: (0.0, 0.0)),
    Command(
        "land",
        21,
        EMPTY,
        lambda value: (0.0, 0.0, 0.0, math.nan, math.nan, math.nan, math.nan),
    ),
    Command("hold", 176, EMPTY, lambda value: (1.0, 4.0, 3.0)),
    Command(
        "orbit",
        34,
        PayloadSchema(
            kind=SchemaKind.RECORD,
            fields={
                key: NUMBER
                for key in (
                    "radius_m",
                    "speed_m_s",
                    "latitude_deg",
                    "longitude_deg",
                    "altitude_m",
                )
            },
            metadata={
                "altitude_reference": "AMSL",
                "radius_sign": "positive_clockwise",
            },
        ),
        orbit_parameters,
    ),
)


def semantics(command: Command, config: Mapping[str, object]) -> BindingSemantics:
    validate_config(config)
    channels = (
        Channel(
            id="request",
            direction=Direction.CONSUMER_TO_AGENT,
            schema=command.schema,
            cardinality=Cardinality.SINGLE,
            lifetime=Lifetime.INVOCATION,
            purpose=Purpose.INPUT,
        ),
        Channel(
            id="ack",
            direction=Direction.AGENT_TO_CONSUMER,
            schema=STRING,
            cardinality=Cardinality.SINGLE,
            lifetime=Lifetime.INVOCATION,
            purpose=Purpose.ACKNOWLEDGEMENT,
            correlates_with="request",
        ),
    )
    return BindingSemantics(
        element=Capability(
            id=command.name,
            description="Request " + command.name,
            execution=Execution.INVOCATION,
            channels=("request", "ack"),
        ),
        channels=channels,
    )


def definition(command: Command) -> BindingDefinition:
    def configure(config: Mapping[str, object]) -> BindingSemantics:
        return semantics(command, config)

    return BindingDefinition(
        id="px4." + command.name,
        description="PX4 " + command.name,
        primitive=Primitive.CAPABILITY,
        default_semantics=configure(DEFAULTS),
        configuration_schema=CONFIG,
        configuration_defaults=DEFAULTS,
        configure=configure,
        runtime_mode=RuntimeMode.CODE_BACKED,
        runtime_factory="agent_binding_px4.runtime:create_command",
        ros2_template={
            "endpoints": [
                endpoint("command", "VehicleCommand", "vehicle_command", service=True)
            ],
            "channel_mappings": [
                mapping("request", "command", "request", "request"),
                mapping("ack", "command", "response", "reply.result"),
            ],
            "internal_communication": {"operation": command.name},
            "lifecycle": {"acknowledgement_is_not_observed_state": True},
        },
    )


def definitions() -> tuple[BindingDefinition, ...]:
    return tuple(definition(command) for command in COMMANDS)
