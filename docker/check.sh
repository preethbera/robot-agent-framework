#!/usr/bin/env bash
set -euo pipefail
cd /workspace/project

# These assertions deliberately fail outside the canonical container environment.
python - <<'PY'
import os
import platform
from pathlib import Path

import rclpy

assert platform.freedesktop_os_release()["VERSION_ID"] == "24.04"
assert os.environ["ROS_DISTRO"] == "jazzy"
assert Path(rclpy.__file__).is_relative_to("/opt/ros/jazzy")
assert os.path.ismount("/workspace/project"), "The full workspace must be bind-mounted"
for directory in ("agent-framework", "bindings", "agents", "deployments", "build", "tests", "docker", "docs"):
    assert Path(directory).is_dir(), directory
assert Path("docs/milestones/M0_Bootstrap.md").is_file()
PY

python -m pip install --no-build-isolation --no-deps -e bindings/px4 -e bindings/lidar
python -m pytest -c agent-framework/pyproject.toml agent-framework/tests bindings/test/tests bindings/px4/tests bindings/lidar/tests tests
python -m ruff check --config agent-framework/pyproject.toml .
python -m ruff format --check --config agent-framework/pyproject.toml .
python -m mypy --config-file agent-framework/pyproject.toml agent-framework/src/agent_framework agent-framework/tests bindings/test/src bindings/test/tests bindings/px4/src bindings/px4/tests bindings/lidar/src bindings/lidar/tests tests
