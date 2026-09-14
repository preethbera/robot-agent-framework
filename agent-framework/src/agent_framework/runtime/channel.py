"""Bounded Channel storage and typed handles; no payload schema interpretation."""

import math
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Condition
from time import monotonic

from .errors import AgentError, FailureCode


def deadline(timeout: float) -> float:
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout < 0:
        raise AgentError(FailureCode.INVALID_VALUE, "timeout must be finite and non-negative")
    return monotonic() + timeout


@dataclass(frozen=True, slots=True)
class ChannelStatistics:
    """Delivery queue measurements; latency is last-read queue residence in seconds."""

    queue_depth: int
    dropped_samples: int
    latency: float | None


class Buffer[T]:
    def __init__(self, capacity: int = 16, *, latest: bool = False, target: str = "") -> None:
        if type(capacity) is not int or capacity < 1:
            raise AgentError(FailureCode.INVALID_VALUE, "capacity must be a positive integer")
        self._capacity = 1 if latest else capacity
        self._latest = latest
        self._target = target
        self._values: deque[tuple[T, float]] = deque()
        self._dropped = 0
        self._latency: float | None = None
        self._condition = Condition()
        self._failure: AgentError | None = None

    def put(self, value: T) -> None:
        with self._condition:
            if self._failure is not None:
                self._dropped += 1
                return
            if self._latest:
                self._dropped += len(self._values)
                self._values.clear()
            elif len(self._values) == self._capacity:
                self._dropped += len(self._values) + 1
                self.fail(
                    AgentError(FailureCode.OVERFLOW, "Channel queue overflow", target=self._target)
                )
                return
            self._values.append((value, monotonic()))
            self._condition.notify_all()

    def read(self, timeout: float = 5.0) -> T:
        end = deadline(timeout)
        with self._condition:
            while not self._values and self._failure is None:
                remaining = end - monotonic()
                if remaining <= 0:
                    raise AgentError(
                        FailureCode.TIMEOUT, "Channel read timed out", target=self._target
                    )
                self._condition.wait(remaining)
            if self._failure is not None:
                raise self._failure
            value, arrived = self._values[-1] if self._latest else self._values.popleft()
            self._latency = monotonic() - arrived
            return value

    def statistics(self) -> ChannelStatistics:
        with self._condition:
            return ChannelStatistics(len(self._values), self._dropped, self._latency)

    def fail(self, error: AgentError) -> None:
        with self._condition:
            if self._failure is None:
                self._failure = error
                self._values.clear()
                self._condition.notify_all()

    def close(self) -> None:
        self.fail(AgentError(FailureCode.CLOSED, "Channel is closed", target=self._target))


class InputChannel[T]:
    def __init__(self, send: Callable[[T], None]) -> None:
        self._send = send

    def send(self, value: T) -> None:
        self._send(value)


class OutputChannel[T]:
    def __init__(
        self, read: Callable[[float], T], statistics: Callable[[], ChannelStatistics] | None = None
    ) -> None:
        self._read = read
        self._statistics = statistics

    @property
    def statistics(self) -> ChannelStatistics:
        if self._statistics is None:
            raise AgentError(FailureCode.NOT_READY, "Channel statistics unavailable")
        return self._statistics()

    def read(self, timeout: float = 5.0) -> T:
        return self._read(timeout)
