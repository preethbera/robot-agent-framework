"""Explicitly supported v0.1.0 QoS fields, without middleware dependencies."""

from .errors import RealizationError
from .model import keys, mapping

QOS_POLICIES = {
    "history": {"system_default", "keep_last", "keep_all"},
    "reliability": {"system_default", "reliable", "best_effort"},
    "durability": {"system_default", "volatile", "transient_local"},
}
QOS_FIELDS = {*QOS_POLICIES, "depth"}


def parse_qos(value: object, *, partial: bool = False) -> dict[str, object]:
    qos = mapping(value, "qos")
    keys(qos, QOS_FIELDS, set(), "qos")
    for name, choices in QOS_POLICIES.items():
        if name in qos and (not isinstance(qos[name], str) or qos[name] not in choices):
            raise RealizationError(f"qos.{name}: invalid policy")
    if "depth" in qos and (type(qos["depth"]) is not int or int(str(qos["depth"])) < 0):
        raise RealizationError("qos.depth: expected a non-negative integer")
    if not partial and qos.get("history") == "keep_last" and not qos.get("depth"):
        raise RealizationError("qos keep_last requires positive depth")
    return qos
