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

    perf_schema = PayloadSchema(
        kind=SchemaKind.RECORD,
        fields={
            "latency": PayloadSchema(
                kind=SchemaKind.SCALAR, scalar_type=ScalarType.FLOAT64
            ),
            "queue_depth": PayloadSchema(
                kind=SchemaKind.SCALAR, scalar_type=ScalarType.FLOAT64
            ),
            "dropped_samples": PayloadSchema(
                kind=SchemaKind.SCALAR, scalar_type=ScalarType.FLOAT64
            ),
        },
    )
    perf_channel = Channel(
        id="value",
        direction=Direction.AGENT_TO_CONSUMER,
        schema=perf_schema,
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
                    }
                ],
            },
        ),
        BindingDefinition(
            id="lidar.performance",
            description="Lidar performance instrumentation",
            primitive=Primitive.PROPERTY,
            default_semantics=BindingSemantics(
                element=Property(
                    id="performance",
                    description="Performance metrics for latency, queue depth, dropped samples",
                    schema=perf_schema,
                    channels=("value",),
                ),
                channels=(perf_channel,),
            ),
            ros2_template={
                "endpoints": [
                    {
                        "id": "perf_topic",
                        "kind": "topic",
                        "role": "subscriber",
                        "interface_type": "geometry_msgs/msg/Vector3",
                        "name_template": "/{namespace}/lidar/performance",
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
                        "endpoint": "perf_topic",
                        "part": "message",
                        "adapter": "agent_binding_lidar.properties:performance_adapter",
                    }
                ],
            },
        ),
    )


def performance_adapter(msg: object) -> object:
    m = msg  # Vector3
    return type(
        "Performance",
        (),
        {
            "latency": getattr(m, "x", 0.0),
            "queue_depth": getattr(m, "y", 0.0),
            "dropped_samples": getattr(m, "z", 0.0),
        },
    )()
