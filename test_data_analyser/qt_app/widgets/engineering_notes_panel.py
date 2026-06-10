"""Engineering Notes panel.

A scrollable set of structured note fields (objective, observations, rationale,
and so on) with a compiled report/email preview. The panel is a thin Qt view;
the field definitions, note storage, and report formatting all run through the
framework-independent :class:`EngineeringNotesViewModel`.

The compiled report includes the current file and axis selection, which the main
window supplies through an injected context provider.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.engineering_notes_vm import EngineeringNotesViewModel
from ..adapters import qt_message_service

# Provider returns (file_name, x_axis, y_axis_csv) for the report header.
ContextProvider = Callable[[], tuple[str, str, str]]


class EngineeringNotesPanel(QWidget):
    def __init__(self, view_model: EngineeringNotesViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vm = view_model
        self._context_provider: Optional[ContextProvider] = None
        self._editors: dict[str, QPlainTextEdit] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._build_scroll_area(), stretch=1)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_scroll_area(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        inner = QVBoxLayout(container)
        inner.setContentsMargins(4, 4, 4, 4)

        for key, label, hint in self.vm.field_definitions():
            inner.addWidget(self._build_field(key, label, hint))

        preview_frame = QFrame()
        preview_frame.setObjectName("EatonPanel")
        preview_layout = QVBoxLayout(preview_frame)
        heading = QLabel("Compiled Notes Preview")
        heading.setObjectName("PanelHeading")
        preview_layout.addWidget(heading)
        hint = QLabel("Use this generated text for reports, emails, design reviews, or test summaries.")
        hint.setObjectName("PlaceholderText")
        hint.setWordWrap(True)
        preview_layout.addWidget(hint)
        self.report_text = QPlainTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setMinimumHeight(160)
        self.report_text.setPlaceholderText(
            "Structured engineering notes will appear here after clicking Refresh Report Text."
        )
        preview_layout.addWidget(self.report_text)
        inner.addWidget(preview_frame)
        inner.addStretch(1)

        scroll.setWidget(container)
        return scroll

    def _build_field(self, key: str, label: str, hint: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("EatonPanel")
        layout = QVBoxLayout(frame)
        heading = QLabel(label)
        heading.setObjectName("PanelHeading")
        layout.addWidget(heading)
        hint_label = QLabel(hint)
        hint_label.setObjectName("PlaceholderText")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        editor = QPlainTextEdit()
        editor.setMinimumHeight(70)
        editor.textChanged.connect(lambda k=key: self._on_field_changed(k))
        self._editors[key] = editor
        layout.addWidget(editor)
        return frame

    # ------------------------------------------------------------------
    # Context wiring
    # ------------------------------------------------------------------
    def set_context_provider(self, provider: ContextProvider) -> None:
        self._context_provider = provider

    def _context(self) -> tuple[str, str, str]:
        if self._context_provider is None:
            return "", "", ""
        return self._context_provider()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_from_state(self) -> None:
        """Refresh every editor from the viewmodel's stored notes."""
        notes = self.vm.get_notes()
        for key, editor in self._editors.items():
            editor.blockSignals(True)
            editor.setPlainText(notes.get(key, ""))
            editor.blockSignals(False)
        self.refresh_report()

    def refresh_report(self) -> None:
        file_name, x_axis, y_axis = self._context()
        self.report_text.setPlainText(
            self.vm.report_text(file_name=file_name, x_axis=x_axis, y_axis=y_axis)
        )

    def clear_notes(self) -> bool:
        if not qt_message_service.confirm(
            self, "Clear Engineering Notes", "Clear all structured engineering note fields?"
        ):
            return False
        self.vm.clear()
        for editor in self._editors.values():
            editor.blockSignals(True)
            editor.clear()
            editor.blockSignals(False)
        self.refresh_report()
        return True

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_field_changed(self, key: str) -> None:
        editor = self._editors.get(key)
        if editor is not None:
            self.vm.update_field(key, editor.toPlainText())
