import xml.etree.ElementTree as ET
import numpy as np


def parse_vec(text, n):
    vals = [float(v) for v in text.split()]
    if len(vals) != n:
        raise ValueError(f"Expected {n} values, got {text}")
    return np.array(vals)


def quat_to_yaw(q):
    # MuJoCo quat: w x y z
    w, x, y, z = q
    return np.arctan2(
        2.0 * (w * z + x * y),
        1.0 - 2.0 * (y * y + z * z)
    )


def rotate_z_axis_by_quat(q):
    # Rotate local cylinder axis (0,0,1) into world.
    w, x, y, z = q

    return np.array([
        2.0 * (x * z + w * y),
        2.0 * (y * z - w * x),
        1.0 - 2.0 * (x * x + y * y)
    ])


class OrientedBox2D:
    def __init__(self, center, half_size, yaw, inflation=0.0):
        self.center = np.array(center[:2], dtype=float)
        self.half_size = np.array(half_size[:2], dtype=float) + inflation
        self.yaw = yaw

        c = np.cos(-yaw)
        s = np.sin(-yaw)
        self.R_inv = np.array([[c, -s], [s, c]])

    def contains(self, p):
        local = self.R_inv @ (np.array(p[:2]) - self.center)
        return (
            abs(local[0]) <= self.half_size[0] and
            abs(local[1]) <= self.half_size[1]
        )


class Circle2D:
    def __init__(self, center, radius, inflation=0.0):
        self.center = np.array(center[:2], dtype=float)
        self.radius = radius + inflation

    def contains(self, p):
        return np.linalg.norm(np.array(p[:2]) - self.center) <= self.radius


class Capsule2D:
    def __init__(self, center, direction, half_length, radius, inflation=0.0):
        self.center = np.array(center[:2], dtype=float)

        d = np.array(direction[:2], dtype=float)
        n = np.linalg.norm(d)

        if n < 1e-9:
            d = np.array([1.0, 0.0])
        else:
            d = d / n

        self.a = self.center - half_length * d
        self.b = self.center + half_length * d
        self.radius = radius + inflation

    def contains(self, p):
        p = np.array(p[:2], dtype=float)
        ab = self.b - self.a
        t = np.dot(p - self.a, ab) / (np.dot(ab, ab) + 1e-12)
        t = np.clip(t, 0.0, 1.0)
        closest = self.a + t * ab
        return np.linalg.norm(p - closest) <= self.radius


class MujocoObstacleMap2D:
    def __init__(self, xml_file, robot_radius=0.35):
        self.xml_file = xml_file
        self.robot_radius = robot_radius
        self.obstacles = []
        self.load(xml_file)

    def load(self, xml_file):
        tree = ET.parse(xml_file)
        root = tree.getroot()

        worldbody = root.find("worldbody")
        if worldbody is None:
            raise RuntimeError("No <worldbody> found in MuJoCo XML.")

        for geom in worldbody.findall("geom"):
            name = geom.attrib.get("name", "")
            geom_type = geom.attrib.get("type", "")

            if name == "floor" or geom_type == "plane":
                continue

            if geom_type not in ["box", "cylinder"]:
                continue

            pos = parse_vec(geom.attrib.get("pos", "0 0 0"), 3)
            size = parse_vec(geom.attrib["size"], 2 if geom_type == "cylinder" else 3)

            quat = parse_vec(
                geom.attrib.get("quat", "1 0 0 0"),
                4
            )

            if geom_type == "box":
                yaw = quat_to_yaw(quat)

                self.obstacles.append(
                    OrientedBox2D(
                        center=pos,
                        half_size=size,
                        yaw=yaw,
                        inflation=self.robot_radius,
                    )
                )

            elif geom_type == "cylinder":
                radius = size[0]
                half_length = size[1]

                axis = rotate_z_axis_by_quat(quat)

                # Vertical cylinder -> circle footprint.
                if abs(axis[2]) > 0.7:
                    self.obstacles.append(
                        Circle2D(
                            center=pos,
                            radius=radius,
                            inflation=self.robot_radius,
                        )
                    )

                # Horizontal cylinder -> capsule footprint.
                else:
                    self.obstacles.append(
                        Capsule2D(
                            center=pos,
                            direction=axis[:2],
                            half_length=half_length,
                            radius=radius,
                            inflation=self.robot_radius,
                        )
                    )

    def is_free(self, x, y):
        p = np.array([x, y], dtype=float)
        return not any(obs.contains(p) for obs in self.obstacles)

    def segment_is_free(self, start, end, step=0.10):
        x0, y0 = start[:2]
        x1, y1 = end[:2]

        distance = np.hypot(x1 - x0, y1 - y0)
        n = max(2, int(np.ceil(distance / step)))

        for i in range(n + 1):
            t = i / n
            x = (1.0 - t) * x0 + t * x1
            y = (1.0 - t) * y0 + t * y1

            if not self.is_free(x, y):
                return False

        return True