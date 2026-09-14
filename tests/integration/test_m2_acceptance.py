"""M2 portability and deterministic builds through public installed interfaces."""

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def run(arguments: list[str], directory: Path, *, hash_seed: str = "0") -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONHASHSEED"] = hash_seed
    result = subprocess.run(
        arguments,
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_normal_wheels_discover_outside_workspace_without_yaml_or_ros(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    wheels = tmp_path / "wheels"
    for relative, name in [
        ("agent-framework", "framework"),
        ("bindings/test", "binding"),
    ]:
        source = sources / name
        shutil.copytree(
            WORKSPACE / relative,
            source,
            ignore=shutil.ignore_patterns("*.egg-info", "__pycache__", ".*cache", "build"),
        )
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-index",
                "--no-build-isolation",
                "--no-deps",
                "--wheel-dir",
                str(wheels),
                str(source),
            ],
            tmp_path,
        )
    environment = tmp_path / "environment"
    venv.EnvBuilder(with_pip=False).create(environment)
    python = environment / "bin/python"
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "--python",
            str(python),
            "install",
            "--no-index",
            "--no-deps",
            *(str(path) for path in sorted(wheels.glob("*.whl"))),
        ],
        tmp_path,
    )
    run(
        [
            str(python),
            "-c",
            """
import sys
from pathlib import Path
import agent_binding_test
from agent_framework.binding.discovery import discover_bindings
from agent_framework.definition.model import AgentDefinition, Exposure
from agent_framework.resolution.resolver import resolve_agent

assert Path(agent_binding_test.__file__).is_relative_to(sys.prefix)
registry = discover_bindings(['test.temperature', 'test.command', 'test.stream'])
assert registry.packages['test'].version == '0.1.0'
resolution = resolve_agent(AgentDefinition(schema_version='0.1.0', id='wheel_agent', description='',
    expose=(Exposure(use='test.temperature', alias='temperature'),)))
assert resolution.agent.properties[0].id == 'temperature'
assert not {'rclpy', 'px4_msgs', 'ruamel.yaml', 'pydantic'}.intersection(sys.modules)
""",
        ],
        tmp_path,
    )


def test_fresh_processes_produce_identical_artifacts(tmp_path: Path) -> None:
    source = WORKSPACE / "agents/test_agent/agent.yaml"
    program = """
import sys
from pathlib import Path
from agent_framework.definition.loader import load_agent_definition
from agent_framework.resolution.resolver import resolve_agent
from agent_framework.resolution.artifacts import write_artifacts
write_artifacts(resolve_agent(load_agent_definition(Path(sys.argv[1]))), Path(sys.argv[2]))
"""
    outputs = (tmp_path / "first", tmp_path / "second")
    for output, seed in zip(outputs, ("1", "987654"), strict=True):
        run(
            [sys.executable, "-c", program, str(source), str(output)],
            tmp_path,
            hash_seed=seed,
        )
    for name in ("resolved_agent_model.json", "binding_lock.json"):
        relative = Path("build/agents/test_agent") / name
        assert (outputs[0] / relative).read_bytes() == (outputs[1] / relative).read_bytes()
