"""PX4 Environment Provider for simulation (SITL + Gazebo) and hardware (serial bridge)."""

import glob
import os
import shutil
import socket
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from agent_framework.binding.environment import (
    CheckResult,
    CheckStatus,
    EnvironmentProvider,
    EnvironmentSession,
)
from agent_framework.runtime.supervisor import ProcessSupervisor


class PX4EnvironmentProvider:
    """Manages PX4 runtime targets: headless simulation and physical serial hardware."""

    @property
    def supported_targets(self) -> tuple[str, ...]:
        return ("simulation", "hardware")

    def check(self, target: str, config: Mapping[str, Any]) -> CheckResult:
        if target == "simulation":
            missing = []
            if not shutil.which("MicroXRCEAgent") and not os.path.exists("/usr/local/bin/MicroXRCEAgent"):
                missing.append("MicroXRCEAgent (eProsima Micro-XRCE-DDS-Agent)")
            if not shutil.which("gz"):
                missing.append("gz (Gazebo Harmonic)")
            px4_dir = os.environ.get("PX4_DIR", os.path.expanduser("~/PX4-Autopilot"))
            px4_bin = os.path.join(px4_dir, "build/px4_sitl_default/bin/px4")
            if not os.path.exists(px4_bin) and not shutil.which("px4"):
                missing.append(f"px4 binary (expected at {px4_bin} or in PATH)")

            if missing:
                return CheckResult(
                    status=CheckStatus.MISSING_DEPENDENCY,
                    message="Missing simulation dependencies: " + ", ".join(missing),
                    remediation_hint=(
                        "Install gz-harmonic, compile MicroXRCEAgent, and build PX4 SITL "
                        "(or run 'agent env setup <deployment.yaml> --auto')."
                    ),
                )
            return CheckResult(status=CheckStatus.READY, message="Simulation environment ready")

        if target == "hardware":
            port = config.get("port", "/dev/ttyACM0")
            if not os.path.exists(port):
                return CheckResult(
                    status=CheckStatus.MISSING_DEPENDENCY,
                    message=f"Hardware serial device '{port}' not found.",
                    remediation_hint=f"Connect flight controller USB/Telem and check permissions for {port}.",
                )
            if not os.access(port, os.R_OK | os.W_OK):
                return CheckResult(
                    status=CheckStatus.CONFIG_ERROR,
                    message=f"Cannot read/write to serial device '{port}'.",
                    remediation_hint=f"Run: sudo usermod -a -G dialout $USER and log in again.",
                )
            return CheckResult(status=CheckStatus.READY, message=f"Hardware ready on {port}")

        return CheckResult(
            status=CheckStatus.CONFIG_ERROR,
            message=f"Unsupported target '{target}'. Supported: {self.supported_targets}",
        )

    def setup(self, target: str, config: Mapping[str, Any], *, auto_install: bool = False) -> None:
        result = self.check(target, config)
        if result.is_ready:
            print(f"PX4 ({target}): {result.message}")
            return
        print(f"PX4 ({target}) Setup Required: {result.message}")
        if result.remediation_hint:
            print(f"Action: {result.remediation_hint}")

    @contextmanager
    def session(
        self,
        target: str,
        config: Mapping[str, Any],
        run_dir: Path,
    ) -> Iterator[EnvironmentSession]:
        run_dir.mkdir(parents=True, exist_ok=True)
        supervisor = ProcessSupervisor()

        if target == "simulation":
            # 1. Verify port 8888 is free
            port = int(config.get("udp_port", 8888))
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                try:
                    sock.bind(("0.0.0.0", port))
                except OSError as error:
                    raise RuntimeError(f"UDP port {port} is already in use: {error}") from error

            # 2. Spawn MicroXRCEAgent
            xrce_bin = shutil.which("MicroXRCEAgent") or "/usr/local/bin/MicroXRCEAgent"
            supervisor.spawn(
                "xrce_agent",
                [xrce_bin, "udp4", "-p", str(port)],
                log_file=run_dir / "xrce_agent.log",
            )
            time.sleep(0.3)

            # 3. Resolve PX4 binaries & paths
            px4_dir = Path(os.environ.get("PX4_DIR", os.path.expanduser("~/PX4-Autopilot"))).resolve()
            px4_bin = px4_dir / "build/px4_sitl_default/bin/px4"
            if not px4_bin.exists():
                found_bin = shutil.which("px4")
                if found_bin:
                    px4_bin = Path(found_bin)
                else:
                    raise FileNotFoundError(f"PX4 SITL binary not found at {px4_bin}")

            world = str(config.get("world", "default"))
            headless = "1" if config.get("headless", True) else "0"
            autostart = str(config.get("autostart", 4001))

            env = dict(os.environ)
            env["HEADLESS"] = headless
            env["PX4_SYS_AUTOSTART"] = autostart
            env["PX4_SIM_MODEL"] = "gz_x500"
            env["PX4_GZ_WORLD"] = world
            env["GZ_SIM_RESOURCE_PATH"] = f"{px4_dir}/Tools/simulation/gz/models:{px4_dir}/Tools/simulation/gz/worlds"

            # 4. Spawn PX4 SITL daemon
            supervisor.spawn(
                "px4_sitl",
                [str(px4_bin), "-i", "0", "-d", "-s", f"{px4_dir}/build/px4_sitl_default/etc/init.d-posix/rcS"],
                cwd=px4_dir / "build/px4_sitl_default",
                env=env,
                log_file=run_dir / "px4_sitl.log",
            )
            time.sleep(1.0)

            session_meta = {"target": "simulation", "udp_port": port, "world": world}
            session = EnvironmentSession(target="simulation", metadata=session_meta, run_dir=run_dir)
            try:
                yield session
            finally:
                supervisor.stop_all(timeout=3.0)
                # Copy latest .ulg file to run_dir if present
                log_pattern = str(px4_dir / "build/px4_sitl_default/rootfs/log/*/*.ulg")
                ulogs = glob.glob(log_pattern)
                if ulogs:
                    latest = max(ulogs, key=os.path.getmtime)
                    shutil.copy2(latest, run_dir / "flight.ulg")

        elif target == "hardware":
            port = str(config.get("port", "/dev/ttyACM0"))
            baud = str(config.get("baudrate", 921600))
            xrce_bin = shutil.which("MicroXRCEAgent") or "/usr/local/bin/MicroXRCEAgent"
            supervisor.spawn(
                "xrce_agent",
                [xrce_bin, "serial", "--dev", port, "-b", baud],
                log_file=run_dir / "xrce_agent.log",
            )
            time.sleep(0.5)

            session = EnvironmentSession(
                target="hardware", metadata={"port": port, "baudrate": baud}, run_dir=run_dir
            )
            try:
                yield session
            finally:
                supervisor.stop_all(timeout=2.0)
        else:
            raise ValueError(f"Unknown target: {target}")


__all__ = ["PX4EnvironmentProvider"]
