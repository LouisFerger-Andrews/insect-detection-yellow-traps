from __future__ import annotations

from app.utils.geo import assign_grid_codes, point_in_polygon, polygon_area_m2


def test_polygon_area_and_point_membership() -> None:
    polygon = [
        (52.0, 5.0),
        (52.0, 5.001),
        (52.001, 5.001),
        (52.001, 5.0),
    ]
    area = polygon_area_m2(polygon)
    assert area > 0
    assert point_in_polygon(52.0005, 5.0005, polygon) is True
    assert point_in_polygon(52.01, 5.01, polygon) is False


def test_assign_grid_codes_produces_row_position_labels() -> None:
    traps = [
        ("t1", 52.0000, 5.0000),
        ("t2", 52.0000, 5.0001),
        ("t3", 51.9998, 5.0000),
        ("t4", 51.9998, 5.0001),
    ]
    mapped = assign_grid_codes(traps, row_tolerance_m=30.0)
    assert len(mapped) == 4
    assert all(code.startswith("R") and "-P" in code for _, _, _, code in mapped)

