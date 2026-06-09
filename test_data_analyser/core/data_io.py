from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional
import numpy as np
import pandas as pd

from .config import NUMERIC_EXTRACT_RE

def get_excel_sheets(filepath: str | Path) -> list[str]:
    path = Path(filepath)
    if path.suffix.lower() not in {".xlsx", ".xls"}:
        return []
    engine = "openpyxl" if path.suffix.lower() == ".xlsx" else "xlrd"
    return [str(sheet) for sheet in pd.ExcelFile(path, engine=engine).sheet_names]

def _is_blank_cell(value: object) -> bool:
    """Return True when an Excel cell should be treated as blank."""
    if pd.isna(value):
        return True
    return str(value).strip() == ""

def _looks_numeric_cell(value: object) -> bool:
    """Return True when a cell can be interpreted as a numeric data value."""
    if _is_blank_cell(value):
        return False
    try:
        float(str(value).replace(",", "").strip())
        return True
    except Exception:
        return False

def _make_unique_column_names(columns: Iterable[object]) -> list[str]:
    """Make dataframe column names unique while preserving readable names."""
    seen: dict[str, int] = {}
    unique: list[str] = []
    for col in columns:
        base = str(col).strip() or "Column"
        count = seen.get(base, 0)
        unique.append(base if count == 0 else f"{base} ({count + 1})")
        seen[base] = count + 1
    return unique

def _settings_value(settings_manager: Any, section: str, key: str, default: Any) -> Any:
    if settings_manager is None:
        return default
    try:
        return settings_manager.get(section, key)
    except Exception:
        return default

def _read_excel_with_smart_headers(path: Path, sheet_name: Optional[str], engine: str, settings_manager: Any = None) -> pd.DataFrame:
    """
    Read Excel files with normal single-row headers or grouped/multi-row headers.
    This prevents Pandas-generated "Unnamed" columns from appearing in the GUI.
    """
    header_row = int(_settings_value(settings_manager, "data_import", "header_row_index", 0) or 0)
    skip_rows = int(_settings_value(settings_manager, "data_import", "skip_rows", 0) or 0)
    if header_row != 0 or skip_rows != 0:
        df = pd.read_excel(
            path,
            sheet_name=sheet_name or 0,
            header=header_row,
            skiprows=skip_rows,
            engine=engine,
        )
        df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
        df.columns = _make_unique_column_names(df.columns)
        return df

    raw = pd.read_excel(path, sheet_name=sheet_name or 0, header=None, engine=engine)
    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if raw.empty:
        return raw

    data_start = None
    for idx in range(len(raw)):
        numeric_count = sum(_looks_numeric_cell(v) for v in raw.iloc[idx].tolist())
        if numeric_count >= 2:
            data_start = idx
            break

    if data_start is None:
        df = pd.read_excel(path, sheet_name=sheet_name or 0, engine=engine)
        df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
        df.columns = _make_unique_column_names(df.columns)
        return df

    header_block = raw.iloc[:data_start].copy()
    data = raw.iloc[data_start:].copy().reset_index(drop=True)
    if header_block.empty:
        data.columns = _make_unique_column_names([f"Column {i + 1}" for i in range(data.shape[1])])
        return data
    header_block = header_block.ffill(axis=1)

    built_columns: list[str] = []
    for col_idx in range(raw.shape[1]):
        parts: list[str] = []
        for row_idx in range(header_block.shape[0]):
            value = header_block.iat[row_idx, col_idx]
            if _is_blank_cell(value):
                continue
            part = str(value).strip()
            if part and part not in parts:
                parts.append(part)
        built_columns.append(" - ".join(parts) if parts else f"Column {col_idx + 1}")

    data.columns = _make_unique_column_names(built_columns)
    data = data.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    return data

def load_data(filepath: str | Path, sheet_name: Optional[str] = None, settings_manager: Any = None) -> pd.DataFrame:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()
    if ext == ".csv":
        delimiter = _settings_value(settings_manager, "data_import", "default_delimiter", "auto")
        encoding = str(_settings_value(settings_manager, "data_import", "default_encoding", "utf-8") or "utf-8")
        header_row = int(_settings_value(settings_manager, "data_import", "header_row_index", 0) or 0)
        skip_rows = int(_settings_value(settings_manager, "data_import", "skip_rows", 0) or 0)
        decimal_separator = str(_settings_value(settings_manager, "data_import", "decimal_separator", ".") or ".")
        read_kwargs: dict[str, Any] = {
            "encoding": encoding,
            "header": header_row,
            "skiprows": skip_rows,
            "decimal": decimal_separator,
        }
        if delimiter == "auto":
            read_kwargs.update({"sep": None, "engine": "python"})
        else:
            read_kwargs["sep"] = delimiter
        df = pd.read_csv(path, **read_kwargs)
        df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
        df.columns = _make_unique_column_names([str(c).strip() for c in df.columns])
        return df
    if ext == ".xlsx":
        return _read_excel_with_smart_headers(path, sheet_name, engine="openpyxl", settings_manager=settings_manager)
    if ext == ".xls":
        return _read_excel_with_smart_headers(path, sheet_name, engine="xlrd", settings_manager=settings_manager)

    raise ValueError("Unsupported file format. Please use CSV, XLSX, or XLS.")

def numeric_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    text = series.astype(str).str.strip()
    text = text.replace({"": np.nan, "-": np.nan, "--": np.nan,
                         "N/A": np.nan, "n/a": np.nan, "None": np.nan})
    text = text.str.replace(",", "", regex=False)
    text = text.str.extract(NUMERIC_EXTRACT_RE, expand=False)
    return pd.to_numeric(text, errors="coerce")

