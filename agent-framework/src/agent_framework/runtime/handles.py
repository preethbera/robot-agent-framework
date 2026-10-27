"""Consolidated runtime handles for capabilities, sessions, invocations, and properties."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Self

from .errors import AgentError, FailureCode

if TYPE_CHECKING:
    from .agent import AgentRuntime, Operation


class Capability:
    """Base for statically generated typed Capability handles."""

    def __init__(self, agent: Any) -> None:
        self._agent = agent


class Invocation:
    """Scoped invocation handle with bounded result/feedback channels."""

    def __init__(self, operation: Any) -> None:
        self._operation = operation

    def close(self) -> None:
        self._operation.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class Session(Invocation):
    """Bounded stream session, explicitly closed or used as a context manager."""


class PropertyValue[T]:
    """Typed property access backed by cached value or generated constant."""

    def __init__(
        self, read: Callable[[float], T], write: Callable[[T], None] | None = None
    ) -> None:
        self._read = read
        self._write = write

    def get(self, timeout: float = 5.0) -> T:
        return self._read(timeout)

    def set(self, value: T) -> None:
        if self._write is None:
            raise AgentError(FailureCode.INVALID_VALUE, "Property is read-only")
        self._write(value)
