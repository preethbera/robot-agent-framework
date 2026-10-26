#!/usr/bin/env bash
set -e
export PYTHONDONTWRITEBYTECODE=1
source /opt/ros/jazzy/setup.bash
source /opt/px4/ros/local_setup.bash
exec "$@"
