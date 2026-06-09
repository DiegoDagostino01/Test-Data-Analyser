"""Framework-independent service layer for the Test Data Analyser.

Services contain reusable engineering/data logic with no UI imports. They must
not import Tkinter or PySide6, and must not show message boxes or open dialogs;
instead they return values or an :class:`OperationResult`. ``plot_render_service``
may import Matplotlib, but canvas embedding stays in UI adapters.

These services are designed to be reused by the current Tkinter UI (as thin
wrappers in the existing mixins) and by a future PySide6 UI alike.
"""
from __future__ import annotations

from .results import OperationResult

__all__ = ["OperationResult"]
