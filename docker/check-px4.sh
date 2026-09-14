#!/usr/bin/env bash
set -euo pipefail
cd /workspace/project
source /opt/px4-versions.env
[[ "$(git -c safe.directory=/opt/px4/firmware -C /opt/px4/firmware rev-parse HEAD)" == "$PX4_COMMIT" ]]
python -c 'from px4_msgs.srv import VehicleCommand; from px4_msgs.msg import VehicleStatus; assert VehicleStatus.MESSAGE_VERSION == 1'
python -c 'from importlib.metadata import version; assert version("agent-binding-lidar") == "0.1.0"'
M5_SITL=1 python -m pytest -c agent-framework/pyproject.toml agent-framework/tests bindings/test/tests bindings/px4/tests bindings/lidar/tests tests
python -m ruff check --config agent-framework/pyproject.toml .
python -m ruff format --check --config agent-framework/pyproject.toml .
python -m mypy --config-file agent-framework/pyproject.toml agent-framework/src agent-framework/tests bindings/test/src bindings/test/tests bindings/px4/src bindings/px4/tests bindings/lidar/src bindings/lidar/tests tests
