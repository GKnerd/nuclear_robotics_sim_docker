import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


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

    x_centers = np.sort(df["x_center_m"].unique())
    y_centers = np.sort(df["y_center_m"].unique())
    z_centers = np.sort(df["z_center_m"].unique())

    return tensor, x_centers, y_centers, z_centers


def plot_slice_xy(tensor, x, y, z, z_index):
    img = tensor[:, :, z_index].T

    plt.figure(figsize=(7, 6))
    plt.imshow(
        img,
        origin="lower",
        extent=[x[0], x[-1], y[0], y[-1]],
        aspect="equal",
    )
    plt.colorbar(label="Accumulated gamma track length [m]")
    plt.xlabel("x [m]")
    plt.ylabel("y [m]")
    plt.title(f"Radiation map XY slice at z = {z[z_index]:.3f} m")
    plt.tight_layout()
    plt.show()


def plot_slice_xz(tensor, x, y, z, y_index):
    img = tensor[:, y_index, :].T

    plt.figure(figsize=(7, 5))
    plt.imshow(
        img,
        origin="lower",
        extent=[x[0], x[-1], z[0], z[-1]],
        aspect="auto",
    )
    plt.colorbar(label="Accumulated gamma track length [m]")
    plt.xlabel("x [m]")
    plt.ylabel("z [m]")
    plt.title(f"Radiation map XZ slice at y = {y[y_index]:.3f} m")
    plt.tight_layout()
    plt.show()


def plot_max_projection_xy(tensor, x, y):
    img = np.max(tensor, axis=2).T

    plt.figure(figsize=(7, 6))
    plt.imshow(
        img,
        origin="lower",
        extent=[x[0], x[-1], y[0], y[-1]],
        aspect="equal",
    )
    plt.colorbar(label="Max accumulated gamma track length [m]")
    plt.xlabel("x [m]")
    plt.ylabel("y [m]")
    plt.title("Maximum intensity projection onto XY plane")
    plt.tight_layout()
    plt.show()


def plot_log_slice_xy(tensor, x, y, z, z_index):
    img = tensor[:, :, z_index].T
    img = np.log10(img + 1e-12)

    plt.figure(figsize=(7, 6))
    plt.imshow(
        img,
        origin="lower",
        extent=[x[0], x[-1], y[0], y[-1]],
        aspect="equal",
    )
    plt.colorbar(label="log10(track length [m] + eps)")
    plt.xlabel("x [m]")
    plt.ylabel("y [m]")
    plt.title(f"Log radiation map XY slice at z = {z[z_index]:.3f} m")
    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "csv_file",
        nargs="?",
        default="radiation_map.csv",
        help="CSV file exported by Geant4",
    )
    parser.add_argument(
        "--mode",
        choices=["xy", "xz", "maxxy", "logxy"],
        default="logxy",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=None,
        help="Slice index. Defaults to center slice.",
    )

    args = parser.parse_args()

    tensor, x, y, z = load_tensor(args.csv_file)

    print(f"Loaded tensor shape: {tensor.shape}")
    print(f"Total accumulated track length: {tensor.sum():.6e} m")
    print(f"Max voxel value: {tensor.max():.6e} m")

    if args.mode in ["xy", "logxy"]:
        z_index = args.index if args.index is not None else tensor.shape[2] // 2
        if args.mode == "xy":
            plot_slice_xy(tensor, x, y, z, z_index)
        else:
            plot_log_slice_xy(tensor, x, y, z, z_index)

    elif args.mode == "xz":
        y_index = args.index if args.index is not None else tensor.shape[1] // 2
        plot_slice_xz(tensor, x, y, z, y_index)

    elif args.mode == "maxxy":
        plot_max_projection_xy(tensor, x, y)


if __name__ == "__main__":
    main()