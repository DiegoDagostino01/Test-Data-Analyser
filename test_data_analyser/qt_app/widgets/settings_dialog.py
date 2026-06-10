"""Settings dialog.

A focused Qt settings dialog for the most-used options, driven entirely through
the framework-independent :class:`SettingsViewModel` (get/set/save). Additional
sections can be added to ``FIELD_SPEC`` as needed.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.settings_vm import SettingsViewModel
from ..adapters import qt_message_service
from .no_wheel_combo_box import NoWheelComboBox


@dataclass(frozen=True)
class _Field:
    section: str
    key: str
    label: str
    kind: str  # "combo" | "check" | "int" | "double"
    options: tuple[str, ...] | None = None
    minimum: float = 0
    maximum: float = 1000


# Section title -> ordered fields. Combo options without an explicit tuple are
# pulled from the settings schema's available_* lists at build time.
FIELD_SPEC: dict[str, list[_Field]] = {
    "General": [
        _Field("general_ui", "theme", "Theme", "combo", ("light", "dark")),
        _Field("general_ui", "confirm_before_delete", "Confirm before delete", "check"),
        _Field("general_ui", "show_tooltips", "Show tooltips", "check"),
    ],
    "Plot Appearance": [
        _Field("plot_appearance", "colour_cycle", "Colour cycle", "combo"),
        _Field("plot_appearance", "default_line_width", "Default line width", "double", minimum=0.5, maximum=10.0),
        _Field("plot_appearance", "grid_visible", "Grid visible", "check"),
    ],
    "Analysis": [
        _Field("axis_scaling", "decimal_places_statistics", "Statistics decimal places", "int", minimum=0, maximum=10),
    ],
    "Axis Padding": [
        _Field("axis_scaling", "pad_x_axis", "Pad X-axis", "check"),
        _Field("axis_scaling", "pad_x_percent", "X-axis padding %", "double", minimum=0, maximum=100),
        _Field("axis_scaling", "pad_y_axis", "Pad Y-axis", "check"),
        _Field("axis_scaling", "pad_y_percent", "Y-axis padding %", "double", minimum=0, maximum=100),
    ],
}


class SettingsDialog(QDialog):
    def __init__(self, view_model: SettingsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vm = view_model
        self.setWindowTitle("Settings")
        self.resize(440, 360)
        self._editors: dict[tuple[str, str], QWidget] = {}

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        for title, fields in FIELD_SPEC.items():
            tabs.addTab(self._build_tab(fields), title)
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_tab(self, fields: list[_Field]) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        for field in fields:
            editor = self._build_editor(field)
            self._editors[(field.section, field.key)] = editor
            form.addRow(field.label, editor)
        return page

    def _build_editor(self, field: _Field) -> QWidget:
        current = self.vm.get(field.section, field.key)
        if field.kind == "combo":
            combo = NoWheelComboBox()
            options = list(field.options) if field.options else (self.vm.options_for(field.section, field.key) or [])
            combo.addItems([str(option) for option in options])
            if current is not None and str(current) in [str(o) for o in options]:
                combo.setCurrentText(str(current))
            return combo
        if field.kind == "check":
            check = QCheckBox()
            check.setChecked(bool(current))
            return check
        if field.kind == "int":
            spin = QSpinBox()
            spin.setRange(int(field.minimum), int(field.maximum))
            try:
                spin.setValue(int(current))
            except (TypeError, ValueError):
                pass
            return spin
        double = QDoubleSpinBox()
        double.setRange(float(field.minimum), float(field.maximum))
        double.setSingleStep(0.1)
        try:
            double.setValue(float(current))
        except (TypeError, ValueError):
            pass
        return double

    def _value_for(self, field: _Field) -> object:
        editor = self._editors[(field.section, field.key)]
        if isinstance(editor, QComboBox):
            return editor.currentText()
        if isinstance(editor, QCheckBox):
            return editor.isChecked()
        if isinstance(editor, QSpinBox):
            return editor.value()
        if isinstance(editor, QDoubleSpinBox):
            return editor.value()
        return None

    def _on_save(self) -> None:
        errors: list[str] = []
        for fields in FIELD_SPEC.values():
            for field in fields:
                result = self.vm.set(field.section, field.key, self._value_for(field))
                if not result.ok:
                    errors.append(result.message)
        save_result = self.vm.save()
        if errors or not save_result.ok:
            qt_message_service.error(self, "Settings", "\n".join(errors) or save_result.message)
            return
        self.accept()
