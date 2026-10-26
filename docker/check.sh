#!/usr/bin/env bash
set -euo pipefail
cd /workspace/project

# Validate canonical container environment and workspace layout
python - <<'PY'
import os
import platform
from pathlib import Path

import rclpy

assert platform.freedesktop_os_release()["VERSION_ID"] == "24.04"
assert os.environ["ROS_DISTRO"] == "jazzy"
assert Path(rclpy.__file__).is_relative_to("/opt/ros/jazzy")
assert os.path.ismount("/workspace/project"), "The full workspace must be bind-mounted"
for directory in ("agent-framework", "bindings", "docker"):
    assert Path(directory).is_dir(), directory
PY

# Install all present bindings in editable mode
for binding in bindings/*/; do
    if [ -f "${binding}pyproject.toml" ]; then
        python -m pip install --no-build-isolation --no-deps -e "$binding"
    fi
done

# Run unit tests across framework and all bindings
python -m pytest -c agent-framework/pyproject.toml agent-framework/tests bindings/*/tests
python -m ruff check --config agent-framework/pyproject.toml .
python -m ruff format --check --config agent-framework/pyproject.toml .
python -m mypy --config-file agent-framework/pyproject.toml agent-framework/src/agent_framework agent-framework/tests bindings/*/src bindings/*/tests

