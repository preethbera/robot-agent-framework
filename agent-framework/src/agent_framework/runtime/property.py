"""Typed Property access backed by one cached value or a generated constant."""

from collections.abc import Callable

from .errors import AgentError, FailureCode


class PropertyValue[T]:
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
