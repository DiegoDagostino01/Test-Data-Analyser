"""Safe Maths (calculated) channel evaluation extracted from
``calculated_channels.py``.

This module owns the restricted-AST formula parser, the allowed function set,
and calculated-channel definition normalisation. It is framework-independent and
returns values/structured errors rather than showing message boxes.
"""
from __future__ import annotations

import ast
import keyword
import operator
import re
from typing import Any, Callable

import numpy as np
import pandas as pd

from ..core.data_io import numeric_series
from ..domain import CalculatedChannelDefinition

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


class MathsChannelEvaluator:
    """Evaluate Maths Channel formulas against a single dataframe.

    Construct with the dataframe the formulas should evaluate against, then call
    :meth:`evaluate`. The evaluator raises ``ValueError`` with a user-facing
    message on any invalid formula; callers translate that into UI feedback.
    """

    def __init__(self, df: pd.DataFrame | None):
        self.df = df

    # ------------------------------------------------------------------
    # Column / value coercion
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

    # ------------------------------------------------------------------
    # Safe functions
    # ------------------------------------------------------------------
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

    def safe_functions(self) -> dict[str, Callable[..., Any]]:
        return {
            "abs": abs,
            "sqrt": np.sqrt,
            "log": np.log,
            "rolling_mean": self._rolling_mean,
            "rolling_std": self._rolling_std,
            "where": self._where,
            "clip": self._clip,
        }

    # ------------------------------------------------------------------
    # Formula preparation / evaluation
    # ------------------------------------------------------------------
    def prepare_formula(
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

    def evaluate(
        self,
        formula: str,
        blocked_names: set[str] | None = None,
    ) -> tuple[pd.Series, list[str]]:
        """Evaluate ``formula`` and return ``(result_series, referenced_columns)``."""
        tree, names, referenced_columns = self.prepare_formula(formula, blocked_names)
        evaluator = _FormulaEvaluator(names, self.safe_functions())
        result = evaluator.visit(tree)
        return self._coerce_result_series(result), referenced_columns


def normalise_calculated_channel_definitions(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalise raw calculated-channel definitions into the canonical dict form.

    Invalid entries (missing name/formula) are dropped. Backed by the domain
    :class:`CalculatedChannelDefinition` model.
    """
    if not isinstance(raw, dict):
        return {}
    normalised: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        definition = CalculatedChannelDefinition.from_dict(value, fallback_name=str(key))
        if definition.is_valid:
            normalised[definition.name] = definition.to_dict()
    return normalised
