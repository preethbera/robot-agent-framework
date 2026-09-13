"""Runtime-local Agent Instance identity reservation, without global singletons."""

from threading import RLock

from .errors import AgentError, FailureCode


class Registry[T]:
    def __init__(self) -> None:
        self._items: dict[str, T] = {}
        self._lock = RLock()

    def add(self, identifier: str, value: T) -> None:
        with self._lock:
            if identifier in self._items:
                raise AgentError(
                    FailureCode.BUSY, "Agent instance ID is already registered", target=identifier
                )
            self._items[identifier] = value

    def remove(self, identifier: str) -> None:
        with self._lock:
            self._items.pop(identifier, None)

    def values(self) -> tuple[T, ...]:
        with self._lock:
            return tuple(self._items.values())
