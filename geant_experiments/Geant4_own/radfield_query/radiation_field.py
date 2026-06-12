import json
from pathlib import Path
from typing import Tuple

import numpy as np


class RadiationField:
    def __init__(self, field_prefix: str = "radiation_field"):
        npy_file, json_file = self._infer_files(field_prefix)

        self.field = np.load(npy_file)

        with open(json_file, "r", encoding="utf-8") as f:
            self.meta = json.load(f)

        self.nx, self.ny, self.nz = self.field.shape

        self.x_min = float(self.meta["x_min"])
        self.x_max = float(self.meta["x_max"])
        self.y_min = float(self.meta["y_min"])
        self.y_max = float(self.meta["y_max"])
        self.z_min = float(self.meta["z_min"])
        self.z_max = float(self.meta["z_max"])

    @staticmethod
    def _infer_files(field_prefix: str) -> Tuple[Path, Path]:
        prefix_path = Path(field_prefix)

        if prefix_path.suffix == ".npy":
            npy_file = prefix_path
            json_file = prefix_path.with_suffix(".json")
        else:
            npy_file = Path(str(prefix_path) + ".npy")
            json_file = Path(str(prefix_path) + ".json")

        if not npy_file.exists():
            raise FileNotFoundError(f"Missing tensor file: {npy_file}")

        if not json_file.exists():
            raise FileNotFoundError(f"Missing metadata file: {json_file}")

        return npy_file, json_file

    def contains(self, x: float, y: float, z: float) -> bool:
        return (
            self.x_min <= x <= self.x_max and
            self.y_min <= y <= self.y_max and
            self.z_min <= z <= self.z_max
        )

    def query(self, x: float, y: float, z: float) -> float:
        """
        Default runtime query.

        Uses trilinear interpolation.
        Returns 0.0 outside the radiation-field bounds.
        """
        value, valid = self.query_trilinear(x, y, z)
        return value if valid else 0.0

    def query_trilinear(self, x: float, y: float, z: float) -> Tuple[float, bool]:
        if not self.contains(x, y, z):
            return 0.0, False

        fx = (x - self.x_min) / (self.x_max - self.x_min) * (self.nx - 1)
        fy = (y - self.y_min) / (self.y_max - self.y_min) * (self.ny - 1)
        fz = (z - self.z_min) / (self.z_max - self.z_min) * (self.nz - 1)

        ix0 = int(np.floor(fx))
        iy0 = int(np.floor(fy))
        iz0 = int(np.floor(fz))

        ix1 = min(ix0 + 1, self.nx - 1)
        iy1 = min(iy0 + 1, self.ny - 1)
        iz1 = min(iz0 + 1, self.nz - 1)

        tx = fx - ix0
        ty = fy - iy0
        tz = fz - iz0

        c000 = self.field[ix0, iy0, iz0]
        c100 = self.field[ix1, iy0, iz0]
        c010 = self.field[ix0, iy1, iz0]
        c110 = self.field[ix1, iy1, iz0]
        c001 = self.field[ix0, iy0, iz1]
        c101 = self.field[ix1, iy0, iz1]
        c011 = self.field[ix0, iy1, iz1]
        c111 = self.field[ix1, iy1, iz1]

        c00 = c000 * (1.0 - tx) + c100 * tx
        c10 = c010 * (1.0 - tx) + c110 * tx
        c01 = c001 * (1.0 - tx) + c101 * tx
        c11 = c011 * (1.0 - tx) + c111 * tx

        c0 = c00 * (1.0 - ty) + c10 * ty
        c1 = c01 * (1.0 - ty) + c11 * ty

        value = c0 * (1.0 - tz) + c1 * tz

        return float(value), True

    def query_nearest(self, x: float, y: float, z: float) -> Tuple[float, bool]:
        if not self.contains(x, y, z):
            return 0.0, False

        ix = round((x - self.x_min) / (self.x_max - self.x_min) * (self.nx - 1))
        iy = round((y - self.y_min) / (self.y_max - self.y_min) * (self.ny - 1))
        iz = round((z - self.z_min) / (self.z_max - self.z_min) * (self.nz - 1))

        ix = int(np.clip(ix, 0, self.nx - 1))
        iy = int(np.clip(iy, 0, self.ny - 1))
        iz = int(np.clip(iz, 0, self.nz - 1))

        return float(self.field[ix, iy, iz]), True

    def query_detector_average(
        self,
        x: float,
        y: float,
        z: float,
        radius: float = 0.15,
        samples: int = 3,
    ) -> Tuple[float, bool]:
        """
        Approximate a finite detector volume by averaging several
        trilinear samples in a cube around the detector center.
        """
        offsets = np.linspace(-radius, radius, samples)

        values = []

        for dx in offsets:
            for dy in offsets:
                for dz in offsets:
                    value, valid = self.query_trilinear(
                        x + dx,
                        y + dy,
                        z + dz
                    )

                    if valid:
                        values.append(value)

        if not values:
            return 0.0, False

        return float(np.mean(values)), True