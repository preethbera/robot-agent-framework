from concurrent.futures import Future
from types import SimpleNamespace as NS
from typing import Any

import pytest
from agent_binding_px4 import offboard_runtime, runtime, transport
from agent_framework.runtime.errors import AgentError, FailureCode


class Shared:
    pass


class Node:
    def __init__(self) -> None:
        self.entities: list[Any] = []
        self.requests: list[Any] = []
        self.futures: list[Future[Any]] = []
        self.published: list[Any] = []

    def create_client(self, *args: Any, **kwargs: Any) -> Any:
        def call(request: Any) -> Future[Any]:
            self.requests.append(request)
            future: Future[Any] = Future()
            self.futures.append(future)
            return future

        return self.keep(
            NS(
                wait_for_service=lambda **kw: True,
                call_async=call,
                remove_pending_request=lambda future: None,
            )
        )

    def keep(self, entity: Any) -> Any:
        self.entities.append(entity)
        return entity

    def create_timer(self, interval: float, callback: Any, **kwargs: Any) -> Any:
        return self.keep(NS(callback=callback))

    def create_publisher(self, *args: Any, **kwargs: Any) -> Any:
        return self.keep(NS(publish=self.published.append))

    def create_subscription(self, *args: Any, **kwargs: Any) -> Any:
        return self.keep(NS())

    def destroy(self, entity: Any) -> None:
        self.entities.remove(entity)

    destroy_timer = destroy_client = destroy_publisher = destroy_subscription = destroy


class Native:
    def __init__(self, context: Any) -> None:
        self.context = context
        self.node = context.services.node

    def entity(self, name: str) -> tuple[Any, str, None]:
        cls: Any = NS(Request=lambda: NS(request=NS())) if name == "command" else NS
        return cls, name, None

    def timestamp(self) -> int:
        return 1000


class Operation:
    def __init__(self) -> None:
        self.closed = False
        self.end = float("inf")
        self.transport: dict[str, Any] = {}
        self.cleanup: list[Any] = []
        self.failures: list[AgentError] = []

    def fail(self, error: AgentError) -> None:
        self.failures.append(error)

    def close(self) -> None:
        self.closed = True
        for cleanup in self.cleanup:
            cleanup()


