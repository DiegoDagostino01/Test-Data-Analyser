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
from matplotlib.backends.qt_editor import figureoptions
from matplotlib.colors import to_hex
from matplotlib.ticker import MultipleLocator
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.config import EATON_DARK_BLUE
from ...core.utils import natural_sort_key
from ...services import plot_render_service
from ...services.results import OperationResult
from ...viewmodels.cursor_compare_vm import CursorCompareViewModel
from ...viewmodels.plot_workspace_vm import PlotWorkspaceViewModel
from ...viewmodels.settings_vm import SettingsViewModel
from ..adapters.matplotlib_qt_adapter import LEGEND_DISPLAY_GRAPH, LEGEND_DISPLAY_PANEL, MatplotlibCanvas
from .axis_selection_panel import PLOT_KINDS
from .no_wheel_combo_box import NoWheelComboBox

CURVE_STYLE_KEYS = {
    "line_style",
    "draw_style",
    "line_width",
    "marker_style",
    "marker_size",
    "marker_face_colour",
    "marker_edge_colour",
}

LINE_STYLE_CHOICES = tuple(figureoptions.LINESTYLES.items())
DRAW_STYLE_CHOICES = tuple(figureoptions.DRAWSTYLES.items())
MARKER_STYLE_CHOICES = (("none", "None"), *tuple(figureoptions.MARKERS.items()))


