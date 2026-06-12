import argparse
import numpy as np
import plotly.graph_objects as go

from radiation_field import RadiationField
from mujoco_obstacle_map import MujocoObstacleMap2D


class OnlineRadiationMapper3D:
    def __init__(
        self,
        x_min,
        x_max,
        y_min,
        y_max,
        z_min,
        z_max,
        nx=60,
        ny=60,
        nz=20,
        prior_mean=0.0,
        prior_var=1.0,
        kernel_sigma=0.75,
        measurement_noise=0.08,
        radiation_focus=2.0,
        min_variance=0.03,
        max_gain=0.35,
        z_travel_weight=2.0,
    ):
        self.x = np.linspace(x_min, x_max, nx)
        self.y = np.linspace(y_min, y_max, ny)
        self.z = np.linspace(z_min, z_max, nz)

        self.X, self.Y, self.Z = np.meshgrid(
            self.x,
            self.y,
            self.z,
            indexing="ij",
        )

        self.mean = np.full((nx, ny, nz), prior_mean, dtype=np.float64)
        self.var = np.full((nx, ny, nz), prior_var, dtype=np.float64)

        self.kernel_sigma = kernel_sigma
        self.measurement_noise = measurement_noise
        self.radiation_focus = radiation_focus
        self.min_variance = min_variance
        self.max_gain = max_gain
        self.z_travel_weight = z_travel_weight

        self.measurements = []
        self.trajectory = []

    def update(self, x, y, z, value):
        d2 = (
            (self.X - x) ** 2
            + (self.Y - y) ** 2
            + (self.Z - z) ** 2
        )

        w = np.exp(-0.5 * d2 / (self.kernel_sigma ** 2))
        mask = w > 0.05

        prior_mean = self.mean[mask]
        prior_var = self.var[mask]
        local_w = w[mask]

        base_noise = self.measurement_noise ** 2
        effective_noise = base_noise / np.maximum(local_w, 1e-3)

        kalman_gain = prior_var / (prior_var + effective_noise)
        kalman_gain = np.minimum(kalman_gain, self.max_gain * local_w)

        self.mean[mask] = prior_mean + kalman_gain * (value - prior_mean)

        self.var[mask] = np.maximum(
            (1.0 - kalman_gain) * prior_var,
            self.min_variance,
        )

        self.measurements.append((x, y, z, value))

    def choose_next_target(self, current_x, current_y, current_z, exploration_bias=0.10):
        mean_norm = self.mean / (np.max(self.mean) + 1e-12)
        var_norm = self.var / (np.max(self.var) + 1e-12)

        distance = np.sqrt(
            (self.X - current_x) ** 2
            + (self.Y - current_y) ** 2
            + self.z_travel_weight * (self.Z - current_z) ** 2
        )

        radiation_weight = (mean_norm + exploration_bias) ** self.radiation_focus

        score = var_norm * radiation_weight / (1.0 + 0.12 * distance)

        idx = np.unravel_index(np.argmax(score), score.shape)

        return (
            float(self.X[idx]),
            float(self.Y[idx]),
            float(self.Z[idx]),
            float(score[idx]),
        )


def sample_drive_3d(
    field,
    mapper,
    start,
    target,
    step_size=0.25,
    detector_radius=0.15,
    detector_samples=3,
    noise_std=0.0,
):
    x0, y0, z0 = start
    x1, y1, z1 = target

    distance = np.sqrt(
        (x1 - x0) ** 2
        + (y1 - y0) ** 2
        + (z1 - z0) ** 2
    )

    n_steps = max(2, int(np.ceil(distance / step_size)))

    path = []

    for i in range(n_steps + 1):
        t = i / n_steps

        x = (1.0 - t) * x0 + t * x1
        y = (1.0 - t) * y0 + t * y1
        z = (1.0 - t) * z0 + t * z1

        value, valid = field.query_detector_average(
            x,
            y,
            z,
            radius=detector_radius,
            samples=detector_samples,
        )

        if valid:
            if noise_std > 0:
                value += np.random.normal(0.0, noise_std)

            value = max(0.0, value)
            mapper.update(x, y, z, value)

        mapper.trajectory.append((x, y, z))
        path.append((x, y, z, value if valid else 0.0))

    return target, path


