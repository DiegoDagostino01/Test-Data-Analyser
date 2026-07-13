from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 is not installed")
class UiScalingSmokeTests(unittest.TestCase):
    def test_light_and_dark_shells_construct_at_supported_scale_factors(self) -> None:
        for factor in (1.25, 1.5, 2.0):
            for theme in ("light", "dark"):
                with self.subTest(factor=factor, theme=theme):
                    env = os.environ.copy()
                    env["QT_QPA_PLATFORM"] = "offscreen"
                    env["QT_SCALE_FACTOR"] = str(factor)
                    completed = subprocess.run(
                        [sys.executable, "tools/smoke_ui_scaling.py", "--theme", theme],
                        cwd=PROJECT_ROOT,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    result = json.loads(completed.stdout.strip().splitlines()[-1])
                    self.assertEqual(result["theme"], theme)
                    self.assertAlmostEqual(result["device_pixel_ratio"], factor, places=2)
                    self.assertAlmostEqual(result["figure_dpi"], 150 * factor, places=2)
                    self.assertEqual(len(result["visible_groups"]), 7)


if __name__ == "__main__":
    unittest.main()