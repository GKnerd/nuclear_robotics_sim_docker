#    Copyright 2026 Proximity Robotics & Automation GmbH

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

##############################################################################
##                                 Base Image                               ##
##############################################################################
ARG ROS_DISTRO=jazzy
FROM ros:${ROS_DISTRO}-ros-base

ENV PROJECT_WS=ros2_ws
ENV TZ=Europe/Berlin
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 
ENV LC_ALL=C.UTF-8
    
##############################################################################
##                                 Global Dependecies                       ##
##############################################################################
RUN apt-get update && apt-get install -y --no-install-recommends    \
        build-essential                                             \
        cmake                                                       \
        wget                                                        \
        htop                                                        \
        sudo                                                        \
        apt-utils                                                   \
        tmux                                                        \
        gedit                                                       \
        python3-pip                                                 \
        bash                                                        \
        nano                                                        \
        aptitude                                                    \
        lsb-release                                                 \
        gdb                                                         \
        git                                                         \
        libpcl-dev                                                  \
    && apt-get clean && sudo rm -rf /var/lib/apt/lists/*

##############################################################################
##                                 Create User                              ##
##############################################################################

ARG USER=robot
ARG PASSWORD=robot
ARG UID=1000
ARG GID=1000
ARG ROS_DOMAIN_ID=0
ARG VIDEO_GID=44
ENV ROS_DOMAIN_ID=${ROS_DOMAIN_ID}
ENV UID=${UID}
ENV GID=${GID}
ENV USER=${USER}
RUN existing_user="$(getent passwd | awk -F: -v target_uid=${UID} '$3 == target_uid { print $1 }')" && \
    if [ -n "$existing_user" ]; then \
        userdel --remove "$existing_user"; \
    fi && \
    if ! getent group "$GID" >/dev/null 2>&1; then \
        groupadd -g "$GID" "$USER"; \
    fi && \
    useradd -m -u "$UID" -g "$GID" --shell $(which bash) "$USER" -G sudo && \
    groupadd realtime && \
    groupmod -g ${VIDEO_GID} video && \
    usermod -aG video "$USER" && \
    usermod -aG dialout "$USER" && \
    usermod -aG realtime "$USER" && \
    usermod -aG plugdev "$USER" && \
    usermod -aG sudo "$USER"
RUN echo "$USER:$PASSWORD" | chpasswd && \
    echo "%sudo ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/sudogrp
RUN echo "source /opt/ros/$ROS_DISTRO/setup.bash" >> /etc/bash.bashrc
RUN echo "source /home/$USER/$PROJECT_WS/install/setup.bash" >> /etc/bash.bashrc
RUN echo "export ROS_DOMAIN_ID=${ROS_DOMAIN_ID}" >> /etc/bash.bashrc

ENV CYCLONEDDS_URI=/home/$USER/env/cyclone_dds.xml
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

USER $USER
RUN mkdir -p /home/$USER/$PROJECT_WS/src
RUN mkdir -p /home/$USER/.config/libsurvive

##############################################################################
##                               ROS2 Dependecies                           ##
##############################################################################
USER root

RUN apt-get update && apt-get install -y        \
    ros-$ROS_DISTRO-rmw-cyclonedds-cpp          \
    ros-$ROS_DISTRO-rviz2                       \
    ros-$ROS_DISTRO-rqt*                        \
    ros-$ROS_DISTRO-pcl-conversions             \
    ros-$ROS_DISTRO-joint-state-publisher       \
    ros-$ROS_DISTRO-tf-transformations          \
    python3-rosdep                              \
    python3-colcon-common-extensions            \
    && rm -rf /var/lib/apt/lists/*

USER $USER

##############################################################################
##                              Hello Stretch Robot Deps                    ##
##############################################################################
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Strip distutils/apt-installed Python packages so pip can own them cleanly.
# MUST run before the pip installs below (else pip sees them "already satisfied" and
# keeps the old, NumPy-1-era versions) and AFTER the apt block (tf-transformations pulls
# in apt transforms3d). Needs sudo since these live in /usr/lib and we run as $USER.
RUN sudo rm -rf /usr/lib/python3/dist-packages/sympy* \
                /usr/lib/python3/dist-packages/blinker* \
                /usr/lib/python3/dist-packages/transforms3d* \
                /usr/lib/python3/dist-packages/kiwisolver* || true

# --- pure-pip deps: no workspace source needed, kept above COPY for caching ---
# URDF assets (moved out of stretch_description into a separate pip package)
RUN pip3 install -U hello-robot-stretch-urdf && \
    git clone https://github.com/hello-robot/stretch4_urdf.git --depth 1 /home/$USER/stretch4_urdf && \
    cd /home/$USER/stretch4_urdf && \
    pip3 install -e .

# Stretch4 MuJoCo simulation lib — cloned OUTSIDE the workspace; imported via pip (sys.path), not by path.
# NOTE: HEAD renamed the module stretch_mujoco -> stretch4_mujoco, but the stretch4_ros2 code imports
#       `stretch_mujoco`. Pin to a pre-rename commit (e.g. `git checkout 3bf0011`) once verified.
RUN git clone https://github.com/hello-robot/stretch4_mujoco.git /home/$USER/stretch4_mujoco && \
    cd /home/$USER/stretch4_mujoco && \
    git submodule update --init && \
    pip3 install -e .

# Extra Python deps rosdep misses (distutils versions already stripped above so these install fresh)
# ros2-numpy is split out with --no-deps: its PyPI release hard-pins numpy==1.24.2, which has no
# py3.12 wheel (source-builds and dies on pkgutil.ImpImporter) and would clobber numpy 2.x.
RUN pip3 install PyOpenGL==3.1.4 pyquaternion transforms3d && \
    pip3 install --no-deps ros2-numpy transformations pybase64

##############################################################################
##                                Build ROS 2                               ##
##############################################################################
WORKDIR /home/$USER/$PROJECT_WS
COPY --chown=$USER:$USER $PROJECT_WS/src /home/$USER/$PROJECT_WS/src

WORKDIR /home/$USER/$PROJECT_WS
RUN sudo apt-get update && \
    sudo rosdep update --rosdistro $ROS_DISTRO && \
    sudo PIP_BREAK_SYSTEM_PACKAGES=1 \
        rosdep install --from-paths src --ignore-src -r -y

# Install the stretch_simulation Python package (driver) from the workspace source
RUN . /opt/ros/$ROS_DISTRO/setup.sh && \
    pip3 install -e /home/$USER/$PROJECT_WS/src/stretch4_ros2/stretch_simulation

RUN . /opt/ros/$ROS_DISTRO/setup.sh && colcon build --symlink-install

RUN sudo sed --in-place --expression \
    '$isource "/home/$USER/$PROJECT_WS/install/setup.bash"' \
    /ros_entrypoint.sh

CMD ["/bin/bash"]

