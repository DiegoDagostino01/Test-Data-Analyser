"""Fail a release scan when mutable settings or sensitive local state is bundled."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


TEXT_SUFFIXES = frozenset({".cfg", ".csv", ".ini", ".json", ".log", ".md", ".txt", ".xml", ".yaml", ".yml"})
SENSITIVE_KEYS = frozenset(
    {
        "dock_state_b64",
        "last_data_directory",
        "last_session_directory",
        "main_geometry_b64",
        "monitor_id",
        "recent_files",
        "recent_sessions",
        "screen_id",
    }
)
WINDOWS_USER_PATH = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.IGNORECASE)


def scan_release_tree(root: Path) -> list[str]:
    """Return relative, non-sensitive descriptions of release hygiene failures."""
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        return [f"release root does not exist: {root}"]

    issues: list[str] = []
    for path in sorted(candidate for candidate in resolved_root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(resolved_root).as_posix()
        if path.name.casefold() == "settings.json":
            issues.append(f"mutable settings file bundled: {relative}")
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if WINDOWS_USER_PATH.search(text) or "OneDrive - " in text:
            issues.append(f"local user path found: {relative}")
        if path.suffix.casefold() == ".json":
            issues.extend(_json_issues(relative, text))
    return issues


def _json_issues(relative: str, text: str) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    found: set[str] = set()
    _find_sensitive_values(payload, found)
    return [f"sensitive setting '{key}' has a value: {relative}" for key in sorted(found)]


def _find_sensitive_values(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in SENSITIVE_KEYS and _has_value(child):
                found.add(normalized_key)
            _find_sensitive_values(child, found)
    elif isinstance(value, list):
        for child in value:
            _find_sensitive_values(child, found)


def _has_value(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (str, list, dict, tuple, set)):
        return bool(value)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Release folder to scan")
    args = parser.parse_args()
    issues = scan_release_tree(args.root)
    if not issues:
        print(f"Release artifact scan passed: {args.root}")
        return 0
    print("Release artifact scan failed:")
    for issue in issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())