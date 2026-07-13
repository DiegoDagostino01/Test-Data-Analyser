from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.scan_release_artifacts import scan_release_tree


class ReleaseArtifactScanTests(unittest.TestCase):
    def test_clean_release_tree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "THIRD_PARTY_NOTICES.md").write_text("QtAds LGPL notice", encoding="utf-8")

            self.assertEqual(scan_release_tree(root), [])

    def test_settings_file_and_user_path_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / "_internal" / "config" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(
                json.dumps(
                    {
                        "recent_files": [r"C:\Users\Example\private.csv"],
                        "workspace": {"dock_state_b64": "private-layout"},
                    }
                ),
                encoding="utf-8",
            )

            issues = scan_release_tree(root)

        self.assertTrue(any("mutable settings file" in issue for issue in issues))
        self.assertTrue(any("local user path" in issue for issue in issues))
        self.assertTrue(any("recent_files" in issue for issue in issues))
        self.assertTrue(any("dock_state_b64" in issue for issue in issues))

    def test_empty_sensitive_settings_are_allowed_in_unrelated_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "metadata.json"
            payload.write_text(
                json.dumps({"recent_files": [], "main_geometry_b64": ""}),
                encoding="utf-8",
            )

            self.assertEqual(scan_release_tree(root), [])


if __name__ == "__main__":
    unittest.main()