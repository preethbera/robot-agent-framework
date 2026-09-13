"""Opt-in real PX4 SITL acceptance in the pinned optional image."""

import ast
import os
import signal
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from agent_framework.definition.loader import load_agent_definition
from agent_framework.generation.python import generate_python
from agent_framework.resolution.artifacts import write_artifacts
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.ros2 import write_realization

WORKSPACE = Path(__file__).resolve().parents[2]
FIRMWARE = Path("/opt/px4/firmware")


def test_m5_application_import_boundary() -> None:
    tree = ast.parse((WORKSPACE / "tests/e2e/m5_application.py").read_text())
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert imports == {
        "agent_px4_agent",
        "time",
        "sys",
        "collections.abc",
        "contextlib",
        "threading",
    }


@pytest.mark.skipif(os.environ.get("M5_SITL") != "1", reason="Requires pinned M5 SITL image")
@pytest.mark.parametrize("owner", ["binding", "application"])
def test_px4_sitl_generated_application(tmp_path: Path, owner: str) -> None:
    binary = FIRMWARE / "build/px4_sitl_default/bin/px4"
    assert binary.is_file(), "M5 SITL flag requires the actual pinned firmware binary"
    definition = load_agent_definition(WORKSPACE / "agents/px4_agent/agent.yaml")
    definition = replace(
        definition,
        expose=tuple(
            replace(exposure, config={"liveness_owner": owner})
            if exposure.alias == "offboard"
            else exposure
            for exposure in definition.expose
        ),
    )
    resolved = resolve_agent(definition)
    artifact, _ = write_artifacts(resolved, tmp_path)
    write_realization(resolved, tmp_path)
    package = generate_python(artifact.parent)
    environment = dict(os.environ)
    environment.update(
        PX4_SYS_AUTOSTART="10040",
        PX4_SIM_MODEL="sihsim_quadx",
        PX4_UXRCE_DDS_NS="m5",
        PX4_HOME_LAT="47.397742",
        PX4_HOME_LON="8.545594",
        PX4_HOME_ALT="488.0",
        PX4_PARAM_COM_RC_IN_MODE="4",
        PX4_PARAM_NAV_DLL_ACT="0",
        PX4_PARAM_COM_DISARM_PRFLT="0",
    )
    environment["PYTHONPATH"] = str(package.parent) + os.pathsep + environment.get("PYTHONPATH", "")
    processes: list[subprocess.Popen[bytes]] = []
    with (
        (tmp_path / "bridge.log").open("wb") as bridge_log,
        (tmp_path / "firmware.log").open("wb") as firmware_log,
    ):
        try:
            processes.append(
                subprocess.Popen(
                    ["MicroXRCEAgent", "udp4", "-p", "8888"],
                    env=environment,
                    stdout=bridge_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
            processes.append(
                subprocess.Popen(
                    [str(binary), "-d", str(FIRMWARE / "build/px4_sitl_default/etc")],
                    cwd=tmp_path,
                    env=environment,
                    stdout=firmware_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
            result = subprocess.run(
                [sys.executable, str(WORKSPACE / "tests/e2e/m5_application.py"), owner],
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
                + "\n"
                + (tmp_path / "firmware.log").read_text(errors="replace")[-16000:]
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
