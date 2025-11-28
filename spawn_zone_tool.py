from __future__ import annotations
import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

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


def get_bounds_for_brush(brush, origin=(0.0, 0.0, 0.0)):
    """Compute min/max bounds for a brush."""
    ox, oy, oz = origin

    xs, ys, zs = [], [], []

    for face in brush.faces:
        pts = (face.plane_points.v0, face.plane_points.v1, face.plane_points.v2)
        for p in pts:
            xs.append(p.x + ox)
            ys.append(p.y + oy)
            zs.append(p.z + oz)

    if not xs:
        return None, None

    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


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
            mins, maxs = get_bounds_for_brush(brush)
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