"""Source-agnostic dataset / channel-registry domain models.

These framework-independent dataclasses give every data column a **stable
internal channel ID** (``ch_001`` style) that is decoupled from its
user-visible display name. Plot profiles, maths channels, limits, and saved
sessions reference columns by this stable ID so a header can be renamed without
breaking any of them.

The models hold no row data and import no UI toolkit or pandas; the runtime row
values continue to live in ``AppState.df`` (keyed by display name) and the
pandas-aware build/reconcile helpers live in ``services/dataset_service.py``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .conversions import _int, _mapping, _string

#: Allowed column data types.
DATA_TYPE_NUMERIC = "numeric"
DATA_TYPE_TEXT = "text"

#: Recognised data-source kinds.
SOURCE_EXCEL = "excel"
SOURCE_MANUAL = "manual"

_CHANNEL_ID_RE = re.compile(r"^ch_(\d+)$")


def _normalise_data_type(value: object) -> str:
    text = _string(value).strip().lower()
    return text if text in {DATA_TYPE_NUMERIC, DATA_TYPE_TEXT} else DATA_TYPE_NUMERIC


def _parse_channel_id(channel_id: object) -> int | None:
    match = _CHANNEL_ID_RE.match(str(channel_id))
    return int(match.group(1)) if match else None


def normalise_source_type(value: object) -> str:
    text = _string(value).strip().lower()
    return text if text in {SOURCE_EXCEL, SOURCE_MANUAL} else SOURCE_EXCEL


@dataclass
class ColumnSpec:
    """Stable identity + metadata for a single dataset column/channel."""

    id: str = ""
    display_name: str = ""
    data_type: str = DATA_TYPE_NUMERIC

    @classmethod
    def from_dict(cls, value: object) -> "ColumnSpec":
        data = _mapping(value)
        return cls(
            id=_string(data.get("id")).strip(),
            display_name=_string(data.get("display_name")),
            data_type=_normalise_data_type(data.get("data_type")),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "data_type": self.data_type,
        }

    @property
    def is_numeric(self) -> bool:
        return self.data_type == DATA_TYPE_NUMERIC


@dataclass
class ChannelRegistry:
    """Ordered registry of :class:`ColumnSpec` mirroring the dataframe columns.

    The registry owns a monotonic ``ch_###`` ID allocator. IDs are never reused
    so references stored elsewhere stay valid for the lifetime of a session.
    """

    columns: list[ColumnSpec] = field(default_factory=list)
    next_id: int = 1

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, value: object) -> "ChannelRegistry":
        data = _mapping(value)
        raw_columns = data.get("columns", [])
        columns = (
            [ColumnSpec.from_dict(column) for column in raw_columns]
            if isinstance(raw_columns, list)
            else []
        )
        columns = [column for column in columns if column.id]
        registry = cls(columns=columns, next_id=_int(data.get("next_id", 1), 1))
        registry.sync_next_id()
        return registry

    def to_dict(self) -> dict[str, object]:
        return {
            "columns": [column.to_dict() for column in self.columns],
            "next_id": self.next_id,
        }

    # ------------------------------------------------------------------
    # ID allocation
    # ------------------------------------------------------------------
    def sync_next_id(self) -> None:
        """Ensure ``next_id`` is above the highest existing ``ch_###`` number."""
        highest = 0
        for column in self.columns:
            parsed = _parse_channel_id(column.id)
            if parsed is not None and parsed > highest:
                highest = parsed
        if self.next_id <= highest:
            self.next_id = highest + 1

    def allocate_id(self) -> str:
        existing = {column.id for column in self.columns}
        while True:
            candidate = f"ch_{self.next_id:03d}"
            self.next_id += 1
            if candidate not in existing:
                return candidate

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def spec_for_id(self, channel_id: str) -> ColumnSpec | None:
        for column in self.columns:
            if column.id == channel_id:
                return column
        return None

    def spec_for_name(self, display_name: str) -> ColumnSpec | None:
        target = str(display_name)
        for column in self.columns:
            if column.display_name == target:
                return column
        return None

    def id_for_name(self, display_name: str) -> str | None:
        spec = self.spec_for_name(display_name)
        return spec.id if spec is not None else None

    def name_for_id(self, channel_id: str) -> str | None:
        spec = self.spec_for_id(channel_id)
        return spec.display_name if spec is not None else None

    def has_display_name(self, display_name: str, *, exclude_id: str | None = None) -> bool:
        target = str(display_name)
        for column in self.columns:
            if exclude_id is not None and column.id == exclude_id:
                continue
            if column.display_name == target:
                return True
        return False

    # ------------------------------------------------------------------
    # Ordered views
    # ------------------------------------------------------------------
    def ids(self) -> list[str]:
        return [column.id for column in self.columns]

    def display_names(self) -> list[str]:
        return [column.display_name for column in self.columns]

    def numeric_names(self) -> list[str]:
        return [column.display_name for column in self.columns if column.is_numeric]

    def numeric_ids(self) -> list[str]:
        return [column.id for column in self.columns if column.is_numeric]

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------
    def add_column(self, display_name: str, data_type: str = DATA_TYPE_NUMERIC) -> ColumnSpec:
        spec = ColumnSpec(
            id=self.allocate_id(),
            display_name=str(display_name),
            data_type=_normalise_data_type(data_type),
        )
        self.columns.append(spec)
        return spec

    def remove_column(self, channel_id: str) -> ColumnSpec | None:
        spec = self.spec_for_id(channel_id)
        if spec is not None:
            self.columns = [column for column in self.columns if column.id != channel_id]
        return spec

    def names_to_ids(self, names: list[str]) -> list[str]:
        """Resolve display names to channel IDs, skipping unknown names."""
        resolved: list[str] = []
        for name in names:
            channel_id = self.id_for_name(name)
            if channel_id is not None:
                resolved.append(channel_id)
        return resolved

    def ids_to_names(self, channel_ids: list[str]) -> list[str]:
        """Resolve channel IDs to current display names, skipping unknown IDs."""
        resolved: list[str] = []
        for channel_id in channel_ids:
            name = self.name_for_id(channel_id)
            if name is not None:
                resolved.append(name)
        return resolved
