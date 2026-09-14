"""Independent declarative test binding; no ROS2 or device communication."""

from collections.abc import Mapping
from dataclasses import replace

from agent_framework.binding.api import BindingPackage
from agent_framework.binding.definition import (
    BindingDefinition,
    BindingRequirements,
    BindingSemantics,
    Primitive,
)
from agent_framework.model import (
    Capability,
    Cardinality,
    Channel,
    Constraint,
    ConstraintKind,
    ConstraintTarget,
    Direction,
    Execution,
    Lifetime,
    PayloadSchema,
    Property,
    Purpose,
    ScalarType,
    SchemaKind,
    TargetKind,
    Timing,
)

from .advanced import protocol_bindings
from .ros2 import COMMAND, TEMPERATURE, stream_template

NUMBER = PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.FLOAT64)


def _stream(configuration: Mapping[str, object]) -> BindingSemantics:
    owner = str(configuration["liveness_owner"])
    output = Channel(
        id="output",
        direction=Direction.AGENT_TO_CONSUMER,
        schema=NUMBER,
        cardinality=Cardinality.STREAM,
        lifetime=Lifetime.SESSION,
        purpose=Purpose.OUTPUT,
        timing=Timing(max_rate_hz=float(str(configuration["max_rate_hz"]))),
    )
    channels: tuple[Channel, ...] = (output,)
    if owner == "application":
        channels += (
            Channel(
                id="liveness",
                direction=Direction.CONSUMER_TO_AGENT,
                schema=NUMBER,
                cardinality=Cardinality.STREAM,
                lifetime=Lifetime.SESSION,
                purpose=Purpose.LIVENESS,
                timing=Timing(max_gap_s=0.5),
            ),
        )
    return BindingSemantics(
        element=Capability(
            id="stream",
            description="Stream sensor measurements",
            execution=Execution.SESSION,
            channels=tuple(item.id for item in channels),
        ),
        channels=channels,
        responsibility_ownership={"liveness": owner},
    )


def get_bindings() -> BindingPackage:
    value = Channel(
        id="value",
        direction=Direction.AGENT_TO_CONSUMER,
        schema=NUMBER,
        cardinality=Cardinality.STREAM,
        lifetime=Lifetime.PERSISTENT,
        purpose=Purpose.VALUE,
    )
    request = replace(
        value,
        id="request",
        direction=Direction.CONSUMER_TO_AGENT,
        cardinality=Cardinality.SINGLE,
        lifetime=Lifetime.INVOCATION,
        purpose=Purpose.INPUT,
    )
    result = replace(
        request,
        id="result",
        direction=Direction.AGENT_TO_CONSUMER,
        purpose=Purpose.RESULT,
        correlates_with="request",
    )
    limit = Constraint(
        id="request_range",
        description="Valid requested value",
        target=ConstraintTarget(kind=TargetKind.CHANNEL, id="request"),
        kind=ConstraintKind.RANGE,
        parameters={"min": 0.0, "max": 100.0},
        consumer_visible=True,
    )
    package = BindingPackage(
        api_versions=("0.1.0",),
        definitions=(
            BindingDefinition(
                id="test.temperature",
                description="Component temperature",
                primitive=Primitive.PROPERTY,
                default_semantics=BindingSemantics(
                    element=Property(
                        id="temperature",
                        description="Component temperature",
                        schema=NUMBER,
                        channels=("value",),
                    ),
                    channels=(value,),
                ),
                ros2_template=TEMPERATURE,
            ),
            BindingDefinition(
                id="test.command",
                description="Discrete command",
                primitive=Primitive.CAPABILITY,
                default_semantics=BindingSemantics(
                    element=Capability(
                        id="command",
                        description="Discrete command",
                        execution=Execution.INVOCATION,
                        channels=("request", "result"),
                    ),
                    channels=(request, result),
                ),
                mandatory_requirements=BindingRequirements(constraints=(limit,)),
                ros2_template=COMMAND,
            ),
            BindingDefinition(
                id="test.stream",
                description="Continuous sensing",
                primitive=Primitive.CAPABILITY,
                default_semantics=_stream({"max_rate_hz": 10.0, "liveness_owner": "binding"}),
                mandatory_requirements=BindingRequirements(
                    channels=_stream({"max_rate_hz": 10.0, "liveness_owner": "binding"}).channels
                ),
                configuration_schema=PayloadSchema(
                    kind=SchemaKind.RECORD,
                    fields={
                        "max_rate_hz": NUMBER,
                        "liveness_owner": PayloadSchema(
                            kind=SchemaKind.ENUM,
                            scalar_type=ScalarType.STRING,
                            values=("binding", "application"),
                        ),
                    },
                ),
                configuration_defaults={
                    "max_rate_hz": 10.0,
                    "liveness_owner": "binding",
                },
                configure=_stream,
                configure_ros2=stream_template,
            ),
        ),
    )

    return replace(
        package,
        definitions=package.definitions + protocol_bindings(package.definitions[1]),
    )
