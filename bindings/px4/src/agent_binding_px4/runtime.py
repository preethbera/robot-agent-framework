"""Factory entry points; no runtime definition parsing, discovery, or generation."""

from typing import Any

from agent_framework.runtime.agent import FactoryContext, Operation
from agent_framework.runtime.errors import AgentError, FailureCode

from .commands import COMMANDS
from .transport import CommandClient, Native


class CommandComponent:
    def __init__(self, context: FactoryContext) -> None:
        self.context = context
        name = context.realization["internal_communication"]["operation"]
        self.command = next(item for item in COMMANDS if item.name == name)
        self.client: CommandClient | None = None
        self.closed = False

    def start(self) -> None:
        if self.client is not None or self.closed:
            return
        self.client = CommandClient(Native(self.context))
        self.context.register(self.context.binding_id + ".request", self.send)

    def send(self, value: Any, operation: Operation) -> None:
        assert self.client is not None
        key = self.context.binding_id
        if key in operation.transport:
            raise AgentError(FailureCode.BUSY, "Command already submitted for this invocation")
        parameters = self.command.parameters(value)
        self.client.send(
            self.command.command,
            parameters,
            operation,
            lambda status: self.context.emit(key + ".ack", status, operation),
        )
        operation.transport[key] = True

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.client is not None:
            self.client.close()


def create_command(context: FactoryContext) -> CommandComponent:
    return CommandComponent(context)
