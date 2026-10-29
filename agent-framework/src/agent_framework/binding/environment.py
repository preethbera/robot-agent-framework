"""Binding Environment Protocol (BEP) for hardware, simulation, and custom runtime targets."""

from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class CheckStatus(StrEnum):
    READY = "ready"
    MISSING_DEPENDENCY = "missing_dependency"
    CONFIG_ERROR = "config_error"


@dataclass(frozen=True, slots=True)
class CheckResult:
    status: CheckStatus
    message: str
    remediation_hint: str | None = None

    @property
    def is_ready(self) -> bool:
        return self.status == CheckStatus.READY


@dataclass(frozen=True, slots=True)
class EnvironmentSession:
    """Active runtime context passed to the agent runner."""

    target: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    run_dir: Path | None = None


@runtime_checkable
class EnvironmentProvider(Protocol):
    """Protocol implemented by bindings to manage their target environments."""

    @property
    def supported_targets(self) -> tuple[str, ...]:
        """Supported targets, e.g. ('simulation', 'hardware', 'mock')."""
        ...

    def check(self, target: str, config: Mapping[str, Any]) -> CheckResult:
        """Pre-flight check: verify required binaries, device nodes, or permissions."""
        ...

    def setup(self, target: str, config: Mapping[str, Any], *, auto_install: bool = False) -> None:
        """Automated setup or installation guidance for missing dependencies."""
        ...

    def session(
        self,
        target: str,
        config: Mapping[str, Any],
        run_dir: Path,
    ) -> AbstractContextManager[EnvironmentSession]:
        """Context manager that starts background daemons/bridges and stops them on exit."""
        ...
