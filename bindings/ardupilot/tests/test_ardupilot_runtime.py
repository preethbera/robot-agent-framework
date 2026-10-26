from concurrent.futures import Future
from types import SimpleNamespace as NS
from typing import Any

import pytest
from agent_binding_ardupilot import guided_runtime, runtime, transport
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
        if name in ("service", "mode_service"):
            cls: Any = NS(Request=lambda: NS())
        elif name == "setpoint":
            cls = lambda: NS(pose=NS(position=NS(x=0.0, y=0.0, z=0.0), orientation=NS(z=0.0, w=1.0)))
        elif name == "heartbeat":
            cls = lambda: NS(twist=NS(linear=NS(x=0.0, y=0.0, z=0.0)))
        else:
            cls = NS
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
    monkeypatch.setattr(guided_runtime, "Native", Native)
    output: list[Any] = []
    senders: dict[str, Any] = {}
    return NS(
        binding_id="control",
        instance_configuration={},
        configuration={
            "sysid": 1,
            "compid": 1,
            "liveness_owner": "binding",
        },
        realization={"internal_communication": {"operation": "arm"}},
        services=NS(node=Node(), runtime=Shared(), group=None),
        register=lambda key, callback: senders.update({key: callback}),
        emit=lambda *args: output.append(args),
        output=output,
        senders=senders,
    )


def test_command_ack_accepted(context: Any) -> None:
    component = runtime.create_command(context)
    component.start()
    operation: Any = Operation()
    context.senders["control.request"](NS(), operation)
    node = context.services.node
    assert len(node.requests) == 1
    assert not context.output
    # ArduPilot ArmMotors returns result=True for success
    node.futures[0].set_result(NS(result=True))
    assert context.output == [("control.ack", "accepted", operation)]
    with pytest.raises(AgentError, match="already submitted"):
        context.senders["control.request"](NS(), operation)
    component.close()
    component.close()
    assert not node.entities


def test_command_denied(context: Any) -> None:
    component = runtime.create_command(context)
    component.start()
    operation: Any = Operation()
    context.senders["control.request"](NS(), operation)
    node = context.services.node
    node.futures[0].set_result(NS(result=False))
    assert context.output == [("control.ack", "denied", operation)]
    component.close()


def test_command_timeout_and_bounded_lane(
    context: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
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


def test_guided_warmup_setpoints_and_shutdown(
    context: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [0.0]
    monkeypatch.setattr(guided_runtime, "monotonic", lambda: clock[0])
    component = guided_runtime.create_component(context)
    component.start()
    operation: Any = Operation()
    value = NS(x=1.0, y=2.0, z=3.0, yaw=0.0)
    with pytest.raises(AgentError, match="position"):
        component.send(value, operation)
    component.pose_update(NS())
    component.send(value, operation)
    for index in range(1, 12):
        clock[0] = index * 0.1
        component.pose_update(NS())
        component.tick()
        if index < 10:
            assert not context.services.node.requests
    node = context.services.node
    assert len(node.requests) == 1
    assert getattr(node.requests[0], "mode", None) == 4
    native = node.published[0]
    assert native.pose.position.x == 1.0
    assert native.pose.position.y == 2.0
    assert native.pose.position.z == 3.0
    node.futures[0].set_result(NS(status=True))
    assert context.output[-1] == ("control.status", "active", operation)
    operation.close()
    count = len(node.published)
    component.tick()
    assert len(node.published) == count
    component.close()
    assert not node.entities


def test_application_liveness(context: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]
    monkeypatch.setattr(guided_runtime, "monotonic", lambda: clock[0])
    context.configuration["liveness_owner"] = "application"
    component = guided_runtime.create_component(context)
    component.start()
    operation: Any = Operation()
    component.pose_update(NS())
    component.send(NS(x=0.0, y=0.0, z=2.0, yaw=0.0), operation)
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

