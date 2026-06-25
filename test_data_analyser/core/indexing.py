"""Index helpers shared by stateful coordinators."""
from __future__ import annotations


def clamp_index(index: int, length: int) -> int:
    """Clamp ``index`` into the valid range ``[0, length - 1]``.

    Returns ``0`` for an empty collection (``length <= 0``), matching the
    long-standing ``max(0, min(index, length - 1))`` idiom used across the
    viewmodels for active-profile / active-limit selection.
    """
    return max(0, min(index, length - 1))