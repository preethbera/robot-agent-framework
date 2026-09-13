from dataclasses import replace

import pytest

from agent_framework.model import (
    Cardinality,
    Channel,
    Direction,
    Lifetime,
    PayloadSchema,
    Purpose,
    ScalarType,
    SchemaKind,
)
from agent_framework.ros2.endpoints import materialize_endpoint, parse_endpoint
from agent_framework.ros2.errors import RealizationError
from agent_framework.ros2.mapping import parse_mappings


def channel(identifier: str, direction: Direction) -> Channel:
    return Channel(
        id=f"cap.{identifier}",
        direction=direction,
        schema=PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.FLOAT64),
        cardinality=Cardinality.SINGLE,
        lifetime=Lifetime.INVOCATION,
        purpose=Purpose.INPUT,
    )


@pytest.mark.parametrize(
    ("kind", "role", "interface", "parts"),
    [
        ("topic", "subscriber", "std_msgs/msg/Float64", ["message"]),
        ("service", "client", "std_srvs/srv/Trigger", ["request", "response"]),
        (
            "action",
            "action_client",
            "example_interfaces/action/Fibonacci",
            ["goal", "feedback", "result", "cancel"],
        ),
    ],
)
def test_mapping_parts_and_directions(
    kind: str, role: str, interface: str, parts: list[str]
) -> None:
    endpoint = materialize_endpoint(
        parse_endpoint(
            {
                "id": "native",
                "kind": kind,
                "role": role,
                "interface_type": interface,
                "name": "/native",
                "existing": True,
            }
        ),
        "agent",
        "cap",
    )
    channels = tuple(
        channel(
            part,
            Direction.CONSUMER_TO_AGENT
            if part in {"request", "goal", "cancel"}
            else Direction.AGENT_TO_CONSUMER,
        )
        for part in parts
    )
    data = [{"channel": part, "endpoint": "native", "part": part} for part in parts]
    result = parse_mappings(data, alias="cap", channels=channels, endpoints={endpoint.id: endpoint})
    assert {item.part for item in result} == set(parts)
    with pytest.raises(RealizationError, match="direction"):
        parse_mappings(
            data,
            alias="cap",
            channels=(
                replace(
                    channels[0],
                    direction=(
                        Direction.AGENT_TO_CONSUMER
                        if channels[0].direction is Direction.CONSUMER_TO_AGENT
                        else Direction.CONSUMER_TO_AGENT
                    ),
                ),
                *channels[1:],
            ),
            endpoints={endpoint.id: endpoint},
        )
    opposite = {"subscriber": "publisher", "client": "server", "action_client": "action_server"}[
        role
    ]
    reverse = tuple(
        replace(
            c,
            direction=Direction.AGENT_TO_CONSUMER
            if c.direction is Direction.CONSUMER_TO_AGENT
            else Direction.CONSUMER_TO_AGENT,
        )
        for c in channels
    )
    assert parse_mappings(
        data,
        alias="cap",
        channels=reverse,
        endpoints={endpoint.id: replace(endpoint, role=opposite)},
    )


@pytest.mark.parametrize(
    "data",
    [
        [],
        [{"channel": "missing", "endpoint": "value", "part": "message"}],
        [{"channel": "value", "endpoint": "missing", "part": "message"}],
        [{"channel": "value", "endpoint": "value", "part": "request"}],
        [{"channel": "value", "endpoint": "value", "part": "message", "field": "bad[]"}],
        [{"channel": "value", "endpoint": "value", "part": "message"}] * 2,
    ],
)
def test_bad_mapping_fails(data: list[dict[str, object]]) -> None:
    endpoint = materialize_endpoint(
        parse_endpoint(
            {
                "id": "value",
                "kind": "topic",
                "role": "subscriber",
                "interface_type": "std_msgs/msg/Float64",
                "name": "native",
                "existing": True,
            }
        ),
        "agent",
        "cap",
    )
    with pytest.raises(RealizationError):
        parse_mappings(
            data,
            alias="cap",
            channels=(channel("value", Direction.AGENT_TO_CONSUMER),),
            endpoints={endpoint.id: endpoint},
        )
