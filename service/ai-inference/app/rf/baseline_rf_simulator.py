from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from object_obstacle_rules import los_intersects_object_footprint, resolve_object_loss_db
from rf_materials import MaterialProfileRegistry
from rf_models import (
    AccessPoint,
    ApLayout,
    Opening,
    Point2D,
    Scene,
    SimulationConfig,
)
from rf_persistence import JsonPersistenceStore

EPS = 1e-9

# objects[] LOS·footprint 기반 장애물 추가 손실 합산 상한 [dB] (preview, docs/BASELINE_OBJECTS_OBSTACLE_RULES.md)
_MAX_OBJECT_OBSTACLE_DB = 25.0

# Baseline coverage: 격자점별 strongest RSSI에 대한 단순 비율 (802.11 추천 임계값 근사)
_RSSI_GOOD_DB = -67.0
_RSSI_OK_DB = -70.0
_RSSI_DEAD_DB = -75.0


def compute_rssi_coverage_summary(strongest_rssi_flat: np.ndarray) -> dict[str, float]:
    """Strongest RSSI 샘플(1D)에 대한 커버리지·데드존 비율."""
    if strongest_rssi_flat.size == 0:
        return {
            "fraction_rssi_ge_neg67_dbm": 0.0,
            "fraction_rssi_ge_neg70_dbm": 0.0,
            "dead_zone_fraction_lt_neg75_dbm": 0.0,
        }
    r = strongest_rssi_flat.astype(float)
    return {
        "fraction_rssi_ge_neg67_dbm": float(np.mean(r >= _RSSI_GOOD_DB)),
        "fraction_rssi_ge_neg70_dbm": float(np.mean(r >= _RSSI_OK_DB)),
        "dead_zone_fraction_lt_neg75_dbm": float(np.mean(r < _RSSI_DEAD_DB)),
    }


@dataclass(frozen=True)
class SimulationResult:
    x_coords: np.ndarray
    y_coords: np.ndarray
    strongest_rssi_map: np.ndarray
    best_server_map: np.ndarray
    strongest_path_loss_map: np.ndarray
    strongest_wall_loss_map: np.ndarray
    per_ap_rssi_maps: dict[str, np.ndarray]
    bounds: tuple[float, float, float, float]
    metrics: dict


