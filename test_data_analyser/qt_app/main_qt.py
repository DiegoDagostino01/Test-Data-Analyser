"""PySide6 application entry point.

Run with::

    python -m test_data_analyser.qt_app.main_qt

or via the root script ``run_qt_app.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


APP_ICON_RELATIVE_PATH = Path("test_data_analyser") / "qt_app" / "assets" / "app_icon.png"


def _app_icon_path() -> Path:
    module_asset_path = Path(__file__).resolve().parent / "assets" / "app_icon.png"
    if module_asset_path.exists():
        return module_asset_path

    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return bundle_root / APP_ICON_RELATIVE_PATH


def _load_app_icon() -> QIcon:
    icon_path = _app_icon_path()
    return QIcon(str(icon_path)) if icon_path.exists() else QIcon()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Test Data Analyser")
    app.setOrganizationName("Eaton")
    app_icon = _load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
