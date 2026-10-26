#!/usr/bin/env bash
set -e

export PYTHONDONTWRITEBYTECODE=1

# ROS setup scripts may reference unset variables, so enable nounset afterward.
source /opt/ros/jazzy/setup.bash
if [ -f /opt/px4/ros/local_setup.bash ]; then
    source /opt/px4/ros/local_setup.bash
fi
set -u -o pipefail

exec "$@"