class BaselineRfSimulator:
    """Simple and explainable RF simulator for capstone preview and demos.

    Model assumptions:
    - 2D single-floor simulation
    - distance-based path loss
    - additive wall attenuation by material
    - strongest-AP serving model
    - openings remove wall loss when the line of sight crosses the opening segment
    - objects[] 2D footprint: extra loss when AP–Rx LOS intersects footprint (see object_obstacle_rules)
    """

    def __init__(
        self,
        scene: Scene,
        ap_layout: ApLayout,
        config: SimulationConfig,
        material_registry: MaterialProfileRegistry | None = None,
    ) -> None:
        if scene.scene_version_id != ap_layout.scene_version_id:
            raise ValueError(
                "scene.scene_version_id and ap_layout.scene_version_id must match")
        if scene.scene_version_id != config.scene_version_id:
            raise ValueError(
                "scene.scene_version_id and config.scene_version_id must match")

        self.scene = scene
        self.ap_layout = ap_layout
        self.config = config
        self.material_registry = material_registry or MaterialProfileRegistry()
        self._openings_by_wall = self._group_openings_by_wall(scene.openings)

    def run(self) -> SimulationResult:
        x_coords, y_coords, points, bounds = self._generate_grid()
        point_count = len(points)
        ap_count = len(self.ap_layout.aps)

        rssi_per_ap = np.zeros((ap_count, point_count), dtype=float)
        path_loss_per_ap = np.zeros((ap_count, point_count), dtype=float)
        wall_loss_per_ap = np.zeros((ap_count, point_count), dtype=float)

        for ap_idx, ap in enumerate(self.ap_layout.aps):
            for point_idx, point in enumerate(points):
                rssi, path_loss, wall_loss = self._compute_link_budget(
                    ap, point)
                rssi_per_ap[ap_idx, point_idx] = rssi
                path_loss_per_ap[ap_idx, point_idx] = path_loss
                wall_loss_per_ap[ap_idx, point_idx] = wall_loss

        best_server_indices = np.argmax(rssi_per_ap, axis=0)
        strongest_rssi = rssi_per_ap[best_server_indices, np.arange(
            point_count)]
        strongest_path_loss = path_loss_per_ap[best_server_indices, np.arange(
            point_count)]
        strongest_wall_loss = wall_loss_per_ap[best_server_indices, np.arange(
            point_count)]

        x_size = len(x_coords)
        y_size = len(y_coords)

        strongest_rssi_map = strongest_rssi.reshape(y_size, x_size)
        strongest_path_loss_map = strongest_path_loss.reshape(y_size, x_size)
        strongest_wall_loss_map = strongest_wall_loss.reshape(y_size, x_size)
        best_server_map = best_server_indices.reshape(y_size, x_size)

        per_ap_rssi_maps = {
            ap.ap_id: rssi_per_ap[idx].reshape(y_size, x_size)
            for idx, ap in enumerate(self.ap_layout.aps)
        }

        metrics = self._build_metrics(
            strongest_rssi=strongest_rssi,
            strongest_path_loss=strongest_path_loss,
            strongest_wall_loss=strongest_wall_loss,
            best_server_indices=best_server_indices,
            x_coords=x_coords,
            y_coords=y_coords,
        )

        return SimulationResult(
            x_coords=x_coords,
            y_coords=y_coords,
            strongest_rssi_map=strongest_rssi_map,
            best_server_map=best_server_map,
            strongest_path_loss_map=strongest_path_loss_map,
            strongest_wall_loss_map=strongest_wall_loss_map,
            per_ap_rssi_maps=per_ap_rssi_maps,
            bounds=bounds,
            metrics=metrics,
        )

    def _generate_grid(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, float, float, float]]:
        min_x, max_x, min_y, max_y = self.scene.bounds()
        resolution = self.config.grid_resolution_m

        x_coords = np.arange(min_x, max_x + resolution, resolution)
        y_coords = np.arange(min_y, max_y + resolution, resolution)
        xx, yy = np.meshgrid(x_coords, y_coords)
        points = np.column_stack([xx.ravel(), yy.ravel()])

        return x_coords, y_coords, points, (min_x, max_x, min_y, max_y)

    def _compute_link_budget(self, ap: AccessPoint, point_array: np.ndarray) -> tuple[float, float, float]:
        rx_point = Point2D(x=float(point_array[0]), y=float(point_array[1]))
        distance = max(self._euclidean_distance(ap.position, rx_point), 0.1)
        path_loss = self._compute_path_loss(distance)
        wall_loss = self._compute_wall_loss(ap.position, rx_point)
        obstacle_loss = self._compute_obstacle_loss_on_los(ap.position, rx_point)
        rssi = ap.tx_power_dbm - path_loss - wall_loss - obstacle_loss
        return rssi, path_loss, wall_loss

    def _compute_obstacle_loss_on_los(self, ap_point: Point2D, rx_point: Point2D) -> float:
        """AP–수신 직선이 object 2D footprint 와 겹칠 때 추가 감쇠(객체당 1회, 합산 상한)."""
        total = 0.0
        for obj in self.scene.objects:
            if not isinstance(obj, dict):
                continue
            if not los_intersects_object_footprint(
                ap_point.x, ap_point.y, rx_point.x, rx_point.y, obj
            ):
                continue
            total += resolve_object_loss_db(obj)
        return min(total, _MAX_OBJECT_OBSTACLE_DB)

    def _compute_path_loss(self, distance_m: float) -> float:
        return (
            self.config.path_loss_constant_db
            + 10.0 * self.config.path_loss_exponent * math.log10(distance_m)
        )

    def _compute_wall_loss(self, ap_point: Point2D, rx_point: Point2D) -> float:
        total_loss = 0.0
        for wall in self.scene.walls:
            if wall.is_exterior and not self.config.include_exterior_walls:
                continue
            if not self._segments_intersect(ap_point, rx_point, wall.start, wall.end):
                continue
            if self._line_of_sight_uses_opening(ap_point, rx_point, wall.wall_id):
                continue
            total_loss += self.material_registry.get_loss_db(wall.material)
        return total_loss

    def _line_of_sight_uses_opening(self, ap_point: Point2D, rx_point: Point2D, wall_id: str) -> bool:
        for opening in self._openings_by_wall.get(wall_id, []):
            if self._segments_intersect(ap_point, rx_point, opening.start, opening.end):
                return True
        return False

    @staticmethod
    def _euclidean_distance(a: Point2D, b: Point2D) -> float:
        dx = a.x - b.x
        dy = a.y - b.y
        return math.sqrt(dx * dx + dy * dy)

    def _group_openings_by_wall(self, openings: Iterable[Opening]) -> dict[str, list[Opening]]:
        grouped: dict[str, list[Opening]] = {}
        for opening in openings:
            grouped.setdefault(opening.wall_id, []).append(opening)
        return grouped

    @staticmethod
    def _ccw(a: Point2D, b: Point2D, c: Point2D) -> float:
        return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)

    @classmethod
    def _on_segment(cls, a: Point2D, b: Point2D, c: Point2D, eps: float = EPS) -> bool:
        return (
            min(a.x, b.x) - eps <= c.x <= max(a.x, b.x) + eps
            and min(a.y, b.y) - eps <= c.y <= max(a.y, b.y) + eps
        )

    @classmethod
    def _segments_intersect(
        cls,
        p1: Point2D,
        p2: Point2D,
        q1: Point2D,
        q2: Point2D,
        eps: float = EPS,
    ) -> bool:
        d1 = cls._ccw(p1, p2, q1)
        d2 = cls._ccw(p1, p2, q2)
        d3 = cls._ccw(q1, q2, p1)
        d4 = cls._ccw(q1, q2, p2)

        if (d1 * d2 < 0) and (d3 * d4 < 0):
            return True
        if abs(d1) < eps and cls._on_segment(p1, p2, q1, eps):
            return True
        if abs(d2) < eps and cls._on_segment(p1, p2, q2, eps):
            return True
        if abs(d3) < eps and cls._on_segment(q1, q2, p1, eps):
            return True
        if abs(d4) < eps and cls._on_segment(q1, q2, p2, eps):
            return True
        return False

    def _build_metrics(
        self,
        strongest_rssi: np.ndarray,
        strongest_path_loss: np.ndarray,
        strongest_wall_loss: np.ndarray,
        best_server_indices: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
    ) -> dict:
        serving_counts = {
            self.ap_layout.aps[idx].ap_id: int(
                np.sum(best_server_indices == idx))
            for idx in range(len(self.ap_layout.aps))
        }
        serving_ratios = {
            ap_id: count / float(len(best_server_indices))
            for ap_id, count in serving_counts.items()
        }
        coverage_summary = compute_rssi_coverage_summary(strongest_rssi)
        return {
            "scene_version_id": self.scene.scene_version_id,
            "layout_name": self.ap_layout.layout_name,
            "grid": {
                "resolution_m": self.config.grid_resolution_m,
                "x_count": int(len(x_coords)),
                "y_count": int(len(y_coords)),
                "point_count": int(len(best_server_indices)),
            },
            "rssi_summary": {
                "min_dbm": float(np.min(strongest_rssi)),
                "max_dbm": float(np.max(strongest_rssi)),
                "mean_dbm": float(np.mean(strongest_rssi)),
            },
            "coverage_summary": {
                **coverage_summary,
                "thresholds_dbm": {
                    "good_ge": _RSSI_GOOD_DB,
                    "ok_ge": _RSSI_OK_DB,
                    "dead_lt": _RSSI_DEAD_DB,
                },
                "description": (
                    "Grid-point fractions of strongest RSSI (baseline path loss + wall loss)."
                ),
            },
            "path_loss_summary": {
                "min_db": float(np.min(strongest_path_loss)),
                "max_db": float(np.max(strongest_path_loss)),
                "mean_db": float(np.mean(strongest_path_loss)),
            },
            "wall_loss_summary": {
                "min_db": float(np.min(strongest_wall_loss)),
                "max_db": float(np.max(strongest_wall_loss)),
                "mean_db": float(np.mean(strongest_wall_loss)),
            },
            "serving_ap_distribution": {
                "counts": serving_counts,
                "ratios": serving_ratios,
            },
        }


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def save_outputs(
    scene: Scene,
    ap_layout: ApLayout,
    config: SimulationConfig,
    result: SimulationResult,
    output_dir: Path,
    *,
    skip_heatmap: bool = False,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    strongest_rssi_path = output_dir / "strongest_rssi_map.npy"
    strongest_path_loss_path = output_dir / "strongest_path_loss_map.npy"
    strongest_wall_loss_path = output_dir / "strongest_wall_loss_map.npy"
    best_server_path = output_dir / "best_server_map.npy"

    np.save(strongest_rssi_path, result.strongest_rssi_map)
    np.save(strongest_path_loss_path, result.strongest_path_loss_map)
    np.save(strongest_wall_loss_path, result.strongest_wall_loss_map)
    np.save(best_server_path, result.best_server_map)

    per_ap_files: dict[str, str] = {}
    for ap_id, ap_map in result.per_ap_rssi_maps.items():
        ap_path = output_dir / f"rssi_map_{ap_id}.npy"
        np.save(ap_path, ap_map)
        per_ap_files[ap_id] = ap_path.name

    heatmap_path = output_dir / "strongest_rssi_heatmap.png"
    if not skip_heatmap:
        _plot_heatmap(scene=scene, ap_layout=ap_layout,
                      result=result, save_path=heatmap_path)

    artifacts: dict[str, Any] = {
        "strongest_rssi_map": strongest_rssi_path.name,
        "strongest_path_loss_map": strongest_path_loss_path.name,
        "strongest_wall_loss_map": strongest_wall_loss_path.name,
        "best_server_map": best_server_path.name,
        "per_ap_rssi_maps": per_ap_files,
    }
    if not skip_heatmap:
        artifacts["heatmap_png"] = heatmap_path.name

    manifest = {
        "scene_version_id": scene.scene_version_id,
        "layout_name": ap_layout.layout_name,
        "config": {
            "grid_resolution_m": config.grid_resolution_m,
            "path_loss_constant_db": config.path_loss_constant_db,
            "path_loss_exponent": config.path_loss_exponent,
            "include_exterior_walls": config.include_exterior_walls,
        },
        "bounds": {
            "min_x": result.bounds[0],
            "max_x": result.bounds[1],
            "min_y": result.bounds[2],
            "max_y": result.bounds[3],
        },
        "artifacts": artifacts,
        "metrics": result.metrics,
    }
    save_json(output_dir / "run_manifest.json", manifest)
    return manifest


def _plot_heatmap(
    scene: Scene,
    ap_layout: ApLayout,
    result: SimulationResult,
    save_path: Path,
) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 7))
    min_x, max_x, min_y, max_y = result.bounds
    extent = [min_x, max_x, min_y, max_y]

    image = ax.imshow(
        result.strongest_rssi_map,
        origin="lower",
        extent=extent,
        aspect="auto",
    )
    plt.colorbar(image, ax=ax, label="Strongest RSSI (dBm)")

    for room in scene.rooms:
        xs = [point.x for point in room.polygon]
        ys = [point.y for point in room.polygon]
        ax.plot(xs, ys, linestyle="--", linewidth=1)
        if room.centroid is not None:
            ax.text(room.centroid.x, room.centroid.y,
                    room.room_name, fontsize=8, ha="center")

    for wall in scene.walls:
        label = wall.material if not wall.is_exterior else f"{wall.material} (ext)"
        ax.plot([wall.start.x, wall.end.x], [
                wall.start.y, wall.end.y], linewidth=2.5)
        ax.text(
            (wall.start.x + wall.end.x) / 2.0,
            (wall.start.y + wall.end.y) / 2.0,
            label,
            fontsize=8,
        )

    for opening in scene.openings:
        ax.plot(
            [opening.start.x, opening.end.x],
            [opening.start.y, opening.end.y],
            linewidth=4,
        )
        ax.text(
            (opening.start.x + opening.end.x) / 2.0,
            (opening.start.y + opening.end.y) / 2.0,
            opening.opening_type,
            fontsize=8,
            va="bottom",
        )

    for ap in ap_layout.aps:
        ax.scatter(ap.position.x, ap.position.y,
                   marker="x", s=120, label=ap.ap_name)
        ax.text(ap.position.x + 0.1, ap.position.y + 0.1, ap.ap_name)

    ax.set_title("Baseline RF Preview - Strongest RSSI Heatmap")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(save_path, dpi=200)
    plt.close(fig)