@pytest.fixture
def context(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(runtime, "Native", Native)
    monkeypatch.setattr(offboard_runtime, "Native", Native)
    output: list[Any] = []
    senders: dict[str, Any] = {}
    return NS(
        binding_id="control",
        configuration={"target_system": 1, "target_component": 1, "liveness_owner": "binding"},
        realization={"internal_communication": {"operation": "arm"}},
        services=NS(node=Node(), runtime=Shared(), group=None),
        register=lambda key, callback: senders.update({key: callback}),
        emit=lambda *args: output.append(args),
        output=output,
        senders=senders,
    )


def test_command_ack_is_separate_and_no_force_arm(context: Any) -> None:
    component = runtime.create_command(context)
    component.start()
    operation: Any = Operation()
    context.senders["control.request"](NS(), operation)
    node = context.services.node
    request = node.requests[0].request
    assert (request.command, request.param1, request.param2) == (400, 1.0, 0.0)
    assert request.from_external and not context.output
    node.futures[0].set_result(NS(reply=NS(command=400, result=2)))
    assert context.output == [("control.ack", "denied", operation)]
    with pytest.raises(AgentError, match="already submitted"):
        context.senders["control.request"](NS(), operation)
    component.close()
    component.close()
    assert not node.entities


def test_command_late_ack_and_bounded_lane(context: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    component = runtime.create_command(context)
    component.start()
    operation: Any = Operation()
    context.senders["control.request"](NS(), operation)
    with pytest.raises(AgentError) as error:
        context.senders["control.request"](NS(), Operation())
    assert error.value.code == FailureCode.BUSY
    monkeypatch.setattr(transport, "monotonic", lambda: float("inf"))
    assert component.client is not None
    component.client.check()
    assert operation.failures[0].code == FailureCode.TIMEOUT
    assert context.services.node.futures[0].cancelled()
    with pytest.raises(AgentError, match="uncertain"):
        context.senders["control.request"](NS(), Operation())
    component.close()
    assert not context.services.node.entities


def test_offboard_warmup_setpoints_and_shutdown(
    context: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [0.0]
    monkeypatch.setattr(offboard_runtime, "monotonic", lambda: clock[0])
    component = offboard_runtime.create_component(context)
    component.start()
    operation: Any = Operation()
    value = NS(x=1.0, y=2.0, z=-3.0, yaw=0.0)
    with pytest.raises(AgentError, match="position"):
        component.send(value, operation)
    component.position(NS(xy_valid=True, z_valid=True))
    component.send(value, operation)
    for index in range(1, 13):
        clock[0] = index * 0.1
        component.position(NS(xy_valid=True, z_valid=True))
        component.tick()
        if index < 11:
            assert not context.services.node.requests
    node = context.services.node
    assert len(node.requests) == 1
    assert (node.requests[0].request.command, node.requests[0].request.param2) == (176, 6.0)
    native = node.published[0]
    assert native.position == [1.0, 2.0, -3.0]
    assert all(v != v for v in native.velocity)
    node.futures[0].set_result(NS(reply=NS(command=176, result=0)))
    component.state(NS(nav_state=14))
    assert context.output[-1] == ("control.status", "active", operation)
    operation.close()
    count = len(node.published)
    component.tick()
    assert len(node.published) == count
    component.close()
    assert not node.entities


def test_application_liveness_is_not_generated(
    context: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [0.0]
    monkeypatch.setattr(offboard_runtime, "monotonic", lambda: clock[0])
    context.configuration["liveness_owner"] = "application"
    component = offboard_runtime.create_component(context)
    component.start()
    operation: Any = Operation()
    component.position(NS(xy_valid=True, z_valid=True))
    component.send(NS(x=0.0, y=0.0, z=-2.0, yaw=0.0), operation)
    component.tick()
    assert len(context.services.node.published) == 1  # setpoint only
    component.pulse(NS(), operation)
    assert len(context.services.node.published) == 3  # refreshed target + heartbeat
    clock[0] = 0.41
    component.tick()
    assert operation.failures[0].code == FailureCode.TIMEOUT
    assert component.operation is None
    assert not context.services.node.requests
    component.close()


def test_late_first_pulse_still_requires_full_warmup(
    context: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [0.0]
    monkeypatch.setattr(offboard_runtime, "monotonic", lambda: clock[0])
    context.configuration["liveness_owner"] = "application"
    component = offboard_runtime.create_component(context)
    component.start()
    operation: Any = Operation()
    component.position(NS(xy_valid=True, z_valid=True))
    component.send(NS(x=0.0, y=0.0, z=-2.0, yaw=0.0), operation)
    for value in (0.3, 0.6, 0.9, 1.2):
        clock[0] = value
        component.position(NS(xy_valid=True, z_valid=True))
        component.pulse(NS(), operation)
        component.tick()
        assert not context.services.node.requests
    clock[0] = 1.5
    component.position(NS(xy_valid=True, z_valid=True))
    component.pulse(NS(), operation)
    component.tick()
    assert len(context.services.node.requests) == 1
    component.close()


def test_late_pulse_cannot_hide_expiry(context: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]
    monkeypatch.setattr(offboard_runtime, "monotonic", lambda: clock[0])
    context.configuration["liveness_owner"] = "application"
    component = offboard_runtime.create_component(context)
    component.start()
    operation: Any = Operation()
    component.position(NS(xy_valid=True, z_valid=True))
    value = NS(x=0.0, y=0.0, z=-2.0, yaw=0.0)
    component.send(value, operation)
    clock[0] = 0.41
    with pytest.raises(AgentError, match="interrupted"):
        component.pulse(NS(), operation)
    with pytest.raises(AgentError, match="ended"):
        component.send(value, operation)
    assert len(context.services.node.published) == 1
    component.close()


def test_exclusive_control_and_publish_failure_cleanup(
    context: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = offboard_runtime.create_component(context)
    second = offboard_runtime.create_component(context)
    first.start()
    second.start()
    value = NS(x=0.0, y=0.0, z=-2.0, yaw=0.0)
    operation: Any = Operation()
    next_operation: Any = Operation()
    for component in (first, second):
        component.position(NS(xy_valid=True, z_valid=True))
    first.send(value, operation)
    with pytest.raises(AgentError) as busy:
        second.send(value, next_operation)
    assert busy.value.code == FailureCode.BUSY

    def failed_publish(value: object) -> None:
        raise RuntimeError("native publish failed")

    monkeypatch.setattr(first.heartbeat, "publish", failed_publish)
    first.tick()
    assert operation.failures[0].code == FailureCode.TRANSPORT
    assert first.operation is None
    second.send(value, next_operation)
    first.close()
    second.close()
    assert not context.services.node.entities
