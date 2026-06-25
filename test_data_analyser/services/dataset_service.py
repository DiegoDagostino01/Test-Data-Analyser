"""Source-agnostic dataset editing operations.

Framework-independent structural edits over a ``(DataFrame, ChannelRegistry)``
pair used by both Excel-linked and manual data sources: build/reconcile the
registry, add/rename/delete columns, add/delete rows, and coerce cell edits.
Every column keeps a stable channel ID so renames never break references.

Row mutations return a *new* DataFrame in the result payload (so the caller can
reassign ``AppState.df``); column and registry mutations are applied in place on
the passed objects and also surfaced in the payload for convenience. The UI/edit
layer shows messages; this service only returns :class:`OperationResult`.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from ..core.data_io import detect_column_data_type
from ..domain import DATA_TYPE_NUMERIC, ChannelRegistry, ColumnSpec
from .results import OperationResult


def _duplicate_message(name: str) -> str:
    return f'A column with the name "{name}" already exists. Please choose a unique header name.'


def _try_float(text: object) -> float | None:
    try:
        return float(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------
# Registry build / reconcile
# ----------------------------------------------------------------------
def build_registry_for_dataframe(
    df: Optional[pd.DataFrame], existing: Optional[ChannelRegistry] = None
) -> ChannelRegistry:
    """Build a :class:`ChannelRegistry` for ``df``.

    When ``existing`` is provided, channel IDs are preserved for columns whose
    display name is unchanged (used when an Excel session reloads its source
    file from disk); new columns receive freshly allocated IDs.
    """
    registry = ChannelRegistry()
    existing_by_name: dict[str, ColumnSpec] = {}
    if existing is not None:
        registry.next_id = existing.next_id
        existing_by_name = {column.display_name: column for column in existing.columns}
    if df is not None:
        for column in df.columns:
            name = str(column)
            data_type = detect_column_data_type(df[column])
            prior = existing_by_name.get(name)
            if prior is not None:
                registry.columns.append(
                    ColumnSpec(id=prior.id, display_name=name, data_type=data_type)
                )
            else:
                registry.columns.append(
                    ColumnSpec(id=registry.allocate_id(), display_name=name, data_type=data_type)
                )
    registry.sync_next_id()
    return registry


def revalidate_types(df: Optional[pd.DataFrame], registry: ChannelRegistry) -> None:
    """Refresh every column's detected data type from current values."""
    if df is None:
        return
    for spec in registry.columns:
        if spec.display_name in df.columns:
            spec.data_type = detect_column_data_type(df[spec.display_name])


# ----------------------------------------------------------------------
# Column operations
# ----------------------------------------------------------------------
def add_column(
    df: Optional[pd.DataFrame],
    registry: ChannelRegistry,
    display_name: str,
    *,
    data_type: str = DATA_TYPE_NUMERIC,
) -> OperationResult:
    name = str(display_name).strip()
    if not name:
        return OperationResult.failure("Column name cannot be empty.")
    if registry.has_display_name(name):
        return OperationResult.failure(_duplicate_message(name))
    spec = registry.add_column(name, data_type)
    if df is None:
        df = pd.DataFrame()
    df[name] = np.nan
    return OperationResult.success(
        f'Added column "{name}".', payload={"df": df, "column_id": spec.id}
    )


def rename_column(
    df: Optional[pd.DataFrame],
    registry: ChannelRegistry,
    channel_id: str,
    new_display_name: str,
) -> OperationResult:
    spec = registry.spec_for_id(channel_id)
    if spec is None:
        return OperationResult.failure("Column not found.")
    new_name = str(new_display_name).strip()
    if not new_name:
        return OperationResult.failure("Column name cannot be empty.")
    old_name = spec.display_name
    if new_name == old_name:
        return OperationResult.success(
            "No change.",
            payload={"df": df, "old_name": old_name, "new_name": new_name, "column_id": channel_id},
        )
    if registry.has_display_name(new_name, exclude_id=channel_id):
        return OperationResult.failure(_duplicate_message(new_name))
    if df is not None and old_name in df.columns:
        df.rename(columns={old_name: new_name}, inplace=True)
    spec.display_name = new_name
    return OperationResult.success(
        f'Renamed "{old_name}" to "{new_name}".',
        payload={"df": df, "old_name": old_name, "new_name": new_name, "column_id": channel_id},
    )


def delete_column(
    df: Optional[pd.DataFrame], registry: ChannelRegistry, channel_id: str
) -> OperationResult:
    spec = registry.spec_for_id(channel_id)
    if spec is None:
        return OperationResult.failure("Column not found.")
    name = spec.display_name
    if df is not None and name in df.columns:
        df.drop(columns=[name], inplace=True)
    registry.remove_column(channel_id)
    return OperationResult.success(
        f'Deleted column "{name}".',
        payload={"df": df, "deleted_name": name, "column_id": channel_id},
    )


