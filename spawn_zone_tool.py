from __future__ import annotations
import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import sys
import math
import itertools

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from panda3d.core import Vec3
from p3d_libmap.map_parser import MapParser

ZONE_FORMAT_VERSION = "1.1.0"


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ZoneBrush:
    mins: Tuple[float, float, float]
    maxs: Tuple[float, float, float]


@dataclass
class Zone:
    name: str
    zone_id: int
    target: str
    fog: str = ""
    adjacent_zones: List[int] = field(default_factory=list)
    door_waypoint_targets: List[str] = field(default_factory=list)
    brushes: List[ZoneBrush] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Map utilities
# ---------------------------------------------------------------------------

def load_map_without_geo(path: Path):
    """Load a .map file but do not parse brush geometry."""
    parser = MapParser()
    parser.parser_load(str(path))
    return parser.map_data


def _vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

def _vec_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

def _vec_dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def _vec_cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )

def _vec_scale(v, s):
    return (v[0]*s, v[1]*s, v[2]*s)

def _vec_len(v):
    return math.sqrt(_vec_dot(v, v))

def _vec_norm(v):
    l = _vec_len(v)
    if l == 0.0:
        return (0.0, 0.0, 0.0)
    return (v[0]/l, v[1]/l, v[2]/l)

def _plane_from_face(face):
    # p1, p2, p3 are any 3 points on the plane
    p1 = (face.plane_points.v0.x, face.plane_points.v0.y, face.plane_points.v0.z)
    p2 = (face.plane_points.v1.x, face.plane_points.v1.y, face.plane_points.v1.z)
    p3 = (face.plane_points.v2.x, face.plane_points.v2.y, face.plane_points.v2.z)

    # normal = normalize((p3 - p1) x (p2 - p1))  (matches your format description)
    n = _vec_cross(_vec_sub(p3, p1), _vec_sub(p2, p1))
    n = _vec_norm(n)

    # Plane equation: n·x = d
    d = _vec_dot(n, p1)

    # Half-space rule from your docs:
    # points p where (p - p1)·n <= 0 are inside
    # => n·p <= n·p1 == d is inside
    return n, d

def _intersect_3_planes(p1, p2, p3, eps=1e-9):
    # Planes: n·x = d
    (n1, d1) = p1
    (n2, d2) = p2
    (n3, d3) = p3

    n2xn3 = _vec_cross(n2, n3)
    denom = _vec_dot(n1, n2xn3)

    if abs(denom) < eps:
        return None  # parallel / no single point intersection

    term1 = _vec_scale(n2xn3, d1)
    term2 = _vec_scale(_vec_cross(n3, n1), d2)
    term3 = _vec_scale(_vec_cross(n1, n2), d3)

    x = _vec_scale(_vec_add(_vec_add(term1, term2), term3), 1.0 / denom)
    return x

def get_vertices_for_brush(brush, epsilon=0.05):
    """
    Return a list of world-space vertices for a convex Quake brush by intersecting planes.
    epsilon is in Quake units.
    """
    planes = []
    for face in brush.faces:
        n, d = _plane_from_face(face)
        # Skip degenerate faces
        if _vec_len(n) == 0.0:
            continue
        planes.append((n, d))

    verts = []
    for i in range(len(planes)):
        for j in range(i + 1, len(planes)):
            for k in range(j + 1, len(planes)):
                p = _intersect_3_planes(planes[i], planes[j], planes[k])
                if p is None:
                    continue

                # Inside test: n·p <= d + epsilon for all planes
                inside = True
                for (n, d) in planes:
                    if _vec_dot(n, p) > d + epsilon:
                        inside = False
                        break
                if not inside:
                    continue

                # Dedupe near-identical points
                dup = False
                for q in verts:
                    if (abs(p[0] - q[0]) <= epsilon and
                        abs(p[1] - q[1]) <= epsilon and
                        abs(p[2] - q[2]) <= epsilon):
                        dup = True
                        break
                if not dup:
                    verts.append(p)

    return verts

def get_aabb_for_brush(brush, epsilon=0.05):
    verts = get_vertices_for_brush(brush, epsilon=epsilon)
    if not verts:
        return None, None

    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]

    mins = (min(xs), min(ys), min(zs))
    maxs = (max(xs), max(ys), max(zs))
    return mins, maxs


