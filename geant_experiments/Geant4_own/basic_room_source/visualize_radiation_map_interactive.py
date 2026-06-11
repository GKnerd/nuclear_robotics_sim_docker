import argparse
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter
import plotly.graph_objects as go


def load_tensor(csv_file):
    df = pd.read_csv(csv_file)

    nx = df["ix"].max() + 1
    ny = df["iy"].max() + 1
    nz = df["iz"].max() + 1

    tensor = np.zeros((nx, ny, nz), dtype=np.float64)

    tensor[
        df["ix"].astype(int),
        df["iy"].astype(int),
        df["iz"].astype(int),
    ] = df["track_length_m"]

    x = np.sort(df["x_center_m"].unique())
    y = np.sort(df["y_center_m"].unique())
    z = np.sort(df["z_center_m"].unique())

    return tensor, x, y, z


def smooth_tensor(tensor, sigma):
    if sigma <= 0:
        return tensor

    return gaussian_filter(
        tensor,
        sigma=(sigma, sigma, sigma)
    )


def write_html_with_color_controls(fig, output_html, initial_cmin, initial_cmax):
    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
    )

    step = (initial_cmax - initial_cmin) / 1000.0
    if step <= 0:
        step = 1e-12

    control_panel = f"""
<div style="position:fixed; top:10px; left:10px; z-index:9999; background:white; padding:12px; border:1px solid #ccc; border-radius:8px; font-family:Arial; width:320px;">
  <b>Color range control</b><br><br>

  <label>cmin: <span id="cminVal">{initial_cmin:.4g}</span></label>
  <input id="cminSlider" type="range" min="{initial_cmin:.8g}" max="{initial_cmax:.8g}" step="{step:.8g}" value="{initial_cmin:.8g}" style="width:100%;">

  <label>cmax: <span id="cmaxVal">{initial_cmax:.4g}</span></label>
  <input id="cmaxSlider" type="range" min="{initial_cmin:.8g}" max="{initial_cmax:.8g}" step="{step:.8g}" value="{initial_cmax:.8g}" style="width:100%;">

  <button onclick="resetColor()" style="margin-top:8px;">Reset</button>
</div>

<script>
function updateColor() {{
    const cmin = parseFloat(document.getElementById("cminSlider").value);
    const cmax = parseFloat(document.getElementById("cmaxSlider").value);

    document.getElementById("cminVal").innerText = cmin.toPrecision(4);
    document.getElementById("cmaxVal").innerText = cmax.toPrecision(4);

    const graphDiv = document.querySelector(".plotly-graph-div");

    Plotly.restyle(graphDiv, {{
        "marker.cmin": [cmin],
        "marker.cmax": [cmax],
        "marker.cauto": [false],
        "zmin": [cmin],
        "zmax": [cmax],
        "zauto": [false]
    }});
}}

function resetColor() {{
    document.getElementById("cminSlider").value = {initial_cmin:.8g};
    document.getElementById("cmaxSlider").value = {initial_cmax:.8g};
    updateColor();
}}

document.getElementById("cminSlider").addEventListener("input", updateColor);
document.getElementById("cmaxSlider").addEventListener("input", updateColor);
</script>
"""

    html = html.replace("<body>", "<body>" + control_panel)

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)

    print("Wrote:", output_html)


