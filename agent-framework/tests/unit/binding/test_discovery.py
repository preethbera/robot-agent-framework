"""Binding discovery remains independent of any particular middleware or device."""

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from agent_framework.binding.api import BindingPackage
from agent_framework.binding.definition import (
    BindingDefinition,
    BindingSemantics,
    Primitive,
)
from agent_framework.binding.discovery import discover_bindings
from agent_framework.binding.errors import BindingError
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


@dataclass
class FakeEntryPoint:
    name: str
    package: BindingPackage
    distribution: str
    version: str
    loads: int = 0

    @property
    def dist(self) -> SimpleNamespace:
        return SimpleNamespace(metadata={"Name": self.distribution}, version=self.version)

    def load(self) -> Callable[[], BindingPackage]:
        self.loads += 1
        return lambda: self.package


def property_definition(identifier: str, *, dependencies: tuple[str, ...] = ()) -> BindingDefinition:
    channel = Channel(
        id="value",
        direction=Direction.AGENT_TO_CONSUMER,
        schema=PayloadSchema(kind=SchemaKind.SCALAR, scalar_type=ScalarType.FLOAT64),
        cardinality=Cardinality.STREAM,
        lifetime=Lifetime.PERSISTENT,
        purpose=Purpose.VALUE,
    )
    return BindingDefinition(
        id=identifier,
        description="Generic value",
        primitive=Primitive.PROPERTY,
        default_semantics=BindingSemantics(
            element=Property(
                id="value",
                description="Generic value",
                schema=channel.schema,
                channels=(channel.id,),
            ),
            channels=(channel,),
        ),
        dependencies=dependencies,
    )


def test_discovery_loads_arbitrary_namespaces_and_transitive_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    camera = FakeEntryPoint(
        name="camera",
        package=BindingPackage(
            api_versions=("0.1.0",),
            definitions=(property_definition("camera.frame"),),
        ),
        distribution="camera-binding",
        version="2.3.0",
    )
    analytics = FakeEntryPoint(
        name="analytics",
        package=BindingPackage(
            api_versions=("0.1.0",),
            definitions=(property_definition("analytics.detection", dependencies=("camera.frame",)),),
        ),
        distribution="analytics-binding",
        version="4.0.1",
    )
    monkeypatch.setattr(
        "agent_framework.binding.discovery.entry_points", lambda *, group: (camera, analytics)
    )

    registry = discover_bindings(("analytics.detection", "analytics.detection"))

    assert set(registry.definitions) == {"analytics.detection", "camera.frame"}
    assert registry.packages["analytics"].distribution == "analytics-binding"
    assert registry.packages["camera"].version == "2.3.0"
    assert (analytics.loads, camera.loads) == (1, 1)


def test_discovery_rejects_a_provider_claiming_another_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeEntryPoint(
        name="camera",
        package=BindingPackage(
            api_versions=("0.1.0",),
            definitions=(property_definition("lidar.frame"),),
        ),
        distribution="camera-binding",
        version="1.0.0",
    )
    monkeypatch.setattr(
        "agent_framework.binding.discovery.entry_points", lambda *, group: (provider,)
    )

    with pytest.raises(BindingError, match="invalid or duplicate binding ID"):
        discover_bindings(("camera.frame",))