def print_run_summary(scene: Scene, ap_layout: ApLayout, config: SimulationConfig, result: SimulationResult) -> None:
    print("=== RF Baseline Simulation ===")
    print(f"units             : {scene.units}")
    print(f"sourceType        : {scene.source_type}")
    print(f"scene_version_id : {scene.scene_version_id}")
    print(f"floor_id          : {scene.floor_id}")
    print(f"layout_name       : {ap_layout.layout_name}")
    print(f"ap_count          : {len(ap_layout.aps)}")
    print(f"grid_resolution_m : {config.grid_resolution_m}")
    print(f"walls             : {len(scene.walls)}")
    print(f"openings          : {len(scene.openings)}")
    print(f"rooms             : {len(scene.rooms)}")
    print()
    print("=== Bounds ===")
    print(
        f"min_x={result.bounds[0]:.2f}, max_x={result.bounds[1]:.2f}, "
        f"min_y={result.bounds[2]:.2f}, max_y={result.bounds[3]:.2f}"
    )
    print()
    print("=== Metrics ===")
    print(json.dumps(result.metrics, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the baseline RF preview simulator.")
    parser.add_argument("--scene", type=Path, required=True,
                        help="Path to rf_scene_input.json")
    parser.add_argument("--layout", type=Path, required=True,
                        help="Path to ap_layout_input.json")
    parser.add_argument("--config", type=Path, required=True,
                        help="Path to sim_config.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scene = Scene.from_dict(load_json(args.scene))
    layout = ApLayout.from_dict(load_json(args.layout))
    config = SimulationConfig.from_dict(load_json(args.config))

    simulator = BaselineRfSimulator(
        scene=scene, ap_layout=layout, config=config)
    result = simulator.run()

    output_dir = args.config.parent / config.output_dir_name
    manifest = save_outputs(
        scene=scene,
        ap_layout=layout,
        config=config,
        result=result,
        output_dir=output_dir,
    )

    floor_id = scene.floor_id or "unknown_floor"
    persistence_root = args.config.parent / "persistence"
    store = JsonPersistenceStore(persistence_root)
    rf_run = store.create_rf_run(
        scene_version_id=scene.scene_version_id,
        floor_id=floor_id,
        run_type="preview",
        engine_name="baseline",
        engine_version="baseline-0.1",
        project_id=None,
        job_id=None,
        ap_candidates_json=None,
        sim_config_json={
            "grid_resolution_m": config.grid_resolution_m,
            "path_loss_constant_db": config.path_loss_constant_db,
            "path_loss_exponent": config.path_loss_exponent,
            "include_exterior_walls": config.include_exterior_walls,
            "output_dir_name": config.output_dir_name,
        },
        output_root=str(output_dir.resolve()),
    )
    placements_json = [
        {
            "ap_id": ap.ap_id,
            "ap_name": ap.ap_name,
            "x_m": ap.position.x,
            "y_m": ap.position.y,
            "z_m": ap.z_m,
            "tx_power_dbm": ap.tx_power_dbm,
            "frequency_ghz": ap.frequency_ghz,
        }
        for ap in layout.aps
    ]
    store.save_ap_layout(
        rf_run_id=rf_run.id,
        layout_name=layout.layout_name,
        layout_type=layout.layout_type,
        placements_json=placements_json,
    )
    store.finish_rf_run(
        rf_run_id=rf_run.id,
        status="succeeded",
        metrics_json=manifest["metrics"],
    )
    store.save_maps_from_manifest(
        rf_run_id=rf_run.id,
        manifest=manifest,
        output_dir=output_dir,
    )

    print_run_summary(scene=scene, ap_layout=layout,
                      config=config, result=result)
    print()
    print(f"Output directory: {output_dir}")
    print(f"Persistence directory: {persistence_root.resolve()}")


if __name__ == "__main__":
    main()
