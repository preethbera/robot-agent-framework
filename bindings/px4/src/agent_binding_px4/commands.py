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
    INSTANCE_CONFIG,
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


def takeoff_parameters(value: Any) -> tuple[float, ...]:
    alt = float(value.altitude_m)
    if not math.isfinite(alt) or alt <= 0.0:
        raise ValueError("Takeoff altitude must be positive and finite")
    return (0.0, 0.0, 0.0, 0.0, math.nan, math.nan, alt)


def reposition_parameters(value: Any) -> tuple[float, ...]:
    lat = float(value.latitude_deg)
    lon = float(value.longitude_deg)
    alt = float(value.altitude_m)
    speed = float(getattr(value, "ground_speed_m_s", -1.0))
    yaw = float(getattr(value, "yaw_deg", math.nan))
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        raise ValueError("Invalid latitude/longitude coordinates")
    return (speed, 0.0, 0.0, yaw, lat, lon, alt)


def speed_parameters(value: Any) -> tuple[float, ...]:
    speed = float(value.speed_m_s)
    if not math.isfinite(speed) or speed <= 0.0:
        raise ValueError("Speed must be positive and finite")
    return (1.0, speed, -1.0, 0.0, 0.0, 0.0, 0.0)


def set_home_parameters(value: Any) -> tuple[float, ...]:
    current = 1.0 if getattr(value, "use_current", False) else 0.0
    lat = float(getattr(value, "latitude_deg", math.nan))
    lon = float(getattr(value, "longitude_deg", math.nan))
    alt = float(getattr(value, "altitude_m", math.nan))
    return (current, 0.0, 0.0, 0.0, lat, lon, alt)


def gimbal_parameters(value: Any) -> tuple[float, ...]:
    pitch = float(value.pitch_deg)
    roll = float(value.roll_deg)
    yaw = float(value.yaw_deg)
    if not all(math.isfinite(v) for v in (pitch, roll, yaw)):
        raise ValueError("Gimbal angles must be finite")
    return (pitch, roll, yaw, 0.0, 0.0, 0.0, 2.0)


def camera_trigger_parameters(value: Any) -> tuple[float, ...]:
    interval = float(value.interval_s)
    count = float(value.count)
    if not math.isfinite(interval) or interval < 0.0:
        raise ValueError("Capture interval must be non-negative")
    if not math.isfinite(count) or count < 1.0:
        raise ValueError("Capture count must be at least 1")
    return (0.0, interval, count, 0.0, 0.0, 0.0, 0.0)


TAKEOFF_SCHEMA = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={"altitude_m": NUMBER},
    metadata={"units": "m", "reference": "relative"},
)

ORBIT_SCHEMA = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={key: NUMBER for key in ("radius_m", "speed_m_s", "latitude_deg", "longitude_deg", "altitude_m")},
    metadata={"altitude_reference": "AMSL", "radius_sign": "positive_clockwise"},
)

REPOSITION_SCHEMA = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={
        "latitude_deg": NUMBER,
        "longitude_deg": NUMBER,
        "altitude_m": NUMBER,
        "ground_speed_m_s": NUMBER,
        "yaw_deg": NUMBER,
    },
    metadata={"altitude_reference": "AMSL"},
)

SET_SPEED_SCHEMA = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={"speed_m_s": NUMBER},
    metadata={"units": "m/s", "type": "groundspeed"},
)

SET_HOME_SCHEMA = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={
        "use_current": NUMBER,
        "latitude_deg": NUMBER,
        "longitude_deg": NUMBER,
        "altitude_m": NUMBER,
    },
)

GIMBAL_SCHEMA = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={"pitch_deg": NUMBER, "roll_deg": NUMBER, "yaw_deg": NUMBER},
    metadata={"units": "degrees", "frame": "body"},
)

CAMERA_TRIGGER_SCHEMA = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={"interval_s": NUMBER, "count": NUMBER},
    metadata={"units": "seconds/frames"},
)

COMMANDS = (
    Command("arm", 400, EMPTY, lambda value: (1.0, 0.0)),
    Command("disarm", 400, EMPTY, lambda value: (0.0, 0.0)),
    Command("takeoff", 22, TAKEOFF_SCHEMA, takeoff_parameters),
    Command("land", 21, EMPTY, lambda value: (0.0, 0.0, 0.0, math.nan, math.nan, math.nan, math.nan)),
    Command("hold", 176, EMPTY, lambda value: (1.0, 4.0, 3.0)),
    Command("return_to_launch", 20, EMPTY, lambda value: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
    Command("flight_termination", 185, EMPTY, lambda value: (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
    Command("reposition", 192, REPOSITION_SCHEMA, reposition_parameters),
    Command("orbit", 34, ORBIT_SCHEMA, orbit_parameters),
    Command("set_speed", 178, SET_SPEED_SCHEMA, speed_parameters),
    Command("set_home", 179, SET_HOME_SCHEMA, set_home_parameters),
    Command("mount_control", 205, GIMBAL_SCHEMA, gimbal_parameters),
    Command("camera_trigger", 2000, CAMERA_TRIGGER_SCHEMA, camera_trigger_parameters),
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
        instance_configuration_schema=INSTANCE_CONFIG,
        runtime_mode=RuntimeMode.CODE_BACKED,
        runtime_factory="agent_binding_px4.runtime:create_command",
        ros2_template={
            "endpoints": [endpoint("command", "VehicleCommand", "vehicle_command", service=True)],
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
