"""Axis / channel selection panel.

Lets the user choose the X column, the Y channels, an optional analysis window,
and filter settings. Holds no analysis logic; it only gathers the selection for
the plot workspace.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core.utils import channel_group_options, classify_channel_name, natural_sort_key
from .no_wheel_combo_box import NoWheelComboBox

PLOT_KINDS = ("Line", "Scatter", "Line + Markers")
_GROUP_HEADER_ROLE = "channel_group_header"


class CheckableChannelListWidget(QListWidget):
    """QListWidget whose checkable rows toggle from any click position."""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        if item is not None and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
            next_state = (
                Qt.CheckState.Unchecked
                if item.checkState() == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
            item.setCheckState(next_state)
            event.accept()
            return
        super().mousePressEvent(event)


class AxisSelectionPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EatonPanel")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._columns: list[str] = []
        self._channel_groups: dict[str, str] = {}
        self._checked_primary: set[str] = set()
        self._checked_secondary: set[str] = set()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        heading = QLabel("Plot Controls")
        heading.setObjectName("PanelHeading")
        root.addWidget(heading)

        # The grouped controls live in a scroll area so the panel never feels
        # cramped on shorter windows.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        controls = QVBoxLayout(container)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(10)

        # --- Axes & Channels -------------------------------------------------
        axes_group = QGroupBox("Axes & Channels")
        axes_layout = QVBoxLayout(axes_group)
        axes_layout.setSpacing(4)
        axes_layout.addWidget(QLabel("X-axis column:"))
        self.x_combo = NoWheelComboBox()
        self.x_combo.currentTextChanged.connect(self._refresh_channel_lists)
        axes_layout.addWidget(self.x_combo)
        axes_layout.addWidget(QLabel("Channel group:"))
        self.group_combo = NoWheelComboBox()
        self.group_combo.addItems(channel_group_options())
        self.group_combo.currentTextChanged.connect(self._refresh_channel_lists)
        axes_layout.addWidget(self.group_combo)
        axes_layout.addWidget(QLabel("Primary Y-axis channels:"))
        self.y_list = CheckableChannelListWidget()
        self.y_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.y_list.setMinimumHeight(160)
        self.y_list.setMaximumHeight(220)
        self.y_list.itemChanged.connect(self._on_primary_item_changed)
        axes_layout.addWidget(self.y_list, stretch=1)
        self.primary_select_all_button = QPushButton("Select All")
        self.primary_select_all_button.setToolTip("Select all visible primary Y channels in the current group.")
        self.primary_select_all_button.clicked.connect(self._select_visible_primary)
        self.primary_clear_all_button = QPushButton("Clear All")
        self.primary_clear_all_button.setToolTip("Clear every selected primary Y channel.")
        self.primary_clear_all_button.clicked.connect(self._clear_primary)
        primary_buttons = self._button_row(self.primary_select_all_button, self.primary_clear_all_button)
        axes_layout.addLayout(primary_buttons)
        axes_layout.addWidget(QLabel("Secondary Y-axis channels (right):"))
        self.secondary_y_list = CheckableChannelListWidget()
        self.secondary_y_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.secondary_y_list.setMinimumHeight(160)
        self.secondary_y_list.setMaximumHeight(220)
        self.secondary_y_list.itemChanged.connect(self._on_secondary_item_changed)
        axes_layout.addWidget(self.secondary_y_list, stretch=1)
        self.secondary_select_all_button = QPushButton("Select All")
        self.secondary_select_all_button.setToolTip("Select all visible secondary Y channels in the current group.")
        self.secondary_select_all_button.clicked.connect(self._select_visible_secondary)
        self.secondary_clear_all_button = QPushButton("Clear All")
        self.secondary_clear_all_button.setToolTip("Clear every selected secondary Y channel.")
        self.secondary_clear_all_button.clicked.connect(self._clear_secondary)
        secondary_buttons = self._button_row(self.secondary_select_all_button, self.secondary_clear_all_button)
        axes_layout.addLayout(secondary_buttons)
        controls.addWidget(axes_group)

        # --- Plot Options ----------------------------------------------------
        options_group = QGroupBox("Plot Options")
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(4)
        options_layout.addWidget(QLabel("Plot kind:"))
        self.plot_kind_combo = NoWheelComboBox()
        self.plot_kind_combo.addItems(PLOT_KINDS)
        self._make_expanding(self.plot_kind_combo)
        options_layout.addWidget(self.plot_kind_combo)
        controls.addWidget(options_group)

        # --- Analysis Window -------------------------------------------------
        window_group = QGroupBox("Analysis Window")
        window_layout = QGridLayout(window_group)
        window_layout.setHorizontalSpacing(6)
        window_layout.setVerticalSpacing(4)
        window_layout.addWidget(QLabel("X range:"), 0, 0, 1, 2)
        window_layout.addWidget(QLabel("Min:"), 1, 0)
        window_layout.addWidget(QLabel("Max:"), 1, 1)
        self.xmin_edit = QLineEdit()
        self.xmin_edit.setPlaceholderText("min")
        self.xmax_edit = QLineEdit()
        self.xmax_edit.setPlaceholderText("max")
        self._make_expanding(self.xmin_edit)
        self._make_expanding(self.xmax_edit)
        window_layout.addWidget(self.xmin_edit, 2, 0)
        window_layout.addWidget(self.xmax_edit, 2, 1)
        window_layout.setColumnStretch(0, 1)
        window_layout.setColumnStretch(1, 1)
        controls.addWidget(window_group)

        # --- Filter ----------------------------------------------------------
        filter_group = QGroupBox("Filter")
        filter_layout = QGridLayout(filter_group)
        filter_layout.setHorizontalSpacing(6)
        filter_layout.setVerticalSpacing(4)
        self.filter_check = QCheckBox("Low-pass filter")
        filter_layout.addWidget(self.filter_check, 0, 0, 1, 2)
        filter_layout.addWidget(QLabel("Cutoff Hz:"), 1, 0)
        filter_layout.addWidget(QLabel("Order:"), 1, 1)
        self.cutoff_edit = QLineEdit()
        self.cutoff_edit.setPlaceholderText("e.g. 50")
        self.order_edit = QLineEdit("4")
        self._make_expanding(self.cutoff_edit)
        self._make_expanding(self.order_edit)
        filter_layout.addWidget(self.cutoff_edit, 2, 0)
        filter_layout.addWidget(self.order_edit, 2, 1)
        filter_layout.setColumnStretch(0, 1)
        filter_layout.setColumnStretch(1, 1)
        controls.addWidget(filter_group)

        controls.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)

        self.setMinimumWidth(240)

    @staticmethod
    def _button_row(left_button: QPushButton, right_button: QPushButton) -> QGridLayout:
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        for column, button in enumerate((left_button, right_button)):
            AxisSelectionPanel._make_expanding(button)
            layout.addWidget(button, 0, column)
            layout.setColumnStretch(column, 1)
        return layout

    @staticmethod
    def _make_expanding(widget: QWidget) -> None:
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def _populate_checklist(self, widget: QListWidget, columns: list[str], checked: set[str]) -> None:
        widget.blockSignals(True)
        widget.clear()
        if self.group_combo.currentText() == "All":
            current_group = ""
            for column in columns:
                group = self._channel_groups.get(column, "Other Numeric")
                if group != current_group:
                    widget.addItem(self._group_header_item(group))
                    current_group = group
                widget.addItem(self._channel_item(column, checked))
        else:
            for column in columns:
                widget.addItem(self._channel_item(column, checked))
        widget.blockSignals(False)

    @staticmethod
    def _channel_item(column: str, checked: set[str]) -> QListWidgetItem:
        item = QListWidgetItem(column)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if column in checked else Qt.CheckState.Unchecked)
        return item

    @staticmethod
    def _group_header_item(group: str) -> QListWidgetItem:
        item = QListWidgetItem(group)
        item.setData(Qt.ItemDataRole.UserRole, _GROUP_HEADER_ROLE)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = QFont()
        font.setBold(True)
        item.setFont(font)
        return item

    def set_columns(self, columns: list[str], suggested_x: str) -> None:
        self._columns = list(columns)
        self._channel_groups = {column: classify_channel_name(column) for column in self._columns}
        self._checked_primary.clear()
        self._checked_secondary.clear()
        self.x_combo.blockSignals(True)
        self.x_combo.clear()
        self.x_combo.addItems(columns)
        if suggested_x in columns:
            self.x_combo.setCurrentText(suggested_x)
        self.x_combo.blockSignals(False)

        self.group_combo.blockSignals(True)
        self.group_combo.setCurrentText("All")
        self.group_combo.blockSignals(False)

        self._refresh_channel_lists()

    def update_columns(self, columns: list[str]) -> None:
        """Refresh the available columns, preserving the current X and checked Y.

        Used when calculated channels add or remove columns so the user's current
        axis selection survives the refresh.
        """
        current_x = self.x_column()
        self._columns = list(columns)
        self._channel_groups = {column: classify_channel_name(column) for column in self._columns}
        available = set(self._columns)
        self._checked_primary &= available
        self._checked_secondary &= available

        self.x_combo.blockSignals(True)
        self.x_combo.clear()
        self.x_combo.addItems(columns)
        if current_x in columns:
            self.x_combo.setCurrentText(current_x)
        self.x_combo.blockSignals(False)

        self._refresh_channel_lists()

    def apply_selection(
        self,
        columns: list[str],
        x_column: str,
        y_columns: list[str],
        secondary_y_columns: list[str],
    ) -> None:
        """Populate the columns and restore a saved X / Y / secondary-Y selection."""
        self._columns = list(columns)
        self._channel_groups = {column: classify_channel_name(column) for column in self._columns}
        available = set(self._columns)
        self._checked_primary = set(y_columns) & available
        self._checked_secondary = set(secondary_y_columns) & available
        skip_x = x_column or (columns[0] if columns else "")
        self.x_combo.blockSignals(True)
        self.x_combo.clear()
        self.x_combo.addItems(columns)
        if skip_x in columns:
            self.x_combo.setCurrentText(skip_x)
        self.x_combo.blockSignals(False)
        self._refresh_channel_lists()

    def apply_plot_settings(self, profile: dict) -> None:
        """Restore the left-panel plot options that are still owned by this panel."""
        plot_kind = str(profile.get("plot_kind", "Line"))
        if self.plot_kind_combo.findText(plot_kind) >= 0:
            self.plot_kind_combo.setCurrentText(plot_kind)

        window = profile.get("analysis_window", {})
        if not isinstance(window, dict):
            window = {}
        self.xmin_edit.setText(str(window.get("start_x", "")))
        self.xmax_edit.setText(str(window.get("end_x", "")))

        filter_settings = profile.get("filter", {})
        if not isinstance(filter_settings, dict):
            filter_settings = {}
        self.filter_check.setChecked(bool(filter_settings.get("enabled", False)))
        self.cutoff_edit.setText(str(filter_settings.get("cutoff_hz", "")))
        self.order_edit.setText(str(filter_settings.get("order", "4") or "4"))

    def _refresh_channel_lists(self, *_args) -> None:
        visible_columns = self._filtered_y_columns(self.x_column())
        self._populate_checklist(self.y_list, visible_columns, self._checked_primary)
        self._populate_checklist(self.secondary_y_list, visible_columns, self._checked_secondary)

    def _filtered_y_columns(self, skip: str) -> list[str]:
        group = self.group_combo.currentText() if hasattr(self, "group_combo") else "All"
        available = [column for column in self._columns if column != skip]
        if group != "All":
            return self._sort_columns(
                [column for column in available if self._channel_groups.get(column) == group]
            )
        ordered: list[str] = []
        for group_name in channel_group_options()[1:]:
            ordered.extend(
                self._sort_columns(
                    [column for column in available if self._channel_groups.get(column) == group_name]
                )
            )
        return ordered

    @staticmethod
    def _sort_columns(columns: list[str]) -> list[str]:
        return sorted(columns, key=natural_sort_key)

    def _on_primary_item_changed(self, item: QListWidgetItem) -> None:
        if item.data(Qt.ItemDataRole.UserRole) == _GROUP_HEADER_ROLE:
            return
        self._set_checked(self._checked_primary, item)

    def _on_secondary_item_changed(self, item: QListWidgetItem) -> None:
        if item.data(Qt.ItemDataRole.UserRole) == _GROUP_HEADER_ROLE:
            return
        self._set_checked(self._checked_secondary, item)

    def _select_visible_primary(self) -> None:
        self._select_visible_channels(self.y_list, self._checked_primary)

    def _select_visible_secondary(self) -> None:
        self._select_visible_channels(self.secondary_y_list, self._checked_secondary)

    def _clear_primary(self) -> None:
        self._checked_primary.clear()
        self._sync_checklist_checks(self.y_list, self._checked_primary)

    def _clear_secondary(self) -> None:
        self._checked_secondary.clear()
        self._sync_checklist_checks(self.secondary_y_list, self._checked_secondary)

    def _select_visible_channels(self, widget: QListWidget, target: set[str]) -> None:
        for row in range(widget.count()):
            item = widget.item(row)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                target.add(item.text())
        self._sync_checklist_checks(widget, target)

    @staticmethod
    def _sync_checklist_checks(widget: QListWidget, checked: set[str]) -> None:
        widget.blockSignals(True)
        for row in range(widget.count()):
            item = widget.item(row)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                state = Qt.CheckState.Checked if item.text() in checked else Qt.CheckState.Unchecked
                item.setCheckState(state)
        widget.blockSignals(False)

    @staticmethod
    def _set_checked(target: set[str], item: QListWidgetItem) -> None:
        if item.checkState() == Qt.CheckState.Checked:
            target.add(item.text())
        else:
            target.discard(item.text())

    # ------------------------------------------------------------------
    # Selection accessors
    # ------------------------------------------------------------------
    def x_column(self) -> str:
        return self.x_combo.currentText()

    def channel_group(self) -> str:
        return self.group_combo.currentText()

    def selected_y(self) -> list[str]:
        x_column = self.x_column()
        return [column for column in self._columns if column in self._checked_primary and column != x_column]

    def selected_secondary_y(self) -> list[str]:
        x_column = self.x_column()
        return [column for column in self._columns if column in self._checked_secondary and column != x_column]

    def all_selected_y(self) -> list[str]:
        """Return primary + secondary Y channels (secondary appended, de-duplicated)."""
        primary = self.selected_y()
        return primary + [column for column in self.selected_secondary_y() if column not in primary]

    def plot_kind(self) -> str:
        return self.plot_kind_combo.currentText()

    def filter_settings(self) -> tuple[bool, Optional[float], int]:
        """Return ``(use_filter, cutoff_hz, order)`` for the low-pass filter."""
        cutoff = self._parse(self.cutoff_edit.text())
        try:
            order = int(float(self.order_edit.text())) if self.order_edit.text().strip() else 4
        except ValueError:
            order = 4
        return self.filter_check.isChecked(), cutoff, max(1, order)

    def analysis_window(self) -> tuple[Optional[float], Optional[float]]:
        return self._parse(self.xmin_edit.text()), self._parse(self.xmax_edit.text())

    def analysis_window_texts(self) -> dict[str, str]:
        return {"start_x": self.xmin_edit.text().strip(), "end_x": self.xmax_edit.text().strip()}

    def filter_setting_texts(self) -> dict[str, object]:
        return {
            "enabled": self.filter_check.isChecked(),
            "cutoff_hz": self.cutoff_edit.text().strip(),
            "order": self.order_edit.text().strip() or "4",
        }

    @staticmethod
    def _parse(text: str) -> Optional[float]:
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
