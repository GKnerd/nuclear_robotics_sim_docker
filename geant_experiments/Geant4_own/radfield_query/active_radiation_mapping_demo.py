import argparse
import numpy as np
import plotly.graph_objects as go

from radiation_field import RadiationField


class OnlineRadiationMapper2D:
    def __init__(
        self,
        x_min,
        x_max,
        y_min,
        y_max,
        nx=80,
        ny=80,
        prior_mean=0.0,
        prior_var=1.0,
        kernel_sigma=0.75,
        measurement_noise=0.05,
        radiation_focus=2.0,
    ):
        self.x = np.linspace(x_min, x_max, nx)
        self.y = np.linspace(y_min, y_max, ny)
        self.X, self.Y = np.meshgrid(self.x, self.y, indexing="ij")

        self.mean = np.full((nx, ny), prior_mean, dtype=np.float64)
        self.var = np.full((nx, ny), prior_var, dtype=np.float64)

        self.kernel_sigma = kernel_sigma
        self.measurement_noise = measurement_noise
        self.radiation_focus = radiation_focus

        self.measurements = []
        self.trajectory = []

    def update(self, x, y, value):
        d2 = (self.X - x) ** 2 + (self.Y - y) ** 2

        # Spatial correlation kernel.
        w = np.exp(-0.5 * d2 / (self.kernel_sigma ** 2))

        # Ignore very weakly related cells.
        mask = w > 0.05

        prior_mean = self.mean[mask]
        prior_var = self.var[mask]
        local_w = w[mask]

        # Conservative effective noise.
        # Even at the measurement location, we do not allow uncertainty to collapse to zero.
        base_noise = self.measurement_noise ** 2
        effective_noise = base_noise / np.maximum(local_w, 1e-3)

        kalman_gain = prior_var / (prior_var + effective_noise)

        # Limit how much a single measurement can change a cell.
        max_gain = 0.35
        kalman_gain = np.minimum(kalman_gain, max_gain * local_w)

        self.mean[mask] = prior_mean + kalman_gain * (value - prior_mean)

        # Do not allow variance to collapse completely.
        min_variance = 0.03
        self.var[mask] = np.maximum(
            (1.0 - kalman_gain) * prior_var,
            min_variance
        )

        self.measurements.append((x, y, value))

    def choose_next_target(self, current_x, current_y, exploration_bias=0.05):
        mean_norm = self.mean / (np.max(self.mean) + 1e-12)
        var_norm = self.var / (np.max(self.var) + 1e-12)

        distance = np.sqrt((self.X - current_x) ** 2 + (self.Y - current_y) ** 2)

        radiation_weight = (mean_norm + exploration_bias) ** self.radiation_focus

        score = var_norm * radiation_weight / (1.0 + 0.12 * distance)

        idx = np.unravel_index(np.argmax(score), score.shape)

        return float(self.X[idx]), float(self.Y[idx]), float(score[idx])


def sample_drive(
    field,
    mapper,
    start,
    target,
    z,
    step_size=0.25,
    detector_radius=0.15,
    detector_samples=3,
    noise_std=0.0,
):
    x0, y0 = start
    x1, y1 = target

    distance = np.hypot(x1 - x0, y1 - y0)
    n_steps = max(2, int(np.ceil(distance / step_size)))

    path = []

    for i in range(n_steps + 1):
        t = i / n_steps
        x = (1.0 - t) * x0 + t * x1
        y = (1.0 - t) * y0 + t * y1

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
            mapper.update(x, y, value)

        mapper.trajectory.append((x, y))
        path.append((x, y, value if valid else 0.0))

    return target, path


def query_true_map(field, mapper, z, detector_radius=0.15, detector_samples=3):
    true_map = np.zeros_like(mapper.mean)

    for ix in range(mapper.X.shape[0]):
        for iy in range(mapper.X.shape[1]):
            value, valid = field.query_detector_average(
                float(mapper.X[ix, iy]),
                float(mapper.Y[ix, iy]),
                z,
                radius=detector_radius,
                samples=detector_samples,
            )
            true_map[ix, iy] = value if valid else 0.0

    return true_map


