"""Matplotlib ↔ Qt canvas adapter.

Owns the ``FigureCanvasQTAgg`` and ``NavigationToolbar2QT`` so the rest of the Qt
UI does not import the Matplotlib backends directly. This adapter is responsible
only for embedding/displaying a Matplotlib figure and applying theme surfaces;
data preparation lives in the services/viewmodels and series styling lives in
``plot_render_service``.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.qt_editor import _formlayout, figureoptions
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ...core.config import theme_palette
from ...core.utils import classify_channel_name

LEGEND_DISPLAY_PANEL = "panel"
LEGEND_DISPLAY_GRAPH = "graph"
LEGEND_DISPLAY_CHOICES = (
    (LEGEND_DISPLAY_PANEL, "Right-side Legend panel"),
    (LEGEND_DISPLAY_GRAPH, "Inside graph"),
)
_AUTO_LEGEND_FIELD = "(Re-)Generate automatic legend"


class LegendAwareNavigationToolbar(NavigationToolbar2QT):
    """Navigation toolbar that adds Test Data Analyser legend options."""

    toolitems = tuple(
        item
        for item in NavigationToolbar2QT.toolitems
        if item[0] not in {"Subplots", "Customize", "Save"}
    )

    def __init__(self, canvas, parent=None, coordinates: bool = True) -> None:
        super().__init__(canvas, parent, coordinates)
        self._legend_display_getter: Callable[[], str] | None = None
        self._legend_display_setter: Callable[[str], None] | None = None
        self._export_preparer: Callable[[], Any] | None = None
        self._axis_padding_getter: Callable[[], dict[str, object]] | None = None
        self._axis_tick_settings_getter: Callable[[], dict[str, object]] | None = None
        self._axis_tick_settings_setter: Callable[[dict[str, object]], None] | None = None
        self._axis_tick_settings_applier: Callable[[], None] | None = None
        self.addSeparator()
        self.edit_axis_button = QPushButton("Edit Axis")
        self.edit_axis_button.setObjectName("PrimaryButton")
        self.edit_axis_button.setToolTip("Edit plot title, axis labels, limits, and legend placement.")
        self.edit_axis_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.edit_axis_button.clicked.connect(self.edit_parameters)
        self.edit_axis_action = self.addWidget(self.edit_axis_button)
        self.edit_axis_action.setText("Edit Axis")
        self.edit_axis_action.setToolTip(self.edit_axis_button.toolTip())

    def set_legend_display_controller(
        self,
        getter: Callable[[], str],
        setter: Callable[[str], None],
    ) -> None:
        self._legend_display_getter = getter
        self._legend_display_setter = setter

    def set_export_preparer(self, preparer: Callable[[], Any]) -> None:
        """Register a context manager run around figure export (e.g. ``savefig``).

        The plot workspace uses this to temporarily draw the side-panel legend
        onto the figure so it is captured in the saved image.
        """
        self._export_preparer = preparer

    def set_axis_padding_getter(self, getter: Callable[[], dict[str, object]]) -> None:
        self._axis_padding_getter = getter

    def set_axis_tick_settings_controller(
        self,
        getter: Callable[[], dict[str, object]],
        setter: Callable[[dict[str, object]], None],
        applier: Callable[[], None],
    ) -> None:
        self._axis_tick_settings_getter = getter
        self._axis_tick_settings_setter = setter
        self._axis_tick_settings_applier = applier

    def save_figure(self, *args):
        preparer = self._export_preparer
        if preparer is None:
            return super().save_figure(*args)
        with preparer():
            return super().save_figure(*args)

    def edit_parameters(self) -> None:
        axes = self._select_axes_for_edit()
        if axes is not None:
            self._figure_edit_with_legend(axes)

    def _select_axes_for_edit(self):
        axes = self.canvas.figure.get_axes()
        if not axes:
            QMessageBox.warning(self, "Error", "There are no Axes to edit.")
            return None
        if self._is_primary_secondary_y_pair(axes):
            return axes[0]
        if len(axes) == 1:
            return axes[0]

        titles = [self._axes_title(axes_item) for axes_item in axes]
        duplicate_titles = [title for title in titles if titles.count(title) > 1]
        for index, title in enumerate(titles):
            if title in duplicate_titles:
                titles[index] = f"{title} (id: {id(axes[index]):#x})"
        item, ok = QInputDialog.getItem(self, "Customize", "Select Axes:", titles, 0, False)
        if not ok:
            return None
        return axes[titles.index(item)]

    @staticmethod
    def _is_primary_secondary_y_pair(axes: list) -> bool:
        if len(axes) != 2:
            return False
        try:
            return bool(axes[0].get_shared_x_axes().joined(axes[0], axes[1]))
        except Exception:
            return False

    @staticmethod
    def _axes_title(axes) -> str:
        return (
            axes.get_label()
            or axes.get_title()
            or axes.get_title("left")
            or axes.get_title("right")
            or " - ".join(filter(None, [axes.get_xlabel(), axes.get_ylabel()]))
            or f"<anonymous {type(axes).__name__}>"
        )

    def _figure_edit_with_legend(self, axes) -> None:
        include_legend = self._legend_display_getter is not None and self._legend_display_setter is not None
        original_fedit = _formlayout.fedit

        def fedit_with_legend(
            data,
            title: str = "",
            comment: str = "",
            icon=None,
            parent=None,
            apply=None,
        ):
            form_data, removed_auto_legend = self._without_auto_legend_checkbox(data) if include_legend else (data, False)
            form_data, removed_curves = self._without_curves_tab(form_data)
            form_data, secondary_axes = self._with_secondary_y_axis_fields(form_data, axes)
            form_data = self._with_axis_tab_title(form_data)
            include_axis_ticks = self._axis_tick_settings_getter is not None and self._axis_tick_settings_setter is not None

            def apply_with_legend(form_data: list[Any]) -> None:
                form_sections = list(form_data)
                legend_data = form_sections.pop() if include_legend and form_sections else []
                axis_tick_data = form_sections.pop() if include_axis_ticks and form_sections else []
                secondary_data = self._pop_secondary_y_axis_data(form_sections, secondary_axes is not None)
                if apply is not None:
                    restored = self._restore_auto_legend_checkbox(form_sections, removed_auto_legend)
                    restored = self._restore_curves_tab(restored, removed_curves)
                    apply(restored)
                if secondary_axes is not None and secondary_data is not None:
                    self._apply_secondary_y_axis_data(secondary_axes, secondary_data)
                if include_axis_ticks:
                    self._apply_axis_tick_form_data(axis_tick_data)
                if include_legend:
                    self._apply_legend_form_data(legend_data)

            extra_sections = []
            if include_axis_ticks:
                extra_sections.append((self._axis_tick_form_data(), "Axis Ticks", ""))
            if include_legend:
                extra_sections.append((self._legend_form_data(), "Legend", ""))
            result = original_fedit(
                [*form_data, *extra_sections],
                title=title,
                comment=comment,
                icon=icon,
                parent=parent,
                apply=apply_with_legend,
            )
            self._install_axis_helper_buttons(axes)
            return result

        _formlayout.fedit = fedit_with_legend
        try:
            figureoptions.figure_edit(axes, self)
        finally:
            _formlayout.fedit = original_fedit

    @staticmethod
    def _with_axis_tab_title(data) -> list:
        form_data = list(data)
        if not form_data:
            return form_data
        axes_section = form_data[0]
        if not (isinstance(axes_section, tuple) and len(axes_section) == 3):
            return form_data
        fields, title, comment = axes_section
        if title == "Axes":
            form_data[0] = (fields, "Axis", comment)
        return form_data

    def _with_secondary_y_axis_fields(self, data, axes) -> tuple[list, Any | None]:
        secondary_axes = self._secondary_y_axes_for(axes)
        if secondary_axes is None:
            return list(data), None
        form_data = list(data)
        if not form_data:
            return form_data, None
        axes_section = form_data[0]
        if not (isinstance(axes_section, tuple) and len(axes_section) == 3):
            return form_data, None
        fields, title, comment = axes_section
        if title not in {"Axes", "Axis"} or not isinstance(fields, list):
            return form_data, None
        ymin, ymax = secondary_axes.get_ylim()
        secondary_fields = [
            (None, "<b>Secondary Y-Axis</b>"),
            ("Min", float(ymin)),
            ("Max", float(ymax)),
            ("Label", secondary_axes.get_ylabel()),
            ("Scale", [secondary_axes.get_yscale(), "linear", "log", "symlog", "logit"]),
            (None, None),
        ]
        form_data[0] = ([*fields, *secondary_fields], title, comment)
        return form_data, secondary_axes

    def _secondary_y_axes_for(self, axes):
        figure_axes = list(axes.get_figure().axes)
        for candidate in figure_axes:
            if candidate is axes:
                continue
            try:
                if axes.get_shared_x_axes().joined(axes, candidate):
                    return candidate
            except Exception:
                continue
        return None

    @staticmethod
    def _pop_secondary_y_axis_data(form_sections: list[Any], has_secondary_axis: bool) -> list[Any] | None:
        if not has_secondary_axis or not form_sections or not isinstance(form_sections[0], list):
            return None
        general = list(form_sections[0])
        if len(general) < 4:
            return None
        secondary_data = general[-4:]
        form_sections[0] = general[:-4]
        return secondary_data

    @staticmethod
    def _apply_secondary_y_axis_data(secondary_axes, values: list[Any]) -> None:
        if len(values) != 4:
            return
        axis_min, axis_max, axis_label, axis_scale = values
        if secondary_axes.yaxis.get_scale() != axis_scale:
            secondary_axes.set_yscale(axis_scale)
        secondary_axes.set_ylim(axis_min, axis_max, auto=False)
        secondary_axes.set_ylabel(str(axis_label))
        figure = secondary_axes.get_figure()
        figure.canvas.draw()
        toolbar = getattr(figure.canvas, "toolbar", None)
        if toolbar is not None:
            toolbar.push_current()

    @staticmethod
    def _without_auto_legend_checkbox(data) -> tuple[list, bool]:
        form_data = list(data)
        if not form_data:
            return form_data, False
        axes_section = form_data[0]
        if not (isinstance(axes_section, tuple) and len(axes_section) == 3):
            return form_data, False
        fields, title, comment = axes_section
        if title not in {"Axes", "Axis"} or not isinstance(fields, list) or not fields:
            return form_data, False
        last_field = fields[-1]
        if not (isinstance(last_field, tuple) and len(last_field) >= 2 and last_field[0] == _AUTO_LEGEND_FIELD):
            return form_data, False
        form_data[0] = (list(fields[:-1]), title, comment)
        return form_data, True

    @staticmethod
    def _restore_auto_legend_checkbox(form_sections: list[Any], removed: bool) -> list[Any]:
        if not removed or not form_sections or not isinstance(form_sections[0], list):
            return form_sections
        restored = list(form_sections)
        restored[0] = [*form_sections[0], False]
        return restored

    @classmethod
    def _without_curves_tab(cls, data) -> tuple[list, list[Any] | None]:
        form_data = list(data)
        removed_curves = None
        kept = []
        for section in form_data:
            if isinstance(section, tuple) and len(section) == 3 and section[1] == "Curves":
                removed_curves = cls._default_curves_values(section[0])
                continue
            kept.append(section)
        return kept, removed_curves

    @staticmethod
    def _restore_curves_tab(form_sections: list[Any], removed_curves: list[Any] | None) -> list[Any]:
        if removed_curves is None:
            return form_sections
        restored = list(form_sections)
        restored.insert(1, removed_curves)
        return restored

    @classmethod
    def _default_curves_values(cls, curves_section: object) -> list[list[Any]]:
        if not isinstance(curves_section, list):
            return []
        return [cls._default_section_values(curve[0]) for curve in curves_section if isinstance(curve, list) and curve]

    @classmethod
    def _default_section_values(cls, fields: object) -> list[Any]:
        if not isinstance(fields, list):
            return []
        values = []
        for field in fields:
            if not (isinstance(field, tuple) and len(field) >= 2):
                continue
            label, value = field[0], field[1]
            if label is None:
                continue
            values.append(cls._default_field_value(value))
        return values

    @staticmethod
    def _default_field_value(value: Any) -> Any:
        if isinstance(value, list) and value:
            return value[0]
        return value

    def _install_axis_helper_buttons(self, axes) -> None:
        dialog = getattr(self, "_fedit_dialog", None)
        formwidget = getattr(dialog, "formwidget", None)
        widgetlist = getattr(formwidget, "widgetlist", [])
        if not widgetlist:
            return
        axes_form = widgetlist[0]
        if getattr(axes_form, "_tda_axis_helpers_installed", False):
            return
        fields = self._axes_form_fields(axes_form)
        if not fields.get("title"):
            return

        helper_row = QWidget(axes_form)
        helper_layout = QHBoxLayout(helper_row)
        helper_layout.setContentsMargins(0, 0, 0, 0)
        helper_layout.setSpacing(6)

        auto_label_button = QPushButton("Auto Label", helper_row)
        auto_label_button.setObjectName("AxisAutoLabelButton")
        auto_label_button.setToolTip("Generate the plot title and axis labels from the plotted X and Y channels.")
        auto_label_button.clicked.connect(lambda: self._auto_label_axes_form(axes, axes_form))
        helper_layout.addWidget(auto_label_button)

        auto_fit_x_button = QPushButton("Auto-fit X", helper_row)
        auto_fit_x_button.setObjectName("AxisAutoFitXButton")
        auto_fit_x_button.setToolTip("Set X-axis limits to the plotted data range using the configured X padding.")
        auto_fit_x_button.clicked.connect(lambda: self._auto_fit_axis_form(axes, axes_form, "x"))
        helper_layout.addWidget(auto_fit_x_button)

        auto_fit_y_button = QPushButton("Auto-fit Y", helper_row)
        auto_fit_y_button.setObjectName("AxisAutoFitYButton")
        auto_fit_y_button.setToolTip("Set Y-axis limits to the plotted data range using the configured Y padding.")
        auto_fit_y_button.clicked.connect(lambda: self._auto_fit_axis_form(axes, axes_form, "y"))
        helper_layout.addWidget(auto_fit_y_button)

        if fields.get("axes", {}).get("secondary_y"):
            auto_fit_secondary_y_button = QPushButton("Auto-fit Secondary Y", helper_row)
            auto_fit_secondary_y_button.setObjectName("AxisAutoFitSecondaryYButton")
            auto_fit_secondary_y_button.setToolTip(
                "Set secondary Y-axis limits from the plotted right-axis data using the configured Y padding."
            )
            auto_fit_secondary_y_button.clicked.connect(lambda: self._auto_fit_axis_form(axes, axes_form, "secondary_y"))
            helper_layout.addWidget(auto_fit_secondary_y_button)
        helper_layout.addStretch(1)

        axes_form.formlayout.addRow("Helpers", helper_row)
        axes_form._tda_axis_helpers_installed = True

    @staticmethod
    def _axes_form_fields(axes_form) -> dict[str, Any]:
        fields: dict[str, Any] = {"axes": {}}
        current_axis = ""
        for (label, value), widget in zip(getattr(axes_form, "data", []), getattr(axes_form, "widgets", [])):
            if label == "Title":
                fields["title"] = widget
                continue
            if label is None and isinstance(value, str):
                if "X-Axis" in value:
                    current_axis = "x"
                    fields["axes"].setdefault(current_axis, {})
                elif "Secondary Y-Axis" in value:
                    current_axis = "secondary_y"
                    fields["axes"].setdefault(current_axis, {})
                elif "Y-Axis" in value:
                    current_axis = "y"
                    fields["axes"].setdefault(current_axis, {})
                continue
            if current_axis and label in {"Min", "Max", "Label", "Scale"}:
                fields["axes"].setdefault(current_axis, {})[str(label).lower()] = widget
        return fields

    def _auto_label_axes_form(self, axes, axes_form) -> None:
        fields = self._axes_form_fields(axes_form)
        title, x_label, y_label = self._auto_labels_for_axes(axes)
        self._set_field_text(fields.get("title"), title)
        axis_fields = fields.get("axes", {})
        self._set_field_text(axis_fields.get("x", {}).get("label"), x_label)
        self._set_field_text(axis_fields.get("y", {}).get("label"), y_label)
        secondary_axes = self._secondary_y_axes_for(axes)
        if secondary_axes is not None:
            secondary_y_labels = self._series_labels_for_axes(secondary_axes)
            secondary_y_label = (
                self._summarise_series_labels(secondary_y_labels)
                or secondary_axes.get_ylabel()
                or "Secondary Axis Signals"
            )
            self._set_field_text(axis_fields.get("secondary_y", {}).get("label"), secondary_y_label)
        self._update_dialog_buttons(axes_form)

    def _auto_fit_axis_form(self, axes, axes_form, axis_name: str) -> None:
        fields = self._axes_form_fields(axes_form)
        axis_fields = fields.get("axes", {}).get(axis_name, {})
        if not axis_fields:
            return
        target_axes = self._secondary_y_axes_for(axes) if axis_name == "secondary_y" else axes
        if target_axes is None:
            return
        lower, upper = self._auto_fit_limits(target_axes, "y" if axis_name == "secondary_y" else axis_name)
        self._set_field_text(axis_fields.get("min"), self._format_limit(lower))
        self._set_field_text(axis_fields.get("max"), self._format_limit(upper))
        self._update_dialog_buttons(axes_form)

    @staticmethod
    def _set_field_text(widget, text: str) -> None:
        if hasattr(widget, "setText"):
            widget.setText(text)

    def _auto_labels_for_axes(self, axes) -> tuple[str, str, str]:
        x_label = (axes.get_xlabel() or "X Axis").strip()
        y_labels = self._series_labels_for_axes(axes)
        y_label = self._summarise_series_labels(y_labels) or (axes.get_ylabel() or "Selected Signals").strip()
        title = f"{y_label} vs {x_label}" if x_label and y_label else "Engineering Test Data"
        return title, x_label, y_label

    @staticmethod
    def _series_labels_for_axes(axes) -> list[str]:
        labels: list[str] = []
        artists = [*axes.get_lines(), *axes.collections]
        for artist in artists:
            label_getter = getattr(artist, "get_label", None)
            label = str(label_getter() if callable(label_getter) else "").strip()
            clean = LegendAwareNavigationToolbar._clean_series_label(label)
            if clean and clean not in labels:
                labels.append(clean)
        return labels

    @staticmethod
    def _clean_series_label(label: str) -> str:
        if not label or label.startswith("_"):
            return ""
        limit_suffixes = ("[Upper Limit]", "[Lower Limit]", "[Reference Line]")
        if any(label.endswith(suffix) for suffix in limit_suffixes):
            return ""
        label = label.removesuffix(" [Right Y]")
        if " | LP " in label:
            label = label.split(" | LP ", 1)[0]
        return label.strip()

    @staticmethod
    def _summarise_series_labels(labels: list[str]) -> str:
        if not labels:
            return ""
        if len(labels) == 1:
            return labels[0]
        groups = [classify_channel_name(label) for label in labels]
        meaningful_groups = [group for group in groups if group not in {"Other Numeric", "Non-numeric / Metadata"}]
        if meaningful_groups and len(set(meaningful_groups)) == 1:
            return meaningful_groups[0]
        if len(labels) <= 3:
            return ", ".join(labels)
        return "Selected Signals"

    def _auto_fit_limits(self, axes, axis_name: str) -> tuple[float, float]:
        values = self._finite_axis_values(axes, axis_name)
        if not values:
            current_lower, current_upper = getattr(axes, f"get_{axis_name}lim")()
            return float(current_lower), float(current_upper)
        lower = min(values)
        upper = max(values)
        span = upper - lower
        fraction = self._axis_padding_fraction(axis_name)
        if span <= 0:
            span = max(abs(lower), 1.0)
        padding = span * fraction
        if padding == 0 and lower == upper:
            padding = max(abs(lower), 1.0) * 0.05
        return lower - padding, upper + padding

    @staticmethod
    def _finite_axis_values(axes, axis_name: str) -> list[float]:
        values: list[float] = []
        for line in axes.get_lines():
            data = line.get_xdata(orig=False) if axis_name == "x" else line.get_ydata(orig=False)
            values.extend(LegendAwareNavigationToolbar._finite_values(data))
        for collection in axes.collections:
            offsets_getter = getattr(collection, "get_offsets", None)
            if not callable(offsets_getter):
                continue
            offsets = offsets_getter()
            offset_array = np.asarray(offsets, dtype=float)
            if offset_array.size == 0:
                continue
            column = 0 if axis_name == "x" else 1
            values.extend(LegendAwareNavigationToolbar._finite_values(offset_array[:, column]))
        return values

    @staticmethod
    def _finite_values(values) -> list[float]:
        try:
            array = np.asarray(values, dtype=float).ravel()
        except (TypeError, ValueError):
            return []
        return [float(value) for value in array if np.isfinite(value)]

    def _axis_padding_fraction(self, axis_name: str) -> float:
        settings = self._axis_padding_getter() if self._axis_padding_getter is not None else {}
        if not isinstance(settings, dict):
            settings = {}
        if axis_name == "secondary_y":
            axis_name = "y"
        enabled = bool(settings.get(f"pad_{axis_name}_axis", True))
        if not enabled:
            return 0.0
        try:
            percent = float(str(settings.get(f"pad_{axis_name}_percent", 5) or 5))
        except (TypeError, ValueError):
            percent = 5.0
        return max(0.0, percent / 100.0)

    @staticmethod
    def _format_limit(value: float) -> str:
        return f"{float(value):.6g}"

    @staticmethod
    def _update_dialog_buttons(axes_form) -> None:
        dialog_getter = getattr(axes_form, "get_dialog", None)
        if not callable(dialog_getter):
            return
        dialog = dialog_getter()
        updater = getattr(dialog, "update_buttons", None)
        if callable(updater):
            updater()

    def _legend_form_data(self) -> list[tuple[str, list[object]]]:
        getter = self._legend_display_getter
        display = self._normalise_legend_display(getter() if getter is not None else LEGEND_DISPLAY_PANEL)
        return [("Placement", [display, *LEGEND_DISPLAY_CHOICES])]

    def _axis_tick_form_data(self) -> list[tuple[str, object]]:
        getter = self._axis_tick_settings_getter
        settings = getter() if getter is not None else {}
        if not isinstance(settings, dict):
            settings = {}
        return [
            ("X major tick step", str(settings.get("x_major_tick", ""))),
            ("Y major tick step", str(settings.get("y_major_tick", ""))),
            ("Secondary Y major tick step", str(settings.get("y2_major_tick", ""))),
            ("Align secondary Y-axis grid with primary axis", bool(settings.get("align_secondary_y_axis_grid", False))),
        ]

    def _apply_axis_tick_form_data(self, axis_tick_data: list[object]) -> None:
        if self._axis_tick_settings_setter is None:
            return
        values = list(axis_tick_data or [])
        settings = {
            "x_major_tick": str(values[0]).strip() if len(values) > 0 else "",
            "y_major_tick": str(values[1]).strip() if len(values) > 1 else "",
            "y2_major_tick": str(values[2]).strip() if len(values) > 2 else "",
            "align_secondary_y_axis_grid": bool(values[3]) if len(values) > 3 else False,
        }
        self._axis_tick_settings_setter(settings)
        if self._axis_tick_settings_applier is not None:
            self._axis_tick_settings_applier()

    def _apply_legend_form_data(self, legend_data: list[object]) -> None:
        if not legend_data or self._legend_display_setter is None:
            return
        self._legend_display_setter(self._normalise_legend_display(str(legend_data[0])))

    @staticmethod
    def _normalise_legend_display(display: str) -> str:
        if display == LEGEND_DISPLAY_GRAPH:
            return LEGEND_DISPLAY_GRAPH
        return LEGEND_DISPLAY_PANEL


class MatplotlibCanvas(QWidget):
    """A Qt widget embedding a Matplotlib figure, canvas, and navigation toolbar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MatplotlibCanvas")
        self._theme_name = "light"
        self.figure = Figure(figsize=(8.0, 5.0), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setObjectName("MatplotlibFigureCanvas")
        self.toolbar = LegendAwareNavigationToolbar(self.canvas, self)
        self.toolbar.setObjectName("PlotToolbar")
        self.axes = self.figure.add_subplot(111)
        self._apply_plot_surfaces()
        self.canvas.mpl_connect("resize_event", self._on_canvas_resize)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

    def clear(self) -> None:
        """Reset the figure to a single empty axes."""
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)
        self._apply_plot_surfaces()

    def apply_theme(self, theme_name: str) -> None:
        self._theme_name = str(theme_name or "light")
        self._apply_plot_surfaces()
        self.canvas.draw_idle()

    def draw(self, *, tight: bool = True) -> None:
        """Lay out and repaint the canvas."""
        self._apply_plot_surfaces()
        if tight:
            try:
                self.figure.tight_layout()
            except Exception:
                pass
        self.canvas.draw_idle()

    def _apply_plot_surfaces(self) -> None:
        palette = theme_palette(self._theme_name)
        plot_bg = palette["plot_bg"]
        plot_text = palette["plot_text"]
        plot_axis = palette["plot_axis"]
        plot_spine = palette["plot_spine"]
        plot_grid = palette["plot_grid"]
        self.figure.patch.set_facecolor(plot_bg)
        for axes in self.figure.axes:
            axes.set_facecolor(plot_bg)
            axes.title.set_color(plot_text)
            axes.xaxis.label.set_color(plot_text)
            axes.yaxis.label.set_color(plot_text)
            axes.tick_params(axis="both", colors=plot_axis)
            for spine in axes.spines.values():
                spine.set_color(plot_spine)
            for gridline in [*axes.get_xgridlines(), *axes.get_ygridlines()]:
                gridline.set_color(plot_grid)
                gridline.set_alpha(0.65)
                gridline.set_linewidth(0.8)

    def _on_canvas_resize(self, _event) -> None:
        if self.canvas.width() <= 1 or self.canvas.height() <= 1 or not self.figure.axes:
            return
        self.draw()
