"""Plot workspace panel.

Embeds the Matplotlib Qt canvas and renders the active selection through the
framework-independent :class:`PlotWorkspaceViewModel`. Data preparation lives in
the viewmodel/services; colour-cycle resolution is exposed through the settings
viewmodel. This panel only orchestrates rendering onto the canvas.
"""
from __future__ import annotations

import os
import math
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any, Optional, cast

from cycler import cycler
from matplotlib.ticker import MultipleLocator
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.config import EATON_DARK_BLUE
from ...core.naming import natural_sort_key
from ...domain.annotations import normalise_annotations
from ...services import annotation_geometry_service, axis_limits_computer, legend_metadata_service, plot_render_service
from ...services.results import OperationResult
from ...viewmodels.cursor_compare_vm import CursorCompareViewModel
from ...viewmodels.plot_workspace_vm import PlotWorkspaceViewModel
from ...viewmodels.settings_vm import SettingsViewModel
from ..adapters.matplotlib_qt_adapter import LEGEND_DISPLAY_GRAPH, LEGEND_DISPLAY_PANEL, MatplotlibCanvas
from ..adapters import annotation_renderer, best_fit_renderer, qt_message_service
from .axis_selection_panel import PLOT_KINDS
from .legend_channel_style_dialog import LegendChannelStyleDialog
from .no_wheel_combo_box import NoWheelComboBox

CURVE_STYLE_KEYS = plot_render_service.CURVE_STYLE_KEYS

ANNOTATION_SELECT = "select"
ANNOTATION_TEXT = "text"
ANNOTATION_ARROW = "arrow"
ANNOTATION_BOX = "box"
ANNOTATION_TOOL_LABELS = {
    ANNOTATION_SELECT: "Select",
    ANNOTATION_TEXT: "Text",
    ANNOTATION_ARROW: "Arrow",
    ANNOTATION_BOX: "Box",
}
ANNOTATION_PICK_TOLERANCE = 8


