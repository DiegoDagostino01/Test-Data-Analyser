"""Dataset editing viewmodel.

Coordinates source-agnostic structural edits — add/rename/delete columns and
rows plus cell edits — over :class:`AppState`'s dataframe and its stable-ID
:class:`~test_data_analyser.domain.ChannelRegistry`. When a column is renamed or
deleted it propagates the change across plot profiles, the current X-axis, Maths
Channel formulas, and limit lines so every reference stays consistent.

Framework-independent: it returns :class:`OperationResult` and mutates
``AppState`` in place. The Qt panel collects edits and triggers any plot/maths
refresh after calling these methods.
"""
from __future__ import annotations

from typing import Iterable, Optional

from ..services import clipboard_service, column_reference_service, dataset_service, fill_series_service
from ..services.results import OperationResult, payload_dict
from .app_state import AppState
from .state_controller import AppStateController, DatasetUndoSnapshot


class DatasetViewModel:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self._state_controller = AppStateController(state)
        self._undo_stack: list[DatasetUndoSnapshot] = []

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------
    def editable_columns(self) -> list[dict[str, str]]:
        """Return the editable source columns as ``{id, display_name, data_type}``."""
        return [
            {"id": spec.id, "display_name": spec.display_name, "data_type": spec.data_type}
            for spec in self.state.channel_registry.columns
        ]

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def _capture_undo(self, description: str) -> DatasetUndoSnapshot:
        return self._state_controller.capture_dataset_snapshot(description)

    def _push_undo(self, snapshot: DatasetUndoSnapshot) -> None:
        self._undo_stack.append(snapshot)

    def undo_last_edit(self) -> OperationResult:
        if not self._undo_stack:
            return OperationResult.failure("Nothing to undo")
        snapshot = self._undo_stack.pop()
        self._state_controller.restore_dataset_snapshot(snapshot)
        return OperationResult.success(f"Undid {snapshot.description}.")

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------
    def add_column(self, display_name: str, *, data_type: str = "numeric") -> OperationResult:
        undo = self._capture_undo("add column")
        result = dataset_service.add_column(
            self.state.df, self.state.channel_registry, display_name, data_type=data_type
        )
        payload = payload_dict(result)
        if result.ok and payload:
            self._state_controller.apply_dataframe_payload(payload)
            self._state_controller.mark_dirty()
            self._push_undo(undo)
        return result

    def rename_column(self, channel_id: str, new_display_name: str) -> OperationResult:
        spec = self.state.channel_registry.spec_for_id(channel_id)
        old_name = spec.display_name if spec is not None else None
        undo = self._capture_undo("rename column")
        result = dataset_service.rename_column(
            self.state.df, self.state.channel_registry, channel_id, new_display_name
        )
        payload = payload_dict(result)
        if result.ok and payload:
            self._state_controller.apply_dataframe_payload(payload)
            new_name = str(payload.get("new_name", new_display_name))
            if old_name and old_name != new_name:
                self._propagate_rename(old_name, new_name)
                self._state_controller.mark_dirty()
                self._push_undo(undo)
        return result

    def delete_column(self, channel_id: str) -> OperationResult:
        spec = self.state.channel_registry.spec_for_id(channel_id)
        name = spec.display_name if spec is not None else None
        undo = self._capture_undo("delete column")
        result = dataset_service.delete_column(self.state.df, self.state.channel_registry, channel_id)
        payload = payload_dict(result)
        if result.ok and payload:
            self._state_controller.apply_dataframe_payload(payload)
            if name:
                result.warnings.extend(self._propagate_delete(name))
                self._state_controller.mark_dirty()
                self._push_undo(undo)
        return result

    def move_column(self, channel_id: str, to_index: int) -> OperationResult:
        spec = self.state.channel_registry.spec_for_id(channel_id)
        if spec is None:
            return OperationResult.failure("Column not found.")
        undo = self._capture_undo("move column")
        result = dataset_service.move_column(self.state.df, self.state.channel_registry, channel_id, to_index)
        payload = payload_dict(result)
        if result.ok and payload:
            self._state_controller.apply_dataframe_payload(payload)
            self._state_controller.mark_dirty()
            self._push_undo(undo)
        return result

    def delete_columns(self, channel_ids: Iterable[str]) -> OperationResult:
        unique_ids = list(dict.fromkeys(str(channel_id) for channel_id in channel_ids))
        specs = [self.state.channel_registry.spec_for_id(channel_id) for channel_id in unique_ids]
        if not unique_ids:
            return OperationResult.failure("There is no column to delete.")
        if any(spec is None for spec in specs):
            return OperationResult.failure("One or more selected columns are no longer available.")

        undo = self._capture_undo("delete column(s)")
        deleted_names: list[str] = []
        warnings: list[str] = []
        for channel_id, spec in zip(unique_ids, specs):
            name = spec.display_name if spec is not None else ""
            result = dataset_service.delete_column(self.state.df, self.state.channel_registry, channel_id)
            if not result.ok:
                return result
            self._state_controller.apply_dataframe_payload(payload_dict(result))
            if name:
                deleted_names.append(name)
                warnings.extend(self._propagate_delete(name))

        if not deleted_names:
            return OperationResult.failure("There is no column to delete.")
        self._state_controller.mark_dirty()
        self._push_undo(undo)
        if len(deleted_names) == 1:
            message = f'Deleted column "{deleted_names[0]}".'
        else:
            message = f"Deleted {len(deleted_names)} columns."
        return OperationResult.success(
            message,
            warnings=warnings,
            payload={"df": self.state.df, "deleted_names": deleted_names, "column_ids": unique_ids},
        )

    # ------------------------------------------------------------------
    # Row / cell operations
    # ------------------------------------------------------------------
    def add_row(self, at_index: Optional[int] = None) -> OperationResult:
        undo = self._capture_undo("add row")
        result = dataset_service.add_row(self.state.df, at_index=at_index)
        payload = payload_dict(result)
        if result.ok and payload:
            self._state_controller.apply_dataframe_payload(payload)
            self._state_controller.mark_dirty()
            self._push_undo(undo)
        return result

    def delete_rows(self, indices: Iterable[int]) -> OperationResult:
        undo = self._capture_undo("delete row(s)")
        result = dataset_service.delete_rows(self.state.df, indices)
        payload = payload_dict(result)
        if result.ok and payload:
            self._state_controller.apply_dataframe_payload(payload)
            self._state_controller.mark_dirty()
            self._push_undo(undo)
        return result

    def set_cell(self, channel_id: str, row_index: int, text: object) -> OperationResult:
        undo = self._capture_undo("cell edit")
        result = dataset_service.set_cell(
            self.state.df, self.state.channel_registry, channel_id, row_index, text
        )
        payload = payload_dict(result)
        if result.ok and payload:
            self._state_controller.apply_dataframe_payload(payload)
            self._state_controller.mark_dirty()
            self._push_undo(undo)
        return result

    # ------------------------------------------------------------------
    # Block clipboard operations (copy / cut / paste)
    # ------------------------------------------------------------------
    def copy_block(self, row_indices: Iterable[int], channel_ids: Iterable[str]) -> str:
        """Return the values at the given rows x columns as Excel-compatible TSV."""
        rows = self._valid_rows(row_indices)
        ids = self._valid_channel_ids(channel_ids)
        return clipboard_service.selection_to_tsv(self._block_values(rows, ids))

    def cut_block(self, row_indices: Iterable[int], channel_ids: Iterable[str]) -> OperationResult:
        """Copy the block to TSV then blank the source cells in one undo step."""
        if self.state.df is None:
            return OperationResult.failure("No dataset.")
        rows = self._valid_rows(row_indices)
        ids = self._valid_channel_ids(channel_ids)
        if not rows or not ids:
            return OperationResult.failure("Select cells to cut.")
        tsv = clipboard_service.selection_to_tsv(self._block_values(rows, ids))
        blank = float("nan")
        undo = self._capture_undo("cut cells")
        for channel_id in ids:
            for row in rows:
                result = dataset_service.set_cell_value(
                    self.state.df, self.state.channel_registry, channel_id, row, blank
                )
                if result.ok:
                    self._state_controller.apply_dataframe_payload(payload_dict(result))
        self._state_controller.mark_dirty()
        self._push_undo(undo)
        return OperationResult.success(f"Cut {len(rows)} x {len(ids)} cells.", payload=tsv)

    def paste_block(self, top_row: int, left_channel_id: str, text: str) -> OperationResult:
        """Paste TSV ``text`` with its top-left cell at ``(top_row, left_channel_id)``.

        Expands the dataframe with extra rows and/or ``Column N`` columns when the
        pasted block runs past the current shape, coerces each value to its target
        column type, and records the whole paste as a single undo step.
        """
        if self.state.df is None:
            return OperationResult.failure("No dataset.")
        values = clipboard_service.tsv_to_values(text)
        if not values:
            return OperationResult.failure("There is nothing to paste.")
        ids = self.state.channel_registry.ids()
        if left_channel_id not in ids:
            return OperationResult.failure("The paste anchor column is no longer available.")
        anchor_col = ids.index(left_channel_id)
        block_rows = len(values)
        block_cols = max(len(row) for row in values)
        top = max(0, int(top_row))

        undo = self._capture_undo("paste cells")

        # Expand columns to the right when the block is wider than the dataset.
        while len(self.state.channel_registry.ids()) < anchor_col + block_cols:
            paste_col = len(self.state.channel_registry.ids()) - anchor_col
            cells = [row[paste_col] for row in values if paste_col < len(row)]
            data_type = clipboard_service.infer_column_type(cells)
            result = dataset_service.add_column(
                self.state.df, self.state.channel_registry, self._next_column_name(), data_type=data_type
            )
            if not result.ok:
                break
            self._state_controller.apply_dataframe_payload(payload_dict(result))

        # Expand rows downward when the block runs past the last row.
        while len(self.state.df) < top + block_rows:
            result = dataset_service.add_row(self.state.df, at_index=None)
            if not result.ok:
                break
            self._state_controller.apply_dataframe_payload(payload_dict(result))

        target_ids = self.state.channel_registry.ids()[anchor_col:anchor_col + block_cols]
        specs = [self.state.channel_registry.spec_for_id(cid) for cid in target_ids]
        coerced, warnings = clipboard_service.coerce_pasted_block(values, specs)

        written = 0
        for row_offset, row in enumerate(coerced):
            target_row = top + row_offset
            for col_offset, value in enumerate(row):
                if col_offset >= len(target_ids):
                    continue
                result = dataset_service.set_cell_value(
                    self.state.df, self.state.channel_registry, target_ids[col_offset], target_row, value
                )
                if result.ok:
                    self._state_controller.apply_dataframe_payload(payload_dict(result))
                    written += 1

        self._state_controller.mark_dirty()
        self._push_undo(undo)
        return OperationResult.success(
            f"Pasted {block_rows} row(s) x {block_cols} column(s).",
            warnings=warnings,
            payload={"rows": block_rows, "columns": block_cols, "cells": written},
        )

    def _block_values(self, row_indices: Iterable[int], channel_ids: Iterable[str]) -> list[list[object]]:
        df = self.state.df
        registry = self.state.channel_registry
        values: list[list[object]] = []
        for row in row_indices:
            out_row: list[object] = []
            for channel_id in channel_ids:
                spec = registry.spec_for_id(channel_id)
                if spec is None or df is None or spec.display_name not in df.columns or not (0 <= row < len(df)):
                    out_row.append("")
                else:
                    out_row.append(df.at[row, spec.display_name])
            values.append(out_row)
        return values

    def _valid_rows(self, row_indices: Iterable[int]) -> list[int]:
        df = self.state.df
        count = 0 if df is None else len(df)
        return sorted({int(row) for row in row_indices if 0 <= int(row) < count})

    def _valid_channel_ids(self, channel_ids: Iterable[str]) -> list[str]:
        registry = self.state.channel_registry
        ordered: list[str] = []
        for channel_id in channel_ids:
            cid = str(channel_id)
            if registry.spec_for_id(cid) is not None and cid not in ordered:
                ordered.append(cid)
        return ordered

    def _next_column_name(self) -> str:
        existing = set(self.state.channel_registry.display_names())
        index = len(existing) + 1
        while f"Column {index}" in existing:
            index += 1
        return f"Column {index}"

    # ------------------------------------------------------------------
    # Fill (fill-down / drag-fill)
    # ------------------------------------------------------------------
    def fill_down(self, row_indices: Iterable[int], channel_ids: Iterable[str]) -> OperationResult:
        """Copy the first selected row's values down across the remaining rows."""
        if self.state.df is None:
            return OperationResult.failure("No dataset.")
        rows = self._valid_rows(row_indices)
        ids = self._valid_channel_ids(channel_ids)
        if len(rows) < 2 or not ids:
            return OperationResult.failure("Select a seed row and the rows to fill.")
        seed_row, target_rows = rows[0], rows[1:]
        undo = self._capture_undo("fill down")
        filled = self._fill_columns(ids, [seed_row], target_rows)
        self._state_controller.mark_dirty()
        self._push_undo(undo)
        return OperationResult.success(
            f"Filled {len(target_rows)} row(s) x {len(ids)} column(s).", payload={"filled": filled}
        )

    def fill_drag(
        self,
        seed_rows: Iterable[int],
        target_rows: Iterable[int],
        channel_ids: Iterable[str],
    ) -> OperationResult:
        """Extend the seed-row pattern (constant/linear/repeat) into target rows."""
        if self.state.df is None:
            return OperationResult.failure("No dataset.")
        seeds = self._valid_rows(seed_rows)
        seed_set = set(seeds)
        targets = [row for row in self._valid_rows(target_rows) if row not in seed_set]
        ids = self._valid_channel_ids(channel_ids)
        if not seeds or not targets or not ids:
            return OperationResult.failure("Nothing to fill.")
        undo = self._capture_undo("fill")
        filled = self._fill_columns(ids, seeds, targets)
        self._state_controller.mark_dirty()
        self._push_undo(undo)
        return OperationResult.success(
            f"Filled {len(targets)} row(s) x {len(ids)} column(s).", payload={"filled": filled}
        )

    def _fill_columns(self, channel_ids: list[str], seed_rows: list[int], target_rows: list[int]) -> int:
        filled = 0
        registry = self.state.channel_registry
        for channel_id in channel_ids:
            spec = registry.spec_for_id(channel_id)
            if spec is None or self.state.df is None:
                continue
            seed_values = [self.state.df.at[row, spec.display_name] for row in seed_rows]
            pattern = fill_series_service.infer_fill_pattern(seed_values)
            values = fill_series_service.generate_fill(pattern, len(target_rows))
            for row, value in zip(target_rows, values):
                result = dataset_service.set_cell_value(self.state.df, registry, channel_id, row, value)
                if result.ok:
                    self._state_controller.apply_dataframe_payload(payload_dict(result))
                    filled += 1
        return filled

    # ------------------------------------------------------------------
    # Rename / delete propagation
    # ------------------------------------------------------------------
    def _propagate_rename(self, old: str, new: str) -> None:
        update = column_reference_service.propagate_column_rename(
            current_x_axis=self.state.current_x_axis,
            plot_profiles=self.state.plot_profiles,
            calculated_channels=self.state.calculated_channels,
            limit_lines=self.state.limit_lines,
            old_name=old,
            new_name=new,
        )
        self._state_controller.set_current_x_axis(update.current_x_axis)

    def _propagate_delete(self, name: str) -> list[str]:
        update = column_reference_service.propagate_column_delete(
            current_x_axis=self.state.current_x_axis,
            plot_profiles=self.state.plot_profiles,
            calculated_channels=self.state.calculated_channels,
            name=name,
        )
        self._state_controller.set_current_x_axis(update.current_x_axis)
        return update.warnings
