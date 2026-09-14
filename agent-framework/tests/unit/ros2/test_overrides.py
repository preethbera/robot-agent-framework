from copy import deepcopy

import pytest
from agent_framework.ros2.endpoints import (
    apply_override,
    materialize_endpoint,
    parse_endpoint_template,
)
from agent_framework.ros2.errors import RealizationError

TEMPLATE: dict[str, object] = {
    "id": "value",
    "kind": "topic",
    "interface_type": "std_msgs/msg/Float64",
    "role": "subscriber",
    "existing": True,
    "name_template": "/{namespace}/{instance_id}/{binding_instance_id}/value",
    "qos": {"history": "keep_last", "depth": 5, "reliability": "reliable"},
    "overridable": ["name", "qos.depth", "qos.reliability"],
    "requirements": {"qos": {"reliability": "reliable"}},
}


def test_allowed_override_and_stable_target() -> None:
    before = deepcopy(TEMPLATE)
    template = parse_endpoint_template(TEMPLATE)
    endpoint = apply_override(template, {"name": "/native/value", "qos": {"depth": 20}})
    final = materialize_endpoint(endpoint, "agent", "sensor")
    assert final.id == "sensor.value" and final.name == "/native/value"
    assert final.qos == {"history": "keep_last", "depth": 20, "reliability": "reliable"}
    assert before == TEMPLATE
    assert materialize_endpoint(template.endpoint, "agent", "sensor").name_template == (
        "/{namespace}/{instance_id}/sensor/value"
    )


@pytest.mark.parametrize(
    "override",
    [
        {"kind": "service"},
        {"interface_type": "std_msgs/msg/String"},
        {"role": "publisher"},
        {"existing": False},
        {"channel_mappings": []},
        {"runtime_factory": "override"},
        {"requirements": {}},
        {"qos": {"durability": "volatile"}},
        {"qos": {"deadline": 1}},
        {"qos": {"depth": 0}},
        {"name": "invalid name"},
        {"qos": {"reliability": "best_effort"}},
    ],
)
def test_invalid_override_is_hard_resolution_error(override: dict[str, object]) -> None:
    with pytest.raises(RealizationError):
        apply_override(parse_endpoint_template(TEMPLATE), override)


@pytest.mark.parametrize(
    "change",
    [
        {"overridable": ["kind"]},
        {"overridable": ["name", "name"]},
        {"requirements": {"qos": {"reliability": "best_effort"}}},
        {"requirements": {"qos": {"unsupported": 1}}},
        {"requirements": {"name": "/wrong/default"}},
    ],
)
def test_invalid_binding_requirements_and_permissions(change: dict[str, object]) -> None:
    with pytest.raises(RealizationError):
        parse_endpoint_template({**TEMPLATE, **change})


def test_mandatory_name_cannot_be_overridden() -> None:
    template = parse_endpoint_template(
        {**TEMPLATE, "requirements": {"name": TEMPLATE["name_template"]}}
    )
    with pytest.raises(RealizationError, match="mandatory name"):
        apply_override(template, {"name": "/changed"})
