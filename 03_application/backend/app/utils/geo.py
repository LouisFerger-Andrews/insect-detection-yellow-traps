from __future__ import annotations

from math import atan2, cos, log, pi, sin
from typing import Iterable, List, Tuple


def latlng_to_web_mercator(lat: float, lng: float) -> tuple[float, float]:
    x = lng * 20037508.34 / 180.0
    clamped_lat = max(min(lat, 89.5), -89.5)
    y = clamped_lat * pi / 180.0
    y = 6378137.0 * (0.5 * log((1.0 + sin(y)) / (1.0 - sin(y))))
    return x, y


def polygon_area_m2(polygon_latlng: Iterable[tuple[float, float]]) -> float:
    points = list(polygon_latlng)
    if len(points) < 3:
        return 0.0
    xy = [latlng_to_web_mercator(lat, lng) for lat, lng in points]
    area = 0.0
    for idx in range(len(xy)):
        x1, y1 = xy[idx]
        x2, y2 = xy[(idx + 1) % len(xy)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def point_in_polygon(lat: float, lng: float, polygon_latlng: List[tuple[float, float]]) -> bool:
    inside = False
    n = len(polygon_latlng)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = polygon_latlng[i][0], polygon_latlng[i][1]
        yj, xj = polygon_latlng[j][0], polygon_latlng[j][1]
        intersect = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) + 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def _principal_axis(points_xy: List[tuple[float, float]]) -> tuple[float, float]:
    if len(points_xy) < 2:
        return 1.0, 0.0

    mean_x = sum(x for x, _ in points_xy) / len(points_xy)
    mean_y = sum(y for _, y in points_xy) / len(points_xy)

    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    for x, y in points_xy:
        dx = x - mean_x
        dy = y - mean_y
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy

    # Principal component orientation for 2x2 covariance matrix.
    theta = 0.5 * atan2(2.0 * sxy, sxx - syy)
    return cos(theta), sin(theta)


def assign_grid_codes(traps: List[tuple[str, float, float]], row_tolerance_m: float = 8.0) -> List[tuple[str, int, int, str]]:
    if not traps:
        return []
    points = []
    for trap_id, lat, lng in traps:
        x, y = latlng_to_web_mercator(lat, lng)
        points.append({'id': trap_id, 'lat': lat, 'lng': lng, 'x': x, 'y': y})

    ux, uy = _principal_axis([(item['x'], item['y']) for item in points])
    # Perpendicular axis is used to separate rows.
    vx, vy = -uy, ux

    for point in points:
        point['u'] = point['x'] * ux + point['y'] * uy
        point['v'] = point['x'] * vx + point['y'] * vy

    # Sort by row axis first (higher v = earlier row), then along-row axis (u).
    points.sort(key=lambda item: (-item['v'], item['u']))

    rows: List[List[dict]] = []
    for point in points:
        placed = False
        for row in rows:
            avg_v = sum(item['v'] for item in row) / len(row)
            if abs(point['v'] - avg_v) <= row_tolerance_m:
                row.append(point)
                placed = True
                break
        if not placed:
            rows.append([point])

    output: List[tuple[str, int, int, str]] = []
    for row_idx, row in enumerate(rows, start=1):
        row.sort(key=lambda item: item['u'])
        for pos_idx, point in enumerate(row, start=1):
            output.append((point['id'], row_idx, pos_idx, f'R{row_idx}-P{pos_idx}'))
    return output
