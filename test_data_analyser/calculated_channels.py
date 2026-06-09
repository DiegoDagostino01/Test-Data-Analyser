from __future__ import annotations

import ast
import keyword
import operator
import re
import tkinter as tk
from typing import Any, Callable
from tkinter import messagebox, ttk

import numpy as np
import pandas as pd

from .config import EATON_CARD_BG, EATON_DARK_TEXT, EATON_SECONDARY_TEXT
from .data_io import numeric_series


_BACKTICK_COLUMN_RE = re.compile(r"`([^`]+)`")
_SAFE_FUNCTION_NAMES = {"abs", "sqrt", "log", "rolling_mean", "rolling_std", "where", "clip"}


class _FormulaEvaluator(ast.NodeVisitor):
    """Evaluate a restricted expression AST against prepared dataframe columns."""

    _BIN_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.BitAnd: operator.and_,
        ast.BitOr: operator.or_,
    }
    _UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
        ast.Not: operator.not_,
    }
    _COMPARE_OPS: dict[type[ast.cmpop], Callable[[Any, Any], Any]] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }

    def __init__(self, names: dict[str, Any], functions: dict[str, Callable[..., Any]]):
        self._names = names
        self._functions = functions

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise ValueError("Only numeric constants and referenced dataframe columns are allowed in Maths Channel formulas.")

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in self._names:
            return self._names[node.id]
        raise ValueError(f"Unknown column or value '{node.id}'. Use backticks around column names with spaces.")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op = self._BIN_OPS.get(type(node.op))
        if op is None:
            raise ValueError("Only +, -, *, /, **, &, and | operators are allowed.")
        return op(self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        if isinstance(node.op, ast.Not):
            value = self.visit(node.operand)
            if isinstance(value, (pd.Series, np.ndarray)):
                return operator.invert(value)
            return operator.not_(value)
        op = self._UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError("Only unary +, unary -, and not are allowed.")
        return op(self.visit(node.operand))

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if not node.values:
            raise ValueError("Boolean expressions must include values.")
        result = self.visit(node.values[0])
        for value_node in node.values[1:]:
            value = self.visit(value_node)
            if isinstance(node.op, ast.And):
                result = operator.and_(result, value)
            elif isinstance(node.op, ast.Or):
                result = operator.or_(result, value)
            else:
                raise ValueError("Only and/or boolean operators are allowed.")
        return result

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        result = None
        for op_node, comparator in zip(node.ops, node.comparators):
            op = self._COMPARE_OPS.get(type(op_node))
            if op is None:
                raise ValueError("Only standard numeric comparisons are allowed.")
            right = self.visit(comparator)
            comparison = op(left, right)
            result = comparison if result is None else operator.and_(result, comparison)
            left = right
        return result

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named safe functions are allowed.")
        if node.keywords:
            raise ValueError("Function keyword arguments are not supported.")
        func = self._functions.get(node.func.id)
        if func is None:
            allowed = ", ".join(sorted(self._functions))
            raise ValueError(f"Function '{node.func.id}' is not allowed. Allowed functions: {allowed}.")
        return func(*(self.visit(arg) for arg in node.args))

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"Formula element '{type(node).__name__}' is not allowed.")