def plot_slice_slider(tensor, x, y, z, output_html):
    values = np.log10(tensor + 1e-15)

    finite_values = values[np.isfinite(values)]
    initial_cmin = np.percentile(finite_values, 5)
    initial_cmax = np.percentile(finite_values, 95)

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
                        zmin=initial_cmin,
                        zmax=initial_cmax,
                        zauto=False,
                        colorbar=dict(title="log10(track length)")
                    )
                ],
                name=str(k)
            )
        )

    fig = go.Figure(
        data=[
            go.Heatmap(
                z=values[:, :, 0].T,
                x=x,
                y=y,
                colorscale="Inferno",
                zmin=initial_cmin,
                zmax=initial_cmax,
                zauto=False,
                colorbar=dict(title="log10(track length)")
            )
        ],
        frames=frames
    )

    sliders = [
        dict(
            active=0,
            currentvalue={"prefix": "z = "},
            steps=[
                dict(
                    method="animate",
                    args=[
                        [str(k)],
                        {
                            "mode": "immediate",
                            "frame": {
                                "duration": 0,
                                "redraw": True
                            },
                            "transition": {
                                "duration": 0
                            }
                        }
                    ],
                    label=f"{z[k]:.2f} m"
                )
                for k in range(len(z))
            ]
        )
    ]

    fig.update_layout(
        title="Radiation field slices",
        xaxis_title="x [m]",
        yaxis_title="y [m]",
        yaxis=dict(scaleanchor="x", scaleratio=1),
        sliders=sliders
    )

    write_html_with_color_controls(
        fig,
        output_html,
        initial_cmin,
        initial_cmax
    )


def plot_volume(tensor, x, y, z, output_html):
    X, Y, Z = np.meshgrid(
        x,
        y,
        z,
        indexing="ij"
    )

    mask = tensor > 0

    if not np.any(mask):
        raise RuntimeError("Tensor contains no nonzero values.")

    values_raw = tensor[mask]

    xs = X[mask]
    ys = Y[mask]
    zs = Z[mask]

    values = np.sqrt(values_raw)

    threshold = np.percentile(values, 60)
    keep = values >= threshold

    xs = xs[keep]
    ys = ys[keep]
    zs = zs[keep]
    values = values[keep]

    max_points = 200_000

    if len(values) > max_points:
        idx = np.random.choice(
            len(values),
            max_points,
            replace=False
        )

        xs = xs[idx]
        ys = ys[idx]
        zs = zs[idx]
        values = values[idx]

    initial_cmin = np.percentile(values, 5)
    initial_cmax = np.percentile(values, 95)

    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="markers",
                marker=dict(
                    size=2,
                    color=values,
                    colorscale="Inferno",
                    opacity=0.45,
                    cmin=initial_cmin,
                    cmax=initial_cmax,
                    cauto=False,
                    colorbar=dict(
                        title="sqrt(track length)"
                    )
                )
            )
        ]
    )

    fig.update_layout(
        title="3D radiation field",
        scene=dict(
            aspectmode="data",
            xaxis_title="x [m]",
            yaxis_title="y [m]",
            zaxis_title="z [m]"
        )
    )

    write_html_with_color_controls(
        fig,
        output_html,
        initial_cmin,
        initial_cmax
    )

    print(f"Rendered points: {len(values)}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "csv",
        nargs="?",
        default="radiation_map.csv"
    )

    parser.add_argument(
        "--mode",
        choices=["volume", "slices", "both"],
        default="both"
    )

    parser.add_argument(
        "--sigma",
        type=float,
        default=0.0,
        help="Gaussian smoothing sigma in voxel units."
    )

    parser.add_argument(
        "--prefix",
        default="radiation"
    )

    args = parser.parse_args()

    tensor, x, y, z = load_tensor(args.csv)

    print()
    print("Tensor shape :", tensor.shape)
    print("Raw max      :", tensor.max())
    print("Raw sum      :", tensor.sum())

    if args.sigma > 0:
        print(f"Applying Gaussian smoothing sigma={args.sigma}")

        tensor = smooth_tensor(
            tensor,
            args.sigma
        )

        print("Smoothed max :", tensor.max())
        print("Smoothed sum :", tensor.sum())

    if args.mode in ["volume", "both"]:
        plot_volume(
            tensor,
            x,
            y,
            z,
            f"{args.prefix}_volume.html"
        )

    if args.mode in ["slices", "both"]:
        plot_slice_slider(
            tensor,
            x,
            y,
            z,
            f"{args.prefix}_slices.html"
        )


if __name__ == "__main__":
    main()