from dataclasses import replace
from importlib.metadata import EntryPoint, EntryPoints, distribution
from unittest.mock import patch

import pytest
from agent_framework.binding.api import BindingPackage
from agent_framework.binding.definition import configure_binding
from agent_framework.binding.discovery import discover_bindings
from agent_framework.binding.errors import (
    BindingError,
    IncompatibleBindingError,
    MissingBindingError,
)


def test_installed_binding_discovery() -> None:
    registry = discover_bindings(["test.temperature", "test.command", "test.stream"])
    assert registry.get("test.temperature").id == "test.temperature"
    assert registry.packages["test"].distribution == "agent-binding-test"
    assert registry.packages["test"].version == "0.1.0"


def test_unreferenced_provider_is_not_loaded() -> None:
    point = EntryPoint(
        name="unused", value="nonexistent:provider", group="agent_framework.bindings"
    )
    with patch(
        "agent_framework.binding.discovery.entry_points",
        return_value=EntryPoints((point,)),
    ):
        assert not discover_bindings([]).packages


@pytest.mark.parametrize(
    "reference", ["missing.element", "test.missing", "unqualified"]
)
def test_missing_references(reference: str) -> None:
    with pytest.raises(MissingBindingError):
        discover_bindings([reference])


def test_incompatible_api() -> None:
    with (
        patch.object(
            EntryPoint,
            "load",
            return_value=lambda: BindingPackage(
                api_versions=("99.0.0",), definitions=()
            ),
        ),
        pytest.raises(IncompatibleBindingError, match="incompatible"),
    ):
        discover_bindings(["test.temperature"])


def test_ambiguous_provider() -> None:
    point = next(iter(distribution("agent-binding-test").entry_points))
    with (
        patch(
            "agent_framework.binding.discovery.entry_points",
            return_value=EntryPoints((point, point)),
        ),
        pytest.raises(BindingError, match="ambiguous"),
    ):
        discover_bindings(["test.temperature"])


def test_configuration_schema_rejects_unknown_keys_and_values() -> None:
    definition = discover_bindings(["test.stream"]).get("test.stream")
    for configuration in (
        {"unknown": 1},
        {"max_rate_hz": "bad"},
        {"liveness_owner": "unknown"},
    ):
        with pytest.raises(BindingError, match="configuration"):
            configure_binding(definition, configuration)
    assert (
        configure_binding(definition, {"max_rate_hz": 5}).channels[0].timing is not None
    )


def test_dependency_discovery_reports_missing_dependency() -> None:
    registry = discover_bindings(["test.temperature"])
    definition = replace(
        registry.get("test.temperature"), dependencies=("missing.element",)
    )
    with (
        patch.object(
            EntryPoint,
            "load",
            return_value=lambda: BindingPackage(
                api_versions=("0.1.0",), definitions=(definition,)
            ),
        ),
        pytest.raises(MissingBindingError, match="missing"),
    ):
        discover_bindings(["test.temperature"])