class PlotWorkspace(QWidget):
    cursorPointsChanged = Signal()
    annotationsChanged = Signal()
    legendChannelStyleChanged = Signal(str, dict)
    legendChannelVisibilityChanged = Signal(str, bool)
    bestFitFormulasChanged = Signal()
    LEGEND_DEFAULT_WIDTH = 230
    LEGEND_MAXIMUM_WIDTH = 400
    #: Cap on major ticks per axis; matplotlib raises MAXTICKS (1000) beyond this.
    MAX_AXIS_MAJOR_TICKS = 1000

    def __init__(
        self,
        plot_vm: PlotWorkspaceViewModel,
        settings_vm: SettingsViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PlotWorkspace")
        self.plot_vm = plot_vm
        self.settings_vm = settings_vm
        self._last_plot_data = None
        self._last_x_col = ""
        self._cursor_vm: CursorCompareViewModel | None = None
        self._point_compare = False
        self._cursor_artists: list = []
        self._legend_display = LEGEND_DISPLAY_PANEL
        self._axis_tick_settings = self._normalise_axis_tick_settings({})
        self._best_fit_settings: list[dict[str, object]] = []
        self._best_fit_formula_rows: list[dict[str, object]] = []
        self._annotations: list[dict[str, object]] = []
        self._annotation_artists: dict[str, list[Any]] = {}
        self._selected_annotation_id = ""
        self._annotation_tool = ANNOTATION_SELECT
        self._annotation_drag: dict[str, Any] | None = None
        self._annotation_id_counter = 1
        self._annotation_buttons: dict[str, QPushButton] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = MatplotlibCanvas(self)
        self._install_annotation_toolbar_controls()
        self.apply_theme()
        self.canvas.toolbar.set_legend_display_controller(self.legend_display, self.set_legend_display)
        self.canvas.toolbar.set_export_preparer(self._legend_export_context)
        self.canvas.toolbar.set_axis_padding_getter(self._axis_padding_settings)
        self.canvas.toolbar.set_axis_tick_settings_controller(
            self.axis_tick_setting_texts,
            self.set_axis_tick_settings,
            self.apply_axis_tick_settings_to_current_plot,
        )
        self.canvas.toolbar.set_best_fit_controller(
            self.available_best_fit_channels,
            self.best_fit_settings,
            self.set_best_fit_settings,
            self.apply_best_fit_settings_to_current_plot,
        )
        self.legend_panel = self._build_legend_panel()
        self.plot_legend_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.plot_legend_splitter.setObjectName("PlotLegendSplitter")
        self.plot_legend_splitter.addWidget(self.canvas)
        self.plot_legend_splitter.addWidget(self.legend_panel)
        self.plot_legend_splitter.setCollapsible(0, False)
        self.plot_legend_splitter.setCollapsible(1, True)
        self.plot_legend_splitter.setStretchFactor(0, 1)
        self.plot_legend_splitter.setStretchFactor(1, 0)
        self.plot_legend_splitter.setSizes([900, self.LEGEND_DEFAULT_WIDTH])
        layout.addWidget(self.plot_legend_splitter, stretch=1)

        self.canvas.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.canvas.canvas.mpl_connect("motion_notify_event", self._on_canvas_motion)
        self.canvas.canvas.mpl_connect("button_release_event", self._on_canvas_release)
        self.canvas.canvas.mpl_connect("key_press_event", self._on_canvas_key)

    def _install_annotation_toolbar_controls(self) -> None:
        toolbar = self.canvas.toolbar
        before_action = getattr(toolbar, "edit_axis_action", None)
        if before_action is None:
            toolbar.addSeparator()
        for tool, tooltip in (
            (ANNOTATION_SELECT, "Select, move, or resize plot annotations."),
            (ANNOTATION_TEXT, "Add a text box annotation."),
            (ANNOTATION_ARROW, "Drag to add an arrow annotation."),
            (ANNOTATION_BOX, "Drag to add a rectangle annotation."),
        ):
            button = QPushButton(ANNOTATION_TOOL_LABELS[tool])
            button.setCheckable(True)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _checked=False, tool=tool: self.set_annotation_tool(tool))
            self._annotation_buttons[tool] = button
            if before_action is not None:
                toolbar.insertWidget(before_action, button)
            else:
                toolbar.addWidget(button)
        self.delete_annotation_button = QPushButton("Delete")
        self.delete_annotation_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_annotation_button.setToolTip("Delete the selected annotation.")
        self.delete_annotation_button.clicked.connect(self.delete_selected_annotation)
        if before_action is not None:
            toolbar.insertWidget(before_action, self.delete_annotation_button)
            toolbar.insertSeparator(before_action)
        else:
            toolbar.addWidget(self.delete_annotation_button)
            toolbar.addSeparator()
        self.set_annotation_tool(ANNOTATION_SELECT)

    def apply_theme(self, theme_name: str | None = None) -> None:
        self.canvas.apply_theme(theme_name or self._theme_name())

    def _theme_name(self) -> str:
        resolver = getattr(self.settings_vm, "theme_name", None)
        if callable(resolver):
            return str(resolver())
        return "light"

    # ------------------------------------------------------------------
    # Annotation state / interaction
    # ------------------------------------------------------------------
    def set_annotation_tool(self, tool: str) -> None:
        self._annotation_tool = tool if tool in ANNOTATION_TOOL_LABELS else ANNOTATION_SELECT
        for name, button in self._annotation_buttons.items():
            button.setChecked(name == self._annotation_tool)

    def set_annotations(self, annotations: object) -> None:
        self._annotations = normalise_annotations(annotations)
        self._annotation_id_counter = max(self._annotation_id_counter, len(self._annotations) + 1)
        if self._selected_annotation_id and self._annotation_by_id(self._selected_annotation_id) is None:
            self._selected_annotation_id = ""
        self._redraw_annotations()

    def current_annotations(self) -> list[dict[str, object]]:
        return normalise_annotations(self._annotations)

    def selected_annotation_id(self) -> str:
        return self._selected_annotation_id

    def delete_selected_annotation(self) -> None:
        if not self._selected_annotation_id:
            return
        self._delete_annotation(self._selected_annotation_id)

    def edit_selected_annotation(self) -> None:
        annotation = self._annotation_by_id(self._selected_annotation_id)
        if annotation is None or annotation.get("type") != ANNOTATION_TEXT:
            return
        text, ok = QInputDialog.getText(
            self,
            "Edit Text Annotation",
            "Text:",
            text=str(annotation.get("text", "")),
        )
        if not ok:
            return
        text = text.strip()
        if not text:
            return
        annotation["text"] = text
        self._annotations_changed()

    def _on_canvas_click(self, event) -> None:
        if self._handle_annotation_button_press(event):
            return
        if not self._point_compare or self._cursor_vm is None:
            return
        if event.inaxes is None or event.xdata is None or event.button != 1:
            return
        if self._cursor_vm.lock_at(event.xdata):
            point = self._cursor_vm.points[-1]
            marker = self.canvas.axes.axvline(
                point["x"], color=EATON_DARK_BLUE, linestyle="--", linewidth=1.0, alpha=0.75
            )
            self._cursor_artists.append(marker)
            self.canvas.canvas.draw_idle()
            self.cursorPointsChanged.emit()

    def _handle_annotation_button_press(self, event) -> bool:
        if event.button == 3:
            self._show_annotation_context_menu(event)
            return True
        if event.button != 1:
            return False
        if self._annotation_tool == ANNOTATION_TEXT:
            if self._valid_annotation_event(event):
                self._add_text_annotation(event)
                return True
            return False
        if self._annotation_tool in {ANNOTATION_ARROW, ANNOTATION_BOX}:
            if self._valid_annotation_event(event):
                self._annotation_drag = {
                    "mode": f"new_{self._annotation_tool}",
                    "axis": self._axis_name_for_event(event),
                    "axes": event.inaxes,
                    "start": (float(event.xdata), float(event.ydata)),
                    "pixel_start": (float(event.x), float(event.y)),
                }
                return True
            return False
        handle_hit = self._hit_annotation_handle(event)
        if handle_hit is not None:
            annotation_id, handle = handle_hit
            self._select_annotation(annotation_id)
            self._start_annotation_drag(event, annotation_id, handle)
            return True
        annotation_id = self._hit_annotation(event)
        if annotation_id:
            self._select_annotation(annotation_id)
            if bool(getattr(event, "dblclick", False)):
                self.edit_selected_annotation()
            else:
                self._start_annotation_drag(event, annotation_id, "move")
            return True
        return False

    def _on_canvas_motion(self, event) -> None:
        drag = self._annotation_drag
        if not drag or str(drag.get("mode", "")).startswith("new_"):
            return
        axes = drag.get("axes")
        if axes is None:
            return
        current = self._event_data_for_axes(event, axes)
        start = drag.get("start")
        original = drag.get("original")
        if current is None or not isinstance(start, tuple) or not isinstance(original, dict):
            return
        dx = float(current[0]) - float(start[0])
        dy = float(current[1]) - float(start[1])
        annotation = self._annotation_by_id(str(drag.get("id", "")))
        if annotation is None:
            return
        self._apply_annotation_drag(annotation, original, str(drag.get("mode", "move")), dx, dy, current)
        self._redraw_annotations()

    def _on_canvas_release(self, event) -> None:
        drag = self._annotation_drag
        if not drag:
            return
        self._annotation_drag = None
        mode = str(drag.get("mode", ""))
        if mode in {"new_arrow", "new_box"}:
            axes = drag.get("axes")
            current = self._event_data_for_axes(event, axes) if axes is not None else None
            start = drag.get("start")
            if current is None or not isinstance(start, tuple):
                return
            if self._drag_distance_too_small(drag, event):
                return
            if mode == "new_arrow":
                self._append_annotation(
                    {
                        "id": self._next_annotation_id(),
                        "type": ANNOTATION_ARROW,
                        "axis": str(drag.get("axis", "primary")),
                        "start_x": float(start[0]),
                        "start_y": float(start[1]),
                        "end_x": float(current[0]),
                        "end_y": float(current[1]),
                    }
                )
            else:
                self._append_annotation(
                    {
                        "id": self._next_annotation_id(),
                        "type": ANNOTATION_BOX,
                        "axis": str(drag.get("axis", "primary")),
                        "x_min": float(start[0]),
                        "x_max": float(current[0]),
                        "y_min": float(start[1]),
                        "y_max": float(current[1]),
                    }
                )
            self.set_annotation_tool(ANNOTATION_SELECT)
            return
        self._annotations = normalise_annotations(self._annotations)
        self._annotations_changed()

    def _on_canvas_key(self, event) -> None:
        if event.key in {"delete", "backspace"} and self._selected_annotation_id:
            self.delete_selected_annotation()
            return
        if event.key == "escape" and self._selected_annotation_id:
            self._select_annotation("")
            return
        if event.key == "escape":
            self.clear_cursor_markers()
            self.cursorPointsChanged.emit()

    def _valid_annotation_event(self, event) -> bool:
        return event.inaxes in self.canvas.figure.axes and event.xdata is not None and event.ydata is not None

    def _add_text_annotation(self, event, text: str | None = None) -> None:
        if text is None:
            text, ok = QInputDialog.getText(self, "Add Text Annotation", "Text:")
            if not ok:
                return
        text = str(text).strip()
        if not text:
            return
        self._append_annotation(
            {
                "id": self._next_annotation_id(),
                "type": ANNOTATION_TEXT,
                "axis": self._axis_name_for_event(event),
                "text": text,
                "x": float(event.xdata),
                "y": float(event.ydata),
                "offset_x": 8.0,
                "offset_y": -8.0,
            }
        )
        self.set_annotation_tool(ANNOTATION_SELECT)

    def _append_annotation(self, annotation: dict[str, object]) -> None:
        normalised = normalise_annotations([*self._annotations, annotation])
        if len(normalised) == len(self._annotations):
            return
        self._annotations = normalised
        self._selected_annotation_id = str(normalised[-1].get("id", ""))
        self._annotations_changed()

    def _delete_annotation(self, annotation_id: str) -> None:
        original_count = len(self._annotations)
        self._annotations = [annotation for annotation in self._annotations if str(annotation.get("id", "")) != annotation_id]
        if len(self._annotations) == original_count:
            return
        self._selected_annotation_id = ""
        self._annotations_changed()

    def _annotations_changed(self) -> None:
        self._redraw_annotations()
        self.annotationsChanged.emit()

    def _select_annotation(self, annotation_id: str) -> None:
        self._selected_annotation_id = annotation_id if self._annotation_by_id(annotation_id) is not None else ""
        self._redraw_annotations()

    def _annotation_by_id(self, annotation_id: str) -> dict[str, object] | None:
        if not annotation_id:
            return None
        for annotation in self._annotations:
            if str(annotation.get("id", "")) == annotation_id:
                return annotation
        return None

    def _next_annotation_id(self) -> str:
        existing = {str(annotation.get("id", "")) for annotation in self._annotations}
        while True:
            annotation_id = f"ann_{self._annotation_id_counter:03d}"
            self._annotation_id_counter += 1
            if annotation_id not in existing:
                return annotation_id

    def _axis_name_for_event(self, event) -> str:
        return "secondary" if event.inaxes is self._secondary_axes() else "primary"

    def _target_axes_for_annotation(self, annotation: dict[str, object]):
        if annotation.get("axis") == "secondary":
            secondary = self._secondary_axes()
            if secondary is not None:
                return secondary
        return self.canvas.axes

    def _event_data_for_axes(self, event, axes) -> tuple[float, float] | None:
        event_x = getattr(event, "x", None)
        event_y = getattr(event, "y", None)
        if event_x is None or event_y is None:
            return None
        try:
            if event.inaxes is axes and event.xdata is not None and event.ydata is not None:
                return float(event.xdata), float(event.ydata)
            x_value, y_value = axes.transData.inverted().transform((event_x, event_y))
            return float(x_value), float(y_value)
        except Exception:
            return None

    def _start_annotation_drag(self, event, annotation_id: str, mode: str) -> None:
        annotation = self._annotation_by_id(annotation_id)
        if annotation is None:
            return
        axes = self._target_axes_for_annotation(annotation)
        start = self._event_data_for_axes(event, axes)
        if start is None:
            return
        self._annotation_drag = {
            "mode": mode,
            "id": annotation_id,
            "axes": axes,
            "start": start,
            "original": dict(annotation),
        }

    def _apply_annotation_drag(
        self,
        annotation: dict[str, object],
        original: dict[str, object],
        mode: str,
        dx: float,
        dy: float,
        current: tuple[float, float],
    ) -> None:
        annotation_geometry_service.apply_annotation_drag(annotation, original, mode, dx, dy, current)

    @staticmethod
    def _annotation_float(annotation: dict[str, object], key: str, default: float = 0.0) -> float:
        return annotation_geometry_service.annotation_float(annotation, key, default)

    @staticmethod
    def _move_annotation(annotation: dict[str, object], original: dict[str, object], dx: float, dy: float) -> None:
        annotation_geometry_service.move_annotation(annotation, original, dx, dy)

    @staticmethod
    def _resize_box_annotation(
        annotation: dict[str, object],
        original: dict[str, object],
        mode: str,
        current: tuple[float, float],
    ) -> None:
        annotation_geometry_service.resize_box_annotation(annotation, original, mode, current)

    def _drag_distance_too_small(self, drag: dict[str, Any], event) -> bool:
        start = drag.get("pixel_start")
        event_x = getattr(event, "x", None)
        event_y = getattr(event, "y", None)
        if not isinstance(start, tuple) or event_x is None or event_y is None:
            return True
        return math.hypot(float(event_x) - float(start[0]), float(event_y) - float(start[1])) < 4.0

    def _show_annotation_context_menu(self, event) -> None:
        hit = self._hit_annotation(event)
        if hit:
            self._select_annotation(hit)
        menu = QMenu(self)
        add_text_action = menu.addAction("Add Text Box")
        add_arrow_action = menu.addAction("Add Arrow")
        add_box_action = menu.addAction("Add Box")
        menu.addSeparator()
        edit_action = menu.addAction("Edit Selected Annotation")
        delete_action = menu.addAction("Delete Selected Annotation")
        menu.addSeparator()
        mark_peaks_action = menu.addAction("Mark Peaks…")
        selected = self._annotation_by_id(self._selected_annotation_id)
        edit_action.setEnabled(selected is not None and selected.get("type") == ANNOTATION_TEXT)
        delete_action.setEnabled(selected is not None)
        chosen = menu.exec(QCursor.pos())
        if chosen == add_text_action and self._valid_annotation_event(event):
            self._add_text_annotation(event)
        elif chosen == add_arrow_action and self._valid_annotation_event(event):
            self._add_default_arrow_annotation(event)
        elif chosen == add_box_action and self._valid_annotation_event(event):
            self._add_default_box_annotation(event)
        elif chosen == edit_action:
            self.edit_selected_annotation()
        elif chosen == delete_action:
            self.delete_selected_annotation()
        elif chosen == mark_peaks_action:
            self.mark_peaks()

    def _peak_channel(self) -> str | None:
        df = self.plot_vm.state.df
        profile = self.plot_vm.state.active_plot_profile()
        y_columns = profile.get("y_columns", []) if isinstance(profile, dict) else []
        columns = [column for column in y_columns if df is not None and column in df.columns]
        if not columns:
            qt_message_service.warning(self, "Mark Peaks", "Generate a plot with at least one Y channel first.")
            return None
        if len(columns) == 1:
            return columns[0]
        choice, ok = QInputDialog.getItem(self, "Mark Peaks", "Channel:", columns, 0, False)
        return choice if ok else None

    def mark_peaks(self) -> None:
        """Detect peaks for a plotted channel and add a text annotation at each."""
        channel = self._peak_channel()
        if channel is None:
            return
        prominence, ok = QInputDialog.getDouble(
            self, "Mark Peaks", "Minimum prominence (0 = auto):", 0.0, 0.0, 1e12, 3
        )
        if not ok:
            return
        include_troughs = qt_message_service.confirm(self, "Mark Peaks", "Also mark troughs (minima)?")
        result = self.plot_vm.detect_peaks(channel, prominence=prominence or None, find_troughs=include_troughs)
        if not result.ok:
            qt_message_service.warning(self, "Mark Peaks", result.message)
            return
        annotations = result.payload.get("annotations", []) if isinstance(result.payload, dict) else []
        if not annotations:
            qt_message_service.info(self, "Mark Peaks", result.message)
            return
        new_annotations = [dict(annotation, id=self._next_annotation_id()) for annotation in annotations]
        self._annotations = normalise_annotations([*self._annotations, *new_annotations])
        self._annotations_changed()

    def _add_default_arrow_annotation(self, event) -> None:
        x_span, y_span = self._axes_span(event.inaxes)
        self._append_annotation(
            {
                "id": self._next_annotation_id(),
                "type": ANNOTATION_ARROW,
                "axis": self._axis_name_for_event(event),
                "start_x": float(event.xdata) - x_span * 0.08,
                "start_y": float(event.ydata) + y_span * 0.08,
                "end_x": float(event.xdata),
                "end_y": float(event.ydata),
            }
        )

    def _add_default_box_annotation(self, event) -> None:
        x_span, y_span = self._axes_span(event.inaxes)
        self._append_annotation(
            {
                "id": self._next_annotation_id(),
                "type": ANNOTATION_BOX,
                "axis": self._axis_name_for_event(event),
                "x_min": float(event.xdata) - x_span * 0.05,
                "x_max": float(event.xdata) + x_span * 0.05,
                "y_min": float(event.ydata) - y_span * 0.05,
                "y_max": float(event.ydata) + y_span * 0.05,
            }
        )

    @staticmethod
    def _axes_span(axes) -> tuple[float, float]:
        try:
            xmin, xmax = axes.get_xlim()
            ymin, ymax = axes.get_ylim()
            return max(abs(float(xmax) - float(xmin)), 1.0), max(abs(float(ymax) - float(ymin)), 1.0)
        except Exception:
            return 1.0, 1.0

    def _hit_annotation_handle(self, event) -> tuple[str, str] | None:
        event_x = getattr(event, "x", None)
        event_y = getattr(event, "y", None)
        if event_x is None or event_y is None or not self._selected_annotation_id:
            return None
        annotation = self._annotation_by_id(self._selected_annotation_id)
        if annotation is None:
            return None
        axes = self._target_axes_for_annotation(annotation)
        for handle, point in self._annotation_handle_points(annotation).items():
            distance = self._pixel_distance(axes, point, (float(event_x), float(event_y)))
            if distance <= ANNOTATION_PICK_TOLERANCE:
                return self._selected_annotation_id, handle
        return None

    def _hit_annotation(self, event) -> str:
        if getattr(event, "x", None) is None or getattr(event, "y", None) is None:
            return ""
        for annotation in reversed(self._annotations):
            annotation_id = str(annotation.get("id", ""))
            if self._annotation_contains_event(annotation, event):
                return annotation_id
        return ""

    def _annotation_contains_event(self, annotation: dict[str, object], event) -> bool:
        annotation_id = str(annotation.get("id", ""))
        for artist in self._annotation_artists.get(annotation_id, []):
            if bool(getattr(artist, "_tda_annotation_handle", False)):
                continue
            try:
                contains, _details = artist.contains(event)
            except Exception:
                contains = False
            if contains:
                return True
        return self._annotation_near_event(annotation, event)

    def _annotation_near_event(self, annotation: dict[str, object], event) -> bool:
        axes = self._target_axes_for_annotation(annotation)
        event_x = getattr(event, "x", None)
        event_y = getattr(event, "y", None)
        if event_x is None or event_y is None:
            return False
        event_point = (float(event_x), float(event_y))
        annotation_type = str(annotation.get("type", ""))
        if annotation_type == ANNOTATION_TEXT:
            return self._pixel_distance(
                axes,
                (self._annotation_float(annotation, "x"), self._annotation_float(annotation, "y")),
                event_point,
            ) <= 12
        if annotation_type == ANNOTATION_ARROW:
            start = (self._annotation_float(annotation, "start_x"), self._annotation_float(annotation, "start_y"))
            end = (self._annotation_float(annotation, "end_x"), self._annotation_float(annotation, "end_y"))
            return self._distance_to_segment_pixels(axes, start, end, event_point) <= ANNOTATION_PICK_TOLERANCE
        if annotation_type == ANNOTATION_BOX:
            return self._box_contains_event(annotation, axes, event_point)
        return False

    @staticmethod
    def _pixel_distance(axes, data_point: tuple[float, float], pixel_point: tuple[float, float]) -> float:
        x_pixel, y_pixel = axes.transData.transform(data_point)
        return annotation_geometry_service.point_distance((float(x_pixel), float(y_pixel)), pixel_point)

    @classmethod
    def _distance_to_segment_pixels(
        cls,
        axes,
        start: tuple[float, float],
        end: tuple[float, float],
        point: tuple[float, float],
    ) -> float:
        sx, sy = axes.transData.transform(start)
        ex, ey = axes.transData.transform(end)
        return annotation_geometry_service.distance_to_segment(point, (float(sx), float(sy)), (float(ex), float(ey)))

    def _box_contains_event(self, annotation: dict[str, object], axes, event_point: tuple[float, float]) -> bool:
        corners = self._annotation_handle_points(annotation)
        if not corners:
            return False
        lines = (
            (corners["bottom_left"], corners["bottom_right"]),
            (corners["bottom_right"], corners["top_right"]),
            (corners["top_right"], corners["top_left"]),
            (corners["top_left"], corners["bottom_left"]),
        )
        if any(self._distance_to_segment_pixels(axes, start, end, event_point) <= ANNOTATION_PICK_TOLERANCE for start, end in lines):
            return True
        try:
            x_value, y_value = axes.transData.inverted().transform(event_point)
            return (
                self._annotation_float(annotation, "x_min") <= float(x_value) <= self._annotation_float(annotation, "x_max")
                and self._annotation_float(annotation, "y_min") <= float(y_value) <= self._annotation_float(annotation, "y_max")
            )
        except Exception:
            return False

    @staticmethod
    def _annotation_handle_points(annotation: dict[str, object]) -> dict[str, tuple[float, float]]:
        return annotation_geometry_service.annotation_handle_points(annotation)

    def _redraw_annotations(self) -> None:
        if not hasattr(self, "canvas") or self.canvas.axes not in self.canvas.figure.axes:
            return
        self._draw_annotations(self.canvas.axes, self._secondary_axes())
        self.canvas.canvas.draw_idle()

    def _clear_annotation_artists(self) -> None:
        for artists in self._annotation_artists.values():
            for artist in artists:
                try:
                    artist.remove()
                except (ValueError, AttributeError, NotImplementedError):
                    pass
        self._annotation_artists.clear()

    def _draw_annotations(self, axes, secondary_axes) -> None:
        self._clear_annotation_artists()
        self._annotations = normalise_annotations(self._annotations)
        valid_ids = {str(annotation.get("id", "")) for annotation in self._annotations}
        if self._selected_annotation_id not in valid_ids:
            self._selected_annotation_id = ""
        for annotation in self._annotations:
            target = secondary_axes if annotation.get("axis") == "secondary" and secondary_axes is not None else axes
            artists = annotation_renderer.draw_annotation(target, annotation)
            if self._selected_annotation_id == annotation.get("id"):
                artists.extend(annotation_renderer.draw_annotation_handles(target, annotation))
            self._annotation_artists[str(annotation.get("id", ""))] = artists

    def _build_legend_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("EatonPanel")
        panel.setMinimumWidth(0)
        panel.setMaximumWidth(self.LEGEND_MAXIMUM_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        heading = QLabel("Legend")
        heading.setObjectName("PanelHeading")
        layout.addWidget(heading)

        self.legend_table = QTableWidget(0, 3)
        self.legend_table.setHorizontalHeaderLabels(["", "Series", "Hide/Show"])
        self.legend_table.verticalHeader().setVisible(False)
        self.legend_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.legend_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.legend_table.cellClicked.connect(self._on_legend_cell_clicked)
        header = self.legend_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 30)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 82)
        layout.addWidget(self.legend_table, stretch=1)
        return panel

    def legend_display(self) -> str:
        return self._legend_display

    def set_legend_display(self, display: str) -> None:
        self._legend_display = LEGEND_DISPLAY_GRAPH if display == LEGEND_DISPLAY_GRAPH else LEGEND_DISPLAY_PANEL
        self._refresh_current_legend()

    def axis_tick_setting_texts(self) -> dict[str, object]:
        return dict(self._axis_tick_settings)

    def set_axis_tick_settings(self, settings: dict[str, object]) -> None:
        self._axis_tick_settings = self._normalise_axis_tick_settings(settings)

    def best_fit_settings(self) -> list[dict[str, object]]:
        return [dict(setting) for setting in self._best_fit_settings]

    def best_fit_formula_rows(self) -> list[dict[str, object]]:
        return [dict(row) for row in self._best_fit_formula_rows]

    def set_best_fit_settings(self, settings: object) -> None:
        self._best_fit_settings = plot_render_service.normalise_best_fit_settings(settings)

    def available_best_fit_channels(self) -> list[str]:
        channels: list[str] = []
        for source in self._best_fit_source_series():
            channel = str(source.get("channel", "")).strip()
            if channel and channel not in channels:
                channels.append(channel)
        return sorted(channels, key=natural_sort_key)

    def apply_best_fit_settings_to_current_plot(self) -> None:
        self._remove_best_fit_artists()
        self._best_fit_formula_rows = []
        self._draw_best_fit_lines(self._best_fit_source_series())
        self._refresh_current_legend()
        self.bestFitFormulasChanged.emit()

    def apply_axis_tick_settings_to_current_plot(self) -> None:
        axes = self.canvas.axes
        if axes not in self.canvas.figure.axes:
            return
        self._apply_axis_tick_settings(axes, self._secondary_axes(), self._axis_tick_settings)
        axes.grid(self._grid_visible(), alpha=0.35)
        self.canvas.canvas.draw_idle()

    def current_axis_appearance(self) -> dict[str, Any]:
        """Read the title, axis labels, and axis limits from the live plot.

        Captures any edits made through the Matplotlib Figure Options dialog so
        they can be persisted in the session and re-applied on load. Returns an
        empty dict when no plot has been generated. ``auto_fit_axes`` is reported
        as ``False`` because the captured limits describe the exact on-screen
        view, which should be reproduced verbatim on restore.
        """
        axes = self.canvas.axes
        if axes not in self.canvas.figure.axes:
            return {}
        secondary = self._secondary_axes()
        xmin, xmax = axes.get_xlim()
        ymin, ymax = axes.get_ylim()
        limits = {
            "xmin": self._format_limit(xmin),
            "xmax": self._format_limit(xmax),
            "ymin": self._format_limit(ymin),
            "ymax": self._format_limit(ymax),
            "y2min": "",
            "y2max": "",
        }
        if secondary is not None:
            y2min, y2max = secondary.get_ylim()
            limits["y2min"] = self._format_limit(y2min)
            limits["y2max"] = self._format_limit(y2max)
        return {
            "title": axes.get_title(),
            "x_label": axes.get_xlabel(),
            "y_label": axes.get_ylabel(),
            "secondary_y_label": secondary.get_ylabel() if secondary is not None else "",
            "axis_limits": limits,
            "auto_fit_axes": False,
        }

    @staticmethod
    def _format_limit(value: float) -> str:
        return f"{float(value):.6g}"

    def save_plot_png(self, path: str) -> OperationResult:
        """Save the current figure to an image file (PNG by default).

        Reuses the legend export context so the right-side panel legend is baked
        into the image, mirroring the toolbar's save button. Fails cleanly when
        nothing has been plotted yet.
        """
        if not self._has_plot_content():
            return OperationResult.failure("Generate a plot before saving an image.")
        target = path
        if os.path.splitext(target)[1].lower() not in (".png", ".svg", ".pdf", ".jpg", ".jpeg"):
            target = f"{target}.png"
        try:
            dpi = int(self.settings_vm.get("export", "default_dpi", 150) or 150)
        except (TypeError, ValueError):
            dpi = 150
        try:
            with self._legend_export_context():
                self.canvas.figure.savefig(target, dpi=dpi, bbox_inches="tight")
        except Exception as exc:
            return OperationResult.failure(f"Could not save the plot image: {exc}")
        return OperationResult.success(f"Plot image saved:\n{target}", payload=target)

    def _has_plot_content(self) -> bool:
        for axes in self.canvas.figure.axes:
            if axes.get_lines() or axes.collections:
                return True
        return False

    def clear_plot(self) -> OperationResult:
        self._last_plot_data = None
        self._last_x_col = ""
        self._best_fit_formula_rows = []
        self._remove_cursor_artists()
        self._set_cursor_data(None)
        self._clear_annotation_artists()
        self.canvas.clear()
        self._update_legend_table([], [])
        self.legend_panel.setVisible(self._legend_display == LEGEND_DISPLAY_PANEL)
        self.canvas.draw()
        self.bestFitFormulasChanged.emit()
        return OperationResult.success("Plot cleared.")

    @contextmanager
    def _legend_export_context(self):
        """Temporarily draw the side-panel legend onto the figure for image export.

        In panel mode the visible legend lives in a Qt widget beside the canvas,
        so it is absent from ``savefig`` output. This adds a matching Matplotlib
        legend for the duration of the export, then removes it and repaints so
        the on-screen figure stays clean.
        """
        temporary_legend = None
        selected_annotation_id = self._selected_annotation_id
        if selected_annotation_id:
            self._selected_annotation_id = ""
            self._redraw_annotations()
        if self._legend_display == LEGEND_DISPLAY_PANEL and self.canvas.axes in self.canvas.figure.axes:
            handles, labels = self._legend_handles_and_labels(
                self.canvas.axes,
                self._secondary_axes(),
                include_hidden=False,
            )
            if handles:
                temporary_legend = self.canvas.axes.legend(handles, labels, loc="best", fontsize=8)
        try:
            yield
        finally:
            if temporary_legend is not None:
                temporary_legend.remove()
            if selected_annotation_id:
                self._selected_annotation_id = selected_annotation_id
                self._redraw_annotations()
            elif temporary_legend is not None:
                self.canvas.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Cursor / point-compare
    # ------------------------------------------------------------------
    def set_cursor_viewmodel(self, cursor_vm: CursorCompareViewModel) -> None:
        self._cursor_vm = cursor_vm

    def set_point_compare_enabled(self, enabled: bool) -> None:
        self._point_compare = bool(enabled)

    def clear_cursor_markers(self) -> None:
        if self._cursor_vm is not None:
            self._cursor_vm.clear()
        self._remove_cursor_artists()
        self.canvas.canvas.draw_idle()

    def _remove_cursor_artists(self) -> None:
        for artist in self._cursor_artists:
            try:
                artist.remove()
            except (ValueError, AttributeError):
                pass
        self._cursor_artists.clear()

    def _set_cursor_data(self, data) -> None:
        """Reset the cursor viewmodel after a (re)plot and notify listeners."""
        self._cursor_artists.clear()
        if self._cursor_vm is not None:
            self._cursor_vm.set_data(data)
            self.cursorPointsChanged.emit()

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _colours(self) -> list[str]:
        resolver = getattr(self.settings_vm, "plot_colours", None)
        if callable(resolver):
            resolved = resolver()
            if isinstance(resolved, str):
                return [resolved]
            if isinstance(resolved, Iterable):
                return [str(colour) for colour in resolved]
        return SettingsViewModel.plot_colours(self.settings_vm)

    def _secondary_colours(self, colours: list[str]) -> list[str]:
        resolver = getattr(self.settings_vm, "secondary_plot_colours", None)
        if callable(resolver):
            resolved = resolver(colours)
            if isinstance(resolved, str):
                return [resolved]
            if isinstance(resolved, Iterable):
                return [str(colour) for colour in resolved]
        return SettingsViewModel.secondary_plot_colours(self.settings_vm, colours)

    def _line_width(self) -> float:
        try:
            return float(self.settings_vm.get("plot_appearance", "default_line_width", 1.5))
        except (TypeError, ValueError):
            return 1.5

    def _grid_visible(self) -> bool:
        return bool(self.settings_vm.get("plot_appearance", "grid_visible", True))

    def _axis_padding_settings(self) -> dict[str, object]:
        return {
            "pad_x_axis": bool(self.settings_vm.get("axis_scaling", "pad_x_axis", True)),
            "pad_x_percent": self.settings_vm.get("axis_scaling", "pad_x_percent", 5),
            "pad_y_axis": bool(self.settings_vm.get("axis_scaling", "pad_y_axis", True)),
            "pad_y_percent": self.settings_vm.get("axis_scaling", "pad_y_percent", 5),
        }

    @staticmethod
    def _normalise_axis_tick_settings(settings: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(settings, dict):
            settings = {}
        return {
            "x_major_tick": str(settings.get("x_major_tick", "")).strip(),
            "y_major_tick": str(settings.get("y_major_tick", "")).strip(),
            "y2_major_tick": str(settings.get("y2_major_tick", "")).strip(),
            "align_secondary_y_axis_grid": bool(settings.get("align_secondary_y_axis_grid", False)),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_plot(
        self,
        x_col: str,
        y_cols: list[str],
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        title: str = "Engineering Test Data",
        x_label: str = "",
        y_label: str = "",
        secondary_y_label: str = "",
        axis_limits: Optional[dict[str, Optional[float]]] = None,
        auto_fit_axes: bool = True,
        limit_lines: Optional[list[dict]] = None,
        secondary_y: Optional[list[str]] = None,
        plot_kind: str = "Line",
        use_filter: bool = False,
        cutoff: Optional[float] = None,
        order: int = 4,
        channel_colours: Optional[dict[str, str]] = None,
        channel_styles: Optional[dict[str, dict[str, str]]] = None,
        axis_tick_settings: Optional[dict[str, object]] = None,
        annotations: Optional[list[dict[str, object]]] = None,
    ) -> OperationResult:
        try:
            data = self.plot_vm.prepare_plot_data(x_col, y_cols, xmin, xmax)
        except ValueError as exc:
            return OperationResult.failure(str(exc))

        return self.render_plot_data(
            data,
            x_col,
            title=title,
            x_label=x_label,
            y_label=y_label,
            secondary_y_label=secondary_y_label,
            axis_limits=axis_limits,
            auto_fit_axes=auto_fit_axes,
            limit_lines=limit_lines,
            secondary_y=secondary_y,
            plot_kind=plot_kind,
            use_filter=use_filter,
            cutoff=cutoff,
            order=order,
            channel_colours=channel_colours,
            channel_styles=channel_styles,
            axis_tick_settings=axis_tick_settings,
            annotations=annotations,
        )

    def render_plot_data(
        self,
        data,
        x_col: str,
        title: str = "Engineering Test Data",
        x_label: str = "",
        y_label: str = "",
        secondary_y_label: str = "",
        axis_limits: Optional[dict[str, Optional[float]]] = None,
        auto_fit_axes: bool = True,
        limit_lines: Optional[list[dict]] = None,
        secondary_y: Optional[list[str]] = None,
        plot_kind: str = "Line",
        use_filter: bool = False,
        cutoff: Optional[float] = None,
        order: int = 4,
        channel_colours: Optional[dict[str, str]] = None,
        channel_styles: Optional[dict[str, dict[str, str]]] = None,
        axis_tick_settings: Optional[dict[str, object]] = None,
        annotations: Optional[list[dict[str, object]]] = None,
    ) -> OperationResult:

        secondary_set = set(secondary_y or [])
        if annotations is not None:
            self._annotations = normalise_annotations(annotations)
        self.canvas.clear()
        self._best_fit_formula_rows = []
        axes = self.canvas.axes
        colours = self._colours()
        secondary_colours = self._secondary_colours(colours)
        axes.set_prop_cycle(cycler(color=colours))
        series_result = self.plot_vm.plot_series(
            data,
            secondary_y=secondary_set,
            use_filter=use_filter,
            cutoff=cutoff,
            order=order,
        )
        if not series_result.ok:
            return series_result
        series_items = series_result.payload if isinstance(series_result.payload, list) else []
        series_items = self._apply_channel_style_overrides(series_items, channel_styles, plot_kind)
        secondary_axes = None
        if any(bool(item.get("secondary")) for item in series_items):
            secondary_axes = axes.twinx()
            secondary_axes.set_prop_cycle(cycler(color=secondary_colours))
        line_width = self._line_width()
        series_colours = self._series_colours(series_items, channel_colours, colours, secondary_colours)
        plotted = 0
        source_series: list[dict[str, Any]] = []
        for index, item in enumerate(series_items):
            target = secondary_axes if item.get("secondary") and secondary_axes is not None else axes
            item_plot_kind = str(item.get("plot_kind", plot_kind))
            series_colour = series_colours[index]
            artist = self._plot_series(
                target,
                item["x"],
                item["y"],
                str(item.get("label", "")),
                item_plot_kind,
                line_width,
                series_colour,
                item,
            )
            hidden = bool(item.get("hidden", False))
            artist.set_visible(not hidden)
            self._set_legend_artist_metadata(artist, str(item.get("channel", "")), item_plot_kind, item)
            if not hidden:
                source_series.append(
                    {
                        "axes": target,
                        "channel": str(item.get("channel", "")),
                        "label": str(item.get("label", "")),
                        "x": item["x"],
                        "y": item["y"],
                        "colour": series_colour or self._legend_colour(artist),
                    }
                )
            plotted += 1
        if plotted == 0:
            return OperationResult.failure("No numeric data was available for the selected columns.")

        self._draw_best_fit_lines(source_series)
        self._draw_limit_lines(axes, limit_lines)
        axes.set_title(title.strip() or "Engineering Test Data")
        axes.set_xlabel(x_label.strip() or x_col)
        axes.set_ylabel(y_label.strip() or "Selected Signals")
        if secondary_axes is not None:
            secondary_axes.set_ylabel(secondary_y_label.strip() or "Secondary Axis Signals")
        self._apply_axis_padding(axes, secondary_axes, auto_fit_axes)
        self._apply_axis_limits(axes, secondary_axes, axis_limits or {}, auto_fit_axes)
        self.set_axis_tick_settings(axis_tick_settings if axis_tick_settings is not None else self._axis_tick_settings)
        self._apply_axis_tick_settings(axes, secondary_axes, self._axis_tick_settings)
        axes.grid(self._grid_visible(), alpha=0.35)
        handles, labels = self._legend_handles_and_labels(axes, secondary_axes)
        self._apply_legend_display(axes, handles, labels)
        self._draw_annotations(axes, secondary_axes)
        self.canvas.draw()
        self._last_plot_data = data
        self._last_x_col = x_col
        self._set_cursor_data(data)
        self.bestFitFormulasChanged.emit()
        return OperationResult.success(f"Plotted {plotted} channel(s).", payload={"plot_data": data})

    @staticmethod
    def _plot_series(
        axes,
        x,
        y,
        label: str,
        plot_kind: str,
        line_width: float,
        colour: str | None = None,
        style: dict[str, Any] | None = None,
    ):
        style = style or {}
        colour = str(style.get("colour") or colour or "").strip()
        line_width = PlotWorkspace._style_float(style.get("line_width"), line_width)
        line_style = str(style.get("line_style", "-")).strip() or "-"
        draw_style = str(style.get("draw_style", "default")).strip() or "default"
        marker_style = PlotWorkspace._normalise_marker_style(style.get("marker_style"))
        marker_size = PlotWorkspace._style_float(style.get("marker_size"), 3.0)
        marker_face_colour = str(style.get("marker_face_colour", "")).strip()
        marker_edge_colour = str(style.get("marker_edge_colour", "")).strip()
        kwargs: dict[str, Any] = {"label": label}
        if plot_kind == "Scatter":
            marker = marker_style if marker_style not in {"", "none", "None"} else "o"
            if marker_face_colour:
                kwargs["facecolors"] = marker_face_colour
            elif colour:
                kwargs["color"] = colour
            if marker_edge_colour:
                kwargs["edgecolors"] = marker_edge_colour
            artist = axes.scatter(x, y, s=marker_size ** 2, marker=marker, **kwargs)
            setattr(artist, "_tda_marker_style", marker)
            return artist
        if colour:
            kwargs["color"] = colour
        kwargs["linestyle"] = line_style
        kwargs["drawstyle"] = draw_style
        if marker_style and marker_style not in {"none", "None"}:
            kwargs["marker"] = marker_style
            kwargs["markersize"] = marker_size
            if marker_face_colour:
                kwargs["markerfacecolor"] = marker_face_colour
            if marker_edge_colour:
                kwargs["markeredgecolor"] = marker_edge_colour
        elif plot_kind == "Line + Markers":
            kwargs["marker"] = "o"
            kwargs["markersize"] = marker_size
        artist = axes.plot(x, y, linewidth=line_width, **kwargs)[0]
        return artist

    @classmethod
    def _apply_channel_style_overrides(
        cls,
        series_items: list[dict[str, Any]],
        channel_styles: Optional[dict[str, dict[str, str]]],
        default_plot_kind: str,
    ) -> list[dict[str, Any]]:
        return plot_render_service.apply_channel_style_overrides(series_items, channel_styles, default_plot_kind)

    @classmethod
    def _normalised_channel_styles(cls, channel_styles: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        return plot_render_service.normalised_channel_styles(channel_styles)

    @staticmethod
    def _style_bool(value: object) -> bool:
        return plot_render_service.style_bool(value)

    @staticmethod
    def _series_label_with_override(item: dict[str, Any], style: dict[str, str]) -> str:
        return plot_render_service.series_label_with_override(item, style)

    @staticmethod
    def _normalise_plot_kind(plot_kind: object) -> str:
        return plot_render_service.normalise_plot_kind(plot_kind)

    @staticmethod
    def _style_float(value: object, default: float) -> float:
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _normalise_marker_style(value: object) -> str:
        return legend_metadata_service.normalise_marker_style(value)

    def _series_colours(
        self,
        series_items: list[dict[str, Any]],
        channel_colours: Optional[dict[str, str]],
        primary_colours: list[str],
        secondary_colours: list[str],
    ) -> list[str | None]:
        return plot_render_service.series_colour_assignment(
            series_items, channel_colours, primary_colours, secondary_colours
        )

    @staticmethod
    def _series_channel_key(item: dict[str, Any]) -> str:
        return plot_render_service.series_channel_key(item)

    def _draw_best_fit_lines(self, source_series: list[dict[str, Any]]) -> None:
        self._best_fit_formula_rows.extend(
            best_fit_renderer.draw_best_fit_lines(
                self._best_fit_settings,
                source_series,
                self.canvas.axes,
                line_width=self._line_width(),
                default_colour=EATON_DARK_BLUE,
            )
        )

    def _remove_best_fit_artists(self) -> None:
        best_fit_renderer.remove_best_fit_artists(list(self.canvas.figure.axes))

    def _best_fit_source_series(self) -> list[dict[str, Any]]:
        return best_fit_renderer.source_series(list(self.canvas.figure.axes))

    @classmethod
    def _legend_handles_and_labels(cls, axes, secondary_axes, *, include_hidden: bool = True):
        handles, labels = cls._artist_handles_and_labels(axes, include_hidden=include_hidden)
        if secondary_axes is not None:
            extra_handles, extra_labels = cls._artist_handles_and_labels(secondary_axes, include_hidden=include_hidden)
            handles += extra_handles
            labels += extra_labels
        return cls._sort_legend_handles_and_labels(handles, labels)

    @staticmethod
    def _artist_handles_and_labels(axes, *, include_hidden: bool) -> tuple[list, list[str]]:
        handles = []
        labels = []
        for artist in [*axes.get_lines(), *axes.collections]:
            if bool(getattr(artist, "_tda_hidden", False)) and not include_hidden:
                continue
            label_getter = getattr(artist, "get_label", None)
            label = str(label_getter() if callable(label_getter) else "")
            if not label or label.startswith("_"):
                continue
            handles.append(artist)
            labels.append(label)
        return handles, labels

    @staticmethod
    def _sort_legend_handles_and_labels(handles, labels):
        pairs = list(zip(handles, labels))
        pairs.sort(key=lambda item: PlotWorkspace._legend_label_sort_key(item[1]))
        return [handle for handle, _label in pairs], [label for _handle, label in pairs]

    @staticmethod
    def _legend_label_sort_key(label: str) -> list[object]:
        text = PlotWorkspace._without_right_y_suffix(label)
        return natural_sort_key(" ".join(text.split()))

    @staticmethod
    def _without_right_y_suffix(label: str) -> str:
        return str(label).replace(" [Right Y]", "").strip()

    def _update_legend_table(self, handles, labels) -> None:
        self.legend_table.setRowCount(0)
        for handle, label in zip(handles, labels):
            if not label:
                continue
            row = self.legend_table.rowCount()
            self.legend_table.insertRow(row)
            metadata = self._legend_channel_metadata(handle, label)
            swatch_item = QTableWidgetItem("")
            swatch_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            text = QTableWidgetItem(label)
            text.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if metadata:
                swatch_item.setData(Qt.ItemDataRole.UserRole, metadata)
                text.setData(Qt.ItemDataRole.UserRole, metadata)
                text.setToolTip("Click to edit this plotted channel.")
            self.legend_table.setItem(row, 0, swatch_item)
            self.legend_table.setCellWidget(row, 0, self._legend_swatch(self._legend_colour(handle)))
            self.legend_table.setItem(row, 1, text)
            if metadata:
                self.legend_table.setCellWidget(row, 2, self._legend_visibility_cell(metadata))

    @staticmethod
    def _set_legend_artist_metadata(artist, channel: str, plot_kind: str, style: dict[str, object]) -> None:
        setattr(artist, "_tda_channel", channel)
        setattr(artist, "_tda_plot_kind", plot_kind)
        setattr(artist, "_tda_label_overridden", bool(style.get("label_overridden", False)))
        setattr(artist, "_tda_plot_kind_overridden", bool(style.get("plot_kind_overridden", False)))
        setattr(artist, "_tda_hidden", bool(style.get("hidden", False)))
        for key in CURVE_STYLE_KEYS:
            if key in style:
                setattr(artist, f"_tda_{key}", style[key])
        try:
            artist.set_gid(channel)
        except AttributeError:
            pass

    def _legend_channel_metadata(self, handle, label: str) -> dict[str, object]:
        return legend_metadata_service.channel_metadata(handle, label)

    def _legend_visibility_cell(self, metadata: dict[str, object]) -> QWidget:
        channel = str(metadata.get("channel", ""))
        hidden = bool(metadata.get("hidden", False))
        checkbox = QCheckBox()
        checkbox.setObjectName("LegendVisibilityCheckBox")
        checkbox.setChecked(not hidden)
        checkbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        checkbox.setToolTip(("Show" if hidden else "Hide") + f" '{metadata.get('label', channel)}' on the plot.")
        checkbox.toggled.connect(lambda checked, channel=channel: self.legendChannelVisibilityChanged.emit(channel, not checked))
        cell = QWidget()
        cell.setObjectName("LegendVisibilityCell")
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(checkbox, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        return cell

    def _on_legend_cell_clicked(self, row: int, _column: int) -> None:
        if _column != 1:
            return
        item = self.legend_table.item(row, 1)
        metadata = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(metadata, dict) or not metadata.get("channel"):
            return
        channel = str(metadata.get("channel", ""))
        dialog = LegendChannelStyleDialog(channel, metadata, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.legendChannelStyleChanged.emit(channel, dialog.values())

    @staticmethod
    def _legend_swatch(colour: str) -> QWidget:
        container = QWidget()
        container.setObjectName("LegendSwatchCell")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        swatch = QFrame(container)
        swatch.setObjectName("LegendColourSwatch")
        swatch.setMinimumSize(14, 12)
        swatch.setStyleSheet(
            f"QFrame#LegendColourSwatch {{ background-color: {colour}; border: 1px solid #FFFFFF; border-radius: 2px; }}"
        )
        layout.addWidget(swatch)
        return container

    def _apply_legend_display(self, axes, handles, labels) -> None:
        self._update_legend_table(handles, labels)
        self.legend_panel.setVisible(self._legend_display == LEGEND_DISPLAY_PANEL)
        self._remove_canvas_legends()
        if self._legend_display == LEGEND_DISPLAY_GRAPH and handles:
            graph_handles, graph_labels = self._legend_handles_and_labels(axes, self._secondary_axes(), include_hidden=False)
            if graph_handles:
                axes.legend(graph_handles, graph_labels, loc="best", fontsize=8)

    def _refresh_current_legend(self) -> None:
        if self.canvas.axes not in self.canvas.figure.axes:
            return
        handles, labels = self._legend_handles_and_labels(self.canvas.axes, self._secondary_axes())
        self._apply_legend_display(self.canvas.axes, handles, labels)
        self.canvas.canvas.draw_idle()

    def _secondary_axes(self):
        for axes in self.canvas.figure.axes:
            if axes is not self.canvas.axes:
                return axes
        return None

    def _remove_canvas_legends(self) -> None:
        for axes in self.canvas.figure.axes:
            legend = axes.get_legend()
            if legend is not None:
                legend.remove()

    @staticmethod
    def _legend_colour(handle) -> str:
        return legend_metadata_service.legend_colour(handle)

    def _apply_axis_padding(self, axes, secondary_axes, auto_fit_axes: bool) -> None:
        """Apply the user-configured X/Y autoscale padding (margins).

        Only affects auto-fitted axes; explicit limits already define their own
        range. Disabling an axis sets its margin to zero so the data spans the
        full axis, while enabling uses the configured percentage (default 5%).
        """
        if not auto_fit_axes:
            return
        pad_x = self._axis_pad_fraction("pad_x_axis", "pad_x_percent")
        pad_y = self._axis_pad_fraction("pad_y_axis", "pad_y_percent")
        axes.margins(x=pad_x, y=pad_y)
        if secondary_axes is not None:
            secondary_axes.margins(y=pad_y)

    def _axis_pad_fraction(self, enabled_key: str, percent_key: str) -> float:
        if not bool(self.settings_vm.get("axis_scaling", enabled_key, True)):
            return 0.0
        try:
            percent = float(self.settings_vm.get("axis_scaling", percent_key, 5))
        except (TypeError, ValueError):
            percent = 5.0
        return max(0.0, percent / 100.0)

    @staticmethod
    def _apply_axis_limits(axes, secondary_axes, axis_limits: dict[str, Optional[float]], auto_fit_axes: bool) -> None:
        if auto_fit_axes:
            return
        PlotWorkspace._set_axis_range(axes.set_xlim, axes.get_xlim, axis_limits.get("xmin"), axis_limits.get("xmax"))
        PlotWorkspace._set_axis_range(axes.set_ylim, axes.get_ylim, axis_limits.get("ymin"), axis_limits.get("ymax"))
        if secondary_axes is not None:
            PlotWorkspace._set_axis_range(
                secondary_axes.set_ylim,
                secondary_axes.get_ylim,
                axis_limits.get("y2min"),
                axis_limits.get("y2max"),
            )

    @staticmethod
    def _set_axis_range(setter, getter, minimum: Optional[float], maximum: Optional[float]) -> None:
        resolved = plot_render_service.resolve_axis_range(getter(), minimum, maximum)
        if resolved is not None:
            setter(*resolved)

    @classmethod
    def _apply_axis_tick_settings(cls, axes, secondary_axes, settings: dict[str, object]) -> None:
        x_major_tick = cls._safe_major_tick(cls._positive_float(settings.get("x_major_tick")), axes.get_xlim())
        y_major_tick = cls._safe_major_tick(cls._positive_float(settings.get("y_major_tick")), axes.get_ylim())
        y2_major_tick = None
        if secondary_axes is not None:
            y2_major_tick = cls._safe_major_tick(cls._positive_float(settings.get("y2_major_tick")), secondary_axes.get_ylim())

        if x_major_tick is not None:
            axes.xaxis.set_major_locator(MultipleLocator(x_major_tick))
        if y_major_tick is not None:
            axes.yaxis.set_major_locator(MultipleLocator(y_major_tick))
        if secondary_axes is not None and y2_major_tick is not None:
            secondary_axes.yaxis.set_major_locator(MultipleLocator(y2_major_tick))
        if secondary_axes is not None and bool(settings.get("align_secondary_y_axis_grid", False)):
            cls._align_secondary_y_ticks_to_primary(axes, secondary_axes)

    @classmethod
    def _safe_major_tick(cls, step: float | None, limits: tuple[float, float]) -> float | None:
        """Ignore a tick step too small for the axis range to avoid a tick blow-up.

        Matplotlib's ``MultipleLocator`` raises ``Locator.MAXTICKS`` once a step
        forces more than ~1000 ticks across the axis span. A tiny step on a wide
        axis (for example 2 on a 0-90000 flow-rate axis) would crash rendering, so
        the step is dropped and automatic ticks are kept instead.
        """
        return axis_limits_computer.safe_major_tick(step, limits, max_ticks=cls.MAX_AXIS_MAJOR_TICKS)

    @staticmethod
    def _positive_float(value: object) -> float | None:
        return axis_limits_computer.positive_float(value)

    @staticmethod
    def _align_secondary_y_ticks_to_primary(axes, secondary_axes) -> None:
        primary_min, primary_max = axes.get_ylim()
        secondary_min, secondary_max = secondary_axes.get_ylim()
        if primary_min == primary_max or secondary_min == secondary_max:
            return
        visible_lower = min(primary_min, primary_max)
        visible_upper = max(primary_min, primary_max)
        primary_ticks = [
            tick
            for tick in axes.get_yticks()
            if visible_lower <= float(tick) <= visible_upper
        ]
        if len(primary_ticks) < 2:
            return
        secondary_ticks = axis_limits_computer.mapped_secondary_ticks(
            primary_ticks, primary_min, primary_max, secondary_min, secondary_max
        )
        secondary_axes.set_yticks(secondary_ticks)

    @staticmethod
    def _draw_limit_lines(axes, limit_lines: Optional[list[dict]]) -> None:
        """Overlay requirement limit lines (already normalised) with >=2 points."""
        for line in limit_lines or []:
            points = line.get("points", [])
            if len(points) < 2:
                continue
            xs = [point["x"] for point in points]
            ys = [point["y"] for point in points]
            limit_type = line.get("type", "Upper Limit")
            linestyle = ":" if limit_type == "Reference Line" else "--"
            label = f"{line.get('name', 'Limit')} [{limit_type}]"
            colour = line.get("color", EATON_DARK_BLUE)
            try:
                axes.plot(xs, ys, linestyle=linestyle, linewidth=1.6, color=colour, label=label)
            except (ValueError, KeyError):
                axes.plot(xs, ys, linestyle=linestyle, linewidth=1.6, color=EATON_DARK_BLUE, label=label)

    def generate_comparison_plot(
        self,
        items: list[dict],
        x_col: str,
        title: str = "Run Comparison",
        limit_lines: Optional[list[dict]] = None,
    ) -> OperationResult:
        """Draw prepared comparison items (one line per run/channel).

        Each item is ``{"label", "x", "y", "colour"}`` from
        :meth:`RunsComparisonViewModel.comparison_plot_items`.
        """
        if not items:
            return OperationResult.failure("No numeric comparison data was available for the enabled runs.")

        self.canvas.clear()
        axes = self.canvas.axes
        axes.set_prop_cycle(cycler(color=self._colours()))
        line_width = self._line_width()
        plotted = 0
        for item in self.plot_vm.comparison_series(items):
            axes.plot(item["x"], item["y"], label=item.get("label", ""), linewidth=line_width, color=item.get("colour"))
            plotted += 1
        if plotted == 0:
            return OperationResult.failure("No numeric comparison data was available for the enabled runs.")

        self._draw_limit_lines(axes, limit_lines)
        axes.set_title(title)
        axes.set_xlabel(x_col)
        axes.set_ylabel("Selected Signals")
        axes.grid(self._grid_visible(), alpha=0.35)
        handles, labels = self._legend_handles_and_labels(axes, None)
        self._apply_legend_display(axes, handles, labels)
        self._draw_annotations(axes, None)
        self.canvas.draw()
        self._set_cursor_data(None)
        return OperationResult.success(f"Comparison plot generated for {plotted} series.")
