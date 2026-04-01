import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from material_profiles import get_material_loss

EPS = 1e-9

BASE_DIR = Path(__file__).resolve().parent
SCENE_PATH = BASE_DIR / "sample_scene.json"
OUTPUT_DIR = BASE_DIR / "output"


def load_scene(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_wall(wall: dict) -> dict:
    if "x1" in wall and "y1" in wall and "x2" in wall and "y2" in wall:
        return {
            "id": wall["id"],
            "x1": float(wall["x1"]),
            "y1": float(wall["y1"]),
            "x2": float(wall["x2"]),
            "y2": float(wall["y2"]),
            "material": wall.get("material", "unknown"),
            "boundary": wall.get("boundary", False),
        }

    if "centerline_geom" in wall:
        coords = wall["centerline_geom"]["coordinates"]
        return {
            "id": wall["id"],
            "x1": float(coords[0][0]),
            "y1": float(coords[0][1]),
            "x2": float(coords[1][0]),
            "y2": float(coords[1][1]),
            "material": wall.get("material", "unknown"),
            "boundary": wall.get("wall_role") == "exterior",
        }

    raise ValueError(f"Unsupported wall format: {wall}")


def normalize_walls(walls: list[dict]) -> list[dict]:
    return [normalize_wall(w) for w in walls]


def generate_grid(bounds: dict, resolution: float = 0.5):
    width = bounds["width"]
    height = bounds["height"]

    x_coords = np.arange(0.0, width + resolution, resolution)
    y_coords = np.arange(0.0, height + resolution, resolution)

    xx, yy = np.meshgrid(x_coords, y_coords)
    points = np.column_stack([xx.ravel(), yy.ravel()])

    return x_coords, y_coords, xx, yy, points


def compute_distance(ap: dict, point: np.ndarray) -> float:
    dx = float(point[0]) - float(ap["x"])
    dy = float(point[1]) - float(ap["y"])
    distance = math.sqrt(dx * dx + dy * dy)

    return max(distance, 0.1)


def compute_path_loss(distance: float, a: float = 40.0, n: float = 2.0) -> float:
    return a + 10.0 * n * math.log10(distance)


def ccw(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a, b, c, eps: float = EPS) -> bool:
    return (
        min(a[0], b[0]) - eps <= c[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= c[1] <= max(a[1], b[1]) + eps
    )


def segments_intersect(p1, p2, q1, q2, eps: float = EPS) -> bool:
    d1 = ccw(p1, p2, q1)
    d2 = ccw(p1, p2, q2)
    d3 = ccw(q1, q2, p1)
    d4 = ccw(q1, q2, p2)

    if (d1 * d2 < 0) and (d3 * d4 < 0):
        return True

    if abs(d1) < eps and on_segment(p1, p2, q1, eps):
        return True
    if abs(d2) < eps and on_segment(p1, p2, q2, eps):
        return True
    if abs(d3) < eps and on_segment(q1, q2, p1, eps):
        return True
    if abs(d4) < eps and on_segment(q1, q2, p2, eps):
        return True

    return False


def get_crossed_walls(ap: dict, point: np.ndarray, walls: list) -> list:
    ap_point = (float(ap["x"]), float(ap["y"]))
    rx_point = (float(point[0]), float(point[1]))

    crossed = []

    for wall in walls:
        if wall.get("boundary", False):
            continue

        w1 = (float(wall["x1"]), float(wall["y1"]))
        w2 = (float(wall["x2"]), float(wall["y2"]))

        if segments_intersect(ap_point, rx_point, w1, w2):
            crossed.append(wall)

    return crossed


def compute_wall_loss(crossed_walls: list) -> float:
    total_loss = 0.0

    for wall in crossed_walls:
        material = wall.get("material", "")
        total_loss += get_material_loss(material)

    return total_loss


def compute_rssi(ap: dict, point: np.ndarray, walls: list) -> tuple[float, float, float, list]:
    distance = compute_distance(ap, point)
    path_loss = compute_path_loss(distance)
    crossed_walls = get_crossed_walls(ap, point, walls)
    wall_loss = compute_wall_loss(crossed_walls)

    rssi = float(ap["tx_power_dbm"]) - path_loss - wall_loss
    return rssi, path_loss, wall_loss, crossed_walls


def save_outputs(
    x_coords: np.ndarray,
    y_coords: np.ndarray,
    rssi_map: np.ndarray,
    path_loss_map: np.ndarray,
    wall_loss_map: np.ndarray,
    scene: dict,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    np.save(output_dir / "rssi_map.npy", rssi_map)
    np.save(output_dir / "path_loss_map.npy", path_loss_map)
    np.save(output_dir / "wall_loss_map.npy", wall_loss_map)

    fig, ax = plt.subplots(figsize=(10, 6))

    extent = [x_coords.min(), x_coords.max(), y_coords.min(), y_coords.max()]
    image = ax.imshow(
        rssi_map,
        origin="lower",
        extent=extent,
        aspect="auto",
    )

    plt.colorbar(image, ax=ax, label="RSSI (dBm)")

    ap = scene["ap"]
    walls = normalize_walls(scene["walls"])

    ax.scatter(ap["x"], ap["y"], marker="x", s=120, label=ap["id"])
    ax.text(ap["x"] + 0.1, ap["y"] + 0.1, ap["id"])

    for wall in walls:
        x1 = wall["x1"]
        x2 = wall["x2"]
        y1 = wall["y1"]
        y2 = wall["y2"]
        material = wall.get("material", "unknown")
        boundary = wall.get("boundary", False)

        ax.plot([x1, x2], [y1, y2], linewidth=2)

        mid_x = (x1 + x2) / 2.0
        mid_y = (y1 + y2) / 2.0

        label = f"{material} (boundary)" if boundary else material
        ax.text(mid_x, mid_y, label, fontsize=8)

    ax.set_title("Baseline RSSI Heatmap")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_dir / "rssi_heatmap.png", dpi=200)
    plt.close(fig)


def main():
    scene = load_scene(SCENE_PATH)

    bounds = scene["bounds"]
    ap = scene["ap"]
    walls = normalize_walls(scene["walls"])

    x_coords, y_coords, xx, yy, points = generate_grid(bounds, resolution=0.5)

    rssi_values = []
    path_loss_values = []
    wall_loss_values = []
    crossed_wall_ids = []

    for point in points:
        rssi, path_loss, wall_loss, crossed_walls = compute_rssi(
            ap, point, walls)
        rssi_values.append(rssi)
        path_loss_values.append(path_loss)
        wall_loss_values.append(wall_loss)
        crossed_wall_ids.append([wall["id"] for wall in crossed_walls])

    rssi_values = np.array(rssi_values)
    path_loss_values = np.array(path_loss_values)
    wall_loss_values = np.array(wall_loss_values)

    rssi_map = rssi_values.reshape(len(y_coords), len(x_coords))
    path_loss_map = path_loss_values.reshape(len(y_coords), len(x_coords))
    wall_loss_map = wall_loss_values.reshape(len(y_coords), len(x_coords))

    print("=== Scene Info ===")
    print(f"scene_version_id: {scene['scene_version_id']}")
    print(f"bounds: {bounds['width']}m x {bounds['height']}m")
    print()

    print("=== AP Info ===")
    print(f"AP id: {ap['id']}")
    print(f"AP position: ({ap['x']}, {ap['y']})")
    print(f"tx_power_dbm: {ap['tx_power_dbm']}")
    print(f"frequency_ghz: {ap['frequency_ghz']}")
    print()

    print("=== Grid Info ===")
    print(f"x count: {len(x_coords)}")
    print(f"y count: {len(y_coords)}")
    print(f"total points: {len(points)}")
    print()

    print("=== First 10 Grid Points ===")
    for point in points[:10]:
        print((float(point[0]), float(point[1])))
    print()

    print("=== RSSI Sample (First 10) ===")
    for idx, point in enumerate(points[:10]):
        print(
            f"point=({float(point[0])}, {float(point[1])}) "
            f"-> RSSI={rssi_values[idx]:.2f} dBm, "
            f"path_loss={path_loss_values[idx]:.2f} dB, "
            f"wall_loss={wall_loss_values[idx]:.2f} dB, "
            f"crossed={crossed_wall_ids[idx]}"
        )
    print()

    print("=== Map Shapes ===")
    print(f"rssi_map.shape = {rssi_map.shape}")
    print(f"path_loss_map.shape = {path_loss_map.shape}")
    print(f"wall_loss_map.shape = {wall_loss_map.shape}")
    print()

    print("=== RSSI Summary ===")
    print(f"min RSSI: {rssi_values.min():.2f} dBm")
    print(f"max RSSI: {rssi_values.max():.2f} dBm")
    print(f"mean RSSI: {rssi_values.mean():.2f} dBm")
    print()

    save_outputs(
        x_coords=x_coords,
        y_coords=y_coords,
        rssi_map=rssi_map,
        path_loss_map=path_loss_map,
        wall_loss_map=wall_loss_map,
        scene=scene,
        output_dir=OUTPUT_DIR,
    )

    print("=== Output Saved ===")
    print(f"rssi npy: {OUTPUT_DIR / 'rssi_map.npy'}")
    print(f"path loss npy: {OUTPUT_DIR / 'path_loss_map.npy'}")
    print(f"wall loss npy: {OUTPUT_DIR / 'wall_loss_map.npy'}")
    print(f"png: {OUTPUT_DIR / 'rssi_heatmap.png'}")


if __name__ == "__main__":
    main()