class LegendChannelStyleDialog(QDialog):
    def __init__(self, channel: str, style: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channel = channel.strip()
        self._original_label = str(style.get("label", self._channel)).strip() or self._channel
        self._label_overridden = bool(style.get("label_overridden", False))
        self._original_plot_kind = PlotWorkspace._normalise_plot_kind(style.get("plot_kind")) or "Line"
        self._plot_kind_overridden = bool(style.get("plot_kind_overridden", False))
        self._current_colours = {
            "colour": self._normalise_colour(style.get("colour")) or EATON_DARK_BLUE,
            "marker_face_colour": self._normalise_colour(style.get("marker_face_colour"))
            or self._normalise_colour(style.get("colour"))
            or EATON_DARK_BLUE,
            "marker_edge_colour": self._normalise_colour(style.get("marker_edge_colour"))
            or self._normalise_colour(style.get("colour"))
            or EATON_DARK_BLUE,
        }
        self._colour_edits: dict[str, QLineEdit] = {}
        self._colour_swatches: dict[str, QFrame] = {}
        self.setWindowTitle("Edit Legend Channel")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(self._original_label)
        form.addRow("Name:", self.name_edit)

        form.addRow("Colour:", self._build_colour_row("colour"))

        self.plot_kind_combo = NoWheelComboBox()
        self.plot_kind_combo.addItems(PLOT_KINDS)
        self.plot_kind_combo.setCurrentText(self._original_plot_kind)
        form.addRow("Plot Type:", self.plot_kind_combo)

        self.line_style_combo = self._style_combo(LINE_STYLE_CHOICES, str(style.get("line_style", "-")))
        form.addRow("Line style:", self.line_style_combo)
        self.draw_style_combo = self._style_combo(DRAW_STYLE_CHOICES, str(style.get("draw_style", "default")))
        form.addRow("Draw style:", self.draw_style_combo)
        self.line_width_spin = self._number_spin(style.get("line_width", 1.5), default=1.5)
        form.addRow("Line width:", self.line_width_spin)

        marker_default = self._default_marker_for_plot_kind(self._original_plot_kind)
        self.marker_style_combo = self._style_combo(MARKER_STYLE_CHOICES, str(style.get("marker_style", marker_default)))
        form.addRow("Marker style:", self.marker_style_combo)
        self.marker_size_spin = self._number_spin(style.get("marker_size", 3.0), default=3.0)
        form.addRow("Marker size:", self.marker_size_spin)
        form.addRow("Marker face:", self._build_colour_row("marker_face_colour"))
        form.addRow("Marker edge:", self._build_colour_row("marker_edge_colour"))
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        label = self.name_edit.text().strip() or self._channel
        plot_kind = self.plot_kind_combo.currentText()
        values = {
            "channel": self._channel,
            "colour": self._current_colours["colour"],
            "line_style": self._combo_value(self.line_style_combo),
            "draw_style": self._combo_value(self.draw_style_combo),
            "line_width": f"{self.line_width_spin.value():g}",
            "marker_style": self._combo_value(self.marker_style_combo),
            "marker_size": f"{self.marker_size_spin.value():g}",
            "marker_face_colour": self._current_colours["marker_face_colour"],
            "marker_edge_colour": self._current_colours["marker_edge_colour"],
        }
        if self._label_overridden or label != self._original_label:
            values["label"] = label
        if self._plot_kind_overridden or plot_kind != self._original_plot_kind:
            values["plot_kind"] = plot_kind
        return values

    def accept(self) -> None:
        for key in self._current_colours:
            self._sync_colour_from_text(key)
        if not self.name_edit.text().strip():
            self.name_edit.setText(self._channel)
        super().accept()

    def _build_colour_row(self, key: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(self._current_colours[key])
        edit.setFixedWidth(92)
        edit.editingFinished.connect(lambda key=key: self._sync_colour_from_text(key))
        swatch = QFrame()
        swatch.setFrameShape(QFrame.Shape.Box)
        swatch.setFixedWidth(28)
        pick_button = QPushButton("Choose...")
        pick_button.clicked.connect(lambda _checked=False, key=key: self._pick_colour(key))
        layout.addWidget(edit)
        layout.addWidget(swatch)
        layout.addWidget(pick_button)
        layout.addStretch(1)
        self._colour_edits[key] = edit
        self._colour_swatches[key] = swatch
        if key == "colour":
            self.colour_edit = edit
            self.colour_swatch = swatch
        self._update_swatch(key)
        return row

    def _pick_colour(self, key: str) -> None:
        chosen = QColorDialog.getColor(QColor(self._current_colours[key]), self, "Select Channel Colour")
        if chosen.isValid():
            self._set_colour(key, chosen.name())

    def _sync_colour_from_text(self, key: str) -> None:
        self._set_colour(key, self._colour_edits[key].text())

    def _set_colour(self, key: str, colour: str) -> None:
        normalised = self._normalise_colour(colour)
        if normalised:
            self._current_colours[key] = normalised
        self._colour_edits[key].setText(self._current_colours[key])
        self._update_swatch(key)

    def _update_swatch(self, key: str) -> None:
        self._colour_swatches[key].setStyleSheet(
            f"background-color: {self._current_colours[key]}; border: 1px solid #888888; border-radius: 2px;"
        )

    @staticmethod
    def _style_combo(choices: Iterable[tuple[object, object]], current: str) -> NoWheelComboBox:
        combo = NoWheelComboBox()
        seen: set[str] = set()
        for value, label in choices:
            value_text = str(value)
            if value_text in seen:
                continue
            seen.add(value_text)
            combo.addItem(str(label), value_text)
        index = combo.findData(current)
        if index < 0 and current in {"None", "none", ""}:
            index = combo.findData("none")
        combo.setCurrentIndex(max(0, index))
        return combo

    @staticmethod
    def _combo_value(combo: NoWheelComboBox) -> str:
        data = combo.currentData()
        return str(data if data is not None else combo.currentText())

    @staticmethod
    def _number_spin(value: object, *, default: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setRange(0.0, 1000.0)
        spin.setSingleStep(0.5)
        try:
            spin.setValue(float(str(value)))
        except (TypeError, ValueError):
            spin.setValue(default)
        return spin

    @staticmethod
    def _default_marker_for_plot_kind(plot_kind: str) -> str:
        return "o" if plot_kind in {"Scatter", "Line + Markers"} else "none"

    @staticmethod
    def _normalise_colour(colour: object) -> str:
        qt_colour = QColor(str(colour or "").strip())
        return qt_colour.name() if qt_colour.isValid() else ""


class PlotWorkspace(QWidget):
    cursorPointsChanged = Signal()
    legendChannelStyleChanged = Signal(str, dict)
    LEGEND_DEFAULT_WIDTH = 230
    LEGEND_MAXIMUM_WIDTH = 320

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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = MatplotlibCanvas(self)
        self.apply_theme()
        self.canvas.toolbar.set_legend_display_controller(self.legend_display, self.set_legend_display)
        self.canvas.toolbar.set_export_preparer(self._legend_export_context)
        self.canvas.toolbar.set_axis_padding_getter(self._axis_padding_settings)
        self.canvas.toolbar.set_axis_tick_settings_controller(
            self.axis_tick_setting_texts,
            self.set_axis_tick_settings,
            self.apply_axis_tick_settings_to_current_plot,
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
        layout.addWidget(self.plot_legend_splitter)

        self.canvas.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.canvas.canvas.mpl_connect("key_press_event", self._on_canvas_key)

    def apply_theme(self, theme_name: str | None = None) -> None:
        self.canvas.apply_theme(theme_name or self._theme_name())

    def _theme_name(self) -> str:
        resolver = getattr(self.settings_vm, "theme_name", None)
        if callable(resolver):
            return str(resolver())
        return "light"

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

        self.legend_table = QTableWidget(0, 2)
        self.legend_table.setHorizontalHeaderLabels(["", "Series"])
        self.legend_table.verticalHeader().setVisible(False)
        self.legend_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.legend_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.legend_table.cellClicked.connect(self._on_legend_cell_clicked)
        self.legend_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.legend_table.horizontalHeader().resizeSection(0, 28)
        self.legend_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
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
        self._remove_cursor_artists()
        self._set_cursor_data(None)
        self.canvas.clear()
        self._update_legend_table([], [])
        self.legend_panel.setVisible(self._legend_display == LEGEND_DISPLAY_PANEL)
        self.canvas.draw()
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
        if self._legend_display == LEGEND_DISPLAY_PANEL and self.canvas.axes in self.canvas.figure.axes:
            handles, labels = self._legend_handles_and_labels(self.canvas.axes, self._secondary_axes())
            if handles:
                temporary_legend = self.canvas.axes.legend(handles, labels, loc="best", fontsize=8)
        try:
            yield
        finally:
            if temporary_legend is not None:
                temporary_legend.remove()
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

    def _on_canvas_click(self, event) -> None:
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

    def _on_canvas_key(self, event) -> None:
        if event.key == "escape":
            self.clear_cursor_markers()
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
    ) -> OperationResult:
        try:
            data = self.plot_vm.prepare_plot_data(x_col, y_cols, xmin, xmax)
        except ValueError as exc:
            return OperationResult.failure(str(exc))

        secondary_set = set(secondary_y or [])
        self.canvas.clear()
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
        for index, item in enumerate(series_items):
            target = secondary_axes if item.get("secondary") and secondary_axes is not None else axes
            item_plot_kind = str(item.get("plot_kind", plot_kind))
            artist = self._plot_series(
                target,
                item["x"],
                item["y"],
                str(item.get("label", "")),
                item_plot_kind,
                line_width,
                series_colours[index],
                item,
            )
            self._set_legend_artist_metadata(artist, str(item.get("channel", "")), item_plot_kind, item)
            plotted += 1
        if plotted == 0:
            return OperationResult.failure("No numeric data was available for the selected columns.")

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
        self.canvas.draw()
        self._last_plot_data = data
        self._last_x_col = x_col
        self._set_cursor_data(data)
        return OperationResult.success(f"Plotted {plotted} channel(s).")

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
        styles = cls._normalised_channel_styles(channel_styles or {})
        fallback_plot_kind = cls._normalise_plot_kind(default_plot_kind) or "Line"
        styled_items: list[dict[str, Any]] = []
        for item in series_items:
            styled = dict(item)
            style = styles.get(cls._series_channel_key(item), {})
            label = cls._series_label_with_override(item, style)
            if label:
                styled["label"] = label
            plot_kind = cls._normalise_plot_kind(style.get("plot_kind")) or fallback_plot_kind
            styled["plot_kind"] = plot_kind
            colour = str(style.get("colour", "")).strip()
            if colour:
                styled["colour"] = colour
            for key in CURVE_STYLE_KEYS:
                value = str(style.get(key, "")).strip()
                if value:
                    styled[key] = value
            styled["label_overridden"] = bool(style.get("label"))
            styled["plot_kind_overridden"] = bool(style.get("plot_kind"))
            styled_items.append(styled)
        return styled_items

    @classmethod
    def _normalised_channel_styles(cls, channel_styles: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        normalised: dict[str, dict[str, str]] = {}
        for raw_key, raw_style in channel_styles.items():
            if not isinstance(raw_style, dict):
                continue
            style: dict[str, str] = {}
            for raw_name, raw_value in raw_style.items():
                value = str(raw_value).strip()
                if not value:
                    continue
                name = "label" if raw_name == "name" else "colour" if raw_name == "color" else str(raw_name)
                if name == "plot_kind":
                    value = cls._normalise_plot_kind(value)
                    if not value:
                        continue
                if name in {"channel", "label", "colour", "plot_kind", *CURVE_STYLE_KEYS}:
                    style[name] = value
            channel_key = plot_render_service.normalise_channel_name(style.get("channel") or raw_key)
            if channel_key and style:
                normalised[channel_key] = style
        return normalised

    @staticmethod
    def _series_label_with_override(item: dict[str, Any], style: dict[str, str]) -> str:
        custom_label = str(style.get("label", "")).strip()
        if not custom_label:
            return str(item.get("label", ""))
        label = PlotWorkspace._without_right_y_suffix(custom_label)
        return f"{label} [Right Y]" if item.get("secondary") else label

    @staticmethod
    def _normalise_plot_kind(plot_kind: object) -> str:
        text = str(plot_kind or "").strip()
        if text == "Line + Marker":
            text = "Line + Markers"
        return text if text in PLOT_KINDS else ""

    @staticmethod
    def _style_float(value: object, default: float) -> float:
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _normalise_marker_style(value: object) -> str:
        text = str(value or "").strip()
        if text in {"", "None", "none"}:
            return "none"
        return text

    def _series_colours(
        self,
        series_items: list[dict[str, Any]],
        channel_colours: Optional[dict[str, str]],
        primary_colours: list[str],
        secondary_colours: list[str],
    ) -> list[str | None]:
        persistent_colours = self._normalised_channel_colours(channel_colours or {})
        manual_colours = [self._manual_series_colour(item) for item in series_items]
        has_manual_colour = any(manual_colours)
        has_repeated_channel = any(self._series_channel_key(item) in persistent_colours for item in series_items)
        if not has_manual_colour and not has_repeated_channel:
            return [None for _item in series_items]

        reserved = {
            self._colour_key(colour)
            for item, manual_colour in zip(series_items, manual_colours)
            for colour in (manual_colour or persistent_colours.get(self._series_channel_key(item)),)
            if colour
        }
        assignments: list[str | None] = []
        used: set[str] = set()
        primary_index = 0
        secondary_index = 0
        for item, manual_colour in zip(series_items, manual_colours):
            is_secondary = bool(item.get("secondary"))
            channel_colour = manual_colour or persistent_colours.get(self._series_channel_key(item))
            if not channel_colour:
                cycle = secondary_colours if is_secondary else primary_colours
                cycle_index = secondary_index if is_secondary else primary_index
                channel_colour = self._next_distinct_colour(cycle, cycle_index, used | reserved)
            assignments.append(channel_colour)
            if channel_colour:
                used.add(self._colour_key(channel_colour))
            if is_secondary:
                secondary_index += 1
            else:
                primary_index += 1
        return assignments

    @staticmethod
    def _normalised_channel_colours(channel_colours: dict[str, str]) -> dict[str, str]:
        normalised: dict[str, str] = {}
        for channel, colour in channel_colours.items():
            key = plot_render_service.normalise_channel_name(channel)
            colour_text = str(colour).strip()
            if key and colour_text:
                normalised[key] = colour_text
        return normalised

    @staticmethod
    def _series_channel_key(item: dict[str, Any]) -> str:
        return plot_render_service.normalise_channel_name(item.get("channel", item.get("label", "")))

    @staticmethod
    def _manual_series_colour(item: dict[str, Any]) -> str:
        colour = item.get("colour", item.get("color"))
        return "" if colour is None else str(colour).strip()

    @classmethod
    def _next_distinct_colour(cls, colours: list[str], start_index: int, blocked: set[str]) -> str | None:
        if not colours:
            return None
        for offset in range(len(colours)):
            colour = colours[(start_index + offset) % len(colours)]
            if cls._colour_key(colour) not in blocked:
                return colour
        return colours[start_index % len(colours)]

    @staticmethod
    def _colour_key(colour: str) -> str:
        try:
            return to_hex(colour).lower()
        except Exception:
            return str(colour).strip().lower()

    @classmethod
    def _legend_handles_and_labels(cls, axes, secondary_axes):
        handles, labels = axes.get_legend_handles_labels()
        if secondary_axes is not None:
            extra_handles, extra_labels = secondary_axes.get_legend_handles_labels()
            handles += extra_handles
            labels += extra_labels
        return cls._sort_legend_handles_and_labels(handles, labels)

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

    @staticmethod
    def _set_legend_artist_metadata(artist, channel: str, plot_kind: str, style: dict[str, object]) -> None:
        setattr(artist, "_tda_channel", channel)
        setattr(artist, "_tda_plot_kind", plot_kind)
        setattr(artist, "_tda_label_overridden", bool(style.get("label_overridden", False)))
        setattr(artist, "_tda_plot_kind_overridden", bool(style.get("plot_kind_overridden", False)))
        for key in CURVE_STYLE_KEYS:
            if key in style:
                setattr(artist, f"_tda_{key}", style[key])
        try:
            artist.set_gid(channel)
        except AttributeError:
            pass

    def _legend_channel_metadata(self, handle, label: str) -> dict[str, object]:
        channel = str(getattr(handle, "_tda_channel", "")).strip()
        if not channel:
            return {}
        return {
            "channel": channel,
            "label": self._without_right_y_suffix(label),
            "colour": self._legend_colour(handle),
            "plot_kind": str(getattr(handle, "_tda_plot_kind", "Line")),
            "label_overridden": bool(getattr(handle, "_tda_label_overridden", False)),
            "plot_kind_overridden": bool(getattr(handle, "_tda_plot_kind_overridden", False)),
            **self._legend_curve_metadata(handle),
        }

    def _legend_curve_metadata(self, handle) -> dict[str, str]:
        metadata = {key: str(getattr(handle, f"_tda_{key}", "")).strip() for key in CURVE_STYLE_KEYS}
        try:
            metadata["line_style"] = metadata["line_style"] or str(handle.get_linestyle())
            metadata["draw_style"] = metadata["draw_style"] or str(handle.get_drawstyle())
            metadata["line_width"] = metadata["line_width"] or f"{float(handle.get_linewidth()):g}"
            metadata["marker_style"] = metadata["marker_style"] or self._normalise_marker_style(handle.get_marker())
            metadata["marker_size"] = metadata["marker_size"] or f"{float(handle.get_markersize()):g}"
            metadata["marker_face_colour"] = metadata["marker_face_colour"] or self._colour_to_hex(handle.get_markerfacecolor())
            metadata["marker_edge_colour"] = metadata["marker_edge_colour"] or self._colour_to_hex(handle.get_markeredgecolor())
        except AttributeError:
            sizes = getattr(handle, "get_sizes", lambda: [])()
            face_colours = getattr(handle, "get_facecolors", lambda: [])()
            edge_colours = getattr(handle, "get_edgecolors", lambda: [])()
            metadata["line_style"] = metadata["line_style"] or "None"
            metadata["draw_style"] = metadata["draw_style"] or "default"
            metadata["line_width"] = metadata["line_width"] or "0"
            metadata["marker_style"] = metadata["marker_style"] or str(getattr(handle, "_tda_marker_style", "o"))
            if len(sizes):
                metadata["marker_size"] = metadata["marker_size"] or f"{math.sqrt(float(sizes[0])):g}"
            metadata["marker_face_colour"] = metadata["marker_face_colour"] or self._first_colour_to_hex(face_colours)
            metadata["marker_edge_colour"] = metadata["marker_edge_colour"] or self._first_colour_to_hex(edge_colours)
        return metadata

    @staticmethod
    def _colour_to_hex(colour: object) -> str:
        try:
            return to_hex(cast(Any, colour))
        except Exception:
            return ""

    @classmethod
    def _first_colour_to_hex(cls, colours: object) -> str:
        try:
            colour_values = list(cast(Any, colours))
            if colour_values:
                return cls._colour_to_hex(colour_values[0])
        except Exception:
            pass
        return ""

    def _on_legend_cell_clicked(self, row: int, _column: int) -> None:
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
            axes.legend(handles, labels, loc="best", fontsize=8)

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
        try:
            colour = handle.get_color()
            return to_hex(colour)
        except Exception:
            pass
        try:
            colours = handle.get_facecolors()
            if len(colours):
                return to_hex(colours[0])
        except Exception:
            pass
        return EATON_DARK_BLUE

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
        if minimum is None and maximum is None:
            return
        current_min, current_max = getter()
        lower = current_min if minimum is None else minimum
        upper = current_max if maximum is None else maximum
        if lower < upper:
            setter(lower, upper)

    @classmethod
    def _apply_axis_tick_settings(cls, axes, secondary_axes, settings: dict[str, object]) -> None:
        x_major_tick = cls._positive_float(settings.get("x_major_tick"))
        y_major_tick = cls._positive_float(settings.get("y_major_tick"))
        y2_major_tick = cls._positive_float(settings.get("y2_major_tick"))

        if x_major_tick is not None:
            axes.xaxis.set_major_locator(MultipleLocator(x_major_tick))
        if y_major_tick is not None:
            axes.yaxis.set_major_locator(MultipleLocator(y_major_tick))
        if secondary_axes is not None and y2_major_tick is not None:
            secondary_axes.yaxis.set_major_locator(MultipleLocator(y2_major_tick))
        if secondary_axes is not None and bool(settings.get("align_secondary_y_axis_grid", False)):
            cls._align_secondary_y_ticks_to_primary(axes, secondary_axes)

    @staticmethod
    def _positive_float(value: object) -> float | None:
        text = str(value).strip()
        if not text:
            return None
        try:
            number = float(text)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number) or number <= 0:
            return None
        return number

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
        secondary_ticks = [
            secondary_min + ((float(tick) - primary_min) / (primary_max - primary_min)) * (secondary_max - secondary_min)
            for tick in primary_ticks
        ]
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
        self.canvas.draw()
        self._set_cursor_data(None)
        return OperationResult.success(f"Comparison plot generated for {plotted} series.")
