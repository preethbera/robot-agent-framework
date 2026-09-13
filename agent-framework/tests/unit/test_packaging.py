"""Verify the installation boundary and the distributable M0 skeleton."""

import os
import shutil
import subprocess
import sys
import tomllib
import venv
from importlib.metadata import distribution
from pathlib import Path
from zipfile import ZipFile

import pytest
from packaging.requirements import Requirement

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def run_python(python: Path, arguments: list[str], cwd: Path) -> str:
    """Run a Python process without inheriting source or ROS path injection."""
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    result = subprocess.run(
        [str(python), *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.fixture(scope="session")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a normal wheel outside the source tree without downloading anything."""
    staging = tmp_path_factory.mktemp("wheel-build")
    source = staging / "agent-framework"
    shutil.copytree(
        PACKAGE_ROOT,
        source,
        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", "build", ".*cache"),
    )
    run_python(
        Path(sys.executable),
        [
            "-m",
            "pip",
            "wheel",
            "--no-build-isolation",
            "--no-deps",
            "--no-index",
            "--wheel-dir",
            str(staging / "dist"),
            str(source),
        ],
        staging,
    )
    wheels = list((staging / "dist").glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_installed_metadata() -> None:
    with (PACKAGE_ROOT / "pyproject.toml").open("rb") as stream:
        metadata = tomllib.load(stream)["project"]
    installed = distribution("agent-framework")
    assert installed.version == metadata["version"] == "0.1.0"
    assert not [
        requirement
        for item in installed.requires or ()
        if (requirement := Requirement(item)).marker is None
        or requirement.marker.evaluate({"extra": ""})
    ]


def test_checkout_requires_installation(tmp_path: Path) -> None:
    environment = tmp_path / "uninstalled"
    venv.EnvBuilder(with_pip=False).create(environment)
    for directory in (PACKAGE_ROOT, PACKAGE_ROOT.parent):
        run_python(
            environment / "bin/python",
            [
                "-c",
                "import importlib.util; assert importlib.util.find_spec('agent_framework') is None",
            ],
            directory,
        )


def test_wheel_contains_complete_typed_package(wheel: Path) -> None:
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
    source = PACKAGE_ROOT / "src"
    expected = {path.relative_to(source).as_posix() for path in source.rglob("*.py")}
    assert expected
    assert {name for name in names if name.endswith(".py")} == expected
    assert "agent_framework/py.typed" in names
    assert not any(name.startswith(("tests/", "bindings/")) for name in names)


def test_wheel_installs_and_imports_without_runtime_dependencies(
    wheel: Path, tmp_path: Path
) -> None:
    environment = tmp_path / "installed"
    venv.EnvBuilder(with_pip=False).create(environment)
    python = environment / "bin/python"
    run_python(
        Path(sys.executable),
        ["-m", "pip", "--python", str(python), "install", "--no-index", "--no-deps", str(wheel)],
        tmp_path,
    )
    run_python(
        python,
        [
            "-c",
            """
import importlib
import importlib.metadata
import pkgutil
import sys
from pathlib import Path

import agent_framework

assert Path(agent_framework.__file__).is_relative_to(sys.prefix)
assert importlib.metadata.version("agent-framework") == "0.1.0"
for module in pkgutil.walk_packages(agent_framework.__path__, "agent_framework."):
    importlib.import_module(module.name)
assert not {"rclpy", "pydantic", "ruamel", "px4_msgs"}.intersection(sys.modules)
""",
        ],
        tmp_path,
    )