def query_true_map_3d(
    field,
    mapper,
    detector_radius=0.15,
    detector_samples=3,
):
    true_map = np.zeros_like(mapper.mean)

    for ix in range(mapper.X.shape[0]):
        for iy in range(mapper.X.shape[1]):
            for iz in range(mapper.X.shape[2]):
                value, valid = field.query_detector_average(
                    float(mapper.X[ix, iy, iz]),
                    float(mapper.Y[ix, iy, iz]),
                    float(mapper.Z[ix, iy, iz]),
                    radius=detector_radius,
                    samples=detector_samples,
                )

                true_map[ix, iy, iz] = value if valid else 0.0

    return true_map


def point_cloud_from_volume(
    volume,
    X,
    Y,
    Z,
    percentile=70,
    max_points=150_000,
    transform="sqrt",
):
    mask = volume > 0.0

    if not np.any(mask):
        return np.array([]), np.array([]), np.array([]), np.array([])

    values_raw = volume[mask]
    xs = X[mask]
    ys = Y[mask]
    zs = Z[mask]

    if transform == "log":
        values = np.log10(values_raw + 1e-15)
    elif transform == "sqrt":
        values = np.sqrt(values_raw)
    else:
        values = values_raw

    threshold = np.percentile(values, percentile)
    keep = values >= threshold

    xs = xs[keep]
    ys = ys[keep]
    zs = zs[keep]
    values = values[keep]

    if len(values) > max_points:
        idx = np.random.choice(len(values), max_points, replace=False)
        xs = xs[idx]
        ys = ys[idx]
        zs = zs[idx]
        values = values[idx]

    return xs, ys, zs, values


