"""Additional external protocol fixtures for M4 transport coverage."""

from copy import deepcopy
from dataclasses import replace

from agent_framework.binding.definition import (
    BindingDefinition,
    BindingSemantics,
    Primitive,
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
)


def protocol_bindings(command: BindingDefinition) -> tuple[BindingDefinition, ...]:
    result = []
    integer = PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.INT32)
    sequence = PayloadSchema(kind=SchemaKind.SEQUENCE, items=integer)
    empty = PayloadSchema(kind=SchemaKind.RECORD)
    for server in (False, True):
        name = "test.action_server" if server else "test.action"
        channels = tuple(
            Channel(
                id=part,
                direction=Direction.AGENT_TO_CONSUMER
                if incoming == server
                else Direction.CONSUMER_TO_AGENT,
                schema=schema,
                cardinality=Cardinality.STREAM if part == "feedback" else Cardinality.SINGLE,
                lifetime=Lifetime.INVOCATION,
                purpose=purpose,
            )
            for part, incoming, schema, purpose in (
                ("goal", True, integer, Purpose.INPUT),
                ("feedback", False, sequence, Purpose.FEEDBACK),
                ("result", False, sequence, Purpose.RESULT),
                ("cancel", True, empty, Purpose.CANCELLATION),
            )
        )
        result.append(
            BindingDefinition(
                id=name,
                description="Fibonacci protocol fixture",
                primitive=Primitive.CAPABILITY,
                default_semantics=BindingSemantics(
                    element=Capability(
                        id="compute",
                        description="Fibonacci",
                        execution=Execution.INVOCATION,
                        channels=tuple(item.id for item in channels),
                    ),
                    channels=channels,
                ),
                ros2_template={
                    "endpoints": [
                        {
                            "id": "native",
                            "kind": "action",
                            "role": "action_server" if server else "action_client",
                            "existing": True,
                            "interface_type": "example_interfaces/action/Fibonacci",
                            "name_template": "/native/{instance_id}/fibonacci",
                        }
                    ],
                    "channel_mappings": [
                        {
                            "channel": "goal",
                            "endpoint": "native",
                            "part": "goal",
                            "field": "order",
                        },
                        {
                            "channel": "feedback",
                            "endpoint": "native",
                            "part": "feedback",
                            "field": "sequence",
                        },
                        {
                            "channel": "result",
                            "endpoint": "native",
                            "part": "result",
                            "field": "sequence",
                        },
                        {"channel": "cancel", "endpoint": "native", "part": "cancel"},
                    ],
                },
            )
        )
    template = deepcopy(dict(command.ros2_template))
    template["endpoints"][0]["role"] = "server"  # type: ignore[index]
    semantics = command.default_semantics
    result.append(
        replace(
            command,
            id="test.command_server",
            ros2_template=template,
            default_semantics=replace(
                semantics,
                channels=tuple(
                    replace(
                        channel,
                        direction=Direction.AGENT_TO_CONSUMER
                        if channel.direction is Direction.CONSUMER_TO_AGENT
                        else Direction.CONSUMER_TO_AGENT,
                    )
                    for channel in semantics.channels
                ),
            ),
        )
    )
    return tuple(result)
