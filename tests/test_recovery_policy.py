from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import unittest

from test_data_analyser.qt_app.recovery_policy import (
    RECOVERY_MAX_AGE_SECONDS,
    find_recovery_candidate,
)


class RecoveryPolicyTests(unittest.TestCase):
    def test_newest_recent_recovery_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older_dir = root / "older"
            newer_dir = root / "newer"
            older_dir.mkdir()
            newer_dir.mkdir()
            older = older_dir / "autosave.json"
            newer = newer_dir / "autosave.json"
            older.write_text("{}", encoding="utf-8")
            newer.write_text("{}", encoding="utf-8")
            now = time.time()
            os.utime(older, (now - 20, now - 20))
            os.utime(newer, (now - 10, now - 10))

            candidate = find_recovery_candidate(
                [str(older_dir / "data.csv")],
                [str(newer_dir / "session.json")],
                [],
                working_directory=root / "empty",
                now_epoch=now,
            )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.path, newer)

    def test_expired_recovery_is_hidden_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recovery = root / "autosave.json"
            recovery.write_text("{}", encoding="utf-8")
            now = time.time()
            expired = now - RECOVERY_MAX_AGE_SECONDS - 1
            os.utime(recovery, (expired, expired))

            candidate = find_recovery_candidate(
                [], [], [], working_directory=root, now_epoch=now
            )

            self.assertIsNone(candidate)
            self.assertTrue(recovery.exists())

    def test_dismissed_recovery_reappears_after_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recovery = root / "autosave.json"
            recovery.write_text("{}", encoding="utf-8")
            first = find_recovery_candidate([], [], [], working_directory=root)
            assert first is not None

            dismissed = find_recovery_candidate(
                [], [], [first.fingerprint], working_directory=root
            )
            recovery.write_text('{"updated": true}', encoding="utf-8")
            updated = find_recovery_candidate(
                [], [], [first.fingerprint], working_directory=root
            )

        self.assertIsNone(dismissed)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertNotEqual(updated.fingerprint, first.fingerprint)

    def test_missing_recovery_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = find_recovery_candidate(
                [str(Path(directory) / "missing" / "data.csv")],
                [],
                [],
                working_directory=Path(directory) / "other",
            )

        self.assertIsNone(candidate)


if __name__ == "__main__":
    unittest.main()