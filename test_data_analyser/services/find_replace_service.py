"""Find & replace over a dataframe for the Raw Data view.

Framework-independent: searches the *string representation* of each cell so
numeric cells match by their displayed text, supports plain or regex queries with
optional case sensitivity and column scoping, and applies replacements through an
injected ``write`` callable so the caller keeps control of type coercion, dtype
upcasting, and undo. No PySide6 here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import pandas as pd


@dataclass(frozen=True)
class Match:
    """A single search hit: the dataframe index label, column, and cell text."""

    row: object
    column: str
    value: str


@dataclass
class ReplacementSummary:
    replaced: int = 0
    warnings: list[str] = field(default_factory=list)


WriteCell = Callable[[object, str, str], object]


def _compile(query: str, regex: bool, case_sensitive: bool) -> "re.Pattern[str]":
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(query if regex else re.escape(query), flags)


def _cell_text(value: object) -> Optional[str]:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def replace_in_text(
    text: str, query: str, replacement: str, *, regex: bool = False, case_sensitive: bool = False
) -> str:
    """Return ``text`` with ``query`` replaced by ``replacement`` (one cell)."""
    return _compile(query, regex, case_sensitive).sub(replacement, text)


def find_matches(
    df: Optional[pd.DataFrame],
    query: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
    columns: Optional[Sequence[str]] = None,
) -> list[Match]:
    """Return every cell whose text matches ``query`` (``re.error`` on bad regex)."""
    if df is None or query == "":
        return []
    pattern = _compile(query, regex, case_sensitive)
    search_columns = [c for c in (columns if columns is not None else list(df.columns)) if c in df.columns]
    matches: list[Match] = []
    for column in search_columns:
        for row_label, value in df[column].items():
            text = _cell_text(value)
            if text is not None and pattern.search(text):
                matches.append(Match(row=row_label, column=str(column), value=text))
    return matches


def apply_replacements(
    df: Optional[pd.DataFrame],
    matches: Sequence[Match],
    replacement: str,
    *,
    query: str,
    regex: bool = False,
    case_sensitive: bool = False,
    write: WriteCell,
) -> ReplacementSummary:
    """Replace ``query`` with ``replacement`` in each match, via ``write``.

    ``write(row, column, new_text)`` performs the actual cell write (coercion,
    dtype upcast, undo bookkeeping) and returns an object with ``ok``/``warnings``
    attributes. Only cells whose text actually changes are written.
    """
    summary = ReplacementSummary()
    if df is None or not matches:
        return summary
    for match in matches:
        if match.column not in df.columns:
            continue
        try:
            current = df.at[match.row, match.column]
        except KeyError:
            continue
        text = _cell_text(current)
        if text is None:
            continue
        new_text = replace_in_text(text, query, replacement, regex=regex, case_sensitive=case_sensitive)
        if new_text == text:
            continue
        result = write(match.row, match.column, new_text)
        if result is None or getattr(result, "ok", True):
            summary.replaced += 1
            summary.warnings.extend(getattr(result, "warnings", None) or [])
    return summary
