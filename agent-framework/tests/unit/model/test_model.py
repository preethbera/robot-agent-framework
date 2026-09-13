"""Required M1 scenarios and validation of complete semantic graphs."""

from dataclasses import replace
from typing import cast

import pytest

from agent_framework.model import (
    Agent,
    Capability,
    Cardinality,
    Channel,
    Constraint,
    ConstraintKind,
    ConstraintTarget,
    Delivery,
    Direction,
    Execution,
    Group,
    Lifetime,
    Ordering,
    PayloadSchema,
    Property,
    Purpose,
    Reliability,
    ScalarType,
    SchemaKind,
    TargetKind,
    Timing,
    validate_agent,
    validate_capability,
    validate_channel,
    validate_constraint,
    validate_groups,
    validate_property,
)

FLOAT = PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.FLOAT64)
BOOL = PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.BOOL)
VECTOR = PayloadSchema(kind=SchemaKind.RECORD, fields={"x": FLOAT, "y": FLOAT, "z": FLOAT})


def channel(
    identifier: str,
    *,
    purpose: Purpose = Purpose.OUTPUT,
    direction: Direction = Direction.AGENT_TO_CONSUMER,
    cardinality: Cardinality = Cardinality.STREAM,
    lifetime: Lifetime = Lifetime.SESSION,
    schema: PayloadSchema = FLOAT,
    correlates_with: str | None = None,
) -> Channel:
    return Channel(
        id=identifier,
        schema=schema,
        direction=direction,
        purpose=purpose,
        cardinality=cardinality,
        lifetime=lifetime,
        correlates_with=correlates_with,
    )


@pytest.fixture
def sensor_agent() -> Agent:
    return Agent(
        id="inspection_agent",
        description="Reusable inspection Agent",
        properties=(
            Property(
                id="health", description="Sensor health", schema=BOOL, channels=("health_value",)
            ),
            Property(id="mass", description="Agent mass", schema=FLOAT, constant_value=2.5),
        ),
        capabilities=(
            Capability(
                id="lidar_stream",
                description="Stream environmental measurements",
                execution=Execution.SESSION,
                channels=("points",),
            ),
            Capability(
                id="lidar_scan",
                description="Acquire one scan",
                execution=Execution.INVOCATION,
                channels=("scan_result",),
            ),
        ),
        channels=(
            channel(
                "health_value", schema=BOOL, purpose=Purpose.VALUE, lifetime=Lifetime.PERSISTENT
            ),
            channel("points", schema=PayloadSchema(kind=SchemaKind.SEQUENCE, items=VECTOR)),
            channel(
                "scan_result",
                schema=PayloadSchema(kind=SchemaKind.SEQUENCE, items=VECTOR),
                purpose=Purpose.RESULT,
                cardinality=Cardinality.SINGLE,
                lifetime=Lifetime.INVOCATION,
            ),
        ),
        groups=(
            Group(
                id="lidar",
                description="Lidar subsystem",
                members=("health", "lidar_stream", "lidar_scan"),
            ),
            Group(id="sensors", description="Sensors", subgroups=("lidar",)),
            Group(id="all", description="Whole Agent", members=("mass",), subgroups=("sensors",)),
        ),
    )


def test_mixed_group_contains_property_and_capability(sensor_agent: Agent) -> None:
    validate_agent(sensor_agent)
    assert sensor_agent.groups[0].members == ("health", "lidar_stream", "lidar_scan")


def test_nested_groups_and_shared_subgroups(sensor_agent: Agent) -> None:
    groups = (
        *sensor_agent.groups,
        Group(id="diagnostics", description="Shared subsystem", subgroups=("lidar",)),
    )
    validate_agent(replace(sensor_agent, groups=groups))


