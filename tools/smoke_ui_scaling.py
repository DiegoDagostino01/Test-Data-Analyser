"""Construct the Qt shell at the process scale factor and report key geometry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from PySide6.QtWidgets import QApplication, QLabel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from test_data_analyser.core.settings_manager import SettingsManager
from test_data_analyser.qt_app.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", choices=("light", "dark"), required=True)
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        settings = SettingsManager(Path(directory) / "settings.json")
        settings.set("general_ui", "theme", args.theme)
        settings.set("general_ui", "user_experience_mode", "advanced")
        window = MainWindow(settings)
        window._show_workspace()
        window.show()
        app.processEvents()

        groups = window.ribbon.findChildren(QLabel, "RibbonGroupLabel")
        visible_groups = [label.text() for label in groups if label.parentWidget().isVisible()]
        generate_button = window.ribbon_manager.button_for("plot.generate")
        if len(visible_groups) != 7 or not generate_button.isVisible():
            raise RuntimeError("Ribbon controls are not reachable at this scale factor.")
        if window.width() <= 0 or window.height() <= 0 or window.dashboard.width() <= 0:
            raise RuntimeError("Main shell geometry is invalid at this scale factor.")

        screen = app.primaryScreen()
        result = {
            "theme": args.theme,
            "device_pixel_ratio": screen.devicePixelRatio() if screen is not None else 0.0,
            "figure_dpi": window.plot_workspace.canvas.figure.dpi,
            "window_size": [window.width(), window.height()],
            "visible_groups": visible_groups,
        }
        print(json.dumps(result))
        window.workspace_manager.begin_shutdown()
        window.vm.state.is_dirty = False
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())