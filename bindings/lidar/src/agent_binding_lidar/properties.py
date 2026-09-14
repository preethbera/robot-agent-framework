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


def definitions() -> tuple[BindingDefinition, ...]:
    status_schema = PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.INT32)
    status_channel = Channel(
        id="value",
        direction=Direction.AGENT_TO_CONSUMER,
        schema=status_schema,
        cardinality=Cardinality.STREAM,
        lifetime=Lifetime.PERSISTENT,
        purpose=Purpose.VALUE,
    )

    return (
        BindingDefinition(
            id="lidar.status",
            description="Lidar health/status",
            primitive=Primitive.PROPERTY,
            default_semantics=BindingSemantics(
                element=Property(
                    id="status",
                    description="Lidar status",
                    schema=status_schema,
                    channels=("value",),
                ),
                channels=(status_channel,),
            ),
            ros2_template={
                "endpoints": [
                    {
                        "id": "status_topic",
                        "kind": "topic",
                        "role": "subscriber",
                        "interface_type": "diagnostic_msgs/msg/DiagnosticStatus",
                        "name_template": "/{namespace}/lidar/status",
                        "existing": True,
                        "qos": {
                            "history": "keep_last",
                            "depth": 1,
                            "reliability": "reliable",
                            "durability": "volatile",
                        },
                    }
                ],
                "channel_mappings": [
                    {
                        "channel": "value",
                        "endpoint": "status_topic",
                        "part": "message",
                        "field": "level",
                        "adapter": "agent_binding_lidar.properties:status_adapter",
                    }
                ],
            },
        ),
    )


def status_adapter(level: object) -> int:
    if isinstance(level, bytes) and len(level) == 1:
        level = level[0]
    if type(level) is not int or level not in (0, 1, 2, 3):
        raise ValueError("invalid DiagnosticStatus level")
    return level