@pytest.mark.parametrize(
    "groups",
    [
        (Group(id="a", description="", subgroups=("a",)),),
        (
            Group(id="a", description="", subgroups=("b",)),
            Group(id="b", description="", subgroups=("a",)),
        ),
        (
            Group(id="root", description=""),
            Group(id="a", description="", subgroups=("b",)),
            Group(id="b", description="", subgroups=("a",)),
        ),
    ],
)
def test_group_cycles_are_rejected(groups: tuple[Group, ...]) -> None:
    with pytest.raises(ValueError, match="cycle"):
        validate_groups(groups, ())


def test_deep_group_graph_does_not_depend_on_python_recursion_limit() -> None:
    groups = tuple(
        Group(id=str(i), description="", subgroups=(str(i + 1),) if i < 1999 else ())
        for i in range(2000)
    )
    validate_groups(groups, ())
    with pytest.raises(ValueError, match="cycle"):
        validate_groups((*groups[:-1], replace(groups[-1], subgroups=("0",))), ())


def test_multiple_channels_and_correlated_request_response() -> None:
    request = channel(
        "request",
        purpose=Purpose.INPUT,
        schema=VECTOR,
        direction=Direction.CONSUMER_TO_AGENT,
        cardinality=Cardinality.SINGLE,
        lifetime=Lifetime.INVOCATION,
    )
    channels = (
        request,
        *(
            channel(
                purpose.value,
                purpose=purpose,
                correlates_with="request",
                cardinality=Cardinality.STREAM
                if purpose is Purpose.FEEDBACK
                else Cardinality.SINGLE,
                lifetime=Lifetime.INVOCATION,
                direction=Direction.CONSUMER_TO_AGENT
                if purpose is Purpose.CANCELLATION
                else Direction.AGENT_TO_CONSUMER,
            )
            for purpose in (
                Purpose.ACKNOWLEDGEMENT,
                Purpose.FEEDBACK,
                Purpose.RESULT,
                Purpose.CANCELLATION,
            )
        ),
    )
    capability = Capability(
        id="move",
        description="Move to target",
        execution=Execution.INVOCATION,
        channels=tuple(item.id for item in channels),
    )
    validate_agent(
        Agent(id="mobile", description="", capabilities=(capability,), channels=channels)
    )
    assert len(capability.channels) == 5
    assert channels[1].correlates_with == request.id


def test_sensing_session_can_have_only_continuous_output(sensor_agent: Agent) -> None:
    validate_agent(sensor_agent)
    capability = sensor_agent.capabilities[0]
    output = sensor_agent.channels[1]
    assert capability.execution is Execution.SESSION
    assert capability.channels == (output.id,)
    assert (output.purpose, output.direction, output.cardinality, output.lifetime) == (
        Purpose.OUTPUT,
        Direction.AGENT_TO_CONSUMER,
        Cardinality.STREAM,
        Lifetime.SESSION,
    )


def test_sensing_invocation_has_one_time_result(sensor_agent: Agent) -> None:
    validate_agent(sensor_agent)
    assert sensor_agent.capabilities[1].execution is Execution.INVOCATION
    result = sensor_agent.channels[2]
    assert (result.purpose, result.cardinality, result.lifetime) == (
        Purpose.RESULT,
        Cardinality.SINGLE,
        Lifetime.INVOCATION,
    )


@pytest.mark.parametrize(
    "constant,schema",
    [
        (0, PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.INT32)),
        (False, BOOL),
        ("", PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.STRING)),
        (None, PayloadSchema(kind=SchemaKind.OPAQUE)),
    ],
)
def test_contract_static_property_without_channels(constant: object, schema: PayloadSchema) -> None:
    prop = Property(id="static", description="", schema=schema, constant_value=constant)
    validate_agent(Agent(id="static_agent", description="", properties=(prop,)))
    assert prop.channels == ()
    assert prop.constant_value is constant


def test_validation_is_explicit() -> None:
    prop = Property(id="dynamic", description="", schema=FLOAT)
    with pytest.raises(ValueError, match="requires a channel"):
        validate_property(prop)