# ----------------------------------------------------------------------
# Row operations (return a new DataFrame)
# ----------------------------------------------------------------------
def add_row(df: Optional[pd.DataFrame], *, at_index: Optional[int] = None) -> OperationResult:
    if df is None or df.shape[1] == 0:
        return OperationResult.failure("Add a column before adding rows.")
    new_frame = pd.DataFrame([{column: np.nan for column in df.columns}], columns=df.columns)
    if at_index is None or at_index >= len(df):
        combined = pd.concat([df, new_frame], ignore_index=True)
    else:
        idx = max(0, int(at_index))
        combined = pd.concat([df.iloc[:idx], new_frame, df.iloc[idx:]], ignore_index=True)
    return OperationResult.success("Row added.", payload={"df": combined})


def delete_rows(df: Optional[pd.DataFrame], indices: Iterable[int]) -> OperationResult:
    if df is None:
        return OperationResult.failure("No dataset.")
    valid = sorted({int(i) for i in indices if 0 <= int(i) < len(df)})
    if not valid:
        return OperationResult.failure("No valid rows selected to delete.")
    combined = df.drop(index=valid).reset_index(drop=True)
    return OperationResult.success(
        f"Deleted {len(valid)} row(s).", payload={"df": combined}
    )


# ----------------------------------------------------------------------
# Cell editing
# ----------------------------------------------------------------------
def coerce_cell_value(spec: ColumnSpec, text: object) -> Any:
    """Coerce edited ``text`` for a column. Blank -> NaN; invalid numeric text is
    kept as-is (visible) rather than silently zeroed."""
    raw = "" if text is None else str(text)
    stripped = raw.strip()
    if stripped == "":
        return np.nan
    if spec.data_type == DATA_TYPE_NUMERIC:
        parsed = _try_float(stripped)
        return parsed if parsed is not None else raw
    return raw


def set_cell(
    df: Optional[pd.DataFrame],
    registry: ChannelRegistry,
    channel_id: str,
    row_index: int,
    text: object,
) -> OperationResult:
    spec = registry.spec_for_id(channel_id)
    if spec is None:
        return OperationResult.failure("Column not found.")
    return _assign_cell(df, spec, channel_id, row_index, coerce_cell_value(spec, text))


def set_cell_value(
    df: Optional[pd.DataFrame],
    registry: ChannelRegistry,
    channel_id: str,
    row_index: int,
    value: Any,
) -> OperationResult:
    """Write an already-coerced ``value`` without re-coercing it from text.

    Used by bulk paste/fill operations that coerce a whole block in one pass, so
    coerced ``NaN``/numeric values are not turned back into text. Dtype upcasting
    and type re-detection match :func:`set_cell`.
    """
    spec = registry.spec_for_id(channel_id)
    if spec is None:
        return OperationResult.failure("Column not found.")
    return _assign_cell(df, spec, channel_id, row_index, value)


def _assign_cell(
    df: Optional[pd.DataFrame],
    spec: ColumnSpec,
    channel_id: str,
    row_index: int,
    value: Any,
) -> OperationResult:
    name = spec.display_name
    if df is None or name not in df.columns:
        return OperationResult.failure(f'Column "{name}" not found.')
    if not (0 <= int(row_index) < len(df)):
        return OperationResult.failure("Row index out of range.")
    # Upcast a numeric column to object before storing kept-visible invalid text
    # so pandas does not reject the assignment.
    if isinstance(value, str) and pd.api.types.is_numeric_dtype(df[name]):
        df[name] = df[name].astype(object)
    df.at[int(row_index), name] = value
    spec.data_type = detect_column_data_type(df[name])
    warnings: list[str] = []
    if spec.data_type == DATA_TYPE_NUMERIC and isinstance(value, str):
        warnings.append(
            f'"{value}" is not numeric and will be ignored when plotting "{name}".'
        )
    return OperationResult.success(
        "Cell updated.",
        warnings=warnings,
        payload={"df": df, "value": value, "data_type": spec.data_type, "column_id": channel_id},
    )


# ----------------------------------------------------------------------
# Session embedding (manual datasets)
# ----------------------------------------------------------------------
def _json_safe(value: object) -> object:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(value)


def rows_from_dataframe(registry: ChannelRegistry, df: Optional[pd.DataFrame]) -> list[dict[str, object]]:
    """Serialise the dataframe rows keyed by stable channel ID for embedding in a
    manual session."""
    if df is None:
        return []
    id_by_name = {column.display_name: column.id for column in registry.columns}
    rows: list[dict[str, object]] = []
    for _, series in df.iterrows():
        row: dict[str, object] = {}
        for name, value in series.items():
            channel_id = id_by_name.get(str(name))
            if channel_id is None:
                continue
            row[channel_id] = _json_safe(value)
        rows.append(row)
    return rows


def dataframe_from_rows(
    registry: ChannelRegistry, rows: Optional[list[dict[str, object]]]
) -> pd.DataFrame:
    """Rebuild a dataframe (columns in registry order, keyed by display name) from
    channel-ID-keyed embedded session rows."""
    names = registry.display_names()
    ids = registry.ids()
    records: list[list[object]] = []
    for row in rows or []:
        mapping = row if isinstance(row, dict) else {}
        records.append([_from_json_safe(mapping.get(channel_id)) for channel_id in ids])
    if not records:
        return pd.DataFrame(columns=names)
    return pd.DataFrame(records, columns=names)


def _from_json_safe(value: object) -> object:
    return np.nan if value is None else value
