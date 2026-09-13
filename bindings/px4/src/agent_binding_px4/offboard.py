"""Position-control session declaration, separate from reusable native transport."""

from collections.abc import Mapping

from agent_framework.binding.definition import (
    BindingDefinition,
    BindingRequirements,
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
    ScalarType,
    SchemaKind,
    Timing,
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

SETPOINT = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={key: NUMBER for key in ("x", "y", "z", "yaw")},
    metadata={"frame": "local_NED", "position_units": "m", "yaw_units": "rad"},
)
OFFBOARD_DEFAULTS = {**DEFAULTS, "liveness_owner": "binding"}
OFFBOARD_CONFIG = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={
        **CONFIG.fields,
        "liveness_owner": PayloadSchema(
            kind=SchemaKind.ENUM,
            scalar_type=ScalarType.STRING,
            values=("binding", "application"),
        ),
    },
)


def semantics(config: Mapping[str, object]) -> BindingSemantics:
    validate_config(config)
    channels: tuple[Channel, ...] = (
        Channel(
            id="setpoint",
            direction=Direction.CONSUMER_TO_AGENT,
            schema=SETPOINT,
            cardinality=Cardinality.STREAM,
            lifetime=Lifetime.SESSION,
            purpose=Purpose.INPUT,
        ),
        Channel(
            id="ack",
            direction=Direction.AGENT_TO_CONSUMER,
            schema=STRING,
            cardinality=Cardinality.SINGLE,
            lifetime=Lifetime.SESSION,
            purpose=Purpose.ACKNOWLEDGEMENT,
        ),
        Channel(
            id="status",
            direction=Direction.AGENT_TO_CONSUMER,
            schema=STRING,
            cardinality=Cardinality.STREAM,
            lifetime=Lifetime.SESSION,
            purpose=Purpose.STATUS,
        ),
    )
    owner = str(config["liveness_owner"])
    if owner == "application":
        channels += (
            Channel(
                id="liveness",
                direction=Direction.CONSUMER_TO_AGENT,
                schema=EMPTY,
                cardinality=Cardinality.STREAM,
                lifetime=Lifetime.SESSION,
                purpose=Purpose.LIVENESS,
                timing=Timing(min_rate_hz=2.5, max_gap_s=0.4),
            ),
        )
    return BindingSemantics(
        element=Capability(
            id="position_control",
            description="Explicit local NED position control; does not arm",
            execution=Execution.SESSION,
            channels=tuple(c.id for c in channels),
        ),
        channels=channels,
        responsibility_ownership={"liveness": owner},
    )


def realization(config: Mapping[str, object]) -> Mapping[str, object]:
    mappings = [
        mapping("setpoint", "setpoint"),
        mapping("ack", "command", "response", "reply.result"),
        mapping("status", "state", field="nav_state"),
    ]
    if config["liveness_owner"] == "application":
        mappings.append(mapping("liveness", "heartbeat"))
    return {
        "endpoints": [
            endpoint("command", "VehicleCommand", "vehicle_command", service=True),
            endpoint(
                "setpoint",
                "TrajectorySetpoint",
                "in/trajectory_setpoint",
                publisher=True,
            ),
            endpoint(
                "heartbeat",
                "OffboardControlMode",
                "in/offboard_control_mode",
                publisher=True,
            ),
            endpoint("state", "VehicleStatus", "out/vehicle_status_v1"),
            endpoint("position", "VehicleLocalPosition", "out/vehicle_local_position"),
        ],
        "channel_mappings": mappings,
        "startup": {
            "warmup_s": 1.1,
            "requires_valid_local_position": True,
            "automatic_arming": False,
        },
        "lifecycle": {
            "heartbeat_hz": 10.0,
            "application_max_gap_s": 0.4,
            "close": "stop_liveness; PX4 configured Offboard-loss policy applies",
        },
    }


def definition() -> BindingDefinition:
    baseline = semantics(OFFBOARD_DEFAULTS)
    return BindingDefinition(
        id="px4.offboard.position",
        description="PX4 Offboard position session",
        primitive=Primitive.CAPABILITY,
        default_semantics=baseline,
        mandatory_requirements=BindingRequirements(channels=baseline.channels),
        configuration_schema=OFFBOARD_CONFIG,
        configuration_defaults=OFFBOARD_DEFAULTS,
        configure=semantics,
        configure_ros2=realization,
        runtime_mode=RuntimeMode.CODE_BACKED,
        runtime_factory="agent_binding_px4.offboard_runtime:create_component",
    )
