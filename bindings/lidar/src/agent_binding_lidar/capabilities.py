from agent_framework.binding.definition import (
    BindingDefinition,
    BindingSemantics,
    Primitive,
)
from agent_framework.model import (
    Capability,
    Cardinality,
    Channel,
    Direction,
    Execution,
    Lifetime,
    PayloadSchema,
    Purpose,
    ScalarType,
    SchemaKind,
)


def definitions() -> tuple[BindingDefinition, ...]:
    # Represent sensor acquisition as a Capability
    # Continuous high-bandwidth output Channel
    schema = PayloadSchema(
        kind=SchemaKind.RECORD,
        fields={
            "ranges": PayloadSchema(
                kind=SchemaKind.SCALAR, scalar_type=ScalarType.FLOAT32
            )
        },
    )
    scan_channel = Channel(
        id="scan",
        direction=Direction.AGENT_TO_CONSUMER,
        schema=schema,
        cardinality=Cardinality.STREAM,
        lifetime=Lifetime.INVOCATION,
        purpose=Purpose.OUTPUT,
    )
    return (
        BindingDefinition(
            id="lidar.scan",
            description="Lidar scan capability",
            primitive=Primitive.CAPABILITY,
            default_semantics=BindingSemantics(
                element=Capability(
                    id="scan",
                    description="Continuous high-bandwidth output",
                    execution=Execution.INVOCATION,
                    channels=("scan",),
                ),
                channels=(scan_channel,),
            ),
            ros2_template={
                "endpoints": [
                    {
                        "id": "scan_topic",
                        "kind": "topic",
                        "role": "subscriber",
                        "interface_type": "sensor_msgs/msg/LaserScan",
                        "name_template": "/{namespace}/lidar/scan",
                        "existing": True,
                        "qos": {
                            "history": "keep_last",
                            "depth": 5,
                            "reliability": "best_effort",
                            "durability": "volatile",
                        },
                    }
                ],
                "channel_mappings": [
                    {"channel": "scan", "endpoint": "scan_topic", "part": "message"}
                ],
            },
        ),
    )