class CalculatedChannelsMixin:
    """Maths/Calculated Channel creation, safe formula evaluation, and tab UI."""

    def __init__(self, *args, **kwargs):
        self.calculated_channels: dict[str, dict[str, Any]] = {}
        self._selected_calculated_channel_name: str | None = None
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # State and session helpers
    # ------------------------------------------------------------------
    def _ensure_calculated_channels_state(self) -> None:
        if not isinstance(getattr(self, "calculated_channels", None), dict):
            self.calculated_channels = {}
        if not hasattr(self, "_selected_calculated_channel_name"):
            self._selected_calculated_channel_name = None

    def _normalise_calculated_channel_definitions(self, raw: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(raw, dict):
            return {}
        normalised: dict[str, dict[str, Any]] = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            name = str(value.get("name") or key).strip()
            formula = str(value.get("formula") or "").strip()
            if not name or not formula:
                continue
            created_from = value.get("created_from_columns", [])
            if not isinstance(created_from, list):
                created_from = []
            normalised[name] = {
                "name": name,
                "formula": formula,
                "description": str(value.get("description") or ""),
                "enabled": bool(value.get("enabled", True)),
                "created_from_columns": [str(column) for column in created_from],
            }
        return normalised

    def _serialisable_calculated_channels(self) -> dict[str, dict[str, Any]]:
        self._ensure_calculated_channels_state()
        return self._normalise_calculated_channel_definitions(self.calculated_channels)

    def _restore_calculated_channels_from_session(self, raw: Any) -> None:
        self.calculated_channels = self._normalise_calculated_channel_definitions(raw)
        self._selected_calculated_channel_name = None
        self._refresh_calculated_channels_ui()

    # ------------------------------------------------------------------
    # Safe formula evaluation
    # ------------------------------------------------------------------
    def _dataframe_columns_by_name(self) -> dict[str, str]:
        if self.df is None:
            return {}
        return {str(column): str(column) for column in self.df.columns}

    def _column_as_formula_series(self, column: str) -> pd.Series:
        if self.df is None or column not in self.df.columns:
            raise ValueError(f"Column '{column}' is not available in the loaded dataframe.")
        return numeric_series(self.df[column])

    def _coerce_formula_series(self, value: Any) -> pd.Series:
        if self.df is None:
            raise ValueError("Please load a data file first.")
        if isinstance(value, pd.Series):
            return value.reindex(self.df.index) if not value.index.equals(self.df.index) else value
        if isinstance(value, np.ndarray):
            if len(value) != len(self.df):
                raise ValueError("Formula result arrays must match the dataframe row count.")
            return pd.Series(value, index=self.df.index)
        if np.isscalar(value):
            return pd.Series(value, index=self.df.index)
        raise ValueError("Formula result must be a numeric value or a series matching the dataframe length.")

    def _coerce_result_series(self, value: Any) -> pd.Series:
        series = self._coerce_formula_series(value)
        if self.df is not None and len(series) != len(self.df):
            raise ValueError("Formula result must have the same number of rows as the loaded dataframe.")
        return numeric_series(series)

    def _coerce_window(self, value: Any) -> int:
        if isinstance(value, pd.Series):
            raise ValueError("Rolling window must be a numeric constant.")
        try:
            window = int(float(value))
        except Exception as exc:
            raise ValueError("Rolling window must be a positive whole number.") from exc
        if window < 1:
            raise ValueError("Rolling window must be at least 1.")
        return window

    def _rolling_mean(self, value: Any, window: Any) -> pd.Series:
        series = self._coerce_result_series(value)
        return series.rolling(window=self._coerce_window(window), min_periods=1).mean()

    def _rolling_std(self, value: Any, window: Any) -> pd.Series:
        series = self._coerce_result_series(value)
        return series.rolling(window=self._coerce_window(window), min_periods=1).std()

    def _where(self, condition: Any, value_if_true: Any, value_if_false: Any) -> pd.Series:
        condition_series = self._coerce_formula_series(condition).fillna(False).astype(bool)
        true_value = self._coerce_formula_series(value_if_true) if not np.isscalar(value_if_true) else value_if_true
        false_value = self._coerce_formula_series(value_if_false) if not np.isscalar(value_if_false) else value_if_false
        return pd.Series(np.where(condition_series, true_value, false_value), index=condition_series.index)

    def _clip(self, value: Any, lower: Any, upper: Any) -> pd.Series:
        series = self._coerce_result_series(value)
        return series.clip(lower=lower, upper=upper)

    def _safe_formula_functions(self) -> dict[str, Callable[..., Any]]:
        return {
            "abs": abs,
            "sqrt": np.sqrt,
            "log": np.log,
            "rolling_mean": self._rolling_mean,
            "rolling_std": self._rolling_std,
            "where": self._where,
            "clip": self._clip,
        }

    def _prepare_calculated_formula(
        self,
        formula: str,
        blocked_names: set[str] | None = None,
    ) -> tuple[ast.Expression, dict[str, Any], list[str]]:
        if self.df is None:
            raise ValueError("Please load a data file first.")
        formula = formula.strip()
        if not formula:
            raise ValueError("Please enter a formula.")

        blocked_names = blocked_names or set()
        columns = self._dataframe_columns_by_name()
        identifier_columns = {
            column
            for column in columns
            if column.isidentifier()
            and not keyword.iskeyword(column)
            and column not in _SAFE_FUNCTION_NAMES
        }
        reserved_names = set(identifier_columns) | _SAFE_FUNCTION_NAMES
        names: dict[str, Any] = {}
        alias_to_column: dict[str, str] = {}
        alias_index = 0

        def next_alias() -> str:
            nonlocal alias_index
            while True:
                alias = f"__calc_col_{alias_index}"
                alias_index += 1
                if alias not in reserved_names and alias not in names:
                    return alias

        def add_column_reference(column: str, alias: str | None = None) -> str:
            if column in blocked_names:
                raise ValueError(f"Formula for '{column}' cannot reference itself.")
            if column not in columns:
                raise ValueError(f"Column '{column}' was not found. Check the spelling or use the column dropdown.")
            safe_name = alias or next_alias()
            names[safe_name] = self._column_as_formula_series(column)
            alias_to_column[safe_name] = column
            return safe_name

        def replace_backtick(match: re.Match[str]) -> str:
            return add_column_reference(match.group(1).strip())

        transformed = _BACKTICK_COLUMN_RE.sub(replace_backtick, formula)

        try:
            tree = ast.parse(transformed, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Formula syntax is invalid: {exc.msg}.") from exc

        class QuotedColumnTransformer(ast.NodeTransformer):
            def visit_Constant(self, node: ast.Constant) -> ast.AST:
                if isinstance(node.value, str):
                    column = node.value.strip()
                    if column in columns:
                        return ast.copy_location(
                            ast.Name(id=add_column_reference(column), ctx=ast.Load()),
                            node,
                        )
                    raise ValueError(
                        f"Quoted text '{node.value}' is not a loaded column. "
                        "Use backticks around column names and do not quote numeric constants."
                    )
                return node

        tree = QuotedColumnTransformer().visit(tree)
        ast.fix_missing_locations(tree)

        used_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id not in used_names:
                used_names.append(node.id)
        for name in used_names:
            if name in alias_to_column or name in _SAFE_FUNCTION_NAMES:
                continue
            if name in identifier_columns:
                add_column_reference(name, alias=name)
        referenced_columns = []
        for name in used_names:
            column = alias_to_column.get(name)
            if column is not None and column not in referenced_columns:
                referenced_columns.append(column)
        self_references = blocked_names.intersection(referenced_columns)
        if self_references:
            blocked = ", ".join(sorted(self_references))
            raise ValueError(f"Formula cannot reference the channel being calculated: {blocked}.")
        return tree, names, referenced_columns

    def _evaluate_calculated_channel_formula_with_metadata(
        self,
        formula: str,
        blocked_names: set[str] | None = None,
    ) -> tuple[pd.Series, list[str]]:
        tree, names, referenced_columns = self._prepare_calculated_formula(formula, blocked_names)
        evaluator = _FormulaEvaluator(names, self._safe_formula_functions())
        result = evaluator.visit(tree)
        return self._coerce_result_series(result), referenced_columns

    def evaluate_calculated_channel_formula(self, formula: str) -> pd.Series:
        series, _referenced_columns = self._evaluate_calculated_channel_formula_with_metadata(formula)
        return series

    # ------------------------------------------------------------------
    # CRUD / recalculation
    # ------------------------------------------------------------------
    def apply_calculated_channel(self, name: str, formula: str, description: str = "") -> None:
        self._ensure_calculated_channels_state()
        try:
            if self.df is None:
                raise ValueError("Please load a data file before creating a Maths Channel.")
            channel_name = str(name).strip()
            if not channel_name:
                raise ValueError("Please enter a channel name.")
            formula = str(formula).strip()
            if not formula:
                raise ValueError("Please enter a formula.")
            existing_selected = self._selected_calculated_channel_name
            if (
                channel_name in self.df.columns
                and channel_name not in self.calculated_channels
                and channel_name != existing_selected
            ):
                raise ValueError(f"'{channel_name}' already exists as a source data column. Choose a different name.")

            series, referenced_columns = self._evaluate_calculated_channel_formula_with_metadata(
                formula,
                blocked_names={channel_name},
            )
        except Exception as exc:
            messagebox.showerror("Maths Channels", f"Could not apply the calculated channel:\n\n{exc}")
            return

        if existing_selected and existing_selected != channel_name:
            self.calculated_channels.pop(existing_selected, None)
            if self.df is not None and existing_selected in self.df.columns:
                del self.df[existing_selected]

        self.df[channel_name] = series
        self.calculated_channels[channel_name] = {
            "name": channel_name,
            "formula": formula,
            "description": str(description).strip(),
            "enabled": True,
            "created_from_columns": referenced_columns,
        }
        self._selected_calculated_channel_name = channel_name
        self._refresh_after_calculated_channel_change(select_channel=channel_name)
        self._load_calculated_channel_into_form(channel_name)
        if hasattr(self, "status_var"):
            self.status_var.set(f"Maths Channel '{channel_name}' saved.")

    def recalculate_calculated_channels(
        self,
        show_success: bool = True,
        show_errors: bool = True,
        refresh: bool = True,
    ) -> list[str]:
        self._ensure_calculated_channels_state()
        if self.df is None:
            if show_errors:
                messagebox.showwarning("Maths Channels", "Load a data file before recalculating Maths Channels.")
            return ["No dataframe is loaded."]
        if not self.calculated_channels:
            if show_success:
                messagebox.showinfo("Maths Channels", "No Maths Channels have been defined.")
            return []

        errors: list[str] = []
        changed = False
        for channel_name, definition in list(self.calculated_channels.items()):
            if not bool(definition.get("enabled", True)):
                # Disabled definitions stay in the session/table, but their dataframe
                # column is removed so disabled channels cannot be plotted accidentally.
                if channel_name in self.df.columns:
                    del self.df[channel_name]
                    changed = True
                continue
            formula = str(definition.get("formula") or "").strip()
            if not formula:
                errors.append(f"{channel_name}: missing formula")
                if channel_name in self.df.columns:
                    del self.df[channel_name]
                    changed = True
                continue
            try:
                series, referenced_columns = self._evaluate_calculated_channel_formula_with_metadata(
                    formula,
                    blocked_names={channel_name},
                )
            except Exception as exc:
                errors.append(f"{channel_name}: {exc}")
                if channel_name in self.df.columns:
                    del self.df[channel_name]
                    changed = True
                continue
            self.df[channel_name] = series
            definition["name"] = channel_name
            definition["created_from_columns"] = referenced_columns
            changed = True

        if changed and refresh:
            self._refresh_after_calculated_channel_change()
        else:
            self._clear_calculated_channel_caches()
            self._refresh_calculated_channels_ui()

        if errors and show_errors:
            messagebox.showwarning(
                "Maths Channels",
                "Some Maths Channels could not be recalculated:\n\n" + "\n".join(errors),
            )
        elif show_success:
            messagebox.showinfo("Maths Channels", "All enabled Maths Channels were recalculated.")
        return errors

    def delete_calculated_channel(self) -> None:
        self._ensure_calculated_channels_state()
        channel_name = self._selected_calculated_channel_name or self.calculated_name_var.get().strip()
        if not channel_name or channel_name not in self.calculated_channels:
            messagebox.showwarning("Maths Channels", "Select a Maths Channel to delete.")
            return
        confirm = self._setting("general_ui", "confirm_before_delete", True) if hasattr(self, "_setting") else True
        if confirm and not messagebox.askyesno("Maths Channels", f"Delete Maths Channel '{channel_name}'?"):
            return
        self.calculated_channels.pop(channel_name, None)
        if self.df is not None and channel_name in self.df.columns:
            del self.df[channel_name]
        self._selected_calculated_channel_name = None
        self._clear_calculated_channel_form()
        self._refresh_after_calculated_channel_change()
        if hasattr(self, "status_var"):
            self.status_var.set(f"Maths Channel '{channel_name}' deleted.")

    # ------------------------------------------------------------------
    # Dataframe/UI refresh integration
    # ------------------------------------------------------------------
    def populate_columns(self) -> None:
        super().populate_columns()
        self._refresh_calculated_channels_ui()

    def _clear_calculated_channel_caches(self, columns: object = None) -> None:
        """Invalidate cached numeric/classification data for changed columns.

        Only the calculated-channel columns (or an explicit ``columns`` set) are
        invalidated so the cached conversions for unchanged source columns are
        preserved. Clearing every cache here forced a full reconversion of the
        whole dataset on each channel change, which froze the GUI on large files.
        """
        affected = set(columns) if columns is not None else set(self.calculated_channels)
        self._invalidate_column_caches(affected)

    def _refresh_after_calculated_channel_change(
        self,
        select_channel: str | None = None,
        affected_columns: object = None,
    ) -> None:
        affected = set(affected_columns or set()) | set(self.calculated_channels)
        self._clear_calculated_channel_caches(affected)
        if self.df is not None:
            for name in self.calculated_channels:
                if name in self.df.columns:
                    self._numeric_cache[name] = numeric_series(self.df[name])
            self.refresh_columns_incrementally(
                select_columns=[select_channel] if select_channel else None
            )

        self._refresh_calculated_channels_ui(select_name=select_channel or self._selected_calculated_channel_name)
        self.update_range_preview()
        self.update_stats()
        self.mark_raw_data_stale()
        self._refresh_limit_applies_options()
        self._capture_current_plot_profile()

    # ------------------------------------------------------------------
    # Tab UI
    # ------------------------------------------------------------------
    def _build_calculated_channels_tab(self, parent: ttk.Frame) -> None:
        self._ensure_calculated_channels_state()
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        ttk.Button(toolbar, text="New / Clear Form", command=self._clear_calculated_channel_form).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Validate Formula", command=self._validate_calculated_channel_formula).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Apply / Save Channel", command=self._apply_calculated_channel_from_form).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Delete Channel", command=self.delete_calculated_channel).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Recalculate All", command=self.recalculate_calculated_channels).pack(side="left", padx=(0, 6))

        body = ttk.PanedWindow(parent, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        form = ttk.Frame(body)
        table_panel = ttk.Frame(body)
        body.add(form, weight=2)
        body.add(table_panel, weight=3)

        details = ttk.LabelFrame(form, text="Maths Channel Definition", style="Card.TLabelframe")
        details.pack(fill="both", expand=True, padx=4, pady=4)
        details.columnconfigure(1, weight=1)

        self.calculated_name_var = tk.StringVar()
        self.calculated_description_var = tk.StringVar()
        self.calculated_column_var = tk.StringVar()

        ttk.Label(details, text="Channel name:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(details, textvariable=self.calculated_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=3)

        ttk.Label(details, text="Existing column:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        column_row = ttk.Frame(details)
        column_row.grid(row=1, column=1, sticky="ew", padx=6, pady=3)
        column_row.columnconfigure(0, weight=1)
        self.calculated_column_combo = ttk.Combobox(column_row, textvariable=self.calculated_column_var, state="readonly")
        self.calculated_column_combo.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            column_row,
            text="Insert Selected Column into Formula",
            command=self._insert_selected_column_into_formula,
        ).grid(row=0, column=1, sticky="e")

        ttk.Label(details, text="Formula:").grid(row=2, column=0, sticky="nw", padx=6, pady=3)
        formula_frame = ttk.Frame(details)
        formula_frame.grid(row=2, column=1, sticky="nsew", padx=6, pady=3)
        formula_frame.rowconfigure(0, weight=1)
        formula_frame.columnconfigure(0, weight=1)
        self.calculated_formula_text = tk.Text(
            formula_frame,
            height=5,
            wrap="word",
            bg=EATON_CARD_BG,
            fg=EATON_DARK_TEXT,
            relief="solid",
            bd=1,
        )
        formula_scroll = ttk.Scrollbar(formula_frame, orient="vertical", command=self.calculated_formula_text.yview)
        self.calculated_formula_text.configure(yscrollcommand=formula_scroll.set)
        self.calculated_formula_text.grid(row=0, column=0, sticky="nsew")
        formula_scroll.grid(row=0, column=1, sticky="ns")

        ttk.Label(details, text="Description:").grid(row=3, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(details, textvariable=self.calculated_description_var).grid(row=3, column=1, sticky="ew", padx=6, pady=3)

        examples = (
            "Examples:\n"
            "`Outlet Pressure` - `Inlet Pressure`\n"
            "`Voltage` * `Current`\n"
            "rolling_mean(`Current`, 25)\n"
            "sqrt(abs(`Signal A`))\n"
            "clip(`Pressure`, 0, 500)\n"
            "Tip: use backticks, or single/double quotes around exact column names."
        )
        ttk.Label(details, text=examples, foreground=EATON_SECONDARY_TEXT, justify="left").grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=6,
            pady=(6, 3),
        )

        table_frame = ttk.LabelFrame(table_panel, text="Calculated Channels", style="Card.TLabelframe")
        table_frame.pack(fill="both", expand=True, padx=4, pady=4)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        columns = ("name", "formula", "enabled", "description")
        self.calculated_channels_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=8,
            style="Bordered.Treeview",
        )
        self.calculated_channels_tree.heading("name", text="Name")
        self.calculated_channels_tree.heading("formula", text="Formula")
        self.calculated_channels_tree.heading("enabled", text="Enabled")
        self.calculated_channels_tree.heading("description", text="Description")
        self.calculated_channels_tree.column("name", width=180, stretch=True)
        self.calculated_channels_tree.column("formula", width=260, stretch=True)
        self.calculated_channels_tree.column("enabled", width=70, anchor="center", stretch=False)
        self.calculated_channels_tree.column("description", width=220, stretch=True)
        self._configure_treeview_tags(self.calculated_channels_tree)
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.calculated_channels_tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.calculated_channels_tree.xview)
        self.calculated_channels_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.calculated_channels_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.calculated_channels_tree.bind("<<TreeviewSelect>>", self._on_calculated_channel_selected)
        self._refresh_calculated_channels_ui()

    def _get_calculated_formula_text(self) -> str:
        if not hasattr(self, "calculated_formula_text"):
            return ""
        return self.calculated_formula_text.get("1.0", "end").strip()

    def _set_calculated_formula_text(self, formula: str) -> None:
        if not hasattr(self, "calculated_formula_text"):
            return
        self.calculated_formula_text.delete("1.0", "end")
        self.calculated_formula_text.insert("1.0", formula)

    def _clear_calculated_channel_form(self) -> None:
        self._selected_calculated_channel_name = None
        if hasattr(self, "calculated_name_var"):
            self.calculated_name_var.set("")
        if hasattr(self, "calculated_description_var"):
            self.calculated_description_var.set("")
        self._set_calculated_formula_text("")
        if hasattr(self, "calculated_channels_tree"):
            self.calculated_channels_tree.selection_remove(self.calculated_channels_tree.selection())

    def _insert_selected_column_into_formula(self) -> None:
        column = self.calculated_column_var.get().strip() if hasattr(self, "calculated_column_var") else ""
        if not column:
            messagebox.showwarning("Maths Channels", "Select an existing column to insert.")
            return
        if "`" in column:
            messagebox.showerror("Maths Channels", "Columns containing backticks cannot be inserted into formulas.")
            return
        self.calculated_formula_text.insert("insert", f"`{column}`")
        self.calculated_formula_text.focus_set()

    def _validate_calculated_channel_formula(self) -> None:
        try:
            result = self.evaluate_calculated_channel_formula(self._get_calculated_formula_text())
            valid = result.dropna()
            if valid.empty:
                summary = "Formula is valid, but it produced no numeric values."
            else:
                summary = (
                    f"Formula is valid.\n\n"
                    f"Rows: {len(result):,}\n"
                    f"Numeric values: {len(valid):,}\n"
                    f"Min / Max: {valid.min():.6g} / {valid.max():.6g}"
                )
            messagebox.showinfo("Maths Channels", summary)
        except Exception as exc:
            messagebox.showerror("Maths Channels", f"Formula validation failed:\n\n{exc}")

    def _apply_calculated_channel_from_form(self) -> None:
        self.apply_calculated_channel(
            self.calculated_name_var.get(),
            self._get_calculated_formula_text(),
            self.calculated_description_var.get(),
        )

    def _select_calculated_channel_tree_item(self, channel_name: str) -> None:
        if not hasattr(self, "calculated_channels_tree"):
            return
        if channel_name not in self.calculated_channels_tree.get_children():
            return
        current_selection = tuple(str(item) for item in self.calculated_channels_tree.selection())
        if current_selection != (channel_name,):
            self.calculated_channels_tree.selection_set(channel_name)
        if str(self.calculated_channels_tree.focus() or "") != channel_name:
            self.calculated_channels_tree.focus(channel_name)

    def _load_calculated_channel_into_form(self, channel_name: str, update_tree_selection: bool = True) -> None:
        definition = self.calculated_channels.get(channel_name)
        if definition is None:
            return
        self._selected_calculated_channel_name = channel_name
        if hasattr(self, "calculated_name_var"):
            self.calculated_name_var.set(definition.get("name", channel_name))
        if hasattr(self, "calculated_description_var"):
            self.calculated_description_var.set(definition.get("description", ""))
        self._set_calculated_formula_text(definition.get("formula", ""))
        if update_tree_selection:
            self._select_calculated_channel_tree_item(channel_name)

    def _on_calculated_channel_selected(self, _event=None) -> None:
        if not hasattr(self, "calculated_channels_tree"):
            return
        selection = self.calculated_channels_tree.selection()
        if not selection:
            return
        channel_name = str(selection[0])
        self._load_calculated_channel_into_form(channel_name, update_tree_selection=False)

    def _refresh_calculated_channels_ui(self, select_name: str | None = None) -> None:
        self._ensure_calculated_channels_state()
        if hasattr(self, "calculated_column_combo"):
            values = [str(column) for column in self.df.columns] if self.df is not None else []
            self.calculated_column_combo.configure(values=values)
            if self.calculated_column_var.get() not in values:
                self.calculated_column_var.set(values[0] if values else "")

        if not hasattr(self, "calculated_channels_tree"):
            return
        children = self.calculated_channels_tree.get_children()
        if children:
            self.calculated_channels_tree.delete(*children)
        for index, (channel_name, definition) in enumerate(self.calculated_channels.items()):
            self.calculated_channels_tree.insert(
                "",
                "end",
                iid=channel_name,
                values=(
                    definition.get("name", channel_name),
                    definition.get("formula", ""),
                    "Yes" if definition.get("enabled", True) else "No",
                    definition.get("description", ""),
                ),
                tags=(self._tree_row_tag(index),),
            )
        if select_name and select_name in self.calculated_channels:
            self._select_calculated_channel_tree_item(select_name)
