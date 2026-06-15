# Nuclear Robotics Simulation

A simulation framework for **mobile robots operating in radioactive environments**, coupling a
robotics physics engine with a high-fidelity radiation transport toolkit.

The goal is to let a mobile robot navigate a room, build a map of the radiation it encounters on the way to a source, and then use high-fidelity Monte Carlo transport as ground truth to study where a cheap, real-time radiation model agrees with  and where it diverges from the real physics.

## Introduction 

<details open>
<summary><i>Project overview — click to collapse / expand</i></summary>

### Two engines, one data boundary

The system is built from two independent engines that never share a simulation loop. The only thing connecting them is data passed across a boundary.

| Engine | Responsibility |
|--------|----------------|
| **MuJoCo** | Rigid-body physics: the robot, its kinematics/dynamics, the room geometry, and physics-grounded sensors (pose, ray-casting for line-of-sight). |
| **Geant4** | Radiation transport: how particles emitted by the source travel, scatter, and are attenuated by the walls and the robot body. |

MuJoCo has **no concept of radiation**. The radiation reading is an *overlay*: the robot's sensor pose comes from MuJoCo; the radiation value at that pose comes from a field produced by Geant4.

### How a run works

1. **Offline pre-compute.** The source and walls are stationary, so the radiation field over the
   room is fixed for the whole run. Geant4 bakes a **voxelized radiation field** (a scalar
   rate per voxel) once, before the interactive loop starts. MuJoCo never waits on Geant4.

2. **Online navigation (MuJoCo + ROS 2 Nav2).** The Stretch 4 robot is spawned in the MuJoCo room
   with a radiation sensor mounted on it. It navigates toward the source — which may be of **known or
   unknown** location — using the ROS 2 Nav2 stack. Each step, the sensor **polls the precomputed
   voxel field** at its current pose (plus noise). The robot logs `(pose, time, measured_rate)`
   along its trajectory, producing a **radiation map** between its start and the source.

3. **Offline ground truth.** The recorded trajectory poses are replayed into **high-fidelity
   Geant4** runs — including the robot body at each pose, so detector self-shielding and
   orientation are captured — to produce reference readings. The cheap voxel-field rate is then
   compared against the high-fidelity rate **at the same poses the robot actually visited**.

The comparison is currently **rate vs. rate** (instantaneous count/dose rate), not integrated
counts. The stationary, high-fidelity measurement the robot performs once it reaches the source is
treated as a separate, higher-fidelity data point.

#### Why a robot simulator at all?

If measurements were only ever static, a box in Geant4 with fixed geometry would suffice. The value here is that the **trajectory is the experimental variable**: a realistic, dynamics- and
navigation-constrained path generates the exact sampling pattern a real robot would, and that is what the fast-vs-ground-truth comparison is run against.

### Stack

