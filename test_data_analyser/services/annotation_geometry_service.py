"""Annotation geometry helpers.

Framework-independent geometry used for annotation hit-testing and handle
placement. No Qt and no Matplotlib: callers pass already-transformed pixel
coordinates for pixel-distance checks, and plain annotation dictionaries for
data-space handle points. Keeping this math here makes it unit-testable in
isolation from the plot workspace widget.
"""
from __future__ import annotations

import math
from typing import Any, cast

from ..domain.annotations import ANNOTATION_ARROW, ANNOTATION_BOX, ANNOTATION_TEXT


def annotation_float(annotation: dict[str, object], key: str, default: float = 0.0) -> float:
    """Coerce an annotation field to ``float``, falling back to ``default``."""
    try:
        return float(cast(Any, annotation.get(key, default)))
    except (TypeError, ValueError):
        return default


def annotation_handle_points(annotation: dict[str, object]) -> dict[str, tuple[float, float]]:
    """Return the data-space handle points for an arrow or box annotation.

    Text annotations (and any unknown type) have no handles and return ``{}``.
    """
    annotation_type = str(annotation.get("type", ""))
    if annotation_type == ANNOTATION_ARROW:
        return {
            "start": (annotation_float(annotation, "start_x"), annotation_float(annotation, "start_y")),
            "end": (annotation_float(annotation, "end_x"), annotation_float(annotation, "end_y")),
        }
    if annotation_type == ANNOTATION_BOX:
        x_min = annotation_float(annotation, "x_min")
        x_max = annotation_float(annotation, "x_max")
        y_min = annotation_float(annotation, "y_min")
        y_max = annotation_float(annotation, "y_max")
        return {
            "bottom_left": (x_min, y_min),
            "bottom_right": (x_max, y_min),
            "top_left": (x_min, y_max),
            "top_right": (x_max, y_max),
        }
    return {}


def point_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Euclidean distance between two pixel points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def distance_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Shortest distance from ``point`` to the segment ``start``-``end`` (pixels).

    Projects ``point`` onto the segment, clamping the projection parameter to
    ``[0, 1]`` so points beyond either end measure to the nearest endpoint.
    """
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return math.hypot(px - sx, py - sy)
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)))
    closest_x = sx + t * dx
    closest_y = sy + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def move_annotation(annotation: dict[str, object], original: dict[str, object], dx: float, dy: float) -> None:
    """Translate an annotation by ``(dx, dy)`` in data coordinates, in place."""
    annotation_type = str(annotation.get("type", ""))
    if annotation_type == ANNOTATION_TEXT:
        annotation["x"] = annotation_float(original, "x") + dx
        annotation["y"] = annotation_float(original, "y") + dy
    elif annotation_type == ANNOTATION_ARROW:
        for point in ("start", "end"):
            annotation[f"{point}_x"] = annotation_float(original, f"{point}_x") + dx
            annotation[f"{point}_y"] = annotation_float(original, f"{point}_y") + dy
    elif annotation_type == ANNOTATION_BOX:
        annotation["x_min"] = annotation_float(original, "x_min") + dx
        annotation["x_max"] = annotation_float(original, "x_max") + dx
        annotation["y_min"] = annotation_float(original, "y_min") + dy
        annotation["y_max"] = annotation_float(original, "y_max") + dy


def resize_box_annotation(
    annotation: dict[str, object],
    original: dict[str, object],
    mode: str,
    current: tuple[float, float],
) -> None:
    """Resize a box annotation by dragging the ``mode`` edge/corner, in place.

    ``mode`` combines ``left``/``right``/``top``/``bottom``; the resulting bounds
    are normalised so ``min`` <= ``max`` even when an edge is dragged past its
    opposite.
    """
    x_min = annotation_float(original, "x_min")
    x_max = annotation_float(original, "x_max")
    y_min = annotation_float(original, "y_min")
    y_max = annotation_float(original, "y_max")
    x_value, y_value = float(current[0]), float(current[1])
    if "left" in mode:
        x_min = x_value
    if "right" in mode:
        x_max = x_value
    if "bottom" in mode:
        y_min = y_value
    if "top" in mode:
        y_max = y_value
    annotation["x_min"] = min(x_min, x_max)
    annotation["x_max"] = max(x_min, x_max)
    annotation["y_min"] = min(y_min, y_max)
    annotation["y_max"] = max(y_min, y_max)


def apply_annotation_drag(
    annotation: dict[str, object],
    original: dict[str, object],
    mode: str,
    dx: float,
    dy: float,
    current: tuple[float, float],
) -> None:
    """Apply a drag gesture to an annotation, in place.

    ``move`` translates the whole annotation; an arrow ``start``/``end`` mode
    repositions that endpoint; any other mode resizes a box edge/corner.
    """
    annotation_type = str(annotation.get("type", ""))
    if mode == "move":
        move_annotation(annotation, original, dx, dy)
    elif annotation_type == ANNOTATION_ARROW and mode in {"start", "end"}:
        annotation[f"{mode}_x"] = float(current[0])
        annotation[f"{mode}_y"] = float(current[1])
    elif annotation_type == ANNOTATION_BOX:
        resize_box_annotation(annotation, original, mode, current)
