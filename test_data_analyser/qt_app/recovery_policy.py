"""Bounded recovery-file discovery for the no-data dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time


RECOVERY_FILENAME = "autosave.json"
RECOVERY_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


@dataclass(frozen=True)
class RecoveryCandidate:
    path: Path
    modified_epoch: float
    fingerprint: str


def find_recovery_candidate(
    recent_files: list[str],
    recent_sessions: list[str],
    dismissed_fingerprints: list[str],
    *,
    working_directory: Path | None = None,
    now_epoch: float | None = None,
) -> RecoveryCandidate | None:
    """Return the newest recent, non-dismissed recovery file within retention."""
    directories = {(working_directory or Path.cwd()).resolve()}
    for path_text in (*recent_files, *recent_sessions):
        if path_text:
            directories.add(Path(path_text).expanduser().resolve().parent)

    now = time.time() if now_epoch is None else now_epoch
    dismissed = set(dismissed_fingerprints)
    candidates: list[RecoveryCandidate] = []
    for directory in directories:
        path = directory / RECOVERY_FILENAME
        try:
            stat = path.stat()
        except OSError:
            continue
        age = max(0.0, now - stat.st_mtime)
        if age > RECOVERY_MAX_AGE_SECONDS:
            continue
        fingerprint = recovery_fingerprint(path, stat.st_mtime_ns, stat.st_size)
        if fingerprint in dismissed:
            continue
        candidates.append(RecoveryCandidate(path, stat.st_mtime, fingerprint))

    return max(candidates, key=lambda candidate: candidate.modified_epoch, default=None)


def recovery_fingerprint(path: Path, modified_ns: int, size: int) -> str:
    return f"{path.resolve()}|{modified_ns}|{size}"