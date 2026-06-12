"""Maths (calculated) channels viewmodel.

Coordinates validation, application, recalculation, and deletion of calculated
channels against :class:`AppState`. Crucially, it returns :class:`OperationResult`
objects instead of showing message boxes. The dataframe and the
calculated-channel definitions on ``AppState`` are mutated in place.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..core.utils import natural_sort_key
from ..services import maths_channel_service
from ..services.maths_channel_service import MathsChannelEvaluator
from ..services.results import OperationResult
from .app_state import AppState

MATHS_CHANNEL_TABLE_COLUMNS = ["Name", "Formula", "Enabled", "Description"]


class MathsChannelsViewModel:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def _evaluator(self) -> MathsChannelEvaluator:
        return MathsChannelEvaluator(self.state.df)

    def normalise_definitions(self, raw: Any) -> dict[str, dict[str, Any]]:
        return maths_channel_service.normalise_calculated_channel_definitions(raw)

    def channel_names(self) -> list[str]:
        return sorted(self.state.calculated_channels.keys(), key=natural_sort_key)

    def channel_table(self) -> pd.DataFrame:
        rows = []
        for name in self.channel_names():
            definition = self.state.calculated_channels[name]
            rows.append(
                {
                    "Name": definition.get("name", name),
                    "Formula": definition.get("formula", ""),
                    "Enabled": "Yes" if definition.get("enabled", True) else "No",
                    "Description": definition.get("description", ""),
                }
            )
        return pd.DataFrame(rows, columns=MATHS_CHANNEL_TABLE_COLUMNS)

    def validate_formula(self, formula: str) -> OperationResult:
        """Validate a formula against the loaded dataframe.

        On success the payload is a summary dict with row/numeric counts and the
        min/max of the produced series.
        """
        try:
            series, _referenced = self._evaluator().evaluate(formula)
        except Exception as exc:
            return OperationResult.failure(str(exc))
        valid = series.dropna()
        if valid.empty:
            return OperationResult.success(
                "Formula is valid, but it produced no numeric values.",
                payload={"rows": int(len(series)), "numeric": 0, "min": None, "max": None},
            )
        return OperationResult.success(
            "Formula is valid.",
            payload={
                "rows": int(len(series)),
                "numeric": int(len(valid)),
                "min": float(valid.min()),
                "max": float(valid.max()),
            },
        )

    def apply_channel(
        self,
        name: str,
        formula: str,
        description: str = "",
        *,
        selected_name: str | None = None,
    ) -> OperationResult:
        """Create or update a calculated channel.

        ``selected_name`` is the channel currently being edited (if any), so a
        rename removes the previous column. On success the payload carries the
        channel name and its referenced source columns.
        """
        if self.state.df is None:
            return OperationResult.failure("Please load a data file before creating a Maths Channel.")
        channel_name = str(name).strip()
        if not channel_name:
            return OperationResult.failure("Please enter a channel name.")
        formula = str(formula).strip()
        if not formula:
            return OperationResult.failure("Please enter a formula.")
        if (
            channel_name in self.state.df.columns
            and channel_name not in self.state.calculated_channels
            and channel_name != selected_name
        ):
            return OperationResult.failure(
                f"'{channel_name}' already exists as a source data column. Choose a different name."
            )
        try:
            series, referenced_columns = self._evaluator().evaluate(formula, blocked_names={channel_name})
        except Exception as exc:
            return OperationResult.failure(str(exc))

        if selected_name and selected_name != channel_name:
            self.state.calculated_channels.pop(selected_name, None)
            if selected_name in self.state.df.columns:
                del self.state.df[selected_name]

        self.state.df[channel_name] = series
        self.state.calculated_channels[channel_name] = {
            "name": channel_name,
            "formula": formula,
            "description": str(description).strip(),
            "enabled": True,
            "created_from_columns": referenced_columns,
        }
        return OperationResult.success(
            f"Maths Channel '{channel_name}' saved.",
            payload={"name": channel_name, "created_from_columns": referenced_columns},
        )

    def recalculate(self) -> OperationResult:
        """Recalculate all enabled calculated channels.

        Disabled or invalid channels have their dataframe column removed but their
        definition is preserved. The payload carries the per-channel error list
        and whether the dataframe changed.
        """
        if self.state.df is None:
            return OperationResult.failure("Load a data file before recalculating Maths Channels.")
        if not self.state.calculated_channels:
            return OperationResult.success("No Maths Channels have been defined.", payload={"errors": [], "changed": False})

        errors: list[str] = []
        changed = False
        for channel_name, definition in list(self.state.calculated_channels.items()):
            if not bool(definition.get("enabled", True)):
                if channel_name in self.state.df.columns:
                    del self.state.df[channel_name]
                    changed = True
                continue
            formula = str(definition.get("formula") or "").strip()
            if not formula:
                errors.append(f"{channel_name}: missing formula")
                if channel_name in self.state.df.columns:
                    del self.state.df[channel_name]
                    changed = True
                continue
            try:
                series, referenced_columns = self._evaluator().evaluate(formula, blocked_names={channel_name})
            except Exception as exc:
                errors.append(f"{channel_name}: {exc}")
                if channel_name in self.state.df.columns:
                    del self.state.df[channel_name]
                    changed = True
                continue
            self.state.df[channel_name] = series
            definition["name"] = channel_name
            definition["created_from_columns"] = referenced_columns
            changed = True

        message = (
            "Some Maths Channels could not be recalculated."
            if errors
            else "All enabled Maths Channels were recalculated."
        )
        return OperationResult(ok=not errors, message=message, errors=errors, payload={"errors": errors, "changed": changed})

    def delete_channel(self, name: str) -> OperationResult:
        """Delete a calculated channel and its dataframe column."""
        channel_name = str(name).strip()
        if not channel_name or channel_name not in self.state.calculated_channels:
            return OperationResult.failure("Select a Maths Channel to delete.")
        self.state.calculated_channels.pop(channel_name, None)
        if self.state.df is not None and channel_name in self.state.df.columns:
            del self.state.df[channel_name]
        return OperationResult.success(f"Maths Channel '{channel_name}' deleted.", payload={"name": channel_name})
