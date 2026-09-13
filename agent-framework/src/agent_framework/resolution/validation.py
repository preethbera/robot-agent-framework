"""Mandatory requirement checks; no technology inference or expression language."""

import math
from collections.abc import Mapping

from agent_framework.binding.definition import BindingSemantics
from agent_framework.model import (
    Channel,
    Constraint,
    ConstraintKind,
    Ordering,
    Reliability,
)

from .errors import MandatoryRequirementError, ResolutionError


def _number(value: object) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ResolutionError("range bounds must be numbers")
    if isinstance(value, float) and not math.isfinite(value):
        raise ResolutionError("range bounds must be finite")
    return value


def validate_constraint_parameters(constraint: Constraint) -> None:
    parameters = constraint.parameters
    if constraint.kind is ConstraintKind.RANGE:
        if not parameters.keys() & {"min", "max"} or parameters.keys() - {"min", "max", "field"}:
            raise ResolutionError("range parameters require min/max and optional field")
        low = _number(parameters["min"]) if "min" in parameters else None
        high = _number(parameters["max"]) if "max" in parameters else None
        if low is not None and high is not None and low > high:
            raise ResolutionError("range minimum exceeds maximum")
    elif constraint.kind is ConstraintKind.ALLOWED_VALUES:
        values = parameters.get("values")
        if (
            parameters.keys() - {"values", "field"}
            or not isinstance(values, (list, tuple))
            or not values
        ):
            raise ResolutionError("allowed_values requires a non-empty values list")
    # Preconditions/mutual exclusions are declarative; do not invent an evaluator.


def require_stricter(
    required: Constraint, candidate: Constraint, *, replacement: bool = False
) -> None:
    """Same-target requirements can only be narrowed, never removed or weakened."""
    validate_constraint_parameters(required)
    validate_constraint_parameters(candidate)
    if required.consumer_visible and not candidate.consumer_visible:
        raise MandatoryRequirementError("cannot hide a mandatory consumer-visible constraint")
    if required.kind is ConstraintKind.RANGE:
        for name in ("min", "max"):
            if name in required.parameters:
                if name not in candidate.parameters:
                    if replacement:
                        raise MandatoryRequirementError(f"mandatory {name} bound cannot be removed")
                    continue
                old, new = _number(required.parameters[name]), _number(candidate.parameters[name])
                if (name == "min" and new < old) or (name == "max" and new > old):
                    raise MandatoryRequirementError(f"mandatory {name} bound cannot be weakened")
    elif required.kind is ConstraintKind.ALLOWED_VALUES:
        old_values, new_values = required.parameters["values"], candidate.parameters["values"]
        assert isinstance(old_values, (list, tuple)) and isinstance(new_values, (list, tuple))
        if any(value not in old_values for value in new_values):
            raise MandatoryRequirementError("mandatory allowed values cannot be widened")
    elif dict(required.parameters) != dict(candidate.parameters):
        raise MandatoryRequirementError("mandatory declarative requirement cannot be replaced")


def same_subject(first: Constraint, second: Constraint) -> bool:
    return first.kind is second.kind and first.target == second.target


def protect_constraints(
    required: tuple[Constraint, ...], candidates: tuple[Constraint, ...]
) -> None:
    for candidate in candidates:
        validate_constraint_parameters(candidate)
        for baseline in required:
            if candidate.id == baseline.id and not same_subject(baseline, candidate):
                raise MandatoryRequirementError("mandatory constraint ID cannot be repurposed")
            if same_subject(baseline, candidate):
                require_stricter(baseline, candidate, replacement=baseline.id == candidate.id)


def protect_channels(required: tuple[Channel, ...], semantics: BindingSemantics) -> None:
    channels = {channel.id: channel for channel in semantics.channels}
    for baseline in required:
        current = channels.get(baseline.id)
        if current is None:
            raise MandatoryRequirementError(f"mandatory channel {baseline.id!r} cannot be removed")
        if (
            baseline.direction,
            baseline.schema,
            baseline.cardinality,
            baseline.lifetime,
            baseline.purpose,
        ) != (
            current.direction,
            current.schema,
            current.cardinality,
            current.lifetime,
            current.purpose,
        ):
            raise MandatoryRequirementError("mandatory channel semantics cannot change")
        if (
            baseline.correlates_with is not None
            and baseline.correlates_with != current.correlates_with
        ):
            raise MandatoryRequirementError("mandatory channel correlation cannot change")
        if baseline.timing is not None:
            for name in ("min_rate_hz", "max_rate_hz", "max_gap_s", "max_latency_s", "max_age_s"):
                bound = getattr(baseline.timing, name)
                if bound is None:
                    continue
                actual = getattr(current.timing, name, None)
                if actual is None or (actual < bound if name == "min_rate_hz" else actual > bound):
                    raise MandatoryRequirementError(f"mandatory channel {name} cannot be weakened")
        if baseline.delivery is not None:
            if current.delivery is None:
                raise MandatoryRequirementError("mandatory delivery cannot be removed")
            if (
                baseline.delivery.reliability is Reliability.RELIABLE
                and current.delivery.reliability is not Reliability.RELIABLE
            ):
                raise MandatoryRequirementError("mandatory reliable delivery cannot be weakened")
            if (
                baseline.delivery.ordering is Ordering.ORDERED
                and current.delivery.ordering is not Ordering.ORDERED
            ):
                raise MandatoryRequirementError("mandatory ordered delivery cannot be weakened")


def validate_dependencies(
    definitions: Mapping[str, tuple[str, ...]], roots: tuple[str, ...]
) -> None:
    active: set[str] = set()
    done: set[str] = set()
    pending = [(root, False) for root in roots]
    while pending:
        name, leaving = pending.pop()
        if leaving:
            active.remove(name)
            done.add(name)
            continue
        if name in active:
            raise ResolutionError(f"binding dependency cycle at {name!r}")
        if name in done:
            continue
        if name not in definitions:
            raise ResolutionError(f"missing dependency {name!r}")
        active.add(name)
        pending.append((name, True))
        pending.extend((child, False) for child in definitions[name])


def validate_constraint_intersections(constraints: tuple[Constraint, ...]) -> None:
    """Reject empty intersections of independently added same-payload limits."""
    ranges: dict[object, tuple[float | int | None, float | int | None]] = {}
    choices: dict[object, list[object]] = {}
    for constraint in constraints:
        subject = constraint.target
        if constraint.kind is ConstraintKind.RANGE:
            low, high = ranges.get(subject, (None, None))
            if "min" in constraint.parameters:
                bound = _number(constraint.parameters["min"])
                low = bound if low is None else max(low, bound)
            if "max" in constraint.parameters:
                bound = _number(constraint.parameters["max"])
                high = bound if high is None else min(high, bound)
            if low is not None and high is not None and low > high:
                raise ResolutionError("incompatible range constraints have an empty intersection")
            ranges[subject] = low, high
        elif constraint.kind is ConstraintKind.ALLOWED_VALUES:
            values = constraint.parameters["values"]
            assert isinstance(values, (list, tuple))
            result = [value for value in choices.get(subject, list(values)) if value in values]
            if not result:
                raise ResolutionError("incompatible allowed values have an empty intersection")
            choices[subject] = result
