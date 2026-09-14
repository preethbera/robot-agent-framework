from copy import deepcopy

import pytest
from agent_framework.ros2.endpoints import parse_endpoint
from agent_framework.ros2.errors import RealizationError
from agent_framework.ros2.qos import parse_qos

TOPIC: dict[str, object] = {
    "id": "value",
    "kind": "topic",
    "interface_type": "std_msgs/msg/Float64",
    "role": "subscriber",
    "existing": True,
    "name": "/native/temperature",
}


@pytest.mark.parametrize(
    ("kind", "role", "interface"),
    [
        ("topic", "publisher", "std_msgs/msg/Float64"),
        ("topic", "subscriber", "std_msgs/msg/Float64"),
        ("service", "client", "std_srvs/srv/Trigger"),
        ("service", "server", "std_srvs/srv/Trigger"),
        ("action", "action_client", "example_interfaces/action/Fibonacci"),
        ("action", "action_server", "example_interfaces/action/Fibonacci"),
    ],
)
def test_endpoint_kinds(kind: str, role: str, interface: str) -> None:
    endpoint = parse_endpoint({**TOPIC, "kind": kind, "role": role, "interface_type": interface})
    assert endpoint.existing and endpoint.role == role


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "other"},
        {"role": "server"},
        {"existing": 1},
        {"id": "a.b"},
        {"interface_type": "std_srvs/srv/Trigger"},
        {"name": "/bad//name"},
        {"name": "/1bad"},
        {"name": "bad name"},
        {"name": "/trailing/"},
        {"name_template": "/{instance_id}/value"},
        {"unknown": True},
    ],
)
def test_invalid_endpoints(change: dict[str, object]) -> None:
    with pytest.raises(RealizationError):
        parse_endpoint({**TOPIC, **change})


def test_templates_remain_instance_independent() -> None:
    template = deepcopy(TOPIC)
    del template["name"]
    template["name_template"] = "/{namespace}/{instance_id}/{binding_instance_id}/value"
    assert parse_endpoint(template).name_template == template["name_template"]
    for invalid in ("/{unknown}/value", "/{instance_id.foo}", "/{instance_id!r}", "/{", "/{0}"):
        with pytest.raises(RealizationError):
            parse_endpoint({**template, "name_template": invalid})


@pytest.mark.parametrize(
    "qos",
    [
        {"depth": True},
        {"depth": -1},
        {"depth": 2.5},
        {"history": "keep_last"},
        {"history": "keep_last", "depth": 0},
        {"reliability": "unknown"},
        {"durability": ["volatile"]},
        {"unsupported": 1},
    ],
)
def test_invalid_qos(qos: dict[str, object]) -> None:
    with pytest.raises(RealizationError):
        parse_qos(qos)


def test_qos_preserves_binding_choices() -> None:
    qos = {
        "history": "keep_last",
        "depth": 5,
        "reliability": "best_effort",
        "durability": "volatile",
    }
    assert parse_qos(qos) == qos
    assert parse_qos({"history": "keep_all", "depth": 0})["depth"] == 0
