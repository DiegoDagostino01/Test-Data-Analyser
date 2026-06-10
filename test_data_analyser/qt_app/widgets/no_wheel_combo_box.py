"""Mouse-wheel-safe combo box.

A small :class:`QComboBox` subclass that ignores wheel events so the current
selection cannot be changed by accidental scrolling (for example while the
pointer hovers over the control inside a scrollable panel). The event is ignored
rather than consumed, so a surrounding scroll area still scrolls normally.

Living in the ``qt_app`` layer keeps this Qt-specific concern out of the
framework-independent layers, mirroring the intent of the legacy
``core.utils._block_mousewheel`` helper used by the old Tkinter UI.
"""
from __future__ import annotations

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox


class NoWheelComboBox(QComboBox):
    """A combo box that ignores mouse-wheel scrolling over the widget."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt naming)
        event.ignore()