- **Ubuntu 24.04 (Noble)**
- **ROS 2 Jazzy**
- **Hello Robot Stretch 4** via [`stretch4_ros2`](https://github.com/hello-robot/stretch4_ros2), which ships the robot driver, the MuJoCo simulation (`stretch_simulation`, built on *Stretch4 MuJoCo*), and the Nav2 navigation stack (`stretch_nav2`) prebuilt. The MuJoCo↔Nav2 integration is therefore provided by Hello Robot; this project does **not** assemble its own`mujoco_ros2_control` bridge.
- **MuJoCo** for robot physics (version pinned by *Stretch4 MuJoCo*).
- **Geant4** (built from source) for radiation transport 

</details>

## Prerequisites

| | **Linux / Windows (WSL2)** | **macOS (Apple Silicon)** |
|---|---|---|
| Docker | Docker Engine (latest) | Docker Desktop (latest) |
| GPU | NVIDIA GPU + **NVIDIA Container Toolkit** (hardware-accelerated rendering) | none — all OpenGL is software-rendered (Mesa/llvmpipe) |
| GUI | host X11 (native, or **WSLg** on Windows) | in-container virtual desktop streamed to the **browser** (noVNC) |
| `vcstool` | `pip install vcstool` | `pip install vcstool` |

The macOS image is built for `linux/amd64` and runs under emulation (Open3D ships no
`linux/arm64` wheel). It has **no GPU passthrough**, so the sim runs slower than on Linux —
fine for mapping and teleop, not for camera-heavy rendering.

## Installation (all platforms)

1. Clone the repository:
   ```bash
   git clone https://github.com/GKnerd/nuclear_robotics_sim.git
   cd nuclear_robotics_sim
   ```

2. Create the source directory and import dependencies:
   ```bash
   mkdir -p ros2_ws/src
   vcs import ros2_ws/src < ros2.repos
   ```

### Host kernel buffer (crucial — do this before the first run)

CycloneDDS needs a large kernel receive buffer to handle big trajectory messages without
dropping packets. The container shares the **host kernel's** setting, so it must be raised
*outside* the container or the sim crashes on boot. **Where** you set it depends on the OS:

**Linux / Windows (WSL2)** — set it on the host (on Windows, run this inside your WSL distro):
```bash
sudo sysctl -w net.core.rmem_max=2147483647
```
The `-w` form resets on reboot. To persist:
```bash
echo 'net.core.rmem_max=2147483647' | sudo tee /etc/sysctl.d/60-cyclonedds.conf
sudo sysctl --system
```

**macOS** — `sudo sysctl` on the Mac does **nothing** for containers: they run inside Docker
Desktop's Linux VM, which has its own kernel. Set it *inside that VM* by entering its PID-1
namespace:
```bash
docker run --rm --privileged --pid=host alpine sh -c \
  "apk add --no-cache util-linux && nsenter -t 1 -m -u -n -i sh -c 'sysctl -w net.core.rmem_max=2147483647'"
```
This resets whenever the Docker Desktop VM restarts (quit/restart Docker, reboot), so re-run it
after restarting Docker.

## Build & Run

### Linux / Windows (WSL2)

```bash
./docker/build_image.sh      # builds the image + compiles the workspace, copies it back to ros2_ws/
./docker/run_container.sh     # starts the container; GUI windows open on the host (WSLg on Windows)
```

### macOS (Apple Silicon)

```bash
./docker/build_image_on_mac.sh    # builds linux/amd64 under emulation — first build is slow (Geant4 from source)
./docker/run_container_on_mac.sh  # starts the container and a virtual desktop
```
The run script prints a URL. Open it in a browser to reach the GUI (rviz2, MuJoCo viewer):
```
http://localhost:6080/vnc.html
```
(or point any VNC client at `localhost:5900`). All commands below are typed into the container
shell exactly the same way as on Linux — only *where the windows appear* differs.

## Bringup

Everything below runs **inside the container** (after `run_container.sh` /
`run_container_on_mac.sh`).

### Start the simulation

```bash
ros2 launch hello_stretch_sim_bringup hello_stretch_sim_bringup.launch.py
```
This launches the Stretch 4 MuJoCo sim in the `radiation_room` scene (default
`scene_config:=config/radiation_room.yaml`), plus RViz and the MuJoCo viewer. Cameras are
**off by default** (`use_cameras:=false`) — they drop the sim to ~2 Hz and are not needed for
2D mapping or navigation.

Useful arguments:

| Argument | Default | Meaning |
|---|---|---|
| `use_cameras` | `false` | RGB-D cameras (slow; only enable if you need point clouds) |
| `use_sim_time` | `false` | set `true` for mapping/nav so nodes follow the sim `/clock` |
| `use_rviz` / `use_mujoco_viewer` | `true` | the two GUI windows |
| `autonomous` | `false` | `true` launches the Nav2 stack (requires `map:=`) |
| `map` | `""` | path to a map `.yaml`, required when `autonomous:=true` |

### Build a map (2D SLAM)

The base lidar publishes `LaserScan` on `/scan_filtered`; that plus odometry is all
`slam_toolbox` needs — no cameras.

1. **Launch the sim with sim time** (so SLAM and the driver share one clock):
   ```bash
   ros2 launch hello_stretch_sim_bringup hello_stretch_sim_bringup.launch.py use_sim_time:=true
   ```

2. **Start SLAM** (new terminal — `docker exec -it nuclear_robotics_sim_docker bash`):
   ```bash
   ros2 run slam_toolbox sync_slam_toolbox_node --ros-args \
     --params-file "$(ros2 pkg prefix --share hello_stretch_sim_bringup)/config/mapping_sim.yaml" \
     -p use_sim_time:=true
   ```

3. **Drive the robot** (new terminal) — keyboard teleop, remapped to the sim's cmd topic:
   ```bash
   ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/stretch/cmd_vel
   ```
   (Or use `rqt_robot_steering` and set its topic to `/stretch/cmd_vel`.) Drive slowly around
   the whole room; watch the map fill in in RViz (add a `Map` display on `/map`).

4. **Save the map** when it looks complete. `map_saver_cli` does **not** create directories, so
   make the target dir first:
   ```bash
   mkdir -p ~/data/radiation_room
   ros2 run nav2_map_server map_saver_cli -f ~/data/radiation_room/radiation_room
   ```
   This writes `radiation_room.pgm` + `radiation_room.yaml`. `~/data` is volume-mounted, so the
   map persists on the host.

5. **(Optional) Save the pose-graph to resume mapping later** instead of starting fresh:
   ```bash
   ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
     "{filename: '/home/nuclear_robot_sim/data/radiation_room/radiation_room'}"
   ```
   This writes a matched `.posegraph` + `.data` pair. To resume, launch SLAM (step 2) and call
   `/slam_toolbox/deserialize_map` with the same filename, then keep driving.

### Navigate autonomously (Nav2)

Once you have a saved map `.yaml`:
```bash
ros2 launch hello_stretch_sim_bringup hello_stretch_sim_bringup.launch.py \
  autonomous:=true map:=/home/nuclear_robot_sim/data/radiation_room/radiation_room.yaml
```
Nav2 brings its own RViz; set a 2D Pose Estimate, then send a Nav2 Goal.

## Verifying the Setup

### 1. Robot base environment (Stretch 4 + MuJoCo)

```bash
ros2 launch stretch_simulation stretch_mujoco_driver.launch.py
```
The MuJoCo viewer should open with the Stretch 4 robot in the default scene. For the
navigation-control variant, append `mode:=navigation use_mujoco_viewer:=true`.

### 2. Geant4

Confirm the toolchain, datasets, and visualization with the canonical example **B1**:
```bash
source /opt/geant4/bin/geant4.sh

# locate the installed example (or clone it from the pinned Geant4 tag if not present)
B1=$(dirname "$(find /opt/geant4 -name exampleB1.cc 2>/dev/null | head -1)")

cmake -S "$B1" -B /tmp/B1-build && cmake --build /tmp/B1-build -j"$(nproc)"
cd /tmp/B1-build

./exampleB1 run1.mac     # batch: prints the cumulated dose in the scoring volume
./exampleB1              # interactive: opens the Qt viewer; at Idle> type: /run/beamOn 100
```
A run summary with a **cumulated dose**, plus a viewer window showing the geometry and
particle tracks, confirms Geant4 is fully functional end-to-end.

---

Copyright 2026 Georgios Katranis. Licensed under the Apache License, Version 2.0.
