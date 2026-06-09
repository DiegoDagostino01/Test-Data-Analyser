from __future__ import annotations

from .gui_base import TestDataAnalyserGUIBase
from .label_profiles import LabelProfileMixin
from .profile_state import ProfileStateMixin
from .engineering_notes import EngineeringNotesMixin
from .raw_data_editor import RawDataEditorMixin
from .raw_data import RawDataMixin
from .analysis import AnalysisMixin
from .limits import LimitsMixin
from .cursor_tools import CursorToolsMixin
from .plotting import PlottingMixin
from .calculated_channels import CalculatedChannelsMixin
from .multi_run import MultiRunMixin
from .data_loading import DataLoadingMixin


class TestDataAnalyserGUI(
    LabelProfileMixin,
    ProfileStateMixin,
    EngineeringNotesMixin,
    RawDataEditorMixin,
    RawDataMixin,
    AnalysisMixin,
    LimitsMixin,
    CursorToolsMixin,
    PlottingMixin,
    CalculatedChannelsMixin,
    MultiRunMixin,
    DataLoadingMixin,
    TestDataAnalyserGUIBase,
):
    """Main GUI class composed from focused behaviour modules.

    Extracted mixins are the source of truth for their respective
    responsibilities and are listed before ``TestDataAnalyserGUIBase`` in the
    method-resolution order.

    `gui_base.py` (``TestDataAnalyserGUIBase``) is still required and is NOT a
    candidate for further extraction. It owns the shared foundation the mixins
    build on:
      - window/app lifecycle and Eaton styling (`__init__`, `_apply_eaton_style`);
      - the app chrome and master widget tree (`_build_modern_*`, `_build_ui`,
        `_build_left_controls`, `_build_right_panel`);
      - shared infrastructure helpers used across mixins via `self`
        (`_get_numeric`, `_set_text_widget`, `_clear_treeview`) and the
        axis-limit helper cluster (`parse_limit`, `manual_limits`,
        `apply_auto_axis_limits`, etc.);
      - the analysis-window helpers (`copy_axis_limits_to_analysis_window`,
        `clear_analysis_window`).
    """

    def __init__(self, root):
        super().__init__(root)
        self._initialise_label_tracking()