# ---------------------------------------------------------------------------
# Zone file output
# ---------------------------------------------------------------------------

def write_zones_to_file(zones: List[Zone], output_path: Path):
    """Write all zones to an .nsz file."""
    with output_path.open("w") as f:
        f.write(f"zone_file_version: {ZONE_FORMAT_VERSION}\n")
        f.write(f"number_of_zones: {len(zones)}\n")

        for zone in zones:
            f.write(f"{zone.name}\n")
            f.write(f"{zone.zone_id}\n")
            f.write(f"{zone.target}\n")
            f.write(f"{zone.fog}\n")

            f.write(f"{len(zone.adjacent_zones)}\n")
            for adj in zone.adjacent_zones:
                f.write(f"{adj}\n")

            f.write(f"{len(zone.brushes)}\n")
            for b in zone.brushes:
                f.write(f"{b.mins[0]} {b.mins[1]} {b.mins[2]}\n")
                f.write(f"{b.maxs[0]} {b.maxs[1]} {b.maxs[2]}\n")

            f.write(f"{len(zone.door_waypoint_targets)}\n")
            for d in zone.door_waypoint_targets:
                f.write(f"{d}\n")


# ---------------------------------------------------------------------------
# Main Processing Logic
# ---------------------------------------------------------------------------

def process_map(map_data):
    zone_name_to_id: Dict[str, int] = {}
    next_zone_id = 1
    zones: List[Zone] = []

    def get_id_for_zone(name: str) -> int:
        nonlocal next_zone_id
        if name not in zone_name_to_id:
            zone_name_to_id[name] = next_zone_id
            next_zone_id += 1
        return zone_name_to_id[name]

    print(f"Total entities: {len(map_data.entities)}\n")

    for ent in map_data.entities:
        if ent.properties.get("classname") != "spawn_zone":
            continue

        zone_name = ent.properties.get("zone_name")
        zone_target = ent.properties.get("zone_target")
        zone_fog = ent.properties.get("zone_fog", "")

        print(f"+ Found a spawn_zone entity:")
        print(f" - Name:         {zone_name}")
        print(f" - Target:       {zone_target}")
        print(f" - Fog:          [{zone_fog}]")

        # Resolve adjacent zones
        adjacents = ent.properties.get("adjacent_zones", "")
        adjacent_zones = [
            get_id_for_zone(z.strip())
            for z in adjacents.split(",")
            if z.strip()
        ]

        print(f" - Adjacent:     {adjacent_zones}")

        # Resolve door waypoint targets
        door_waypoints = ent.properties.get("door_way_targets", "")
        door_waypoint_targets = [
            z.strip() for z in door_waypoints.split(",") if z.strip()
        ]

        print(f" - Door Targets: {door_waypoint_targets}")

        # Zone brushes
        brushes = []
        for i, brush in enumerate(ent.brushes):
            mins, maxs = get_aabb_for_brush(brush)
            if mins is None or maxs is None:
                print(f"   * Brush {i}: (no points?)")
                continue

            brushes.append(ZoneBrush(mins=mins, maxs=maxs))
            print(f"   * Brush {i}: mins={mins}, maxs={maxs}")

        zone_id = get_id_for_zone(zone_name)

        zones.append(
            Zone(
                name=zone_name,
                zone_id=zone_id,
                target=zone_target,
                fog=zone_fog,
                adjacent_zones=adjacent_zones,
                door_waypoint_targets=door_waypoint_targets,
                brushes=brushes,
            )
        )

        print()

    return zones


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Creates NSZ (NZ:P Spawn Zones) file for use in maps.")
    parser.add_argument(
        "map_file",
        type=Path,
        nargs="?",
        help="Path to the .map file to create NSZ from",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output path for NSZ"
    )

    args = parser.parse_args()

    print(f"Loading map: {args.map_file}")
    map_data = load_map_without_geo(args.map_file)

    zones = process_map(map_data)

    print(f"Writing {len(zones)} zones to: {args.output}")
    write_zones_to_file(zones, args.output)


if __name__ == "__main__":
    main()
