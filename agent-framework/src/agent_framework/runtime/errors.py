"""Transport-independent failures exposed by generated Agent APIs."""

from enum import StrEnum


class FailureCode(StrEnum):
    TIMEOUT = "timeout"
    CLOSED = "closed"
    OVERFLOW = "overflow"
    BUSY = "busy"
    NOT_READY = "not_ready"
    INVALID_VALUE = "invalid_value"
    STARTUP = "startup"
    TRANSPORT = "transport"
    CANCELLED = "cancelled"


class AgentError(RuntimeError):
    def __init__(self, code: FailureCode, message: str, *, target: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.target = target