@pytest.mark.parametrize(
    "kind,identifier,path",
    [
        (TargetKind.AGENT, "inspection_agent", ()),
        (TargetKind.GROUP, "lidar", ()),
        (TargetKind.PROPERTY, "mass", ()),
        (TargetKind.CAPABILITY, "lidar_stream", ()),
        (TargetKind.CHANNEL, "health_value", ()),
        (TargetKind.PROPERTY, "position", ("pose", "x")),
        (TargetKind.CHANNEL, "pose_value", ("pose", "z")),
    ],
)
@pytest.mark.parametrize("constraint_kind", list(ConstraintKind))
def test_constraints_target_valid_elements_and_nested_payload_fields(
    sensor_agent: Agent,
    kind: TargetKind,
    identifier: str,
    path: tuple[str, ...],
    constraint_kind: ConstraintKind,
) -> None:
    schema = PayloadSchema(kind=SchemaKind.RECORD, fields={"pose": VECTOR})
    position = Property(id="position", description="", schema=schema, channels=("pose_value",))
    constraint = Constraint(
        id="limit",
        description="Declarative limitation",
        target=ConstraintTarget(kind=kind, id=identifier, field_path=path),
        kind=constraint_kind,
        parameters={},
        consumer_visible=True,
    )
    validate_agent(
        replace(
            sensor_agent,
            properties=(*sensor_agent.properties, position),
            channels=(*sensor_agent.channels, channel("pose_value", schema=schema)),
            constraints=(constraint,),
        )
    )


@pytest.mark.parametrize("kind", list(TargetKind))
def test_unknown_constraint_targets_are_rejected(sensor_agent: Agent, kind: TargetKind) -> None:
    constraint = Constraint(
        id="bad",
        description="",
        target=ConstraintTarget(kind=kind, id="missing"),
        kind=ConstraintKind.RANGE,
        parameters={"min": 0},
        consumer_visible=False,
    )
    with pytest.raises(ValueError, match="unknown constraint target"):
        validate_agent(replace(sensor_agent, constraints=(constraint,)))


@pytest.mark.parametrize(
    "kind,identifier,path",
    [
        (TargetKind.PROPERTY, "mass", ("x",)),
        (TargetKind.CHANNEL, "health_value", ("unknown",)),
        (TargetKind.CAPABILITY, "lidar_stream", ("x",)),
    ],
)
def test_invalid_payload_field_targets_are_rejected(
    sensor_agent: Agent, kind: TargetKind, identifier: str, path: tuple[str, ...]
) -> None:
    constraint = Constraint(
        id="bad",
        description="",
        target=ConstraintTarget(kind=kind, id=identifier, field_path=path),
        kind=ConstraintKind.RANGE,
        parameters={},
        consumer_visible=True,
    )
    with pytest.raises(ValueError, match="payload field"):
        validate_agent(replace(sensor_agent, constraints=(constraint,)))


