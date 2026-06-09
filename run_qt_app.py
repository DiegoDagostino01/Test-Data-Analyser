"""Root launch script for the PySide6 shell.

Usage::

    python run_qt_app.py

The existing Tkinter application is still launched with ``python run_app.py`` and
remains the full-featured app until the PySide6 path reaches feature parity.
"""
from test_data_analyser.qt_app.main_qt import main

if __name__ == "__main__":
    raise SystemExit(main())
