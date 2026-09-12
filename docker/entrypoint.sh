#!/usr/bin/env bash
set -e

# ROS setup scripts may reference unset variables, so enable nounset afterward.
source /opt/ros/jazzy/setup.bash
set -u -o pipefail

exec "$@"

