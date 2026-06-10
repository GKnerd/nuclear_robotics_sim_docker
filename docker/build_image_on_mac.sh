#!/bin/bash

# macOS (Apple Silicon) build. Builds linux/amd64 under emulation (Open3D has
# no linux/arm64 wheel, so a native build fails with "open3d not found").
# Uses docker/Dockerfile.macos, which adds an in-container virtual desktop
# (Xvfb + VNC + noVNC) so rviz2 and the MuJoCo viewer work without XQuartz.

uid=$(eval "id -u")
gid=$(eval "id -g")

# ANSI escape codes
RED_BOLD="\033[1;31m"
YELLOW_BOLD="\033[1;33m"
GREEN_BOLD="\033[1;32m"
RESET="\033[0m"

PACKAGE_NAME="nuclear_robotics_sim_docker"
ROS_DISTRO="jazzy"
USER="nuclear_robot_sim"

# Set Package root
if [[ "$(pwd)" == *"/$PACKAGE_NAME/"* ]]; then
    # Case A: Inside a subdirectory
    echo -e "${YELLOW_BOLD}Inside subdirectory. Navigating to root...${RESET}"
    # Strip everything after the package name to find the root
    _cwd="$(pwd)"
    PACKAGE_ROOT="${_cwd%%/$PACKAGE_NAME/*}/$PACKAGE_NAME"
    cd "$PACKAGE_ROOT" || exit 1
elif [[ "$(pwd)" == *"/$PACKAGE_NAME" ]]; then
    # Case B: Already at the root
    echo -e "${GREEN_BOLD}Already at package root.${RESET}"
    PACKAGE_ROOT="$(pwd)"
else
    # Case C: Not in the package at all
    echo -e "${RED_BOLD}Error: You are not inside the directory '$PACKAGE_NAME'.${RESET}"
    echo "Current path: $(pwd)"
    exit 1
fi

for FOLDER in ros2_ws/src env log data; do
    HOST_PATH="$PACKAGE_ROOT/$FOLDER"
    if [ ! -d "$HOST_PATH" ]; then
        echo -e "${YELLOW_BOLD}Warning: $HOST_PATH does not exist. Creating it...${RESET}"
        mkdir -p "$HOST_PATH"
    fi
done


docker build --build-arg UID="$uid" --build-arg GID="$gid" \
    --build-arg ROS_DISTRO="$ROS_DISTRO" \
    --build-arg USER="$USER" \
    --platform=linux/amd64 \
    --network=host \
    -t $PACKAGE_NAME/ros:$ROS_DISTRO-mac . \
    -f $PACKAGE_ROOT/docker/Dockerfile.macos \
    && docker create --platform=linux/amd64 --name temp-container-mac $PACKAGE_NAME/ros:$ROS_DISTRO-mac \
    && docker cp temp-container-mac:/home/$USER/ros2_ws/. $PACKAGE_ROOT/ros2_ws/. \
    && docker rm temp-container-mac
