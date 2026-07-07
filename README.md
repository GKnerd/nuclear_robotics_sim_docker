# Nuclear Robotics Simulation

A simulation framework for **mobile robots operating in radioactive environments**, coupling a
robotics physics engine with a high-fidelity radiation transport toolkit.

A Hello Robot Stretch 4 navigates a concrete storage room containing six spent-fuel canisters,
one of which is leaking. Using a virtual gamma detector, an online Bayesian radiation mapper, and
an active exploration policy on top of Nav2, the robot autonomously **finds the leak, localizes it
with an uncertainty estimate, and attributes it to the responsible canister** — all against
ground-truth radiation fields produced by Geant4 Monte Carlo transport.

## Introduction

<details open>
<summary><i>Project overview — click to collapse / expand</i></summary>

### Two engines, one data boundary

The system is built from two independent engines that never share a simulation loop. The only
thing connecting them is data passed across a boundary.

| Engine | Responsibility |
|--------|----------------|
| **MuJoCo** | Rigid-body physics: the robot, its kinematics/dynamics, the room geometry, and physics-grounded sensors (pose, lidar for SLAM/Nav2). |
| **Geant4** | Radiation transport: how gammas emitted by the leak travel, scatter, and are attenuated by the canister steel and the concrete walls. |

MuJoCo has **no concept of radiation**. The radiation reading is an *overlay*: the robot's sensor
pose comes from MuJoCo; the radiation value at that pose comes from a field produced by Geant4.
The room exists in both engines (MuJoCo XML scene, Geant4 `DetectorConstruction`) and the two
descriptions are kept in sync by hand — see
[RADIATION_ROOM.md](geant_experiments/Geant4_own/basic_room_source/RADIATION_ROOM.md).

### How a mission works

1. **Offline field bake (Geant4).** The leak and walls are stationary, so the radiation field is
   fixed for the whole run. The custom Geant4 app in
   [geant_experiments/Geant4_own/basic_room_source](geant_experiments/Geant4_own/basic_room_source)
   scores a **voxelized field** (200×200×60 voxels, 0.2 m XY / 0.075 m Z) of Cs-137 gammas
   (662 keV) and exports it as an `.npy` + `.json` pair. MuJoCo never waits on Geant4.

2. **Online mission (MuJoCo + ROS 2 Nav2 + `nuclear_radiation_exploration`).** The Stretch 4 is
   spawned in the `radiation_room` scene with a virtual detector that samples the baked field at
   its TF pose and emits **Poisson count measurements** — readings improve when the robot dwells,
   just like a real gamma detector. An online mapper fuses the counts into (a) a non-parametric
   belief map of the field and (b) a grid-Bayes posterior over the single-source position and
   strength, plus a which-canister probability. An **active explorer** scores candidate goals with
   a UCB acquisition over that belief and drives Nav2 until the source estimate is tight,
   confirmed up close, and reported.

3. **Offline evaluation.** Missions are recorded as rosbags (`data/*_run`) and scored by
   [ros2_ws/src/paper_eval](ros2_ws/src/paper_eval) against the Geant4 field: identification
   correctness, localization error, coverage, time-to-plume-contact. Method and results:
   [method.md](ros2_ws/src/paper_eval/method.md), [report.md](ros2_ws/src/paper_eval/report.md).

#### Why a robot simulator at all?

If measurements were only ever static, a box in Geant4 with fixed geometry would suffice. The
value here is that the **trajectory is the experimental variable**: a realistic, dynamics- and
navigation-constrained path generates the exact sampling pattern a real robot would, and the
search/mapping performance is evaluated on that.

### Stack

- **Ubuntu 24.04 (Noble)**
- **ROS 2 Jazzy**
- **Hello Robot Stretch 4** via [`stretch4_ros2`](https://github.com/hello-robot/stretch4_ros2), which ships the robot driver, the MuJoCo simulation (`stretch_simulation`, built on *Stretch4 MuJoCo*), and the Nav2 navigation stack (`stretch_nav2`) prebuilt. The MuJoCo↔Nav2 integration is therefore provided by Hello Robot; this project does **not** assemble its own `mujoco_ros2_control` bridge.
- **MuJoCo** for robot physics (version pinned by *Stretch4 MuJoCo*).
- **Geant4** (built from source) for radiation transport.

</details>

## Repository layout

| Path | Contents |
|---|---|
| [docker/](docker/) | Image build + container run scripts for Linux/WSL2 and macOS |
| [ros2_ws/src/nuclear_robotics_sim/hello_stretch_sim_bringup](ros2_ws/src/nuclear_robotics_sim/hello_stretch_sim_bringup) | Top-level bringup: sim + Nav2 + radiation stack, `radiation_room` scene, maps |
| [ros2_ws/src/nuclear_robotics_sim/nuclear_radiation_exploration](ros2_ws/src/nuclear_robotics_sim/nuclear_radiation_exploration) | Virtual radiation sensor, online mapper + source estimator, active explorer |
| [ros2_ws/src/paper_eval](ros2_ws/src/paper_eval) | Rosbag evaluation (`eval_bag.py`), figures, method & results write-ups |
| [geant_experiments/Geant4_own/basic_room_source](geant_experiments/Geant4_own/basic_room_source) | Custom Geant4 app: radiation room, leak model, field export |
| [geant_experiments/Geant4_own/radfield_query](geant_experiments/Geant4_own/radfield_query) | Standalone field loader + active-mapping demos (no ROS needed) |
| [data/](data/) | Baked fields, saved maps, recorded mission bags; leak inventory in [radiation_room_leak_config.md](data/radiation_room_leaks_07_07_2026/radiation_room_leak_config.md) |

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
| `autonomous` | `false` | `true` launches the Nav2 stack |
| `map` | bundled `radiation_room` map | map `.yaml` used by Nav2 when `autonomous:=true` |
| `radiation` | `false` | `true` runs the virtual sensor + mapper (+ explorer when `autonomous:=true`) |
| `radiation_mode` | `search` | `search` hunts the leak; `survey` does uniform coverage |
| `field_prefix` | `~/data/radiation_room_readings/radiation_field` | Geant4 field (`.npy`/`.json` prefix) — select the leak configuration here |

### Run an autonomous leak-search mission

The headline use case — sim, Nav2, and the full radiation stack in one command:

```bash
ros2 launch hello_stretch_sim_bringup hello_stretch_sim_bringup.launch.py \
  autonomous:=true radiation:=true \
  field_prefix:=/home/nuclear_robot_sim/data/radiation_room_leaks_07_07_2026/leak_radius_0.5m/radiation_field
```

In the RViz window, give an initial **2D Pose Estimate** at the robot's spawn (the origin,
near-identity), wait for the costmaps, and the explorer takes over: it publishes Poisson count
readings on `/radiation/reading`, fuses them into a belief map (`/radiation/map_mean`,
`/radiation/map_variance`) and a source posterior (`/radiation/source_estimate`,
`/radiation/canister_probs`, 2σ ellipse on `/radiation/source_markers`), and selects Nav2 goals
with a UCB acquisition until the estimate is tight and confirmed up close. The final claim —
leak position ± σ and the responsible canister — is published on `/radiation/report`.

