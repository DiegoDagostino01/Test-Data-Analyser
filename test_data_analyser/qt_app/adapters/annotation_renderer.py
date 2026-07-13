"""Annotation rendering adapter.

Draws plot annotations (text, arrow, box) and their selection handles onto a
Matplotlib axes. Matplotlib is allowed in the adapter layer; this module holds
no Qt objects and no widget state, so the plot workspace widget can delegate all
annotation drawing here. Each artist is tagged with a gid of ``annotation:<id>``
so the widget's hit-testing and clearing can find it again.
"""
from __future__ import annotations

from typing import Any

from matplotlib.patches import FancyArrowPatch, Rectangle

from ...core.config import EATON_DARK_BLUE
from ...domain.annotations import ANNOTATION_ARROW, ANNOTATION_BOX, ANNOTATION_TEXT
from ...services import annotation_geometry_service

ANNOTATION_HANDLE_SIZE = 42

_annotation_float = annotation_geometry_service.annotation_float


def _annotation_style(annotation: dict[str, object]) -> dict[str, object]:
    style = annotation.get("style", {})
    return style if isinstance(style, dict) else {}


def _style_float(value: object, default: float) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return float(default)


def draw_annotation(axes, annotation: dict[str, object]) -> list[Any]:
    annotation_type = str(annotation.get("type", ""))
    if annotation_type == ANNOTATION_TEXT:
        return [draw_text_annotation(axes, annotation)]
    if annotation_type == ANNOTATION_ARROW:
        return [draw_arrow_annotation(axes, annotation)]
    if annotation_type == ANNOTATION_BOX:
        return [draw_box_annotation(axes, annotation)]
    return []


def draw_text_annotation(axes, annotation: dict[str, object]):
    style = _annotation_style(annotation)
    artist = axes.annotate(
        str(annotation.get("text", "")),
        xy=(_annotation_float(annotation, "x"), _annotation_float(annotation, "y")),
        xytext=(
            _annotation_float(annotation, "offset_x"),
            _annotation_float(annotation, "offset_y"),
        ),
        textcoords="offset points",
        color=str(style.get("text_color", "black")),
        fontsize=9,
        bbox={
            "boxstyle": "round,pad=0.25",
            "facecolor": str(style.get("background_color", "white")),
            "edgecolor": str(style.get("border_color", "black")),
            "linewidth": 1.0,
        },
        zorder=14,
        annotation_clip=False,
    )
    artist.set_gid(f"annotation:{annotation.get('id', '')}")
    return artist


def draw_arrow_annotation(axes, annotation: dict[str, object]):
    style = _annotation_style(annotation)
    artist = FancyArrowPatch(
        (_annotation_float(annotation, "start_x"), _annotation_float(annotation, "start_y")),
        (_annotation_float(annotation, "end_x"), _annotation_float(annotation, "end_y")),
        arrowstyle="->",
        mutation_scale=13,
        linewidth=_style_float(style.get("line_width"), 1.5),
        color=str(style.get("color", "red")),
        zorder=13,
    )
    artist.set_gid(f"annotation:{annotation.get('id', '')}")
    axes.add_patch(artist)
    return artist


def draw_box_annotation(axes, annotation: dict[str, object]):
    style = _annotation_style(annotation)
    fill_color = str(style.get("fill_color", "transparent"))
    transparent = fill_color.strip().casefold() in {"", "none", "transparent"}
    artist = Rectangle(
        (_annotation_float(annotation, "x_min"), _annotation_float(annotation, "y_min")),
        _annotation_float(annotation, "x_max") - _annotation_float(annotation, "x_min"),
        _annotation_float(annotation, "y_max") - _annotation_float(annotation, "y_min"),
        fill=not transparent,
        facecolor="none" if transparent else fill_color,
        edgecolor=str(style.get("edge_color", "orange")),
        linewidth=_style_float(style.get("line_width"), 1.5),
        alpha=1.0 if transparent else 0.18,
        zorder=12,
    )
    artist.set_gid(f"annotation:{annotation.get('id', '')}")
    axes.add_patch(artist)
    return artist


def draw_annotation_handles(axes, annotation: dict[str, object]) -> list[Any]:
    handles: list[Any] = []
    for point in annotation_geometry_service.annotation_handle_points(annotation).values():
        handle = axes.scatter(
            [point[0]],
            [point[1]],
            s=ANNOTATION_HANDLE_SIZE,
            marker="s",
            facecolors="white",
            edgecolors=EATON_DARK_BLUE,
            linewidths=1.2,
            label="_annotation_handle",
            zorder=20,
        )
        setattr(handle, "_tda_annotation_handle", True)
        handles.append(handle)
    return handles
