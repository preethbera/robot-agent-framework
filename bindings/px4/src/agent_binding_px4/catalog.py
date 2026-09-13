"""Small schema/endpoint vocabulary shared by independently extensible definitions."""

from collections.abc import Mapping
from typing import Any

from agent_framework.model import PayloadSchema, ScalarType, SchemaKind


def scalar(kind: ScalarType) -> PayloadSchema:
    return PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=kind)


NUMBER = scalar(ScalarType.FLOAT64)
STRING = scalar(ScalarType.STRING)
EMPTY = PayloadSchema(kind=SchemaKind.RECORD)
VECTOR = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={key: NUMBER for key in ("x", "y", "z")},
    metadata={"frame": "local_NED", "units": "m"},
)
CONFIG = PayloadSchema(
    kind=SchemaKind.RECORD,
    fields={
        "target_system": scalar(ScalarType.UINT8),
        "target_component": scalar(ScalarType.UINT8),
    },
)
DEFAULTS: Mapping[str, object] = {"target_system": 1, "target_component": 1}


def validate_config(config: Mapping[str, object]) -> None:
    if config["target_system"] == 0 or config["target_component"] == 0:
        raise ValueError("PX4 commands require an explicit non-broadcast target")


def endpoint(
    identifier: str,
    interface: str,
    topic: str,
    *,
    service: bool = False,
    publisher: bool = False,
) -> dict[str, Any]:
    qos = {
        "history": "keep_last",
        "depth": 10,
        "reliability": "reliable" if service else "best_effort",
        "durability": "volatile",
    }
    return {
        "id": identifier,
        "kind": "service" if service else "topic",
        "role": "client" if service else ("publisher" if publisher else "subscriber"),
        "interface_type": "px4_msgs/" + ("srv/" if service else "msg/") + interface,
        "existing": True,
        "name_template": "/{namespace}/fmu/" + topic,
        "qos": qos,
        "overridable": ["name", "qos.depth"],
        "requirements": {
            "qos": {
                "history": "keep_last",
                "reliability": qos["reliability"],
                "durability": "volatile",
            }
        },
    }


def mapping(
    channel: str,
    native: str,
    part: str = "message",
    field: str | None = None,
    adapter: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"channel": channel, "endpoint": native, "part": part}
    if field:
        result["field"] = field
    if adapter:
        result["adapter"] = adapter
    return result
