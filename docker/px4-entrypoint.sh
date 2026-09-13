#!/usr/bin/env bash
set -e
source /opt/ros/jazzy/setup.bash
source /opt/px4/ros/local_setup.bash
exec "$@"
