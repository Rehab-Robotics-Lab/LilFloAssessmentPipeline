#!/bin/bash
set -e

# setup ros environment
# shellcheck disable=SC1090
source "/opt/ros/$ROS_DISTRO/setup.bash"
# shellcheck disable=SC1091
source "/catkin_ws/devel/setup.bash"
exec "$@"