def write_visualization_3d(
    mapper,
    true_map,
    output_html,
    delta_mode="abs",
    cloud_percentile=70,
):
    trajectory = np.array(mapper.trajectory)
    measurements = np.array(mapper.measurements)

    eps = 1e-15

    true_log = np.log10(true_map + eps)
    mean_log = np.log10(mapper.mean + eps)

    true_positive = true_map[true_map > 0]
    if len(true_positive) > 0:
        true_floor = np.percentile(true_positive, 1)
    else:
        true_floor = eps

    valid_delta_mask = true_map > true_floor

    if delta_mode == "signed":
        delta = mean_log - true_log
    else:
        delta = np.abs(mean_log - true_log)

    delta = np.where(valid_delta_mask, delta, 0.0)

    true_pc = point_cloud_from_volume(
        true_map,
        mapper.X,
        mapper.Y,
        mapper.Z,
        percentile=cloud_percentile,
        transform="sqrt",
    )

    mean_pc = point_cloud_from_volume(
        mapper.mean,
        mapper.X,
        mapper.Y,
        mapper.Z,
        percentile=cloud_percentile,
        transform="sqrt",
    )

    var_pc = point_cloud_from_volume(
        mapper.var,
        mapper.X,
        mapper.Y,
        mapper.Z,
        percentile=cloud_percentile,
        transform="raw",
    )

    delta_pc = point_cloud_from_volume(
        delta,
        mapper.X,
        mapper.Y,
        mapper.Z,
        percentile=cloud_percentile,
        transform="raw",
    )

    fig = go.Figure()

    def add_cloud(pc, name, colorscale, visible, colorbar_title):
        xs, ys, zs, values = pc

        fig.add_trace(
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="markers",
                marker=dict(
                    size=2,
                    color=values,
                    colorscale=colorscale,
                    opacity=0.45,
                    showscale=visible,
                    colorbar=dict(title=colorbar_title),
                ),
                name=name,
                visible=visible,
            )
        )

    add_cloud(true_pc, "True field", "Inferno", True, "sqrt true")
    add_cloud(mean_pc, "Estimated mean", "Inferno", False, "sqrt estimate")
    add_cloud(var_pc, "Uncertainty", "Viridis", False, "variance")
    add_cloud(delta_pc, "Delta", "Viridis", False, "log error")

    fig.add_trace(
        go.Scatter3d(
            x=trajectory[:, 0],
            y=trajectory[:, 1],
            z=trajectory[:, 2],
            mode="lines",
            line=dict(width=4, color="cyan"),
            name="Robot trajectory",
            visible=True,
        )
    )

    fig.add_trace(
        go.Scatter3d(
            x=measurements[:, 0],
            y=measurements[:, 1],
            z=measurements[:, 2],
            mode="markers",
            marker=dict(
                size=3,
                color=np.log10(measurements[:, 3] + eps),
                colorscale="Inferno",
                opacity=0.85,
                showscale=False,
            ),
            name="Measurements",
            visible=True,
        )
    )

    visibility_true = [True, False, False, False, True, True]
    visibility_mean = [False, True, False, False, True, True]
    visibility_var = [False, False, True, False, True, True]
    visibility_delta = [False, False, False, True, True, True]

    fig.update_layout(
        title="3D active radiation mapping demo",
        scene=dict(
            xaxis_title="x [m]",
            yaxis_title="y [m]",
            zaxis_title="z [m]",
            aspectmode="data",
        ),
        updatemenus=[
            dict(
                buttons=[
                    dict(
                        label="True field",
                        method="update",
                        args=[{"visible": visibility_true}],
                    ),
                    dict(
                        label="Estimated mean",
                        method="update",
                        args=[{"visible": visibility_mean}],
                    ),
                    dict(
                        label="Uncertainty",
                        method="update",
                        args=[{"visible": visibility_var}],
                    ),
                    dict(
                        label="Delta",
                        method="update",
                        args=[{"visible": visibility_delta}],
                    ),
                ],
                direction="down",
                x=0.02,
                y=1.08,
            )
        ],
    )

    fig.write_html(output_html)
    print(f"Wrote visualization: {output_html}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--field", default="../basic_room_source/radiation_field")

    parser.add_argument("--x-min", type=float, default=-20.0)
    parser.add_argument("--x-max", type=float, default=20.0)
    parser.add_argument("--y-min", type=float, default=-20.0)
    parser.add_argument("--y-max", type=float, default=20.0)
    parser.add_argument("--z-min", type=float, default=0.4)
    parser.add_argument("--z-max", type=float, default=3.0)

    parser.add_argument("--grid-nx", type=int, default=60)
    parser.add_argument("--grid-ny", type=int, default=60)
    parser.add_argument("--grid-nz", type=int, default=20)

    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--drive-step", type=float, default=0.35)

    parser.add_argument("--start-x", type=float, default=0.0)
    parser.add_argument("--start-y", type=float, default=0.0)
    parser.add_argument("--start-z", type=float, default=1.0)

    parser.add_argument("--kernel-sigma", type=float, default=0.75)
    parser.add_argument("--measurement-noise", type=float, default=0.08)

    parser.add_argument("--radiation-focus", type=float, default=2.0)
    parser.add_argument("--exploration-bias", type=float, default=0.10)

    parser.add_argument("--min-variance", type=float, default=0.03)
    parser.add_argument("--max-gain", type=float, default=0.35)

    parser.add_argument(
        "--z-travel-weight",
        type=float,
        default=2.0,
        help="Penalty factor for vertical travel. Higher discourages z changes.",
    )

    parser.add_argument("--detector-radius", type=float, default=0.15)
    parser.add_argument("--detector-samples", type=int, default=3)

    parser.add_argument("--delta-mode", choices=["abs", "signed"], default="abs")
    parser.add_argument("--cloud-percentile", type=float, default=70)

    parser.add_argument("--output", default="active_mapping_3d_demo.html")

    args = parser.parse_args()

    field = RadiationField(args.field)

    mapper = OnlineRadiationMapper3D(
        args.x_min,
        args.x_max,
        args.y_min,
        args.y_max,
        args.z_min,
        args.z_max,
        nx=args.grid_nx,
        ny=args.grid_ny,
        nz=args.grid_nz,
        kernel_sigma=args.kernel_sigma,
        measurement_noise=args.measurement_noise,
        radiation_focus=args.radiation_focus,
        min_variance=args.min_variance,
        max_gain=args.max_gain,
        z_travel_weight=args.z_travel_weight,
    )

    current = (args.start_x, args.start_y, args.start_z)

    for k in range(args.iterations):
        target_x, target_y, target_z, score = mapper.choose_next_target(
            current[0],
            current[1],
            current[2],
            exploration_bias=args.exploration_bias,
        )

        current, _ = sample_drive_3d(
            field,
            mapper,
            current,
            (target_x, target_y, target_z),
            step_size=args.drive_step,
            detector_radius=args.detector_radius,
            detector_samples=args.detector_samples,
            noise_std=args.measurement_noise,
        )

        print(
            f"Iteration {k + 1:03d}: "
            f"target=({target_x:.2f}, {target_y:.2f}, {target_z:.2f}), "
            f"score={score:.3e}, "
            f"measurements={len(mapper.measurements)}"
        )

    print("Querying true 3D map on estimator grid...")
    true_map = query_true_map_3d(
        field,
        mapper,
        detector_radius=args.detector_radius,
        detector_samples=args.detector_samples,
    )

    write_visualization_3d(
        mapper,
        true_map,
        args.output,
        delta_mode=args.delta_mode,
        cloud_percentile=args.cloud_percentile,
    )


if __name__ == "__main__":
    main()