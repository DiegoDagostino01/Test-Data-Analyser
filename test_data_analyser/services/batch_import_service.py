"""Batch data-file discovery for importing many runs at once.

Framework-independent: lists data files in a folder by one or more glob patterns
(optionally recursive) and derives a run name from each filename, optionally via
a regex. No file loading or UI here; the runs viewmodel loads each discovered
path through the existing single-run import.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..core.naming import natural_sort_key

DEFAULT_GLOB = "*.csv;*.xlsx"


def discover_data_files(folder: str | Path, *, glob: str = DEFAULT_GLOB, recursive: bool = False) -> list[Path]:
    """Return the data files in ``folder`` matching ``glob`` (``;``-separated).

    Results are de-duplicated and ordered with the shared natural sort so e.g.
    ``Run2`` precedes ``Run10``.
    """
    base = Path(folder)
    if not base.is_dir():
        return []
    patterns = [part.strip() for part in glob.split(";") if part.strip()] or ["*"]
    found: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches = base.rglob(pattern) if recursive else base.glob(pattern)
        for path in matches:
            if path.is_file() and path not in seen:
                seen.add(path)
                found.append(path)
    return sorted(found, key=lambda path: natural_sort_key(path.name))


def extract_run_name(path: str | Path, *, regex: Optional[str] = None) -> str:
    """Derive a run name from ``path``.

    Defaults to the filename stem. When ``regex`` is given and matches the file
    name, the first capture group (or the whole match) is used; an invalid or
    non-matching regex falls back to the stem.
    """
    name = Path(path).name
    stem = Path(path).stem
    if not regex:
        return stem
    try:
        match = re.search(regex, name)
    except re.error:
        return stem
    if match is None:
        return stem
    if match.groups():
        return match.group(1)
    return match.group(0)
