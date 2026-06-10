"""PySide6 application entry point.

Run with::

    python -m test_data_analyser.qt_app.main_qt

or via the root script ``run_qt_app.py``.
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Test Data Analyser")
    app.setOrganizationName("Eaton")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