@pytest.mark.parametrize("collection", ["properties", "capabilities", "channels", "groups"])
def test_duplicate_element_ids_are_rejected(sensor_agent: Agent, collection: str) -> None:
    if collection == "properties":
        duplicate = replace(
            sensor_agent, properties=(*sensor_agent.properties, sensor_agent.properties[0])
        )
    elif collection == "capabilities":
        duplicate = replace(
            sensor_agent, capabilities=(*sensor_agent.capabilities, sensor_agent.capabilities[0])
        )
    elif collection == "channels":
        duplicate = replace(
            sensor_agent, channels=(*sensor_agent.channels, sensor_agent.channels[0])
        )
    else:
        duplicate = replace(sensor_agent, groups=(*sensor_agent.groups, sensor_agent.groups[0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate_agent(duplicate)


def test_ambiguous_primitive_ids_are_rejected(sensor_agent: Agent) -> None:
    capability = replace(sensor_agent.capabilities[0], id="health")
    with pytest.raises(ValueError, match="unambiguous"):
        validate_agent(replace(sensor_agent, capabilities=(capability,)))


def test_unknown_and_unassociated_channels_are_rejected(sensor_agent: Agent) -> None:
    prop = replace(sensor_agent.properties[0], channels=("missing",))
    with pytest.raises(ValueError, match="unknown channel"):
        validate_agent(replace(sensor_agent, properties=(prop,)))
    with pytest.raises(ValueError, match="not associated"):
        validate_agent(replace(sensor_agent, channels=(*sensor_agent.channels, channel("orphan"))))


@pytest.mark.parametrize("correlation", ["missing", "points"])
def test_invalid_correlations_are_rejected(sensor_agent: Agent, correlation: str) -> None:
    channels = list(sensor_agent.channels)
    channels[1] = replace(channels[1], correlates_with=correlation)
    with pytest.raises(ValueError, match="correlat"):
        validate_agent(replace(sensor_agent, channels=tuple(channels)))


@pytest.mark.parametrize(
    "group,message",
    [
        (Group(id="bad", description="", members=("missing",)), "unknown member"),
        (Group(id="bad", description="", subgroups=("missing",)), "unknown subgroup"),
        (Group(id="bad", description="", members=("health", "health")), "duplicate reference"),
        (Group(id="bad", description="", subgroups=("lidar", "lidar")), "duplicate reference"),
    ],
)
def test_invalid_group_references(sensor_agent: Agent, group: Group, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_agent(replace(sensor_agent, groups=(*sensor_agent.groups, group)))


def test_timing_and_delivery_are_transport_neutral() -> None:
    value = replace(
        channel("output"),
        timing=Timing(
            min_rate_hz=10, max_rate_hz=20, max_gap_s=0.2, max_latency_s=0.1, max_age_s=0.2
        ),
        delivery=Delivery(reliability=Reliability.BEST_EFFORT, ordering=Ordering.ORDERED),
    )
    validate_channel(value)


@pytest.mark.parametrize(
    "name", ["min_rate_hz", "max_rate_hz", "max_gap_s", "max_latency_s", "max_age_s"]
)
@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf")])
def test_invalid_timing_is_rejected(name: str, value: float) -> None:
    with pytest.raises(ValueError, match="finite non-negative"):
        validate_channel(replace(channel("output"), timing=Timing(**{name: value})))


def test_inverted_rates_are_rejected() -> None:
    with pytest.raises(ValueError, match="min_rate_hz"):
        validate_channel(replace(channel("output"), timing=Timing(min_rate_hz=20, max_rate_hz=10)))


def test_invalid_enum_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="execution"):
        validate_capability(
            Capability(id="bad", description="", execution=cast(Execution, "future"))
        )
    with pytest.raises(ValueError, match="Direction"):
        validate_channel(replace(channel("bad"), direction=cast(Direction, "bidirectional")))
    with pytest.raises(ValueError, match="reliability"):
        validate_channel(
            replace(
                channel("bad"),
                delivery=Delivery(
                    reliability=cast(Reliability, "unknown"),
                    ordering=Ordering.ORDERED,
                ),
            )
        )
    with pytest.raises(ValueError, match="kind"):
        validate_constraint(
            Constraint(
                id="bad",
                description="",
                kind=cast(ConstraintKind, "expression"),
                target=ConstraintTarget(kind=TargetKind.AGENT, id="agent"),
                parameters={},
                consumer_visible=True,
            )
        )


def test_models_are_slotted_and_metadata_defaults_are_independent() -> None:
    first = Agent(id="first", description="")
    second = Agent(id="second", description="")
    assert not hasattr(first, "__dict__")
    assert first.metadata is not second.metadata
    assert not hasattr(channel("output"), "__dict__")
    assert not hasattr(FLOAT, "__dict__")
