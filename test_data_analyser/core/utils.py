"""Compatibility facade for legacy core helper imports.

New code should import focused helpers from ``core.naming``, ``core.indexing``,
``core.column_matching``, or ``core.channel_classification``. These re-exports
keep older imports and saved user customisations working during the refactor.
"""
from __future__ import annotations

from .channel_classification import (
    channel_group_options,
    classify_channel_name,
    keyword_matches as _keyword_matches,
)
from .column_matching import (
    infer_column_by_keywords,
    matching_x_column_for_y as _matching_x_column_for_y,
    split_grouped_column_name as _split_grouped_column_name,
)
from .indexing import clamp_index
from .naming import natural_sort_key, safe_name


