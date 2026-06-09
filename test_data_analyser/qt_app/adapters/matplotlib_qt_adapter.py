"""Matplotlib ↔ Qt canvas adapter.

Owns the ``FigureCanvasQTAgg`` and ``NavigationToolbar2QT`` so the rest of the Qt
UI does not import the Matplotlib backends directly. This adapter is responsible
only for embedding/displaying a Matplotlib figure; data preparation lives in the
services/viewmodels and plot styling lives in ``plot_render_service``.
"""
from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget


class MatplotlibCanvas(QWidget):
    """A Qt widget embedding a Matplotlib figure, canvas, and navigation toolbar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.figure = Figure(figsize=(8.0, 5.0), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.axes = self.figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

    def clear(self) -> None:
        """Reset the figure to a single empty axes."""
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)

    def draw(self) -> None:
        """Lay out and repaint the canvas."""
        try:
            self.figure.tight_layout()
        except Exception:
            pass
        self.canvas.draw_idle()
