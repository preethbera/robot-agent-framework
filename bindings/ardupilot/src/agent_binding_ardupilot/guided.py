"""Guided-mode position control session, ArduPilot equivalent of PX4 Offboard."""

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
    INSTANCE_CONFIG,
    NUMBER,
    STRING,
    endpoint,
    mapping,
    validate_config,
)

SETPOINT = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={key: NUMBER for key in ("x", "y", "z", "yaw")},
    metadata={"frame": "local_ENU", "position_units": "m", "yaw_units": "rad"},
)
GUIDED_DEFAULTS = {**DEFAULTS, "liveness_owner": "binding"}
GUIDED_CONFIG = PayloadSchema(
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
            description="Guided mode local ENU position control; does not arm",
            execution=Execution.SESSION,
            channels=tuple(c.id for c in channels),
        ),
        channels=channels,
        responsibility_ownership={"liveness": owner},
    )


def realization(config: Mapping[str, object]) -> Mapping[str, object]:
    mappings = [
        mapping("setpoint", "setpoint"),
        mapping("ack", "mode_service", "response"),
        mapping("status", "pose", field="header.frame_id"),
    ]
    if config["liveness_owner"] == "application":
        mappings.append(mapping("liveness", "heartbeat"))
    return {
        "endpoints": [
            endpoint(
                "mode_service",
                "ModeSwitch",
                "mode_switch",
                service=True,
            ),
            endpoint(
                "setpoint",
                "PoseStamped",
                "cmd_pos",
                package="geometry_msgs",
                publisher=True,
            ),
            endpoint(
                "heartbeat",
                "TwistStamped",
                "cmd_vel",
                package="geometry_msgs",
                publisher=True,
            ),
            endpoint(
                "pose",
                "PoseStamped",
                "pose/filtered",
                package="geometry_msgs",
            ),
        ],
        "channel_mappings": mappings,
        "startup": {
            "warmup_s": 1.0,
            "requires_valid_position": True,
            "automatic_arming": False,
        },
        "lifecycle": {
            "heartbeat_hz": 10.0,
            "application_max_gap_s": 0.4,
            "close": "stop_liveness; ArduPilot Guided-mode loss policy applies",
        },
    }


def definition() -> BindingDefinition:
    baseline = semantics(GUIDED_DEFAULTS)
    return BindingDefinition(
        id="ardupilot.guided.position",
        description="ArduPilot Guided-mode position session",
        primitive=Primitive.CAPABILITY,
        default_semantics=baseline,
        mandatory_requirements=BindingRequirements(channels=baseline.channels),
        configuration_schema=GUIDED_CONFIG,
        configuration_defaults=GUIDED_DEFAULTS,
        configure=semantics,
        configure_ros2=realization,
        instance_configuration_schema=INSTANCE_CONFIG,
        runtime_mode=RuntimeMode.CODE_BACKED,
        runtime_factory="agent_binding_ardupilot.guided_runtime:create_component",
    )

