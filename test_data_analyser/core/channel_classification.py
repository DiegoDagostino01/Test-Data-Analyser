"""Engineering channel classification helpers."""
from __future__ import annotations

import re

from .config import COLUMN_GROUP_ORDER, DOMAIN_CONFIG


def classify_channel_name(name: object) -> str:
    """Classify a channel name into a deterministic engineering reading group.

    The classification is name-based only, so unknown columns fall back to
    ``"Other Numeric"``. UI layers with dtype information can still label truly
    non-numeric columns separately, but the common engineering terms live here.
    """
    text = str(name or "").strip()
    if not text:
        return "Other Numeric"
    if _is_temperature_channel_name(text):
        return "Temperature"
    for group in COLUMN_GROUP_ORDER:
        if group in {"Temperature", "Other Numeric", "Non-numeric / Metadata"}:
            continue
        keywords = DOMAIN_CONFIG.get(group, [])
        if any(keyword_matches(text, keyword) for keyword in keywords):
            return group
    return "Other Numeric"


def channel_group_options() -> list[str]:
    """Return channel filter options in the configured engineering order."""
    return ["All", *COLUMN_GROUP_ORDER]


def keyword_matches(text: str, keyword: str) -> bool:
    lowered = text.lower()
    token = str(keyword).lower().strip()
    if not token:
        return False
    if len(token) <= 2:
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", lowered) is not None
    return token in lowered


def _is_temperature_channel_name(name: str) -> bool:
    lowered = name.lower()
    if any(token in lowered for token in ("temp", "temperature", "deg c", "degc", "°c")):
        return True
    return re.search(r"(?<![a-z0-9])tc[\s_\-]*\d+(?![a-z0-9])", lowered) is not None