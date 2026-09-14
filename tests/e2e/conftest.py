"""Shared real SITL process lifecycle for M5 and combined M7 acceptance."""

import os
import signal
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

FIRMWARE = Path("/opt/px4/firmware")
WORKSPACE = Path(__file__).resolve().parents[2]


def run_sitl(
    directory: Path,
    environment: dict[str, str],
    command: Sequence[str],
    *,
    instance: int = 0,
    extra_commands: Sequence[Sequence[str]] = (),
) -> None:
    binary = FIRMWARE / "build/px4_sitl_default/bin/px4"
    assert binary.is_file(), "SITL acceptance requires the pinned firmware binary"
    commands = [
        ["MicroXRCEAgent", "udp4", "-p", "8888"],
        [str(binary), "-i", str(instance), "-d", str(FIRMWARE / "build/px4_sitl_default/etc")],
        *extra_commands,
    ]
    processes: list[subprocess.Popen[bytes]] = []
    with (directory / "sitl.log").open("wb") as log:
        try:
            for child in commands:
                processes.append(
                    subprocess.Popen(
                        child,
                        cwd=directory,
                        env=environment,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                )
            result = subprocess.run(
                command,
                cwd=WORKSPACE,
                env=environment,
                capture_output=True,
                text=True,
                timeout=150,
                check=False,
            )
            assert result.returncode == 0, (
                result.stdout
                + result.stderr
                + (directory / "sitl.log").read_text(errors="replace")[-16000:]
            )
            assert all(process.poll() is None for process in processes)
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)


@pytest.fixture
def sitl_runner() -> Callable[..., None]:
    return run_sitl
