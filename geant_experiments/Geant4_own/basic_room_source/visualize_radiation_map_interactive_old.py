import argparse
import numpy as np
import pandas as pd
import plotly.graph_objects as go


def load_tensor(csv_file: str):
    df = pd.read_csv(csv_file)

    nx = df["ix"].max() + 1
    ny = df["iy"].max() + 1
    nz = df["iz"].max() + 1

    tensor = np.zeros((nx, ny, nz), dtype=float)

    tensor[
        df["ix"].to_numpy(dtype=int),
        df["iy"].to_numpy(dtype=int),
        df["iz"].to_numpy(dtype=int),
    ] = df["track_length_m"].to_numpy(dtype=float)

    x = np.sort(df["x_center_m"].unique())
    y = np.sort(df["y_center_m"].unique())
    z = np.sort(df["z_center_m"].unique())

    return tensor, x, y, z


def plot_volume(tensor, x, y, z, output_html):
    nonzero_mask = tensor > 0.0

    if not np.any(nonzero_mask):
        raise RuntimeError("Tensor contains no nonzero radiation values.")

    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")

    raw_values = tensor[nonzero_mask]

    # Use sqrt compression instead of log10.
    # This keeps weak regions visible but preserves strong leakage better than log.
    values = np.sqrt(raw_values)

    xs = X[nonzero_mask]
    ys = Y[nonzero_mask]
    zs = Z[nonzero_mask]

    # Keep stronger voxels. Lower value -> denser cloud, higher value -> sharper plume.
    threshold = np.percentile(values, 60)

    keep = values >= threshold

    xs = xs[keep]
    ys = ys[keep]
    zs = zs[keep]
    values = values[keep]

    max_points = 200_000
    if len(values) > max_points:
        idx = np.random.choice(len(values), max_points, replace=False)
        xs = xs[idx]
        ys = ys[idx]
        zs = zs[idx]
        values = values[idx]

    fig = go.Figure(
        data=go.Scatter3d(
            x=xs,
            y=ys,
            z=zs,
            mode="markers",
            marker=dict(
                size=2,
                color=values,
                colorscale="Inferno",
                opacity=0.45,
                colorbar=dict(title="sqrt(track length)")
            )
        )
    )

    fig.update_layout(
        title="3D radiation density map — sqrt-scaled nonzero voxel cloud",
        scene=dict(
            xaxis_title="x [m]",
            yaxis_title="y [m]",
            zaxis_title="z [m]",
            aspectmode="data",
        ),
    )

    fig.write_html(output_html)
    print(f"Wrote 3D point-cloud view to {output_html}")
    print(f"Rendered points: {len(values)}")


def plot_slice_slider(tensor, x, y, z, output_html):
    values = np.log10(tensor + 1e-12)

    frames = []

    for k in range(len(z)):
        frames.append(
            go.Frame(
                data=[
                    go.Heatmap(
                        z=values[:, :, k].T,
                        x=x,
                        y=y,
                        colorscale="Inferno",
                        zmin=np.min(values),
                        zmax=np.max(values),
                        colorbar=dict(title="log10(track length)")
                    )
                ],
                name=str(k),
            )
        )

    fig = go.Figure(
        data=[
            go.Heatmap(
                z=values[:, :, 0].T,
                x=x,
                y=y,
                colorscale="Inferno",
                zmin=np.min(values),
                zmax=np.max(values),
                colorbar=dict(title="log10(track length)")
            )
        ],
        frames=frames,
    )

    sliders = [
        dict(
            active=0,
            currentvalue={"prefix": "z slice: "},
            steps=[
                dict(
                    method="animate",
                    args=[
                        [str(k)],
                        dict(
                            mode="immediate",
                            frame=dict(duration=0, redraw=True),
                            transition=dict(duration=0),
                        ),
                    ],
                    label=f"{k} ({z[k]:.2f} m)",
                )
                for k in range(len(z))
            ],
        )
    ]

    fig.update_layout(
        title="Radiation density map — XY slices",
        xaxis_title="x [m]",
        yaxis_title="y [m]",
        yaxis=dict(scaleanchor="x", scaleratio=1),
        sliders=sliders,
    )

    fig.write_html(output_html)
    print(f"Wrote slice slider view to {output_html}")

def plot_leak_focus(tensor, x, y, z, output_html):
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")

    # Canister 3 center
    cx, cy, cz = 4.0, -3.0, 2.09

    # Focus around +x leak side
    focus_mask = (
        (X > cx + 0.2) & (X < cx + 3.5) &
        (Y > cy - 2.0) & (Y < cy + 2.0) &
        (Z > cz - 1.5) & (Z < cz + 1.5) &
        (tensor > 0.0)
    )

    if not np.any(focus_mask):
        raise RuntimeError("No nonzero voxels found in leak-focus region.")

    raw_values = tensor[focus_mask]
    values = np.sqrt(raw_values)

    xs = X[focus_mask]
    ys = Y[focus_mask]
    zs = Z[focus_mask]

    threshold = np.percentile(values, 40)

    keep = values >= threshold

    fig = go.Figure(
        data=go.Scatter3d(
            x=xs[keep],
            y=ys[keep],
            z=zs[keep],
            mode="markers",
            marker=dict(
                size=3,
                color=values[keep],
                colorscale="Inferno",
                opacity=0.65,
                colorbar=dict(title="sqrt(track length)")
            )
        )
    )

    fig.update_layout(
        title="Leak-focused radiation map near canister_3",
        scene=dict(
            xaxis_title="x [m]",
            yaxis_title="y [m]",
            zaxis_title="z [m]",
            aspectmode="data",
        ),
    )

    fig.write_html(output_html)
    print(f"Wrote leak-focused view to {output_html}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "csv_file",
        nargs="?",
        default="radiation_map.csv",
    )
    parser.add_argument(
        "--mode",
        choices=["volume", "slices", "both", "leak"],
        default="both",
    )
    parser.add_argument(
        "--out-prefix",
        default="radiation_map",
    )

    args = parser.parse_args()

    tensor, x, y, z = load_tensor(args.csv_file)

    print(f"Tensor shape: {tensor.shape}")
    print(f"Total track length: {tensor.sum():.6e} m")
    print(f"Max voxel value: {tensor.max():.6e} m")

    if args.mode in ["volume", "both"]:
        plot_volume(
            tensor,
            x,
            y,
            z,
            f"{args.out_prefix}_volume.html",
        )

    if args.mode in ["slices", "both"]:
        plot_slice_slider(
            tensor,
            x,
            y,
            z,
            f"{args.out_prefix}_slices.html",
        )


if __name__ == "__main__":
    main()