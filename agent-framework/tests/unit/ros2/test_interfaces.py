from dataclasses import replace

import pytest
from agent_framework.ros2.endpoints import parse_endpoint
from agent_framework.ros2.errors import RealizationError
from agent_framework.ros2.interfaces import interface_artifacts, parse_custom_interfaces

CUSTOM: dict[str, object] = {
    "interface_type": "test_interfaces/srv/Command",
    "reason": "Test command needs a float64 request/result; standard test services do not fit.",
    "parts": {"request": {"value": "float64"}, "response": {"result": "float64"}},
}


def test_explicit_custom_service_artifacts() -> None:
    interfaces = parse_custom_interfaces([CUSTOM])
    endpoint = parse_endpoint(
        {
            "id": "command",
            "kind": "service",
            "role": "client",
            "interface_type": "test_interfaces/srv/Command",
            "existing": False,
            "name": "/command",
        }
    )
    artifacts = interface_artifacts(interfaces, (endpoint,))
    assert (
        artifacts["interfaces/test_interfaces/srv/Command.srv"]
        == "float64 value\n---\nfloat64 result\n"
    )
    assert '"srv/Command.srv"' in artifacts["interfaces/test_interfaces/CMakeLists.txt"]
    assert "<version>0.1.0</version>" in artifacts["interfaces/test_interfaces/package.xml"]
    with pytest.raises(RealizationError):
        interface_artifacts(interfaces, (replace(endpoint, existing=True),))
    with pytest.raises(RealizationError):
        interface_artifacts((), (endpoint,))
    with pytest.raises(RealizationError):
        interface_artifacts(interfaces, (endpoint, replace(endpoint, id="other", existing=True)))


@pytest.mark.parametrize(
    "change",
    [
        {"interface_type": "../srv/Command"},
        {"reason": ""},
        {"parts": {"request": {}}},
        {"parts": {"request": {"Value": "float64"}, "response": {}}},
        {"parts": {"request": {"value": "unknown"}, "response": {}}},
        {"unknown": True},
    ],
)
def test_invalid_custom_interface(change: dict[str, object]) -> None:
    with pytest.raises(RealizationError):
        parse_custom_interfaces([{**CUSTOM, **change}])


def test_duplicate_custom_interfaces_rejected() -> None:
    with pytest.raises(RealizationError, match="duplicate"):
        parse_custom_interfaces([CUSTOM, CUSTOM])
