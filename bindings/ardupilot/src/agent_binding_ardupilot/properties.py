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
        metadata={"frame": "local_ENU", "units": "m/s"},
    )
    return tuple(
        _property(*item)
        for item in (
            (
                "position",
                VECTOR,
                "PoseStamped",
                "pose/filtered",
                None,
                None,
                "geometry_msgs",
            ),
            (
                "velocity",
                velocity,
                "TwistStamped",
                "twist/filtered",
                None,
                None,
                "geometry_msgs",
            ),
            (
                "armed",
                STRING,
                "ArmMotorsStatus",
                "arm_motors/status",
                "armed",
                "agent_binding_ardupilot.properties:armed_state",
                "ardupilot_msgs",
            ),
            (
                "flight_mode",
                STRING,
                "FlightMode",
                "mode/current",
                "mode",
                "agent_binding_ardupilot.properties:flight_mode",
                "ardupilot_msgs",
            ),
            (
                "battery",
                PayloadSchema(
                    kind=SchemaKind.RECORD,
                    fields={
                        "voltage": NUMBER,
                        "percentage": NUMBER,
                    },
                    metadata={"voltage_units": "V", "percentage_range": "0..1"},
                ),
                "BatteryState",
                "battery/battery0",
                None,
                None,
                "sensor_msgs",
            ),
            (
                "gps",
                PayloadSchema(
                    kind=SchemaKind.RECORD,
                    fields={
                        "latitude": NUMBER,
                        "longitude": NUMBER,
                        "altitude": NUMBER,
                    },
                    metadata={"units": "degrees/metres", "datum": "WGS84"},
                ),
                "NavSatFix",
                "navsat/navsat0",
                None,
                None,
                "sensor_msgs",
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
    package: str,
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
        id="ardupilot." + name,
        description="ArduPilot " + name,
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
            "endpoints": [endpoint("state", interface, topic, package=package)],
            "channel_mappings": [mapping("value", "state", field=field, adapter=adapter)],
        },
    )


def armed_state(value: bool) -> str:
    return "armed" if value else "disarmed"


# ArduPilot Copter flight modes
_MODES = {
    0: "stabilize",
    1: "acro",
    2: "alt_hold",
    3: "auto",
    4: "guided",
    5: "loiter",
    6: "rtl",
    7: "circle",
    9: "land",
    11: "drift",
    13: "sport",
    14: "flip",
    15: "autotune",
    16: "poshold",
    17: "brake",
    18: "throw",
    19: "avoid_adsb",
    20: "guided_nogps",
    21: "smart_rtl",
    22: "flowhold",
    23: "follow",
    24: "zigzag",
    25: "systemid",
    26: "autorotate",
    27: "auto_rtl",
}


def flight_mode(value: int) -> str:
    return _MODES.get(int(value), "unknown")

