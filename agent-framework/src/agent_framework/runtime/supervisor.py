"""Subprocess supervision with POSIX process group isolation and graceful cleanup."""

import os
import signal
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO


@dataclass
class SupervisedProcess:
    name: str
    process: subprocess.Popen[bytes]
    log_file: Path | None = None
    _file_handle: IO[bytes] | None = None


class ProcessSupervisor:
    """Manages child daemon processes in isolated process groups with deterministic teardown."""

    def __init__(self) -> None:
        self._processes: list[SupervisedProcess] = []

    def spawn(
        self,
        name: str,
        cmd: list[str],
        *,
        cwd: Path | str | None = None,
        env: Mapping[str, str] | None = None,
        log_file: Path | None = None,
    ) -> subprocess.Popen[bytes]:
        """Spawn a child process in a new process group."""
        stdout_handle: IO[bytes] | None = None
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            stdout_handle = open(log_file, "wb")

        preexec = os.setsid if hasattr(os, "setsid") else None

        process = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            stdout=stdout_handle or subprocess.DEVNULL,
            stderr=subprocess.STDOUT if stdout_handle else subprocess.DEVNULL,
            preexec_fn=preexec,
        )

        supervised = SupervisedProcess(
            name=name,
            process=process,
            log_file=log_file,
            _file_handle=stdout_handle,
        )
        self._processes.append(supervised)
        return process

    def is_running(self, name: str) -> bool:
        for p in self._processes:
            if p.name == name:
                return p.process.poll() is None
        return False

    def stop_all(self, *, timeout: float = 3.0) -> None:
        """Terminate all managed process groups gracefully via SIGTERM, then SIGKILL."""
        # 1. Send SIGTERM to all process groups
        for p in reversed(self._processes):
            proc = p.process
            if proc.poll() is None:
                try:
                    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    else:
                        proc.terminate()
                except (ProcessLookupError, PermissionError):
                    pass

        # 2. Await termination up to timeout
        deadline = time.monotonic() + timeout
        for p in reversed(self._processes):
            proc = p.process
            remaining = max(0.0, deadline - time.monotonic())
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                # 3. Force kill process group
                try:
                    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    else:
                        proc.kill()
                    proc.wait(timeout=1.0)
                except (ProcessLookupError, PermissionError):
                    pass

        # 4. Close log file handles
        for p in self._processes:
            if p._file_handle is not None and not p._file_handle.closed:
                p._file_handle.close()

        self._processes.clear()

    def __enter__(self) -> "ProcessSupervisor":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.stop_all()
