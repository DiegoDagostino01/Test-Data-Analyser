"""Structured result object returned by service operations.

Services are framework-independent and must not show message boxes or open
dialogs. Instead they return an :class:`OperationResult` (or raise a domain
exception) so the calling viewmodel/UI layer can decide how to present success,
warnings, and errors.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OperationResult:
    ok: bool
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    payload: object | None = None

    @classmethod
    def success(cls, message: str = "", *, payload: object | None = None, warnings: list[str] | None = None) -> "OperationResult":
        return cls(ok=True, message=message, payload=payload, warnings=list(warnings or []))

    @classmethod
    def failure(cls, message: str = "", *, errors: list[str] | None = None, payload: object | None = None) -> "OperationResult":
        return cls(ok=False, message=message, errors=list(errors or ([message] if message else [])), payload=payload)
