"""Typed Property access backed by one cached value or a generated constant."""

from collections.abc import Callable


class PropertyValue[T]:
    def __init__(self, read: Callable[[float], T]) -> None:
        self._read = read

    def get(self, timeout: float = 5.0) -> T:
        return self._read(timeout)
