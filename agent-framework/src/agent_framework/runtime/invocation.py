"""Scoped invocation handles with bounded result/feedback Channels."""

from typing import Self

from .agent import Operation


class Invocation:
    def __init__(self, operation: Operation) -> None:
        self._operation = operation

    def close(self) -> None:
        self._operation.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
