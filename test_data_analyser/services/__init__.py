"""Framework-independent service layer for the Test Data Analyser.

Services contain reusable engineering/data logic with no UI imports. They must
not import Tkinter or PySide6, and must not show message boxes or open dialogs;
instead they return values or an :class:`OperationResult`. ``plot_render_service``
may import Matplotlib, but canvas embedding stays in UI adapters.
"""
from __future__ import annotations

from .results import OperationResult

__all__ = ["OperationResult"]
