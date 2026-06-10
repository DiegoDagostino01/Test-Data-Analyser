"""Matplotlib ↔ Qt canvas adapter.

Owns the ``FigureCanvasQTAgg`` and ``NavigationToolbar2QT`` so the rest of the Qt
UI does not import the Matplotlib backends directly. This adapter is responsible
only for embedding/displaying a Matplotlib figure; data preparation lives in the
services/viewmodels and plot styling lives in ``plot_render_service``.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.qt_editor import _formlayout, figureoptions
from matplotlib.figure import Figure
from PySide6.QtWidgets import QInputDialog, QMessageBox, QVBoxLayout, QWidget

LEGEND_DISPLAY_PANEL = "panel"
LEGEND_DISPLAY_GRAPH = "graph"
LEGEND_DISPLAY_CHOICES = (
    (LEGEND_DISPLAY_PANEL, "Right-side Legend panel"),
    (LEGEND_DISPLAY_GRAPH, "Inside graph"),
)


class LegendAwareNavigationToolbar(NavigationToolbar2QT):
    """Navigation toolbar that adds Test Data Analyser legend options."""

    def __init__(self, canvas, parent=None, coordinates: bool = True) -> None:
        super().__init__(canvas, parent, coordinates)
        self._legend_display_getter: Callable[[], str] | None = None
        self._legend_display_setter: Callable[[str], None] | None = None
        self._export_preparer: Callable[[], Any] | None = None

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
        if self._legend_display_getter is None or self._legend_display_setter is None:
            figureoptions.figure_edit(axes, self)
            return

        original_fedit = _formlayout.fedit

        def fedit_with_legend(
            data,
            title: str = "",
            comment: str = "",
            icon=None,
            parent=None,
            apply=None,
        ):
            def apply_with_legend(form_data: list[Any]) -> None:
                form_sections = list(form_data)
                legend_data = form_sections.pop() if form_sections else []
                if apply is not None:
                    apply(form_sections)
                self._apply_legend_form_data(legend_data)

            return original_fedit(
                [*data, (self._legend_form_data(), "Legend", "")],
                title=title,
                comment=comment,
                icon=icon,
                parent=parent,
                apply=apply_with_legend,
            )

        _formlayout.fedit = fedit_with_legend
        try:
            figureoptions.figure_edit(axes, self)
        finally:
            _formlayout.fedit = original_fedit

    def _legend_form_data(self) -> list[tuple[str, list[object]]]:
        getter = self._legend_display_getter
        display = self._normalise_legend_display(getter() if getter is not None else LEGEND_DISPLAY_PANEL)
        return [("Placement", [display, *LEGEND_DISPLAY_CHOICES])]

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
        self.figure = Figure(figsize=(8.0, 5.0), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = LegendAwareNavigationToolbar(self.canvas, self)
        self.axes = self.figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

    def clear(self) -> None:
        """Reset the figure to a single empty axes."""
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)

    def draw(self, *, tight: bool = True) -> None:
        """Lay out and repaint the canvas."""
        if tight:
            try:
                self.figure.tight_layout()
            except Exception:
                pass
        self.canvas.draw_idle()
