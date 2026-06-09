"""Requirement / limit-line domain models.

Framework-independent dataclasses describing requirement limit lines and their
points. These are reused by the limits service and by any UI that renders limit
overlays.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .conversions import _float, _mapping, _string


@dataclass
class LimitPoint:
    x: float = 0.0
    y: float = 0.0

    @classmethod
    def from_dict(cls, value: object) -> "LimitPoint":
        data = _mapping(value)
        return cls(x=_float(data.get("x")), y=_float(data.get("y")))

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class LimitLine:
    name: str = "Limit 1"
    type: str = "Upper Limit"
    applies_to: str = "All selected Y channels"
    color: str = "#005A8C"
    points: list[LimitPoint] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: object) -> "LimitLine":
        data = _mapping(value)
        points = data.get("points", [])
        return cls(
            name=_string(data.get("name", "Limit 1"), "Limit 1"),
            type=_string(data.get("type", "Upper Limit"), "Upper Limit"),
            applies_to=_string(data.get("applies_to", "All selected Y channels"), "All selected Y channels"),
            color=_string(data.get("color", "#005A8C"), "#005A8C"),
            points=[LimitPoint.from_dict(point) for point in points] if isinstance(points, list) else [],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.type,
            "applies_to": self.applies_to,
            "color": self.color,
            "points": [point.to_dict() for point in self.points],
        }
