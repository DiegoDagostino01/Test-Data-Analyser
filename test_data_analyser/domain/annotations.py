"""Plot annotation domain helpers.

Annotations are stored as plain dictionaries inside plot profiles so sessions
remain JSON-friendly and independent from the Qt/Matplotlib rendering layer.
"""
from __future__ import annotations

import math
from typing import Any

from .conversions import _mapping, _string


ANNOTATION_TEXT = "text"
ANNOTATION_ARROW = "arrow"
ANNOTATION_BOX = "box"
ANNOTATION_TYPES = {ANNOTATION_TEXT, ANNOTATION_ARROW, ANNOTATION_BOX}
ANNOTATION_AXES = {"primary", "secondary"}

DEFAULT_TEXT_STYLE = {
    "text_color": "black",
    "background_color": "white",
    "border_color": "black",
}
DEFAULT_ARROW_STYLE = {"color": "red", "line_width": 1.5}
DEFAULT_BOX_STYLE = {"edge_color": "orange", "fill_color": "transparent", "line_width": 1.5}


def normalise_annotations(value: object) -> list[dict[str, object]]:
    """Return valid plot annotations, silently dropping malformed entries."""
    if not isinstance(value, list):
        return []
    annotations: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        annotation = normalise_annotation(item, index=index)
        if not annotation:
            continue
        annotation_id = str(annotation["id"])
        if annotation_id in seen_ids:
            annotation["id"] = _unique_annotation_id(annotation_id, seen_ids)
        seen_ids.add(str(annotation["id"]))
        annotations.append(annotation)
    return annotations


def normalise_annotation(value: object, *, index: int = 0) -> dict[str, object]:
    data = _mapping(value)
    annotation_type = _string(data.get("type")).strip().casefold()
    if annotation_type not in ANNOTATION_TYPES:
        return {}
    annotation_id = _string(data.get("id")).strip() or f"ann_{index + 1:03d}"
    axis = _normalise_axis(data.get("axis"))
    if annotation_type == ANNOTATION_TEXT:
        return _normalise_text_annotation(data, annotation_id, axis)
    if annotation_type == ANNOTATION_ARROW:
        return _normalise_arrow_annotation(data, annotation_id, axis)
    if annotation_type == ANNOTATION_BOX:
        return _normalise_box_annotation(data, annotation_id, axis)
    return {}


def _normalise_text_annotation(data: dict[str, Any], annotation_id: str, axis: str) -> dict[str, object]:
    x_value = _finite_float(data.get("x", data.get("anchor_x")))
    y_value = _finite_float(data.get("y", data.get("anchor_y")))
    if x_value is None or y_value is None:
        return {}
    text = _string(data.get("text")).strip()
    if not text:
        return {}
    return {
        "id": annotation_id,
        "type": ANNOTATION_TEXT,
        "axis": axis,
        "text": text,
        "x": x_value,
        "y": y_value,
        "offset_x": _finite_float(data.get("offset_x"), default=0.0),
        "offset_y": _finite_float(data.get("offset_y"), default=0.0),
        "style": _normalise_style(
            data.get("style"),
            DEFAULT_TEXT_STYLE,
            colour_keys=("text_color", "background_color", "border_color"),
            numeric_keys=(),
        ),
    }


def _normalise_arrow_annotation(data: dict[str, Any], annotation_id: str, axis: str) -> dict[str, object]:
    start_x = _finite_float(data.get("start_x"))
    start_y = _finite_float(data.get("start_y"))
    end_x = _finite_float(data.get("end_x"))
    end_y = _finite_float(data.get("end_y"))
    if None in {start_x, start_y, end_x, end_y}:
        return {}
    if start_x == end_x and start_y == end_y:
        return {}
    return {
        "id": annotation_id,
        "type": ANNOTATION_ARROW,
        "axis": axis,
        "start_x": start_x,
        "start_y": start_y,
        "end_x": end_x,
        "end_y": end_y,
        "style": _normalise_style(
            data.get("style"),
            DEFAULT_ARROW_STYLE,
            colour_keys=("color",),
            numeric_keys=("line_width",),
        ),
    }


def _normalise_box_annotation(data: dict[str, Any], annotation_id: str, axis: str) -> dict[str, object]:
    x_min = _finite_float(data.get("x_min"))
    x_max = _finite_float(data.get("x_max"))
    y_min = _finite_float(data.get("y_min"))
    y_max = _finite_float(data.get("y_max"))
    if None in {x_min, x_max, y_min, y_max}:
        return {}
    if x_min == x_max or y_min == y_max:
        return {}
    return {
        "id": annotation_id,
        "type": ANNOTATION_BOX,
        "axis": axis,
        "x_min": min(float(x_min), float(x_max)),
        "x_max": max(float(x_min), float(x_max)),
        "y_min": min(float(y_min), float(y_max)),
        "y_max": max(float(y_min), float(y_max)),
        "style": _normalise_style(
            data.get("style"),
            DEFAULT_BOX_STYLE,
            colour_keys=("edge_color", "fill_color"),
            numeric_keys=("line_width",),
        ),
    }


def _normalise_style(
    value: object,
    defaults: dict[str, object],
    *,
    colour_keys: tuple[str, ...],
    numeric_keys: tuple[str, ...],
) -> dict[str, object]:
    data = _mapping(value)
    style = dict(defaults)
    for key in colour_keys:
        colour = _string(data.get(key)).strip()
        if colour:
            style[key] = colour
    for key in numeric_keys:
        number = _finite_float(data.get(key))
        if number is not None and number > 0:
            style[key] = number
    return style


def _normalise_axis(value: object) -> str:
    axis = _string(value).strip().casefold()
    if axis in {"right", "secondary", "y2"}:
        return "secondary"
    return axis if axis in ANNOTATION_AXES else "primary"


def _finite_float(value: object, *, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _unique_annotation_id(annotation_id: str, seen_ids: set[str]) -> str:
    counter = 2
    while f"{annotation_id}_{counter}" in seen_ids:
        counter += 1
    return f"{annotation_id}_{counter}"