"""Cursor / point-comparison panel.

Locks comparison points on the plot and shows a per-point table with delta-
versus-Point-1 rows. The panel is a thin Qt view: locked-point state and table
data live in the :class:`CursorCompareViewModel`, and the Matplotlib click/key
wiring lives in the :class:`PlotWorkspace`. The panel only toggles compare mode
and renders the table.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.cursor_compare_vm import CursorCompareViewModel
from ..adapters import qt_message_service
from ..adapters.pandas_table_model import PandasTableModel
from .plot_workspace import PlotWorkspace

_HINT = (
    "Enable Point Compare, then click the plot to lock comparison points. "
    "Press ESC on the plot (or Clear Points) to remove them."
)


class CursorComparePanel(QWidget):
    analysisWindowRequested = Signal(float, float)

    def __init__(
        self,
        cursor_vm: CursorCompareViewModel,
        plot_workspace: PlotWorkspace,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vm = cursor_vm
        self.plot_workspace = plot_workspace

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(self._build_toolbar())

        self.model = PandasTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        self.hint_label = QLabel(_HINT)
        self.hint_label.setObjectName("PlaceholderText")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.plot_workspace.cursorPointsChanged.connect(self.refresh)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        self.compare_check = QCheckBox("Point Compare mode")
        self.compare_check.toggled.connect(self.plot_workspace.set_point_compare_enabled)
        clear_button = QPushButton("Clear Points")
        clear_button.clicked.connect(self._clear)
        self.window_button = QPushButton("Use P1–P2 as Analysis Window")
        self.window_button.clicked.connect(self._use_as_window)
        toolbar.addWidget(self.compare_check)
        toolbar.addWidget(clear_button)
        toolbar.addWidget(self.window_button)
        toolbar.addStretch(1)
        return toolbar

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.model.set_dataframe(self.vm.comparison_frame())
        count = len(self.vm.points)
        if count:
            self.hint_label.setText(
                f"Locked points: {count}. Delta rows show the difference versus Point 1."
            )
        else:
            self.hint_label.setText(_HINT)

    def _clear(self) -> None:
        self.plot_workspace.clear_cursor_markers()
        self.refresh()

    def _use_as_window(self) -> None:
        window = self.vm.analysis_window_from_points()
        if window is None:
            qt_message_service.info(self, "Analysis Window", "Please lock at least two cursor points first.")
            return
        self.analysisWindowRequested.emit(window[0], window[1])
