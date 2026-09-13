"""Small external code-backed component used by M4 integration tests."""

from typing import Any

from agent_framework.runtime.agent import FactoryContext, Operation

EVENTS: list[tuple[str, str]] = []
FAIL_START = ""
FAIL_CREATE = ""


class TestComponent:
    def __init__(self, context: FactoryContext) -> None:
        self.context = context
        self.timer: Any = None
        self.started = False
        self.closed = False

    def start(self) -> None:
        if self.started or self.closed:
            return
        context = self.context
        EVENTS.append(("start", context.binding_id))
        if context.binding_id == FAIL_START:
            raise RuntimeError("requested fixture startup failure")
        if context.binding_id == "command":

            def send(value: object, operation: Operation) -> None:
                context.emit("command.result", value, operation)

            context.register("command.request", send)
        elif context.binding_id == "temperature":
            self.timer = context.services.node.create_timer(
                0.05, lambda: context.emit("temperature.value", 23.0, None)
            )
        else:
            context.register("lidar_stream.liveness", lambda value, operation: None)
            self.timer = context.services.node.create_timer(
                0.2, lambda: context.emit("lidar_stream.output", 4.0, None)
            )
        self.started = True

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        EVENTS.append(("close", self.context.binding_id))
        if self.timer is not None:
            self.context.services.node.destroy_timer(self.timer)
            self.timer = None


def create_component(context: FactoryContext) -> TestComponent:
    EVENTS.append(("create", context.binding_id))
    if context.binding_id == FAIL_CREATE:
        context.services.node.create_timer(0.2, lambda: None)
        raise RuntimeError("requested fixture factory failure")
    return TestComponent(context)
