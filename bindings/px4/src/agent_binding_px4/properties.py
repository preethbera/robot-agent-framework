"""Direct native state mappings; no command or lifecycle policy in state Properties."""

from agent_framework.binding.definition import (
    BindingDefinition,
    BindingSemantics,
    Primitive,
)
from agent_framework.model import (
    Cardinality,
    Channel,
    Direction,
    Lifetime,
    PayloadSchema,
    Property,
    Purpose,
    ScalarType,
    SchemaKind,
)

from .catalog import NUMBER, STRING, VECTOR, endpoint, mapping, scalar


def definitions() -> tuple[BindingDefinition, ...]:
    velocity = PayloadSchema(
        kind=SchemaKind.RECORD,
        fields={key: NUMBER for key in ("vx", "vy", "vz")},
        metadata={"frame": "local_NED", "units": "m/s"},
    )
    return tuple(
        _property(*item)
        for item in (
            (
                "landed",
                scalar(ScalarType.BOOL),
                "VehicleLandDetected",
                "out/vehicle_land_detected",
                "landed",
                None,
            ),
            (
                "position",
                VECTOR,
                "VehicleLocalPosition",
                "out/vehicle_local_position",
                None,
                None,
            ),
            (
                "velocity",
                velocity,
                "VehicleLocalPosition",
                "out/vehicle_local_position",
                None,
                None,
            ),
            (
                "armed",
                STRING,
                "VehicleStatus",
                "out/vehicle_status_v1",
                "arming_state",
                "agent_binding_px4.properties:armed_state",
            ),
            (
                "flight_mode",
                STRING,
                "VehicleStatus",
                "out/vehicle_status_v1",
                "nav_state",
                "agent_binding_px4.properties:flight_mode",
            ),
        )
    )


def _property(
    name: str,
    schema: PayloadSchema,
    interface: str,
    topic: str,
    field: str | None,
    adapter: str | None,
) -> BindingDefinition:
    value = Channel(
        id="value",
        direction=Direction.AGENT_TO_CONSUMER,
        schema=schema,
        cardinality=Cardinality.STREAM,
        lifetime=Lifetime.PERSISTENT,
        purpose=Purpose.VALUE,
    )
    return BindingDefinition(
        id="px4." + name,
        description="PX4 " + name,
        primitive=Primitive.PROPERTY,
        default_semantics=BindingSemantics(
            element=Property(
                id=name,
                description="Observed " + name,
                schema=schema,
                channels=("value",),
            ),
            channels=(value,),
        ),
        ros2_template={
            "endpoints": [endpoint("state", interface, topic)],
            "channel_mappings": [mapping("value", "state", field=field, adapter=adapter)],
        },
    )


def armed_state(value: int) -> str:
    return {1: "disarmed", 2: "armed"}.get(value, "unknown")


_MODES = {
    0: "manual",
    1: "altitude",
    2: "position",
    3: "mission",
    4: "hold",
    5: "return",
    6: "position_slow",
    10: "acro",
    12: "descend",
    13: "termination",
    14: "offboard",
    15: "stabilized",
    17: "takeoff",
    18: "land",
    19: "follow",
    20: "precision_land",
    21: "orbit",
    22: "vtol_takeoff",
}


def flight_mode(value: int) -> str:
    number = int(value)
    if 23 <= number <= 30:
        return f"external_{number - 22}"
    return _MODES.get(number, "unknown")
