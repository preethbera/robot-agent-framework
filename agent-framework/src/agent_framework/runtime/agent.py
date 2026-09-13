"""Generic runtime plans, bounded operations, and binding component lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from importlib import import_module
from threading import RLock
from time import monotonic
from typing import Any, Protocol, Self, cast

from .channel import Buffer, deadline
from .errors import AgentError, FailureCode
from .registry import Registry


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    id: str
    owner: str
    direction: str
    purpose: str
    property: bool = False
    validate: Callable[[Any], None] = lambda value: None


@dataclass(frozen=True, slots=True)
class Codec:
    channel: str
    endpoint: str
    part: str
    encode: Callable[[Any, Any], None]
    decode: Callable[[Any], Any]
    adapter: str | None = None


@dataclass(frozen=True, slots=True)
class BindingSpec:
    id: str
    configuration: Mapping[str, object]
    runtime_parameters: tuple[str, ...]
    realization: Mapping[str, Any]
    runtime_factory: str | None = None


@dataclass(frozen=True, slots=True)
class AgentSpec:
    id: str
    channels: tuple[ChannelSpec, ...]
    codecs: tuple[Codec, ...]
    bindings: tuple[BindingSpec, ...]
    endpoints: tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, object] = field(default_factory=dict)


class Component(Protocol):
    def start(self) -> None: ...
    def close(self) -> None: ...


class SharedServices(Protocol):
    registry: Registry[AgentRuntime]

    def create_component(self, agent: AgentRuntime, binding: BindingSpec) -> Component: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class FactoryContext:
    binding_id: str
    configuration: Mapping[str, object]
    realization: Mapping[str, Any]
    instance_id: str
    agent_id: str
    namespace: str
    services: Any
    register: Callable[[str, Callable[[object, Operation], None]], None]
    emit: Callable[[str, object, Operation | None], None]


class Operation:
    def __init__(
        self, agent: AgentRuntime, owner: str, capacity: int, timeout: float | None
    ) -> None:
        self.agent = agent
        self.owner = owner
        self.end = float("inf") if timeout is None else deadline(timeout)
        self.buffers = {
            item.id: Buffer[object](capacity, target=item.id)
            for item in agent.spec.channels
            if item.owner == owner and item.direction == "agent_to_consumer"
        }
        self.closed = False
        self.lock = RLock()
        self.cleanup: list[Callable[[], None]] = []
        # Transport operation state has at most one entry per declared endpoint.
        self.transport: dict[str, Any] = {}

    def read(self, channel: str, timeout: float = 5.0) -> object:
        deadline(timeout)
        return self.buffers[channel].read(min(timeout, max(0.0, self.end - monotonic())))

    def send(self, channel: str, value: object) -> None:
        with self.lock:
            if self.closed:
                raise AgentError(FailureCode.CLOSED, "Operation is closed", target=self.owner)
            if monotonic() >= self.end:
                raise AgentError(
                    FailureCode.TIMEOUT, "Operation deadline exceeded", target=self.owner
                )
            try:
                self.agent.channel_specs[channel].validate(value)
                self.agent.senders[channel](value, self)
            except AgentError:
                raise
            except (ValueError, TypeError, OverflowError) as error:
                raise AgentError(FailureCode.INVALID_VALUE, str(error), target=channel) from error
            except Exception as error:
                raise AgentError(FailureCode.TRANSPORT, str(error), target=channel) from error

    def fail(self, error: AgentError) -> None:
        for buffer in self.buffers.values():
            buffer.fail(error)

    def close(self) -> None:
        with self.lock:
            if self.closed:
                return
            self.closed = True
            callbacks, self.cleanup = self.cleanup, []
        errors = []
        for callback in reversed(callbacks):
            try:
                callback()
            except Exception as error:
                errors.append(error)
        for buffer in self.buffers.values():
            buffer.close()
        with self.agent.lock:
            if self.agent.active.get(self.owner) is self:
                del self.agent.active[self.owner]
        if errors:
            raise AgentError(
                FailureCode.TRANSPORT, "Operation cleanup failed", target=self.owner
            ) from errors[0]


class AgentRuntime:
    def __init__(
        self,
        spec: AgentSpec,
        *,
        instance_id: str,
        namespace: str = "",
        runtime: SharedServices | None = None,
        instance_config: dict[str, dict[str, object]] | None = None,
    ) -> None:
        if not instance_id:
            raise AgentError(FailureCode.INVALID_VALUE, "instance_id must not be empty")
        self.spec = spec
        self.instance_id = instance_id
        self.namespace = namespace
        self.instance_config = instance_config or {}
        self.lock = RLock()
        self.active: dict[str, Operation] = {}
        self.openers: dict[str, list[Callable[[Operation], None]]] = {}
        self._failure: AgentError | None = None
        self.channel_specs = {item.id: item for item in spec.channels}
        self.senders: dict[str, Callable[[object, Operation], None]] = {}
        self.properties = {
            item.id: Buffer[object](latest=True, target=item.id)
            for item in spec.channels
            if item.property and item.direction == "agent_to_consumer"
        }
        self.components: list[Component] = []
        self.ready = False
        self.closed = False
        self._owns_runtime = runtime is None
        if runtime is None:
            runtime = create_runtime()
        self.runtime = runtime
        self.runtime.registry.add(instance_id, self)
        try:
            for binding in spec.bindings:
                self.components.append(runtime.create_component(self, binding))
            for component in self.components:
                component.start()
            missing = {
                item.id for item in spec.channels if item.direction == "consumer_to_agent"
            } - self.senders.keys()
            if missing:
                raise AgentError(
                    FailureCode.STARTUP, f"Missing Channel implementations: {sorted(missing)}"
                )
            self.ready = True
        except Exception as error:
            # Preserve startup failure; close attempts every resource independently.
            with suppress(Exception):
                self.close()
            raise AgentError(
                FailureCode.STARTUP, f"Agent startup failed: {error}", target=instance_id
            ) from error

    def register(self, channel: str, send: Callable[[object, Operation], None]) -> None:
        if (
            channel not in self.channel_specs
            or self.channel_specs[channel].direction != "consumer_to_agent"
        ):
            raise AgentError(
                FailureCode.STARTUP, "Unknown/input direction mismatch", target=channel
            )
        if channel in self.senders:
            raise AgentError(
                FailureCode.STARTUP, "Duplicate Channel implementation", target=channel
            )
        self.senders[channel] = send

    def emit(self, channel: str, value: object, operation: Operation | None = None) -> None:
        with self.lock:
            if self.closed:
                return
            if channel in self.properties:
                self.properties[channel].put(value)
                return
            owner = self.channel_specs[channel].owner
            active = self.active.get(owner)
            if (
                active is not None
                and (operation is None or operation is active)
                and not active.closed
            ):
                active.buffers[channel].put(value)

    def fail(self, error: AgentError) -> None:
        with self.lock:
            self._failure = error
            for buffer in self.properties.values():
                buffer.fail(error)
            for operation in self.active.values():
                operation.fail(error)

    def begin(self, owner: str, *, capacity: int = 16, timeout: float | None = 5.0) -> Operation:
        with self.lock:
            if self._failure is not None:
                raise self._failure
            if self.closed or not self.ready:
                raise AgentError(
                    FailureCode.CLOSED if self.closed else FailureCode.NOT_READY,
                    "Agent is not ready",
                )
            if owner in self.active:
                raise AgentError(
                    FailureCode.BUSY, "Capability already has an active operation", target=owner
                )
            operation = Operation(self, owner, capacity, timeout)
            self.active[owner] = operation
            try:
                for opener in self.openers.get(owner, ()):
                    opener(operation)
            except Exception as error:
                with suppress(Exception):
                    operation.close()
                raise AgentError(FailureCode.TRANSPORT, str(error), target=owner) from error
            return operation

    def write_property(self, channel: str, value: object) -> None:
        operation = self.begin(self.channel_specs[channel].owner)
        try:
            operation.send(channel, value)
        finally:
            operation.close()

    def read_property(self, channel: str, timeout: float = 5.0) -> object:
        return self.properties[channel].read(timeout)

    def close(self) -> None:
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.ready = False
            operations = tuple(self.active.values())
        failures = []
        resources: tuple[Operation | Component, ...] = (*operations, *reversed(self.components))
        for resource in resources:
            try:
                resource.close()
            except Exception as error:
                failures.append(error)
        for buffer in self.properties.values():
            buffer.close()
        self.runtime.registry.remove(self.instance_id)
        if self._owns_runtime:
            try:
                self.runtime.close()
            except Exception as error:
                failures.append(error)
        if failures:
            raise AgentError(
                FailureCode.TRANSPORT, "Agent cleanup failed", target=self.instance_id
            ) from failures[0]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def create_runtime() -> SharedServices:
    """Create shared infrastructure without exposing ROS classes in the generated API."""
    try:
        return cast(SharedServices, import_module("agent_framework.ros2.runtime").Runtime())
    except Exception as error:
        raise AgentError(FailureCode.STARTUP, f"Cannot start ROS2 runtime: {error}") from error
