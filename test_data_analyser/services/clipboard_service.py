"""Clipboard (TSV) helpers for Raw Data cell-range copy/paste/cut.

Framework-independent: converts rectangular cell blocks to and from
Excel-compatible tab-separated text, coerces a pasted block to its target column
types via :func:`dataset_service.coerce_cell_value`, and infers the type of new
columns created by an over-wide paste. No PySide6 or clipboard object access
lives here; the Qt panel reads/writes the actual system clipboard.
"""
from __future__ import annotations

import math
from typing import Any, Optional

from ..domain import DATA_TYPE_NUMERIC, DATA_TYPE_TEXT, ColumnSpec
from . import dataset_service


def selection_to_tsv(values: list[list[Any]]) -> str:
    """Convert a 2D block of cell values to Excel-compatible TSV.

    Tabs separate columns and newlines separate rows. ``None``/``NaN`` become
    empty strings so blanks round-trip cleanly through Excel.
    """
    return "\n".join("\t".join(_cell_to_text(cell) for cell in row) for row in values)


def _cell_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def tsv_to_values(text: str) -> list[list[str]]:
    """Parse TSV/clipboard text into a 2D list of strings.

    Splits on newlines then tabs, tolerating ``\\r\\n``/``\\r`` line endings. A
    single trailing empty row produced by a final newline is dropped.
    """
    if text == "":
        return []
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    rows = normalised.split("\n")
    if len(rows) > 1 and rows[-1] == "":
        rows = rows[:-1]
    return [row.split("\t") for row in rows]


def infer_column_type(cells: list[str]) -> str:
    """Infer ``"numeric"`` or ``"text"`` for a new paste column from its cells.

    Blank cells are ignored. The column is numeric unless a non-blank cell fails
    to parse as a number; an all-blank column defaults to numeric.
    """
    seen = False
    for cell in cells:
        stripped = (cell or "").strip()
        if stripped == "":
            continue
        seen = True
        if _to_float(stripped) is None:
            return DATA_TYPE_TEXT
    return DATA_TYPE_NUMERIC if seen else DATA_TYPE_NUMERIC


def coerce_pasted_block(
    values: list[list[str]], column_specs: list[Optional[ColumnSpec]]
) -> tuple[list[list[Any]], list[str]]:
    """Coerce a pasted block per target column, collecting non-fatal warnings.

    ``column_specs[j]`` is the target column for paste-column ``j`` (or ``None``
    when the paste overflows the available columns, leaving the raw text). A
    warning is recorded for each non-numeric value kept in a numeric column.
    """
    coerced: list[list[Any]] = []
    warnings: list[str] = []
    for row_index, row in enumerate(values):
        out_row: list[Any] = []
        for col_index, cell in enumerate(row):
            spec = column_specs[col_index] if col_index < len(column_specs) else None
            if spec is None:
                out_row.append(cell)
                continue
            value = dataset_service.coerce_cell_value(spec, cell)
            if (
                isinstance(value, str)
                and spec.data_type == DATA_TYPE_NUMERIC
                and value.strip() != ""
            ):
                warnings.append(
                    f"{_cell_ref(row_index, col_index)}: '{value}' kept as text in "
                    f"numeric column '{spec.display_name}'."
                )
            out_row.append(value)
        coerced.append(out_row)
    return coerced, warnings


def _cell_ref(row: int, col: int) -> str:
    return f"R{row + 1}C{col + 1}"


def _to_float(text: str) -> Optional[float]:
    try:
        return float(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
