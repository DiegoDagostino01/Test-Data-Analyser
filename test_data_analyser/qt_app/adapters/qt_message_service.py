"""Qt message-box adapter.

Wraps ``QMessageBox`` so panels report success/warning/error and ask yes/no
questions without constructing message boxes inline. This is where service/
viewmodel :class:`OperationResult` objects are translated into user-facing
dialogs.
"""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def info(parent: QWidget | None, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def warning(parent: QWidget | None, title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)


def error(parent: QWidget | None, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def confirm(parent: QWidget | None, title: str, message: str) -> bool:
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    return reply == QMessageBox.Yes


def show_result(parent: QWidget | None, title: str, result) -> None:
    """Display an :class:`OperationResult` as an info or error dialog."""
    if getattr(result, "ok", False):
        info(parent, title, getattr(result, "message", "") or "Done.")
    else:
        error(parent, title, getattr(result, "message", "") or "Operation failed.")
