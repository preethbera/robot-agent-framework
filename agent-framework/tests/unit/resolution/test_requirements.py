from dataclasses import replace

import pytest

from agent_framework.binding.definition import BindingSemantics
from agent_framework.model import (
    Capability,
    Cardinality,
    Channel,
    Constraint,
    ConstraintKind,
    ConstraintTarget,
    Delivery,
    Direction,
    Execution,
    Lifetime,
    Ordering,
    PayloadSchema,
    Purpose,
    Reliability,
    ScalarType,
    SchemaKind,
    TargetKind,
    Timing,
)
from agent_framework.resolution.errors import MandatoryRequirementError
from agent_framework.resolution.validation import protect_channels, require_stricter


def required_channel() -> Channel:
    return Channel(
        id="liveness",
        direction=Direction.CONSUMER_TO_AGENT,
        schema=PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.FLOAT64),
        cardinality=Cardinality.STREAM,
        lifetime=Lifetime.SESSION,
        purpose=Purpose.LIVENESS,
        timing=Timing(min_rate_hz=2, max_gap_s=0.5),
        delivery=Delivery(reliability=Reliability.RELIABLE, ordering=Ordering.ORDERED),
    )


def semantics(channels: tuple[Channel, ...]) -> BindingSemantics:
    return BindingSemantics(
        element=Capability(
            id="control",
            description="",
            execution=Execution.SESSION,
            channels=tuple(item.id for item in channels),
        ),
        channels=channels,
    )


@pytest.mark.parametrize(
    "mode",
    [
        "removed",
        "timing_removed",
        "rate",
        "gap",
        "delivery_removed",
        "reliability",
        "ordering",
        "schema",
    ],
)
def test_mandatory_channel_requirements_cannot_weaken(mode: str) -> None:
    channel = required_channel()
    candidates = {
        "removed": (),
        "timing_removed": (replace(channel, timing=None),),
        "rate": (replace(channel, timing=Timing(min_rate_hz=1, max_gap_s=0.5)),),
        "gap": (replace(channel, timing=Timing(min_rate_hz=2, max_gap_s=1)),),
        "delivery_removed": (replace(channel, delivery=None),),
        "reliability": (
            replace(
                channel,
                delivery=Delivery(reliability=Reliability.BEST_EFFORT, ordering=Ordering.ORDERED),
            ),
        ),
        "ordering": (
            replace(
                channel,
                delivery=Delivery(reliability=Reliability.RELIABLE, ordering=Ordering.UNORDERED),
            ),
        ),
        "schema": (replace(channel, schema=PayloadSchema(kind=SchemaKind.OPAQUE)),),
    }
    with pytest.raises(MandatoryRequirementError):
        protect_channels((channel,), semantics(candidates[mode]))


def test_stricter_channel_timing_is_permitted() -> None:
    channel = required_channel()
    protect_channels(
        (channel,), semantics((replace(channel, timing=Timing(min_rate_hz=4, max_gap_s=0.25)),))
    )


@pytest.mark.parametrize("kind", [ConstraintKind.PRECONDITION, ConstraintKind.MUTUAL_EXCLUSION])
def test_declarative_mandatory_requirements_cannot_be_replaced(kind: ConstraintKind) -> None:
    constraint = Constraint(
        id="requirement",
        description="",
        target=ConstraintTarget(kind=TargetKind.CAPABILITY, id="control"),
        kind=kind,
        parameters={"required": True},
        consumer_visible=True,
    )
    require_stricter(constraint, constraint)
    with pytest.raises(MandatoryRequirementError):
        require_stricter(constraint, replace(constraint, parameters={"required": False}))
    with pytest.raises(MandatoryRequirementError, match="hide"):
        require_stricter(constraint, replace(constraint, consumer_visible=False))
