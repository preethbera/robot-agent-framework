#!/usr/bin/env bash
set -euo pipefail
cd /workspace/project

source /opt/px4-versions.env
[[ "$(git -c safe.directory=/opt/px4/firmware -C /opt/px4/firmware rev-parse HEAD)" == "$PX4_COMMIT" ]]
python -c 'from px4_msgs.srv import VehicleCommand; from px4_msgs.msg import VehicleStatus; assert VehicleStatus.MESSAGE_VERSION == 1'

# Install all present bindings in editable mode
for binding in bindings/*/; do
    if [ -f "${binding}pyproject.toml" ]; then
        python -m pip install --no-build-isolation --no-deps -e "$binding"
    fi
done

# Run SITL-enabled tests across framework and all bindings
PX4_SITL=1 python -m pytest -c agent-framework/pyproject.toml agent-framework/tests bindings/*/tests
python -m ruff check --config agent-framework/pyproject.toml .
python -m ruff format --check --config agent-framework/pyproject.toml .
python -m mypy --config-file agent-framework/pyproject.toml agent-framework/src/agent_framework agent-framework/tests bindings/*/src bindings/*/tests

