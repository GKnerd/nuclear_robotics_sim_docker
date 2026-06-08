# Nuclear Robotics Simulation

A simulation framework for **mobile robots operating in radioactive environments**, coupling a
robotics physics engine with a high-fidelity radiation transport toolkit.

The goal is to let a mobile robot navigate a room, build a map of the radiation it encounters on the way to a source, and then use high-fidelity Monte Carlo transport as ground truth to study where a cheap, real-time radiation model agrees with  and where it diverges from the real physics.

## Introduction 

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

## Prerequisites

Ensure the following are installed on your host machine:
* **Docker** (latest version)
* **vcstool**: To manage repository dependencies.
  ```bash
  pip install vcstool
  ```

## Installation & Setup

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

3. Build the Docker image:
```bash
./.docker/build_image.sh
```

This builds the image, compiles the full ROS 2 workspace inside the container, and copies the built workspace back to `ros2_ws/` on your host.

---

Copyright 2026 Georgios Katranis. Licensed under the Apache License, Version 2.0.
