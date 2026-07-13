"""Record pre-modernization Qt interaction timings for V1.03.00.

This script is deliberately non-gating. Run it on the designated Windows
release machine to establish a comparable baseline before workspace code is
introduced. CI should validate behavior and call counts rather than enforce
wall-clock thresholds from shared runners.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6 import __version__ as pyside_version
from PySide6.QtWidgets import QApplication

from test_data_analyser.core.settings_manager import SettingsManager
from test_data_analyser.qt_app.main_window import MainWindow
from test_data_analyser.qt_app.workspace import WorkspacePreset


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _measure(
    action: Callable[[int], None],
    *,
    samples: int,
    warmups: int,
) -> dict[str, float | int]:
    application = QApplication.instance()
    for index in range(warmups):
        action(index)
        if application is not None:
            application.processEvents()

    durations: list[float] = []
    for index in range(samples):
        started = perf_counter()
        action(index)
        if application is not None:
            application.processEvents()
        durations.append((perf_counter() - started) * 1000.0)

    return {
        "samples": samples,
        "median_ms": round(statistics.median(durations), 3),
        "p95_ms": round(_percentile(durations, 0.95), 3),
        "max_ms": round(max(durations, default=0.0), 3),
    }


def record_baseline(*, samples: int, warmups: int) -> dict[str, object]:
    application = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        manager = SettingsManager(Path(directory) / "settings.json")
        manager.set("general_ui", "user_experience_mode", "advanced")
        window = MainWindow(manager)
        window.show()
        application.processEvents()

        presets = (
            WorkspacePreset.ANALYSIS,
            WorkspacePreset.COMPARISON,
            WorkspacePreset.REPORTING,
            WorkspacePreset.DATA_EDITING,
        )
        channels = ["Time", *[f"Channel {index}" for index in range(1, 10001)]]
        window.axis_panel.set_columns(channels, "Time")
        search_queries = ("999", "channel 42", "other numeric", "no-match")

        results = {
            "workspace_switch": _measure(
                lambda index: window.workspace_manager.apply_preset(
                    presets[index % len(presets)]
                ),
                samples=samples,
                warmups=warmups,
            ),
            "statistics_panel_visibility": _measure(
                lambda index: (
                    window.workspace_manager.show_panel("analysis.statistics")
                    if index % 2 == 0
                    else window.workspace_manager.hide_panel("analysis.statistics")
                ),
                samples=samples,
                warmups=warmups,
            ),
            "channel_search_10000": _measure(
                lambda index: window.axis_panel.channel_search_edit.setText(
                    search_queries[index % len(search_queries)]
                ),
                samples=samples,
                warmups=warmups,
            ),
        }
        window.close()

    return {
        "metadata": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "pyside": pyside_version,
            "qt_platform": os.environ.get("QT_QPA_PLATFORM", ""),
            "warmups": warmups,
            "samples": samples,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.samples < 1 or arguments.warmups < 0:
        parser.error("samples must be positive and warmups cannot be negative")

    baseline = record_baseline(samples=arguments.samples, warmups=arguments.warmups)
    rendered = json.dumps(baseline, indent=2)
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())