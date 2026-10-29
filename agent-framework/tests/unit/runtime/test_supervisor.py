import sys
import time
from pathlib import Path

from agent_framework.runtime.supervisor import ProcessSupervisor


def test_supervisor_spawns_and_cleans_up(tmp_path: Path) -> None:
    log_file = tmp_path / "test.log"
    supervisor = ProcessSupervisor()

    # Spawn a sleeping python process
    cmd = [sys.executable, "-c", "import time, sys; sys.stdout.write('started\\n'); sys.stdout.flush(); time.sleep(10)"]
    proc = supervisor.spawn("sleeper", cmd, log_file=log_file)

    time.sleep(0.3)
    assert supervisor.is_running("sleeper")
    assert log_file.exists()
    assert b"started" in log_file.read_bytes()

    supervisor.stop_all(timeout=1.0)
    assert not supervisor.is_running("sleeper")
    assert proc.poll() is not None


def test_supervisor_context_manager(tmp_path: Path) -> None:
    log_file = tmp_path / "ctx.log"
    with ProcessSupervisor() as supervisor:
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
        supervisor.spawn("sleeper", cmd, log_file=log_file)
        assert supervisor.is_running("sleeper")

    # Upon exiting context manager, process should be terminated
    time.sleep(0.1)
    assert len(supervisor._processes) == 0