- `radiation_mode:=survey` replaces the leak hunt with variance-driven uniform coverage of the room.
- `radiation:=true` **without** `autonomous:=true` runs only the sensor + mapper — drive with
  teleop and watch the radiation map build up (useful for manual surveys).
- Available fields (leak radius 0.1/0.2/0.5 m, different canisters, no-leak control) are catalogued
  in [radiation_room_leak_config.md](data/radiation_room_leaks_07_07_2026/radiation_room_leak_config.md).

Algorithmic details — the Poisson sensor model, grid-Bayes source filter, UCB scoring, and the
honest list of assumptions/limitations — are documented in
[method.md](ros2_ws/src/paper_eval/method.md); quantitative results across leak sizes are in
[report.md](ros2_ws/src/paper_eval/report.md).

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

`autonomous:=true` launches the sim **and** the MPPI Nav2 stack together (don't start the sim
separately, and don't run `stretch_nav2`'s `navigation_mppi.launch.py` directly — that starts the
*real* robot driver + Hesai lidar). The bundled `radiation_room` map is used by default; pass
`map:=` to override:
```bash
ros2 launch hello_stretch_sim_bringup hello_stretch_sim_bringup.launch.py autonomous:=true
```
`use_sim_time` is forced on by the autonomous branch, so you don't pass it. In the Nav2 RViz
window: **2D Pose Estimate** at the robot's start (the origin, where you mapped from — so it's
near-identity), wait for the costmaps to populate, then **Nav2 Goal**. The MPPI controller drives
the base via `/stretch/cmd_vel`.

> The Nav2 stack (`navigation2`, `nav2-bringup`) is baked into the image, and the bringup layers
> `config/nav2_sim_overrides.yaml` last to retarget Nav2's odometry from the real robot's
> `wheel_odom` frame/topic onto the sim's `odom` — without it `local_costmap`/`amcl` abort with
> `Invalid frame ID "wheel_odom"`.

## Generating radiation fields (Geant4)

The fields the sensor samples are baked by the custom Geant4 application in
[geant_experiments/Geant4_own/basic_room_source](geant_experiments/Geant4_own/basic_room_source):
the concrete room, three interior maze walls, and six 304L-steel spent-fuel canisters, with a
configurable cylindrical **leak hole** through one canister's shell (position, radius, depth).
Full geometry reference and MuJoCo↔Geant4 sync notes:
[RADIATION_ROOM.md](geant_experiments/Geant4_own/basic_room_source/RADIATION_ROOM.md).

```bash
cd geant_experiments/Geant4_own/basic_room_source
./compile.sh                                   # cmake build against the installed Geant4
./run.sh                                       # beamOn (run.mac) -> radiation_map.csv
                                               #   -> export_radiation_tensor.py --sigma 1
                                               #   -> interactive Plotly visualization
```

The export writes `radiation_field.npy` + `radiation_field.json` (voxel grid + world-frame
metadata). Point the sim at it with `field_prefix:=`, or query it without ROS via
`radfield_query/radiation_field.py` (trilinear interpolation; the `active_radiation_mapping_*.py`
demos run the mapping algorithms standalone against a field).

Two properties worth knowing before comparing fields:

- Voxel values are **accumulated track length, not normalized per primary** — a 30 M-primary run
  reads exactly 3× hotter than a 10 M run of the same geometry. Only compare equal-`beamOn` fields.
- Canister positions are hardcoded in **both** `DetectorConstruction.cc` and
  `PrimaryGeneratorAction.cc`; moving one without the other silently breaks the shielding.

## Recorded data & evaluation

`data/` holds the baked fields, the saved `radiation_room` maps/pose-graphs, and recorded mission
bags (`r01_run`, `r02_run`, `r05_run`, … — mcap rosbags of full autonomous missions at different
leak sizes). The evaluation pipeline in [ros2_ws/src/paper_eval](ros2_ws/src/paper_eval)
(`eval_bag.py`, `make_figures.py`) replays those bags against the corresponding ground-truth field
and produces the metrics and figures reported in [report.md](ros2_ws/src/paper_eval/report.md).

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
