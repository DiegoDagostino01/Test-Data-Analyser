"""Qt-only workspace management package."""

from .ads_backend import AdsDockBackend
from .workspace_manager import WorkspaceManager
from .workspace_presets import WorkspacePreset
from .workspace_registry import DockArea, PanelDescriptor, SideBarLocation, WorkspaceRegistry
from .workspace_serializer import WorkspaceSerializer

__all__ = [
	"AdsDockBackend",
	"DockArea",
	"PanelDescriptor",
	"SideBarLocation",
	"WorkspaceManager",
	"WorkspacePreset",
	"WorkspaceRegistry",
	"WorkspaceSerializer",
]
