"""Versioned JSON-safe serialization for Qt workspace state."""
from __future__ import annotations

import base64
from dataclasses import dataclass

from PySide6.QtCore import QByteArray

from .workspace_presets import WorkspacePreset, parse_workspace_preset


WORKSPACE_LAYOUT_VERSION = 1
WORKSPACE_BACKEND = "ads"
MAX_STATE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class RestoredWorkspaceState:
    dock_state: QByteArray
    main_geometry: QByteArray
    active_preset: WorkspacePreset
    custom_layout: QByteArray | None


class WorkspaceSerializer:
    """Encode and validate ADS state without leaking Qt types into settings."""

    def serialize(
        self,
        *,
        dock_state: QByteArray,
        main_geometry: QByteArray,
        active_preset: WorkspacePreset,
        custom_layout: QByteArray | None = None,
    ) -> dict[str, object]:
        return {
            "workspace_layout_version": WORKSPACE_LAYOUT_VERSION,
            "backend": WORKSPACE_BACKEND,
            "active_preset": active_preset.value,
            "dock_state_b64": self._encode(dock_state),
            "main_geometry_b64": self._encode(main_geometry),
            "custom_layout_b64": self._encode(custom_layout) if custom_layout else "",
        }

    def restore(self, payload: object) -> RestoredWorkspaceState | None:
        if not isinstance(payload, dict):
            return None
        if payload.get("workspace_layout_version") != WORKSPACE_LAYOUT_VERSION:
            return None
        if payload.get("backend") != WORKSPACE_BACKEND:
            return None
        try:
            dock_state = self._decode(payload.get("dock_state_b64"))
            main_geometry = self._decode(payload.get("main_geometry_b64"))
            custom_text = payload.get("custom_layout_b64")
            custom_layout = self._decode(custom_text) if custom_text else None
        except ValueError:
            return None
        if dock_state.isEmpty():
            return None
        return RestoredWorkspaceState(
            dock_state=dock_state,
            main_geometry=main_geometry,
            active_preset=parse_workspace_preset(payload.get("active_preset")),
            custom_layout=custom_layout,
        )

    @staticmethod
    def _encode(value: QByteArray) -> str:
        raw = value.data()
        if len(raw) > MAX_STATE_BYTES:
            raise ValueError("Workspace state exceeds the supported size limit.")
        return base64.b64encode(raw).decode("ascii")

    @staticmethod
    def _decode(value: object) -> QByteArray:
        if not isinstance(value, str):
            raise ValueError("Workspace state must be base64 text.")
        if len(value) > (MAX_STATE_BYTES * 4 // 3) + 8:
            raise ValueError("Workspace state exceeds the supported size limit.")
        try:
            raw = base64.b64decode(value.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError("Workspace state is not valid base64.") from exc
        if len(raw) > MAX_STATE_BYTES:
            raise ValueError("Workspace state exceeds the supported size limit.")
        return QByteArray(raw)
