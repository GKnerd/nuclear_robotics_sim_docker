import argparse
import json

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter


def load_csv(csv_file):
    df = pd.read_csv(csv_file)

    nx = int(df["ix"].max()) + 1
    ny = int(df["iy"].max()) + 1
    nz = int(df["iz"].max()) + 1

    tensor = np.zeros((nx, ny, nz), dtype=np.float32)

    tensor[
        df["ix"].astype(int),
        df["iy"].astype(int),
        df["iz"].astype(int)
    ] = df["track_length_m"].astype(np.float32)

    x = np.sort(df["x_center_m"].unique())
    y = np.sort(df["y_center_m"].unique())
    z = np.sort(df["z_center_m"].unique())

    return tensor, x, y, z


def apply_smoothing(tensor, sigma):
    if sigma <= 0:
        return tensor

    return gaussian_filter(
        tensor,
        sigma=(sigma, sigma, sigma)
    )


def save_tensor(
    tensor,
    x,
    y,
    z,
    output_prefix,
    sigma
):
    np.save(
        output_prefix + ".npy",
        tensor
    )

    metadata = {
        "shape": [
            int(tensor.shape[0]),
            int(tensor.shape[1]),
            int(tensor.shape[2])
        ],

        "x_min": float(x[0]),
        "x_max": float(x[-1]),

        "y_min": float(y[0]),
        "y_max": float(y[-1]),

        "z_min": float(z[0]),
        "z_max": float(z[-1]),

        "dx": float(x[1] - x[0]),
        "dy": float(y[1] - y[0]),
        "dz": float(z[1] - z[0]),

        "unit": "track_length_m",

        "smoothing_sigma_voxels": float(sigma),

        "storage_order": "tensor[ix, iy, iz]",

        "interpolation": "trilinear"
    }

    with open(
        output_prefix + ".json",
        "w"
    ) as f:
        json.dump(
            metadata,
            f,
            indent=4
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "csv",
        nargs="?",
        default="radiation_map.csv"
    )

    parser.add_argument(
        "--sigma",
        type=float,
        default=0.0,
        help="Gaussian smoothing sigma in voxel units."
    )

    parser.add_argument(
        "--output",
        default="radiation_field",
        help="Output prefix."
    )

    args = parser.parse_args()

    print()
    print("Loading CSV...")

    tensor, x, y, z = load_csv(
        args.csv
    )

    print(
        "Tensor shape:",
        tensor.shape
    )

    print(
        "Maximum value:",
        tensor.max()
    )

    print(
        "Sum:",
        tensor.sum()
    )

    if args.sigma > 0:
        print(
            f"Applying Gaussian smoothing (sigma={args.sigma})"
        )

        tensor = apply_smoothing(
            tensor,
            args.sigma
        )

        print(
            "Smoothed maximum:",
            tensor.max()
        )

    save_tensor(
        tensor,
        x,
        y,
        z,
        args.output,
        args.sigma
    )

    print()
    print(
        "Export finished."
    )
    print(
        f"Tensor : {args.output}.npy"
    )
    print(
        f"Metadata: {args.output}.json"
    )


if __name__ == "__main__":
    main()