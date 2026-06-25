"""Save/load limit-line templates as JSON.

Framework-independent: serialises and reloads requirement limit lines through the
:class:`LimitLine` domain model so a saved template round-trips names, types,
applies-to scope, colours, and points. No Qt; the panel chooses the file path.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domain.limits import LimitLine


def save_limit_template(path: str | Path, lines: list[dict[str, Any]]) -> None:
    """Write ``lines`` (limit-line dicts) to a JSON template at ``path``."""
    normalised = [LimitLine.from_dict(line).to_dict() for line in lines]
    payload = {"limit_lines": normalised}
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_limit_template(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSON limit template into a list of normalised limit-line dicts."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("limit_lines", []) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []
    return [LimitLine.from_dict(line).to_dict() for line in raw]
