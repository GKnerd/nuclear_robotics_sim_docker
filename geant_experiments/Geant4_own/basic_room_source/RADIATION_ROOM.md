# Radiation Room — Scene & Simulation Reference

How the concrete room, canisters, and canister leak are built in Geant4, how the MuJoCo scene and
the physics geometry stay in sync, and how to build, run, and query the resulting radiation field.

- Geometry source: `src/DetectorConstruction.cc`
- Source sampling: `src/PrimaryGeneratorAction.cc`
- Physics list: `FTFP_BERT` — gamma, 662 keV (Cs-137 line)

## How the scene is described twice

The room exists in two places: a MuJoCo XML scene (used for the robot/visual overlay) and this
Geant4 `DetectorConstruction.cc` (used for actual radiation transport). They are **not** generated
from a shared source — each was hand-authored to match the other. When one changes — a wall moves,
a canister is repositioned — the other has to be updated by hand.

> **Gotcha already hit once.** `DetectorConstruction.cc` is not the only place canister positions
> are hardcoded. `PrimaryGeneratorAction.cc` keeps its own independent copy of the same six
> `(center, horizontalX)` pairs, used to sample where inside a canister a primary gamma is born.
> Move a canister in one file and forget the other, and the source point ends up outside the
> (moved) steel shell — full unattenuated emission, no shielding, wildly elevated dose. Always
> change both together.

## Room geometry

Current tuned dimensions. Wall thickness (0.1 m half / 0.2 m total) is the one dimension that has
been held fixed across every revision so far.

**Envelope & outer walls**

| Element     | Half-extents (m)  | Position (m)     | Note                              |
|-------------|--------------------|-------------------|------------------------------------|
| World       | 19.0 × 19.0 × 7.0  | 0, 0, 0           | air, invisible                    |
| Floor       | 16.0 × 16.0 × 0.05 | 0, 0, −0.05       | G4_CONCRETE                        |
| wall_north  | 16.0 × 0.1 × 2.0   | 0, +16.0, 2.0     | –                                  |
| wall_south  | 16.0 × 0.1 × 2.0   | 0, −16.0, 2.0     | –                                  |
| wall_east   | 0.1 × 15.8 × 2.0   | +16.0, 0, 2.0     | shortened 0.2 m, corner overlap    |
| wall_west   | 0.1 × 15.8 × 2.0   | −16.0, 0, 2.0     | shortened 0.2 m, corner overlap    |

**Inner walls (maze partitions)**

| Element      | Half-extents (m)   | Position (m)       | Rotation        |
|--------------|----------------------|----------------------|------------------|
| wall_inner_1 | 10.0 × 0.1 × 2.0    | −5.0, −1.5, 2.0     | none             |
| wall_inner_2 | 6.5 × 0.1 × 2.0     | 4.0, 4.0, 2.0       | none             |
| wall_inner_3 | 6.75 × 0.1 × 2.0    | 12.0, −9.0, 2.0     | +90° about Z     |

## Canisters

Six sealed 304L stainless-steel cylinders. Radius and height are shared; only position and
orientation vary.

**Shared dimensions**

| | | | |
|---|---|---|---|
| Outer radius | 0.89 m | Inner void radius | 0.65 m |
| Shell half-height | 2.09 m | Inner void half-height | 1.85 m |
| Source region radius | 0.55 m | Source region half-height | 1.80 m |

**Placement — index, name, position, orientation**

| Idx | Name        | Position (m)          | Orientation                          |       |
|-----|-------------|-------------------------|----------------------------------------|-------|
| 0   | canister_1  | −12.0, −10.0, 0.89     | horizontal (+90° Y, lies along X)      |       |
| 1   | canister_2  | 0.0, −7.0, 2.09        | vertical                               |       |
| 2   | canister_3  | 14.0, −12.0, 2.09      | vertical                               |       |
| 3   | canister_4  | −14.0, 12.0, 2.09      | vertical                               |       |
| 4   | canister_5  | 0.0, 11.0, 2.09        | vertical                               | leaks |
| 5   | canister_6  | 12.0, 15.0, 2.09       | vertical                               |       |

Each canister is three overlapping volumes: an outer `G4Tubs` shell with the inner void subtracted
out (steel), an independent `CanisterSourceRegion` air cylinder placed at the same center (where
primaries are actually born), and — for exactly one index — a second subtraction that punches the
leak channel through the shell.

## Leak configuration

`namespace LeakConfig` at the top of `DetectorConstruction.cc`. All five constants below have to
stay geometrically consistent with whichever canister they target.

