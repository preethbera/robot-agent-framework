"""Build-time test realizations, deliberately outside framework core."""

from collections.abc import Mapping

TOPIC_QOS: dict[str, object] = {
    "history": "keep_last",
    "depth": 5,
    "reliability": "best_effort",
    "durability": "volatile",
}

TEMPERATURE: dict[str, object] = {
    "endpoints": [
        {
            "id": "value",
            "kind": "topic",
            "role": "subscriber",
            "interface_type": "std_msgs/msg/Float64",
            "existing": True,
            "name_template": "/native/{instance_id}/temperature",
            "qos": TOPIC_QOS,
            "overridable": ["name", "qos.depth", "qos.reliability"],
            "requirements": {"qos": {"durability": "volatile"}},
        }
    ],
    "channel_mappings": [
        {"channel": "value", "endpoint": "value", "part": "message", "field": "data"}
    ],
}

COMMAND: dict[str, object] = {
    "endpoints": [
        {
            "id": "command",
            "kind": "service",
            "role": "client",
            "interface_type": "agent_binding_test_interfaces/srv/Command",
            "existing": False,
            "name_template": "/native/{instance_id}/command",
            "qos": {
                "history": "keep_last",
                "depth": 10,
                "reliability": "reliable",
                "durability": "volatile",
            },
            "overridable": ["name", "qos.depth", "qos.reliability"],
            "requirements": {"qos": {"reliability": "reliable", "durability": "volatile"}},
        }
    ],
    "channel_mappings": [
        {
            "channel": "request",
            "endpoint": "command",
            "part": "request",
            "field": "value",
        },
        {
            "channel": "result",
            "endpoint": "command",
            "part": "response",
            "field": "result",
        },
    ],
    "custom_interfaces": [
        {
            "interface_type": "agent_binding_test_interfaces/srv/Command",
            "reason": "The test command requires one float64 request and one float64 result; "
            "standard Trigger/SetBool/AddTwoInts services cannot preserve that payload.",
            "parts": {
                "request": {"value": "float64"},
                "response": {"result": "float64"},
            },
        }
    ],
    "startup": [{"endpoint": "command", "requirement": "service available before invocation"}],
}


def stream_template(configuration: Mapping[str, object]) -> Mapping[str, object]:
    endpoints: list[dict[str, object]] = [
        {
            "id": "output",
            "kind": "topic",
            "role": "subscriber",
            "interface_type": "std_msgs/msg/Float64",
            "existing": True,
            "name_template": "/native/{instance_id}/sensor/output",
            "qos": dict(TOPIC_QOS),
            "overridable": ["name", "qos.depth"],
        }
    ]
    mappings: list[dict[str, object]] = [
        {
            "channel": "output",
            "endpoint": "output",
            "part": "message",
            "field": "data",
        }
    ]
    internal: list[dict[str, object]] = []
    if configuration["liveness_owner"] == "application":
        endpoints.append(
            {
                "id": "liveness",
                "kind": "topic",
                "role": "publisher",
                "interface_type": "std_msgs/msg/Float64",
                "existing": True,
                "name_template": "/native/{instance_id}/sensor/liveness",
                "qos": {**TOPIC_QOS, "reliability": "reliable"},
                "overridable": ["name", "qos.depth"],
                "requirements": {"qos": {"reliability": "reliable"}},
            }
        )
        mappings.append(
            {
                "channel": "liveness",
                "endpoint": "liveness",
                "part": "message",
                "field": "data",
            }
        )
    else:
        internal.append({"responsibility": "liveness", "owner": "binding", "max_gap_s": 0.5})
    return {
        "endpoints": endpoints,
        "channel_mappings": mappings,
        "internal_communication": internal,
        "startup": [{"endpoint": "output", "requirement": "connect before session starts"}],
        "lifecycle": [{"endpoint": "output", "requirement": "disconnect when session closes"}],
    }