def write_visualization(mapper, true_map, output_html, delta_mode="abs"):
    trajectory = np.array(mapper.trajectory)
    measurements = np.array(mapper.measurements)

    eps = 1e-15
    true_floor = np.percentile(true_map[true_map > 0], 1) if np.any(true_map > 0) else eps

    true_log = np.log10(true_map + eps)
    mean_log = np.log10(mapper.mean + eps)

    valid_delta_mask = true_map > true_floor

    if delta_mode == "signed":
        delta = mean_log - true_log
        delta_title = "log10(estimate) - log10(true)"
        delta_colorscale = "RdBu"
    else:
        delta = np.abs(mean_log - true_log)
        delta_title = "|log10(estimate) - log10(true)|"
        delta_colorscale = "Viridis"

    delta = np.where(valid_delta_mask, delta, np.nan)

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            z=true_log.T,
            x=mapper.x,
            y=mapper.y,
            colorscale="Inferno",
            visible=True,
            name="True field",
            colorbar=dict(title="log10 true", x=1.02),
        )
    )

    fig.add_trace(
        go.Heatmap(
            z=mean_log.T,
            x=mapper.x,
            y=mapper.y,
            colorscale="Inferno",
            visible=False,
            name="Estimated mean",
            showscale=False,
        )
    )

    fig.add_trace(
        go.Heatmap(
            z=mapper.var.T,
            x=mapper.x,
            y=mapper.y,
            colorscale="Viridis",
            visible=False,
            name="Uncertainty",
            showscale=False,
        )
    )

    fig.add_trace(
        go.Heatmap(
            z=delta.T,
            x=mapper.x,
            y=mapper.y,
            colorscale=delta_colorscale,
            visible=False,
            name="Delta",
            showscale=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=trajectory[:, 0],
            y=trajectory[:, 1],
            mode="lines",
            line=dict(width=2, color="cyan"),
            name="Robot trajectory",
            visible=True,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=measurements[:, 0],
            y=measurements[:, 1],
            mode="markers",
            marker=dict(
                size=4,
                color=np.log10(measurements[:, 2] + eps),
                colorscale="Inferno",
                showscale=False,
            ),
            name="Measurements",
            visible=True,
        )
    )

    fig.update_layout(
        title="Active radiation mapping demo",
        xaxis_title="x [m]",
        yaxis_title="y [m]",
        yaxis=dict(scaleanchor="x", scaleratio=1),
        updatemenus=[
            dict(
                buttons=[
                    dict(
                        label="True field",
                        method="update",
                        args=[
                            {
                                "visible": [True, False, False, False, True, True],
                                "showscale": [True, False, False, False, False, False],
                            }
                        ],
                    ),
                    dict(
                        label="Estimated mean",
                        method="update",
                        args=[
                            {
                                "visible": [False, True, False, False, True, True],
                                "showscale": [False, True, False, False, False, False],
                            }
                        ],
                    ),
                    dict(
                        label="Uncertainty",
                        method="update",
                        args=[
                            {
                                "visible": [False, False, True, False, True, True],
                                "showscale": [False, False, True, False, False, False],
                            }
                        ],
                    ),
                    dict(
                        label="Delta",
                        method="update",
                        args=[
                            {
                                "visible": [False, False, False, True, True, True],
                                "showscale": [False, False, False, True, False, False],
                            }
                        ],
                    ),
                ],
                direction="down",
                x=0.02,
                y=1.12,
            )
        ],
    )

    fig.write_html(output_html)
    print(f"Wrote visualization: {output_html}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--field", default="../basic_room_source/radiation_field")
    parser.add_argument("--z", type=float, default=1.0)

    parser.add_argument("--x-min", type=float, default=-20.0)
    parser.add_argument("--x-max", type=float, default=20.0)
    parser.add_argument("--y-min", type=float, default=-20.0)
    parser.add_argument("--y-max", type=float, default=20.0)

    parser.add_argument("--grid-nx", type=int, default=100)
    parser.add_argument("--grid-ny", type=int, default=100)

    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--drive-step", type=float, default=0.25)

    parser.add_argument("--start-x", type=float, default=0.0)
    parser.add_argument("--start-y", type=float, default=0.0)

    parser.add_argument("--kernel-sigma", type=float, default=0.75)
    parser.add_argument("--measurement-noise", type=float, default=0.03)

    parser.add_argument("--radiation-focus", type=float, default=2.0)

    parser.add_argument("--detector-radius", type=float, default=0.15)
    parser.add_argument("--detector-samples", type=int, default=3)

    parser.add_argument("--delta-mode", choices=["abs", "signed"], default="abs")

    parser.add_argument("--output", default="active_mapping_demo.html")

    args = parser.parse_args()

    field = RadiationField(args.field)

    mapper = OnlineRadiationMapper2D(
        args.x_min,
        args.x_max,
        args.y_min,
        args.y_max,
        nx=args.grid_nx,
        ny=args.grid_ny,
        kernel_sigma=args.kernel_sigma,
        measurement_noise=args.measurement_noise,
        radiation_focus=args.radiation_focus,
    )

    current = (args.start_x, args.start_y)

    for k in range(args.iterations):
        target_x, target_y, score = mapper.choose_next_target(
            current[0],
            current[1],
        )

        current, _ = sample_drive(
            field,
            mapper,
            current,
            (target_x, target_y),
            z=args.z,
            step_size=args.drive_step,
            detector_radius=args.detector_radius,
            detector_samples=args.detector_samples,
            noise_std=args.measurement_noise,
        )

        print(
            f"Iteration {k + 1:03d}: "
            f"target=({target_x:.2f}, {target_y:.2f}), "
            f"score={score:.3e}, "
            f"measurements={len(mapper.measurements)}"
        )

    true_map = query_true_map(
        field,
        mapper,
        z=args.z,
        detector_radius=args.detector_radius,
        detector_samples=args.detector_samples,
    )

    write_visualization(
        mapper,
        true_map,
        args.output,
        delta_mode=args.delta_mode,
    )


if __name__ == "__main__":
    main()