| Constant             | Value | Meaning                                                        |
|-----------------------|-------|------------------------------------------------------------------|
| `leakEnabled`         | true  | master on/off switch                                            |
| `leakyCanisterIndex`  | 4     | → canister_5 (0-based)                                           |
| `leakThetaDeg`        | 330.0 | azimuth of the hole, local frame                                 |
| `leakLocalZ_m`        | 1.8   | height along canister axis, 0 = mid-height                      |
| `leakRadius_m`        | 0.01  | hole radius — 1 cm                                               |
| `leakHalfDepth_m`     | 0.30  | cutter half-depth — over-punches the 0.24 m shell on purpose     |

Theta convention (local frame; for an unrotated/vertical canister this maps directly onto world
x/y at the canister's center):

- θ = 0° → local +x side of the cylinder
- θ = 90° → local +y side
- θ = 180° → local −x side
- θ = 270° → local −y side
- θ = 330° → the current leak, just past +x toward −y

> **Why the leak doesn't show up in a track-length map.** Verified directly against a 10M-event
> `radiation_map.csv`: every voxel just outside the shell at the leak azimuth (r = 1.03–1.30 m from
> the canister center, at leak height) reads exactly **0**. Geometrically the configuration is
> correct — index, position, and orientation all check out.
>
> The problem is scale. A 1 cm-radius channel through a 24 cm-thick wall, fed by an isotropic
> source spread across a 0.55 m-radius, 3.6 m-tall cylinder, subtends a solid angle on the order of
> 10⁻⁴–10⁻⁵ from a typical source point. Out of 10M primaries, only a handful ever travel the exact
> channel — far too few to register above background scatter in a 0.2 m × 0.2 m × 0.075 m voxel.
>
> To make it visible: enlarge `leakRadius_m` (e.g. to 0.05–0.10 m, a 25–100× increase in
> transmitted solid angle), or run substantially more primaries — resolution alone won't fix a
> photon-count problem.

## Build → run → visualize → query

The full pipeline from source code to a queryable radiation field. All steps run inside the
project's Docker container.

**1. Enter the container and load Geant4**

```bash
./docker/run_container.sh
# inside the container:
source /opt/geant4/bin/geant4.sh
```

**2. Configure & build**

Standard CMake build of `room_source`. Re-run after any change to `DetectorConstruction.cc` or
`PrimaryGeneratorAction.cc`.

```bash
cd geant_experiments/Geant4_own/basic_room_source/build
cmake .. && make -j"$(nproc)"
```

**3. Interactive visualization**

No macro argument runs `macros/vis.mac` automatically — opens the OGL viewer, colors tracks by
particle (gamma = yellow, e⁻ = blue, e⁺ = red), and fires 30 events. Type more at the `Idle>` prompt.

```bash
./room_source
# at Idle> :
/run/beamOn 200
```

**4. Batch run for statistics**

`macros/run.mac` fires 10,000,000 primaries with no visualization and exports `radiation_map.csv` —
one row per voxel with accumulated gamma track length.

```bash
./room_source macros/run.mac
```

**5. Convert to a queryable tensor**

Folds the CSV into a dense `(nx, ny, nz)` array plus a JSON sidecar with the grid bounds. Optional
Gaussian smoothing in voxel units.

```bash
python export_radiation_tensor.py radiation_map.csv \
    --output radiation_field --sigma 1.0
```

**6. Render (optional)**

Produces two standalone Plotly HTML files — a thresholded 3D point cloud and a z-slice slider —
each with a live color-range control.

```bash
python visualize_radiation_map_interactive.py radiation_map.csv \
    --mode both --prefix radiation
# → radiation_volume.html, radiation_slices.html
```

**7. Query the field from Python**

`RadiationField` (in `radfield_query/radiation_field.py`) loads the `.npy`/`.json` pair and
interpolates trilinearly; returns 0 outside the grid bounds.

```python
from radiation_field import RadiationField

field = RadiationField("radiation_field")
value = field.query(x=0.0, y=11.0, z=2.0)          # trilinear
avg   = field.query_detector_average(0.0, 11.0, 2.0, radius=0.15)
```

## File map

| File | Purpose |
|---|---|
| `DetectorConstruction.cc` | world/floor/walls/canisters/leak geometry — the ground truth for physical layout |
| `PrimaryGeneratorAction.cc` | samples primary gamma position & direction — keeps its own copy of canister positions, must track `DetectorConstruction.cc` |
| `SteppingAction.cc` | sub-divides each gamma step and accumulates track length into the voxel grid |
| `VoxelGrid.{hh,cc}` | 200×200×60 bins over x,y∈[−20,20] m, z∈[0,4.5] m — sized larger than the current 32×32 m room |
| `RunAction.cc` | resets the grid at run start, writes `radiation_map.csv` at run end |
| `macros/vis.mac` / `run.mac` | interactive viewer (30 events) vs. batch statistics run (10M events) |
| `export_radiation_tensor.py` | CSV → `.npy` + `.json` |
| `visualize_radiation_map_interactive.py` | CSV → Plotly volume/slice HTML |
| `radfield_query/radiation_field.py` | runtime query API against the exported tensor |
