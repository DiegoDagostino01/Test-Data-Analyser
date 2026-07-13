"""Legend channel style dialog.

A standalone Qt dialog for editing a single legend channel's appearance (label,
colour, plot kind, line/marker styling). Extracted from ``plot_workspace`` so the
plot workspace widget can focus on rendering. Framework layer: ``qt_app`` only.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.config import EATON_DARK_BLUE
from ...services import plot_render_service
from .axis_selection_panel import PLOT_KINDS
from .no_wheel_combo_box import NoWheelComboBox


def _line_style_choices() -> tuple[tuple[object, str], ...]:
    from matplotlib.backends.qt_editor import figureoptions

    return tuple(figureoptions.LINESTYLES.items())


def _draw_style_choices() -> tuple[tuple[object, str], ...]:
    from matplotlib.backends.qt_editor import figureoptions

    return tuple(figureoptions.DRAWSTYLES.items())


def _marker_style_choices() -> tuple[tuple[object, str], ...]:
    from matplotlib.backends.qt_editor import figureoptions

    return (("none", "None"), *tuple(figureoptions.MARKERS.items()))


class LegendChannelStyleDialog(QDialog):
    def __init__(self, channel: str, style: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channel = channel.strip()
        self._original_label = str(style.get("label", self._channel)).strip() or self._channel
        self._label_overridden = bool(style.get("label_overridden", False))
        self._original_plot_kind = plot_render_service.normalise_plot_kind(style.get("plot_kind")) or "Line"
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

        self.line_style_combo = self._style_combo(_line_style_choices(), str(style.get("line_style", "-")))
        form.addRow("Line style:", self.line_style_combo)
        self.draw_style_combo = self._style_combo(_draw_style_choices(), str(style.get("draw_style", "default")))
        form.addRow("Draw style:", self.draw_style_combo)
        self.line_width_spin = self._number_spin(style.get("line_width", 1.5), default=1.5)
        form.addRow("Line width:", self.line_width_spin)

        marker_default = self._default_marker_for_plot_kind(self._original_plot_kind)
        self.marker_style_combo = self._style_combo(_marker_style_choices(), str(style.get("marker_style", marker_default)))
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
