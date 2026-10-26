"""ArduPilot command descriptors using native DDS services."""

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
    service_interface: str
    service_topic: str
    request_schema: PayloadSchema
    build_request: Callable[[Any], dict[str, Any]]
    extract_result: Callable[[Any], str]


def _arm_request(value: Any) -> dict[str, Any]:
    return {"arm": True}


def _disarm_request(value: Any) -> dict[str, Any]:
    return {"arm": False}


def _takeoff_request(value: Any) -> dict[str, Any]:
    return {"alt": float(value.altitude_m)}


def _mode_guided_request(value: Any) -> dict[str, Any]:
    return {"mode": 4}


def _mode_land_request(value: Any) -> dict[str, Any]:
    return {"mode": 9}


def _mode_rtl_request(value: Any) -> dict[str, Any]:
    return {"mode": 6}


def _mode_loiter_request(value: Any) -> dict[str, Any]:
    return {"mode": 5}


def _bool_result(reply: Any) -> str:
    return "accepted" if getattr(reply, "result", False) else "denied"


def _status_result(reply: Any) -> str:
    return "accepted" if getattr(reply, "status", False) else "denied"


TAKEOFF_SCHEMA = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={"altitude_m": NUMBER},
    metadata={"units": "m", "reference": "relative"},
)

COMMANDS = (
    Command(
        "arm",
        "ArmMotors",
        "arm_motors",
        EMPTY,
        _arm_request,
        _bool_result,
    ),
    Command(
        "disarm",
        "ArmMotors",
        "arm_motors",
        EMPTY,
        _disarm_request,
        _bool_result,
    ),
    Command(
        "takeoff",
        "Takeoff",
        "experimental/takeoff",
        TAKEOFF_SCHEMA,
        _takeoff_request,
        _status_result,
    ),
    Command(
        "guided",
        "ModeSwitch",
        "mode_switch",
        EMPTY,
        _mode_guided_request,
        _status_result,
    ),
    Command(
        "land",
        "ModeSwitch",
        "mode_switch",
        EMPTY,
        _mode_land_request,
        _status_result,
    ),
    Command(
        "rtl",
        "ModeSwitch",
        "mode_switch",
        EMPTY,
        _mode_rtl_request,
        _status_result,
    ),
    Command(
        "loiter",
        "ModeSwitch",
        "mode_switch",
        EMPTY,
        _mode_loiter_request,
        _status_result,
    ),
)


def semantics(command: Command, config: Mapping[str, object]) -> BindingSemantics:
    validate_config(config)
    channels = (
        Channel(
            id="request",
            direction=Direction.CONSUMER_TO_AGENT,
            schema=command.request_schema,
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
        id="ardupilot." + command.name,
        description="ArduPilot " + command.name,
        primitive=Primitive.CAPABILITY,
        default_semantics=configure(DEFAULTS),
        configuration_schema=CONFIG,
        configuration_defaults=DEFAULTS,
        configure=configure,
        instance_configuration_schema=INSTANCE_CONFIG,
        runtime_mode=RuntimeMode.CODE_BACKED,
        runtime_factory="agent_binding_ardupilot.runtime:create_command",
        ros2_template={
            "endpoints": [
                endpoint(
                    "service",
                    command.service_interface,
                    command.service_topic,
                    service=True,
                )
            ],
            "channel_mappings": [
                mapping("request", "service", "request"),
                mapping("ack", "service", "response"),
            ],
            "internal_communication": {"operation": command.name},
        },
    )


def definitions() -> tuple[BindingDefinition, ...]:
    return tuple(definition(command) for command in COMMANDS)

