from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple
import logging
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
try:
    matplotlib.use("TkAgg")
except ImportError:
    matplotlib.use("Agg", force=True)

import matplotlib.figure as mfig
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends._backend_tk import NavigationToolbar2Tk
import pandas as pd

from .config import *
from .config import __version__
from .data_io import *
from .filters import *
from .models import PlotData
from .settings_manager import SettingsManager
from .settings_window import SettingsWindow
from .utils import (_block_mousewheel,)
from .widgets import (ScrollableFrame, _bind_mousewheel_to_canvas, _bind_mousewheel_to_treeview)

logging.getLogger("matplotlib").setLevel(logging.WARNING)

STATISTICS_COLUMNS = ["Count", "Min", "Max", "Mean", "Median", "Std Dev", "RMS", "Peak-to-Peak"]


class TestDataAnalyserGUIBase:
    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Test Data Analyser v{__version__} | Engineering Plot Tool")
        self.root.geometry("1460x860")
        self.root.minsize(1180, 720)
        self.settings_manager = SettingsManager()
        self._settings_window: Optional[SettingsWindow] = None

        self.filepath: Optional[Path] = None
        self.df: Optional[pd.DataFrame] = None
        self.figure: Optional[mfig.Figure] = None
        self.axes: Optional[Axes] = None
        self.secondary_axes: Optional[Axes] = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.toolbar: Optional[NavigationToolbar2Tk] = None
        self.toolbar_frame: Optional[ttk.Frame] = None
        self.cursor_compare_enabled = tk.BooleanVar(value=False)
        self.cursor_compare_btn: Optional[tk.Button] = None
        self.current_lines: list = []
        self.external_legend_required: bool = False
        self.y_vars: dict[str, tk.BooleanVar] = {}
        self.secondary_y_vars: dict[str, tk.BooleanVar] = {}
        self._visible_y_columns: list[str] = []
        self._cursor_cid: Optional[int] = None
        self._cursor_click_cid: Optional[int] = None
        self._cursor_key_cid: Optional[int] = None
        self._cursor_points: list[dict[str, Any]] = []
        self._cursor_click_artists: list[Any] = []
        self.engineering_note_widgets: dict[str, tk.Text] = {}
        self.engineering_notes_report_text: Optional[tk.Text] = None
        self.limit_lines: list[dict[str, Any]] = []
        self.active_limit_line_index: int = 0
        self.limit_name_var = tk.StringVar(value="Limit 1")
        self.limit_type_var = tk.StringVar(value="Upper Limit")
        self.limit_applies_var = tk.StringVar(value="All selected Y channels")
        self.limit_color_var = tk.StringVar(value=EATON_DARK_BLUE)
        self.limit_color_preset_var = tk.StringVar(value="Eaton Dark Blue")
        self.limit_color_preview: Optional[tk.Label] = None
        self.limit_x_var = tk.StringVar()
        self.limit_y_var = tk.StringVar()
        self.raw_data_row_limit_var = tk.StringVar(value="All")
        self.raw_data_apply_window_var = tk.BooleanVar(value=True)
        self.raw_data_drop_blank_rows_var = tk.BooleanVar(value=True)
        self.plot_profiles: list[dict[str, Any]] = []
        self.active_plot_profile_index: int = 0
        self._profile_switch_in_progress: bool = False
        self.status_var = tk.StringVar(value="Ready")
        self.bottom_tabs: Optional[ttk.Notebook] = None
        self._nav_buttons: dict[str, tk.Button] = {}

        self._numeric_cache: dict[str, pd.Series] = {}
        self._column_lower_cache: dict[str, str] = {}
        self._column_group_cache: dict[str, str] = {}
        self._likely_numeric_cache: dict[str, bool] = {}
        self._sorted_columns_cache: list[str] = []
        self._debounce_id: Optional[str] = None
        self._y_rebuild_after_id: Optional[str] = None
        self.eaton_logo_image: Optional[tk.PhotoImage] = None
        self.ribbon_frame: Optional[tk.Frame] = None
        self.ribbon_collapsed = tk.BooleanVar(value=False)
        self.ribbon_toggle_btn: Optional[tk.Button] = None

        self._apply_eaton_style()
        self._build_ui()
        self._apply_runtime_theme()
        self._initialise_plot_profiles()
        self.settings_manager.add_callback(self._on_settings_changed)
        self._apply_clickable_cursors(self.root)

    # ------------------------------------------------------------------
    # Settings integration
    # ------------------------------------------------------------------
    def _setting(self, section: str, key: str, default: Any = None) -> Any:
        try:
            return self.settings_manager.get(section, key)
        except Exception:
            return default

    def _is_dark_theme(self) -> bool:
        return str(self._setting("general_ui", "theme", "light")).lower() == "dark"

    def _theme_palette(self) -> dict[str, str]:
        return theme_palette(str(self._setting("general_ui", "theme", "light")))

    def _apply_runtime_theme(self) -> None:
        palette = self._theme_palette()
        self.root.configure(bg=palette["bg"])
        style = ttk.Style(self.root)
        style.configure(".", background=palette["card"], foreground=palette["text"])
        style.configure("TFrame", background=palette["card"])
        style.configure("TLabel", background=palette["card"], foreground=palette["text"])
        style.configure("TLabelframe", background=palette["card"], foreground=palette["text"], bordercolor=palette["border"])
        style.configure("TLabelframe.Label", background=palette["card"], foreground=palette["text"])
        style.configure("TCheckbutton", background=palette["card"], foreground=palette["text"])
        style.map("TCheckbutton", background=[("active", palette["hover"])])
        style.configure("TEntry", fieldbackground=palette["entry"], foreground=palette["text"], bordercolor=palette["border"])
        style.configure("TSpinbox", fieldbackground=palette["entry"], foreground=palette["text"], bordercolor=palette["border"])
        style.configure("TCombobox", fieldbackground=palette["entry"], foreground=palette["text"], selectbackground=palette["selected"], selectforeground=palette["text"])
        style.configure("TButton", background=palette["card"], foreground=palette["button_fg"], bordercolor=palette["border"])
        style.configure("Secondary.TButton", background=palette["card"], foreground=palette["button_fg"], bordercolor=palette["border"])
        style.map("TButton", background=[("active", palette["hover"]), ("pressed", palette["selected"])])
        style.map("Secondary.TButton", background=[("active", palette["hover"]), ("pressed", palette["selected"])])
        style.configure("Treeview", background=palette["card"], foreground=palette["text"], fieldbackground=palette["card"])
        style.configure("Treeview.Heading", background=palette["hover"], foreground=palette["text"])
        style.configure("Bordered.Treeview", background=palette["card"], foreground=palette["text"], fieldbackground=palette["card"], bordercolor=palette["border"])
        style.configure("Bordered.Treeview.Heading", background=palette["hover"], foreground=palette["text"], bordercolor=palette["border"])
        style.configure("Shell.TFrame", background=palette["bg"])
        style.configure("Workspace.TFrame", background=palette["bg"])
        style.configure("Ribbon.TFrame", background=palette["card"])
        style.configure("Card.TFrame", background=palette["card"], bordercolor=palette["border"])
        style.configure("Card.TLabelframe", background=palette["card"], foreground=palette["text"], bordercolor=palette["border"])
        style.configure("Card.TLabelframe.Label", background=palette["card"], foreground=palette["text"])
        style.configure("Subtle.TLabel", background=palette["bg"], foreground=palette["secondary"])
        style.configure("Card.Subtle.TLabel", background=palette["card"], foreground=palette["secondary"])
        style.configure("TNotebook.Tab", background=palette["bg"], foreground=palette["secondary"])
        style.map(
            "TNotebook.Tab",
            background=[("selected", palette["card"]), ("active", palette["hover"])],
            foreground=[("selected", EATON_BLUE), ("active", palette["button_fg"])],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", palette["entry"]), ("disabled", palette["card"])],
            foreground=[("readonly", palette["text"]), ("disabled", palette["secondary"])],
            selectbackground=[("readonly", palette["entry"])],
            selectforeground=[("readonly", palette["text"])],
        )
        for scrollbar_style in ("TScrollbar", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
            style.configure(
                scrollbar_style,
                background=palette["card"],
                troughcolor=palette["bg"],
                bordercolor=palette["border"],
                arrowcolor=palette["secondary"],
            )
            style.map(scrollbar_style, background=[("active", palette["hover"])])
        for option_name, option_value in (
            ("*TCombobox*Listbox.background", palette["card"]),
            ("*TCombobox*Listbox.foreground", palette["text"]),
            ("*TCombobox*Listbox.selectBackground", palette["selected"]),
            ("*TCombobox*Listbox.selectForeground", palette["text"]),
        ):
            self.root.option_add(option_name, option_value)
        self._apply_theme_to_widget_tree(self.root, palette)

    def _apply_theme_to_widget_tree(self, widget: tk.Widget, palette: dict[str, str]) -> None:
        if isinstance(widget, tk.Toplevel) and widget is not self.root:
            return
        mutable_backgrounds = {
            EATON_BG,
            EATON_CARD_BG,
            EATON_RIBBON_BG,
            EATON_WHITE,
            "#F8FAFC",
            LIGHT_THEME["bg"],
            LIGHT_THEME["card"],
            LIGHT_THEME["tree_alt"],
            LIGHT_THEME["entry"],
            DARK_THEME["bg"],
            DARK_THEME["card"],
            DARK_THEME["tree_alt"],
            DARK_THEME["entry"],
        }
        mutable_foregrounds = {
            EATON_DARK_TEXT,
            EATON_SECONDARY_TEXT,
            EATON_DARK_GREY,
            EATON_MID_GREY,
            LIGHT_THEME["text"],
            LIGHT_THEME["secondary"],
            DARK_THEME["text"],
            DARK_THEME["secondary"],
        }
        preserve_backgrounds = {
            EATON_HEADER_BLUE,
            EATON_NAV_BLUE,
            EATON_BLUE,
            EATON_DARK_BLUE,
            "#005EB8",
            "#003865",
            "#C4262E",
            "#FEE2E2",
        }
        try:
            current_bg = str(widget.cget("bg"))
            if current_bg in mutable_backgrounds and current_bg not in preserve_backgrounds:
                target_bg = palette["bg"] if widget is self.root else palette["card"]
                widget.configure(bg=target_bg)
        except tk.TclError:
            pass
        try:
            current_fg = str(widget.cget("fg"))
            if current_fg in mutable_foregrounds:
                widget.configure(fg=palette["text"])
        except tk.TclError:
            pass
        try:
            widget_class = widget.winfo_class()
        except tk.TclError:
            widget_class = ""
        if widget_class == "Canvas":
            try:
                widget.configure(bg=palette["card"])
            except tk.TclError:
                pass
        elif widget_class in ("Text", "Entry", "Listbox"):
            for option_name, option_value in (
                ("insertbackground", palette["text"]),
                ("selectbackground", palette["selected"]),
                ("selectforeground", palette["text"]),
            ):
                try:
                    widget.configure(**{option_name: option_value})
                except tk.TclError:
                    pass
        if isinstance(widget, ttk.Treeview):
            self._configure_treeview_tags(widget)
        for child in widget.winfo_children():
            self._apply_theme_to_widget_tree(child, palette)

    def open_settings_window(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus_force()
            return
        window = SettingsWindow(self.root, self.settings_manager)
        self._settings_window = window

        def _clear_reference(event: tk.Event) -> None:
            if event.widget is window:
                self._settings_window = None

        window.bind("<Destroy>", _clear_reference, add="+")

    def _on_settings_changed(self, _settings: dict[str, dict[str, Any]]) -> None:
        self._apply_runtime_theme()
        if hasattr(self, "grid_var"):
            self.grid_var.set(bool(self._setting("plot_appearance", "grid_visible", True)))
        if hasattr(self, "legend_threshold_var"):
            self.legend_threshold_var.set(int(self._setting("general_ui", "legend_threshold", 1)))
        if hasattr(self, "auto_fit_var"):
            self.auto_fit_var.set(self._setting("axis_scaling", "auto_scale_mode", "padded") != "manual")
            self.toggle_axis_entries()
        self._configure_stats_tree_columns()
        if hasattr(self, "update_stats"):
            self.update_stats()
        if self.figure is not None and self.df is not None:
            self.generate_plot()

    def _configured_statistics_columns(self) -> list[str]:
        selected = self._setting(
            "engineering_analysis",
            "default_statistics_columns",
            STATISTICS_COLUMNS,
        )
        if not isinstance(selected, list):
            selected = STATISTICS_COLUMNS
        columns = [column for column in STATISTICS_COLUMNS if column in selected]
        return columns or STATISTICS_COLUMNS

    def _configure_stats_tree_columns(self) -> None:
        if not hasattr(self, "stats_tree"):
            return
        columns = ["Signal"] + self._configured_statistics_columns()
        self.stats_tree["columns"] = columns
        for col in columns:
            self.stats_tree.heading(col, text=col)
            self.stats_tree.column(col, width=110 if col != "Signal" else 220, anchor="center")

    # ------------------------------------------------------------------
    # Eaton brand styling
    # ------------------------------------------------------------------
    def _apply_eaton_style(self) -> None:
        self.root.configure(bg=EATON_BG)
        style = ttk.Style(self.root)
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        # Base typography
        style.configure(".", background=EATON_CARD_BG,
                         foreground=EATON_DARK_TEXT,
                         font=("Segoe UI", 9))

        # Frames / Labels
        style.configure("TFrame", background=EATON_CARD_BG)
        style.configure("TLabel", background=EATON_CARD_BG,
                         foreground=EATON_DARK_TEXT,
                         font=("Segoe UI", 9))
        style.configure("TLabelframe", background=EATON_CARD_BG,
                         foreground=EATON_DARK_TEXT, borderwidth=1,
                         relief="solid")
        style.configure("TLabelframe.Label", background=EATON_CARD_BG,
                         foreground=EATON_DARK_TEXT,
                         font=("Segoe UI", 11, "bold"))

        # Buttons: secondary by default, primary only for Generate Plot.
        secondary_button = {
            "background": EATON_CARD_BG,
            "foreground": EATON_BLUE,
            "font": ("Segoe UI", 9, "bold"),
            "padding": (10, 5),
            "borderwidth": 1,
            "relief": "solid",
        }
        style.configure("TButton", **secondary_button)
        style.configure("Secondary.TButton", **secondary_button)
        style.map("TButton",
                  background=[("active", EATON_HOVER),
                              ("pressed", EATON_SELECTED)],
                  foreground=[("active", EATON_DARK_BLUE),
                              ("pressed", EATON_DARK_BLUE)])
        style.map("Secondary.TButton",
                  background=[("active", EATON_HOVER),
                              ("pressed", EATON_SELECTED)],
                  foreground=[("active", EATON_DARK_BLUE),
                              ("pressed", EATON_DARK_BLUE)])
        style.configure("Accent.TButton", background=EATON_BLUE,
                        foreground=EATON_WHITE,
                        font=("Segoe UI", 10, "bold"), padding=(14, 7),
                        borderwidth=1, relief="solid")
        style.configure("Primary.TButton", background=EATON_BLUE,
                        foreground=EATON_WHITE,
                        font=("Segoe UI", 10, "bold"), padding=(14, 7),
                        borderwidth=1, relief="solid")
        for primary_style in ("Accent.TButton", "Primary.TButton"):
            style.map(primary_style,
                      background=[("active", EATON_DARK_BLUE),
                                  ("pressed", EATON_DARK_BLUE)],
                      foreground=[("active", EATON_WHITE),
                                  ("pressed", EATON_WHITE)])
        style.configure("Danger.TButton", background=EATON_CARD_BG,
                        foreground="#C4262E",
                        font=("Segoe UI", 9, "bold"), padding=(10, 5),
                        borderwidth=1, relief="solid")
        style.map("Danger.TButton",
                  background=[("active", "#FEE2E2"),
                              ("pressed", "#FECACA")],
                  foreground=[("active", "#991B1B"),
                              ("pressed", "#991B1B")])

        # Checkbutton
        style.configure("TCheckbutton", background=EATON_CARD_BG,
                         foreground=EATON_DARK_TEXT,
                         font=("Segoe UI", 9))
        style.map("TCheckbutton", background=[("active", EATON_HOVER)])

        # Combobox / Entry / Spinbox
        style.configure("TCombobox", fieldbackground=EATON_WHITE,
                         foreground=EATON_DARK_TEXT,
                         selectbackground=EATON_SELECTED,
                         selectforeground=EATON_DARK_TEXT)
        style.configure("TEntry", fieldbackground=EATON_WHITE,
                        foreground=EATON_DARK_TEXT)
        style.configure("TSpinbox", fieldbackground=EATON_WHITE,
                        foreground=EATON_DARK_TEXT)

        # Treeview
        style.configure("Treeview", background=EATON_CARD_BG,
                         foreground=EATON_DARK_TEXT,
                         fieldbackground=EATON_CARD_BG, rowheight=28)
        style.configure("Treeview.Heading", background=EATON_HOVER,
                         foreground=EATON_DARK_TEXT,
                         font=("Segoe UI", 9, "bold"), padding=(6, 4))
        style.map("Treeview",
                  background=[("selected", EATON_SELECTED)],
                  foreground=[("selected", EATON_DARK_TEXT)])
        style.map("Treeview.Heading",
                  background=[("active", EATON_SELECTED)],
                  foreground=[("active", EATON_DARK_TEXT)])

        # Scrollbar / PanedWindow
        style.configure("TScrollbar", troughcolor=EATON_BG)
        style.configure("TPanedwindow", background=EATON_BG)

        # Modern Eaton shell styling
        style.configure("Shell.TFrame", background=EATON_BG)
        style.configure("Ribbon.TFrame", background=EATON_RIBBON_BG)
        style.configure("Workspace.TFrame", background=EATON_BG)
        style.configure("Card.TFrame", background=EATON_CARD_BG,
                        relief="solid", borderwidth=1)
        style.configure("Modern.TNotebook", background=EATON_BG,
                        borderwidth=0, tabmargins=(0, 4, 0, 0))
        style.configure("Hidden.TNotebook", background=EATON_BG, borderwidth=0, tabmargins=0)
        try:
            style.layout("Hidden.TNotebook.Tab", [])
        except Exception:
            pass
        style.configure("Bordered.Treeview", background=EATON_CARD_BG, foreground=EATON_DARK_TEXT,
                        fieldbackground=EATON_CARD_BG, rowheight=28, borderwidth=1,
                        relief="solid")
        style.configure("Bordered.Treeview.Heading", background=EATON_HOVER, foreground=EATON_DARK_TEXT,
                        font=("Segoe UI", 9, "bold"), borderwidth=1, relief="solid",
                        padding=(6, 4))
        style.map("Bordered.Treeview.Heading",
                  background=[("active", EATON_SELECTED)],
                  foreground=[("active", EATON_DARK_TEXT)])
        style.configure("TNotebook.Tab", background=EATON_BG,
                        foreground=EATON_SECONDARY_TEXT,
                        padding=(16, 6),
                        font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", EATON_CARD_BG),
                              ("active", EATON_HOVER)],
                  foreground=[("selected", EATON_BLUE),
                              ("active", EATON_DARK_BLUE)])
        style.configure("Card.TLabelframe", background=EATON_CARD_BG,
                        foreground=EATON_DARK_TEXT, borderwidth=1,
                        relief="solid")
        style.configure("Card.TLabelframe.Label", background=EATON_CARD_BG,
                        foreground=EATON_DARK_TEXT,
                        font=("Segoe UI", 11, "bold"))
        style.configure("Subtle.TLabel", background=EATON_BG,
                        foreground=EATON_SECONDARY_TEXT,
                        font=("Segoe UI", 8))
        style.configure("Card.Subtle.TLabel", background=EATON_CARD_BG,
                        foreground=EATON_SECONDARY_TEXT,
                        font=("Segoe UI", 8))

        for styled_widget in (
            "TButton", "Secondary.TButton", "Accent.TButton",
            "Primary.TButton", "Danger.TButton", "Card.TFrame",
            "Card.TLabelframe", "Bordered.Treeview",
        ):
            try:
                style.configure(
                    styled_widget,
                    bordercolor=EATON_BORDER,
                    lightcolor=EATON_BORDER,
                    darkcolor=EATON_BORDER,
                )
            except tk.TclError:
                pass

    def _tree_row_tag(self, index: int) -> str:
        return "odd" if index % 2 else "even"

    def _configure_treeview_tags(self, tree: ttk.Treeview) -> None:
        palette = self._theme_palette()
        tree.tag_configure("even", background=palette["card"], foreground=palette["text"])
        tree.tag_configure("odd", background=palette["tree_alt"], foreground=palette["text"])

    def _ttk_button_style_for_text(self, text: str) -> str:
        label = text.strip()
        if label == "Generate Plot":
            return "Accent.TButton"
        if label in {"Clear Analysis Window", "Clear Cursor Points"}:
            return "Danger.TButton"
        if label.startswith(("Delete", "Remove")):
            return "Danger.TButton"
        return "Secondary.TButton"

    def _apply_clickable_cursors(self, parent: tk.Widget) -> None:
        for child in parent.winfo_children():
            widget_class = child.winfo_class()
            if widget_class in {"Button", "TButton"}:
                try:
                    child.configure(cursor="hand2")
                except tk.TclError:
                    pass
            if widget_class == "TButton":
                try:
                    child.configure(
                        style=self._ttk_button_style_for_text(str(child.cget("text")))
                    )
                except tk.TclError:
                    pass
            self._apply_clickable_cursors(child)

    # ------------------------------------------------------------------
    # Cached numeric conversion
    # ------------------------------------------------------------------
    def _get_numeric(self, col: str) -> pd.Series:
        if col not in self._numeric_cache:
            if self.df is not None and col in self.df.columns:
                self._numeric_cache[col] = numeric_series(self.df[col])
        return self._numeric_cache.get(col, pd.Series(dtype=float))

    # ------------------------------------------------------------------
    # UI construction — left panel
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Modern Eaton shell UI
    # ------------------------------------------------------------------
    def _build_modern_header(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=EATON_HEADER_BLUE, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(2, weight=1)

        logo_holder = tk.Frame(header, bg=EATON_HEADER_BLUE)
        logo_holder.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=7, sticky="w")
        try:
            self.eaton_logo_image = tk.PhotoImage(data=EATON_LOGO_PNG_BASE64, format="png")
            tk.Label(logo_holder, image=self.eaton_logo_image, bg=EATON_WHITE, bd=0, relief="flat").pack(side="left")
            try:
                self.root.iconphoto(True, self.eaton_logo_image)
            except Exception:
                pass
        except Exception:
            tk.Label(logo_holder, text="EATON", bg=EATON_HEADER_BLUE, fg=EATON_WHITE,
                     font=("Segoe UI", 20, "bold")).pack(side="left")

        tk.Label(header, text="Test Data Analyser", bg=EATON_HEADER_BLUE, fg=EATON_WHITE,
                 font=("Segoe UI", 14, "bold")).grid(row=0, column=1, sticky="sw", pady=(9, 0))
        tk.Label(header, text="Engineering analysis workspace", bg=EATON_HEADER_BLUE, fg="#DDEEFF",
                 font=("Segoe UI", 8)).grid(row=1, column=1, sticky="nw", pady=(0, 9))

        right_tools = tk.Frame(header, bg=EATON_HEADER_BLUE)
        right_tools.grid(row=0, column=3, rowspan=2, sticky="e", padx=14)
        self.ribbon_toggle_btn = tk.Button(right_tools, text="▴ Collapse Ribbon", command=self.toggle_ribbon,
                                           bg=EATON_HEADER_BLUE, fg=EATON_WHITE, activebackground=EATON_DARK_BLUE,
                                           activeforeground=EATON_WHITE, bd=0, padx=10, font=("Segoe UI", 9),
                                           cursor="hand2")
        self.ribbon_toggle_btn.pack(side="left")
        tk.Label(right_tools, text="? Help", bg=EATON_HEADER_BLUE, fg=EATON_WHITE,
                 font=("Segoe UI", 9), padx=10).pack(side="left")
        tk.Button(right_tools, text="⚙ Settings", command=self.open_settings_window,
                  bg=EATON_HEADER_BLUE, fg=EATON_WHITE,
                  activebackground=EATON_DARK_BLUE,
                  activeforeground=EATON_WHITE, bd=0, padx=10,
                  font=("Segoe UI", 9), cursor="hand2").pack(side="left")


    def _ribbon_button(self, parent: tk.Widget, text: str, command=None) -> tk.Button:
        if text == "Generate Plot":
            bg = EATON_BLUE
            fg = EATON_WHITE
            active_bg = EATON_DARK_BLUE
            active_fg = EATON_WHITE
            border = EATON_BLUE
            padx = 14
            pady = 8
        elif text == "Clear":
            bg = EATON_CARD_BG
            fg = "#C4262E"
            active_bg = "#FEE2E2"
            active_fg = "#991B1B"
            border = "#C4262E"
            padx = 11
            pady = 7
        else:
            bg = EATON_CARD_BG
            fg = EATON_BLUE
            active_bg = EATON_HOVER
            active_fg = EATON_DARK_BLUE
            border = EATON_BORDER
            padx = 11
            pady = 7
        btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                        activebackground=active_bg, activeforeground=active_fg,
                        relief="flat", bd=0, highlightbackground=border,
                        highlightcolor=border, highlightthickness=1,
                        padx=padx, pady=pady, font=("Segoe UI", 9, "bold"),
                        cursor="hand2")
        btn.pack(side="left", padx=2, pady=2)
        return btn


    def _build_modern_ribbon(self, parent: tk.Widget) -> None:
        """Top ribbon is the single navigation surface for analysis panels."""
        ribbon = tk.Frame(parent, bg=EATON_RIBBON_BG, height=100,
                          highlightbackground=EATON_BORDER, highlightthickness=0)
        self.ribbon_frame = ribbon
        ribbon.grid(row=1, column=0, sticky="ew")
        ribbon.grid_propagate(False)
        tk.Frame(ribbon, bg=EATON_BORDER, height=1).place(
            relx=0, rely=1, relwidth=1, anchor="sw"
        )

        groups = [
            ("FILE", [("Save Session", self.save_analysis_session),
                      ("Load Session", self.load_analysis_session), ("Export Data", self.export_selected_data)]),
            ("PLOT", [("Generate Plot", self.generate_plot), ("FFT", self.generate_fft_plot),
                      ("Save Plot", self.save_current_plot), ("Clear", self.clear_plot)]),
            ("ANALYSIS", [("Statistics", lambda: self._select_bottom_tab_by_text("Statistics")),
                           ("Raw Data", lambda: self._select_bottom_tab_by_text("Raw Data")),
                           ("Runs", lambda: self._select_bottom_tab_by_text("Runs / Comparison")),
                           ("Maths", lambda: self._select_bottom_tab_by_text("Maths Channels")),
                           ("Cursor", lambda: self._select_bottom_tab_by_text("Cursor Readout"))]),
            ("REQUIREMENTS", [("Limits", lambda: self._select_bottom_tab_by_text("Requirements / Limits")),
                              ("Margins", lambda: self._select_bottom_tab_by_text("Limit Margins")),
                              ("Refresh", self.refresh_limit_summary)]),
            ("NOTES", [("Engineering Notes", lambda: self._select_bottom_tab_by_text("Engineering Notes")),
                       ("Copy Notes", self._copy_engineering_notes_to_clipboard)]),
        ]
        for col, (group_title, buttons) in enumerate(groups):
            ribbon.grid_columnconfigure(col, weight=0)
            group = tk.Frame(ribbon, bg=EATON_RIBBON_BG, highlightbackground=EATON_BORDER,
                             highlightthickness=1, bd=0)
            group.grid(row=0, column=col, sticky="nsw", padx=(8 if col == 0 else 4, 4), pady=10)
            button_row = tk.Frame(group, bg=EATON_RIBBON_BG)
            button_row.pack(side="top", fill="x", padx=6, pady=(5, 2))
            for text, command in buttons:
                self._ribbon_button(button_row, text, command)
            tk.Label(group, text=group_title, bg=EATON_RIBBON_BG, fg=EATON_SECONDARY_TEXT,
                     font=("Segoe UI", 7, "bold")).pack(side="bottom", fill="x", pady=(0, 3))

    def toggle_ribbon(self) -> None:
        """Collapse/expand the ribbon in an Excel-style manner."""
        collapsed = not self.ribbon_collapsed.get()
        self.ribbon_collapsed.set(collapsed)
        if self.ribbon_frame is not None:
            if collapsed:
                self.ribbon_frame.grid_remove()
            else:
                self.ribbon_frame.grid()
        if self.ribbon_toggle_btn is not None:
            self.ribbon_toggle_btn.configure(text="▾ Show Ribbon" if collapsed else "▴ Collapse Ribbon")
        if hasattr(self, "status_var"):
            self.status_var.set("Ribbon collapsed" if collapsed else "Ribbon expanded")


    def _nav_button(self, parent: tk.Widget, key: str, text: str, command) -> tk.Button:
        btn = tk.Button(parent, text=text, command=lambda: self._handle_nav_click(key, command), bg=EATON_NAV_BLUE, fg=EATON_WHITE, activebackground=EATON_BLUE, activeforeground=EATON_WHITE, relief="flat", bd=0, padx=8, pady=12, font=("Segoe UI", 9, "bold"), cursor="hand2", anchor="w")
        btn.pack(fill="x", padx=0, pady=1)
        self._nav_buttons[key] = btn
        return btn

    def _build_modern_sidebar(self, parent: tk.Widget) -> None:
        nav = tk.Frame(parent, bg=EATON_NAV_BLUE, width=96)
        nav.grid(row=0, column=0, sticky="ns")
        nav.grid_propagate(False)
        tk.Label(nav, text="", bg=EATON_NAV_BLUE, height=1).pack(fill="x")
        self._nav_button(nav, "Home", "⌂  Home", lambda: self._select_bottom_tab_by_text("Statistics"))
        self._nav_button(nav, "Data", "▣  Data", lambda: self._select_bottom_tab_by_text("Raw Data"))
        self._nav_button(nav, "Runs", "⇄  Runs", lambda: self._select_bottom_tab_by_text("Runs / Comparison"))
        self._nav_button(nav, "Maths", "fx  Maths", lambda: self._select_bottom_tab_by_text("Maths Channels"))
        self._nav_button(nav, "Analysis", "⌁  Analysis", self.generate_plot)
        self._nav_button(nav, "Requirements", "◇  Limits", lambda: self._select_bottom_tab_by_text("Requirements / Limits"))
        self._nav_button(nav, "Margins", "✓  Margins", lambda: self._select_bottom_tab_by_text("Limit Margins"))
        self._nav_button(nav, "Notes", "✎  Notes", lambda: self._select_bottom_tab_by_text("Engineering Notes"))
        self._nav_button(nav, "Export", "⇪  Export", self.export_selected_data)
        tk.Frame(nav, bg=EATON_NAV_BLUE).pack(fill="both", expand=True)
        self._nav_button(nav, "Settings", "⚙  Settings", self.open_settings_window)
        self._set_active_nav("Home")

    def _build_modern_statusbar(self, parent: tk.Widget) -> None:
        status = tk.Frame(parent, bg=EATON_HEADER_BLUE, height=26)
        status.grid(row=3, column=0, sticky="ew")
        status.grid_propagate(False)
        tk.Label(status, textvariable=self.status_var, bg=EATON_HEADER_BLUE, fg=EATON_WHITE, font=("Segoe UI", 8)).pack(side="left", padx=10)
        tk.Label(status, text=f"v{__version__} | Eaton Engineering", bg=EATON_HEADER_BLUE, fg="#DDEEFF", font=("Segoe UI", 8)).pack(side="right", padx=10)

    def _handle_nav_click(self, key: str, command) -> None:
        self._set_active_nav(key)
        if callable(command):
            command()
        self.status_var.set(f"{key} workspace selected")

    def _set_active_nav(self, active_key: str) -> None:
        for key, button in self._nav_buttons.items():
            button.configure(bg=EATON_BLUE if key == active_key else EATON_NAV_BLUE)

    def _select_bottom_tab_by_text(self, tab_text: str) -> None:
        if self.bottom_tabs is None:
            return
        for tab_id in self.bottom_tabs.tabs():
            if self.bottom_tabs.tab(tab_id, "text") == tab_text:
                self.bottom_tabs.select(tab_id)
                self.status_var.set(f"{tab_text} selected")
                return

    def _build_ui(self) -> None:
        """Build the Eaton-style shell with one top ribbon navigation surface."""
        self.root.configure(bg=EATON_BG)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self._build_modern_header(self.root)
        self._build_modern_ribbon(self.root)

        body = ttk.Frame(self.root, style="Workspace.TFrame")
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        main = ttk.PanedWindow(body, orient="horizontal")
        main.grid(row=0, column=0, sticky="nsew")
        self.left_scroll = ScrollableFrame(main, width=420)
        main.add(self.left_scroll, weight=0)
        self.right = ttk.Frame(main, style="Workspace.TFrame")
        main.add(self.right, weight=1)
        self._build_left_controls(self.left_scroll.inner)
        self._build_right_panel(self.right)

        self._build_modern_statusbar(self.root)


    def _build_left_controls(self, parent: ttk.Frame) -> None:
        section_pad: dict[str, Any] = {"padx": 12, "pady": (0, 22)}
        first_section_pad: dict[str, Any] = {"padx": 12, "pady": (12, 22)}
        card_padding = (14, 12)
        label_gap = (0, 4)
        field_gap = (0, 12)
        compact_gap = (0, 10)

        # --- 1. Data File ---
        file_frame = ttk.LabelFrame(
            parent, text="1. Data File", style="Card.TLabelframe",
            padding=card_padding
        )
        file_frame.pack(fill="x", **first_section_pad)
        ttk.Button(file_frame, text="Select CSV / Excel File",
                   command=self.select_file).pack(fill="x", pady=field_gap)
        self.file_label = ttk.Label(file_frame, text="No file selected",
                                    wraplength=360, style="Card.Subtle.TLabel")
        self.file_label.pack(fill="x")

        self.sheet_frame = ttk.Frame(file_frame, style="Card.TFrame")
        ttk.Label(self.sheet_frame, text="Excel sheet:").pack(
            anchor="w", pady=label_gap
        )
        self.sheet_var = tk.StringVar()
        self.sheet_combo = ttk.Combobox(self.sheet_frame,
                                        textvariable=self.sheet_var,
                                        state="readonly")
        self.sheet_combo.pack(fill="x", pady=compact_gap)
        ttk.Button(self.sheet_frame, text="Load Sheet",
                   command=self.load_selected_sheet).pack(fill="x")

        # --- 2. Axis Selection ---
        axis_frame = ttk.LabelFrame(
            parent, text="2. Axis Selection", style="Card.TLabelframe",
            padding=card_padding
        )
        axis_frame.pack(fill="x", **section_pad)
        ttk.Label(axis_frame, text="X-axis column:").pack(
            anchor="w", pady=label_gap
        )
        self.x_col_var = tk.StringVar()
        self.x_combo = ttk.Combobox(axis_frame, textvariable=self.x_col_var,
                                     state="readonly")
        self.x_combo.pack(fill="x", pady=field_gap)
        self.x_combo.bind("<<ComboboxSelected>>",
                          lambda _e: self.on_axis_selection_changed())

        ttk.Label(axis_frame, text="Y-axis columns:").pack(
            anchor="w", pady=label_gap
        )

        channel_tools = ttk.Frame(axis_frame, style="Card.TFrame")
        channel_tools.pack(fill="x", pady=compact_gap)
        ttk.Label(channel_tools, text="Search:").grid(row=0, column=0, sticky="w")
        self.channel_search_var = tk.StringVar()
        self.channel_search_var.trace_add("write", lambda *_: self._schedule_y_checkbox_rebuild())
        ttk.Entry(channel_tools, textvariable=self.channel_search_var).grid(
            row=0, column=1, sticky="ew", padx=(8, 0))
        channel_tools.columnconfigure(1, weight=1)
        self.group_channels_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(axis_frame, text="Group channels by engineering type",
                        variable=self.group_channels_var,
                        command=self._rebuild_y_checkboxes).pack(
                            anchor="w", pady=compact_gap)
        self.y_checkbox_frame = ttk.LabelFrame(axis_frame,
                                               text="Tick variables to plot / assign to right Y-axis",
                                               style="Card.TLabelframe",
                                               padding=(8, 8))
        self.y_checkbox_frame.pack(fill="both", pady=compact_gap)

        self.y_check_canvas = tk.Canvas(self.y_checkbox_frame, borderwidth=0,
                                        height=230, highlightthickness=0,
                                        bg=EATON_CARD_BG)
        self.y_check_scrollbar = ttk.Scrollbar(
            self.y_checkbox_frame, orient="vertical",
            command=self.y_check_canvas.yview)
        self.y_check_inner = ttk.Frame(self.y_check_canvas, style="Card.TFrame")
        self.y_check_window = self.y_check_canvas.create_window(
            (0, 0), window=self.y_check_inner, anchor="nw")
        self.y_check_canvas.configure(yscrollcommand=self.y_check_scrollbar.set)
        self.y_check_inner.bind(
            "<Configure>",
            lambda _e: self.y_check_canvas.configure(
                scrollregion=self.y_check_canvas.bbox("all")))
        self.y_check_canvas.bind(
            "<Configure>",
            lambda e: self.y_check_canvas.itemconfigure(
                self.y_check_window, width=e.width))
        self.y_check_canvas.pack(side="left", fill="both", expand=True)
        self.y_check_scrollbar.pack(side="right", fill="y")
        _bind_mousewheel_to_canvas(self.y_check_canvas)

        btn_row = ttk.Frame(axis_frame, style="Card.TFrame")
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Select All",
                   command=self.select_all_y_columns).pack(
                       side="left", fill="x", expand=True)
        ttk.Button(btn_row, text="Clear",
                   command=self.clear_y_selection).pack(
                       side="left", fill="x", expand=True, padx=(8, 0))

        # --- 3. Labels ---
        label_frame = ttk.LabelFrame(
            parent, text="3. Labels", style="Card.TLabelframe",
            padding=card_padding
        )
        label_frame.pack(fill="x", **section_pad)
        self.title_var = tk.StringVar(value="Engineering Test Data")
        self.x_label_var = tk.StringVar(value="")
        self.y_label_var = tk.StringVar(value="")
        self.y2_label_var = tk.StringVar(value="")
        for label, var in [("Plot title", self.title_var),
                           ("X-axis label", self.x_label_var),
                           ("Primary Y-axis label", self.y_label_var),
                           ("Secondary Y-axis label", self.y2_label_var)]:
            ttk.Label(label_frame, text=label + ":").pack(
                anchor="w", pady=label_gap
            )
            ttk.Entry(label_frame, textvariable=var).pack(
                fill="x", pady=field_gap
            )
        ttk.Button(label_frame, text="Auto Labels",
                   command=self.auto_labels_from_selection).pack(
                       fill="x")

        # --- 4. Plot Options ---
        option_frame = ttk.LabelFrame(
            parent, text="4. Plot Options", style="Card.TLabelframe",
            padding=card_padding
        )
        option_frame.pack(fill="x", **section_pad)
        self.plot_kind_var = tk.StringVar(value="Line")
        ttk.Label(option_frame, text="Plot type:").pack(
            anchor="w", pady=label_gap
        )
        self.plot_kind_combo = ttk.Combobox(
            option_frame,
            textvariable=self.plot_kind_var,
            state="readonly",
            values=["Line", "Scatter", "Line + Markers"],
        )
        self.plot_kind_combo.pack(fill="x", pady=field_gap)
        # Prevent accidental plot-type changes while scrolling the left panel.
        # The plot type can still be changed intentionally by opening the dropdown.
        self.plot_kind_combo.bind("<MouseWheel>", _block_mousewheel)
        self.plot_kind_combo.bind("<Button-4>", _block_mousewheel)
        self.plot_kind_combo.bind("<Button-5>", _block_mousewheel)
        self.grid_var = tk.BooleanVar(value=bool(self._setting("plot_appearance", "grid_visible", True)))
        self.auto_fit_var = tk.BooleanVar(value=self._setting("axis_scaling", "auto_scale_mode", "padded") != "manual")
        self.use_filter_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(option_frame, text="Show grid",
                        variable=self.grid_var).pack(anchor="w", pady=(0, 8))
        ttk.Checkbutton(option_frame, text="Auto-fit axes",
                        variable=self.auto_fit_var,
                        command=self.toggle_axis_entries).pack(
                            anchor="w", pady=(0, 8))
        ttk.Checkbutton(option_frame, text="Apply low-pass filter",
                        variable=self.use_filter_var).pack(anchor="w", pady=compact_gap)

        filter_grid = ttk.Frame(option_frame, style="Card.TFrame")
        filter_grid.pack(fill="x", pady=compact_gap)
        self.cutoff_var = tk.StringVar(value="10")
        self.filter_order_var = tk.StringVar(value="4")
        ttk.Label(filter_grid, text="Cutoff Hz").grid(row=0, column=0,
                                                       sticky="w")
        ttk.Entry(filter_grid, textvariable=self.cutoff_var, width=10).grid(
            row=0, column=1, sticky="ew", padx=(8, 12))
        ttk.Label(filter_grid, text="Order").grid(row=0, column=2, sticky="w")
        ttk.Entry(filter_grid, textvariable=self.filter_order_var, width=8).grid(
            row=0, column=3, sticky="ew", padx=(8, 0))
        filter_grid.columnconfigure(1, weight=1)

        legend_grid = ttk.Frame(option_frame, style="Card.TFrame")
        legend_grid.pack(fill="x")
        self.legend_threshold_var = tk.IntVar(value=int(self._setting("general_ui", "legend_threshold", 1)))
        self.legend_location_var = tk.StringVar(value="best")
        self.legend_loc_var = self.legend_location_var  # backwards-compatible alias
        ttk.Label(legend_grid, text="Max in-plot legend entries").grid(
            row=0, column=0, sticky="w")
        ttk.Spinbox(legend_grid, from_=1, to=50,
                    textvariable=self.legend_threshold_var, width=6).grid(
                        row=0, column=1, padx=(8, 0))
        ttk.Label(legend_grid, text="Legend location").grid(
            row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(
            legend_grid, textvariable=self.legend_location_var, state="readonly",
            values=["best", "upper right", "upper left", "lower left",
                    "lower right", "right", "center left", "center right",
                    "lower center", "upper center", "center"],
            width=18).grid(row=1, column=1, sticky="ew", padx=(8, 0),
                           pady=(10, 0))

        # --- 5. Analysis Window ---
        window_frame = ttk.LabelFrame(
            parent, text="5. Analysis Window", style="Card.TLabelframe",
            padding=card_padding
        )
        window_frame.pack(fill="x", **section_pad)
        self.analysis_xmin_var = tk.StringVar()
        self.analysis_xmax_var = tk.StringVar()
        ttk.Label(window_frame, text="Only analyse/plot data between these X values.").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ttk.Label(window_frame, text="Start X").grid(row=1, column=0, sticky="w", pady=(0, 10))
        ttk.Entry(window_frame, textvariable=self.analysis_xmin_var).grid(
            row=1, column=1, sticky="ew", padx=(12, 0), pady=(0, 10))
        ttk.Label(window_frame, text="End X").grid(row=2, column=0, sticky="w", pady=(0, 12))
        ttk.Entry(window_frame, textvariable=self.analysis_xmax_var).grid(
            row=2, column=1, sticky="ew", padx=(12, 0), pady=(0, 12))
        ttk.Button(window_frame, text="Use Manual Axis X Limits",
                   command=self.copy_axis_limits_to_analysis_window).grid(
                       row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Button(window_frame, text="Clear Analysis Window",
                   command=self.clear_analysis_window).grid(
                       row=4, column=0, columnspan=2, sticky="ew")
        window_frame.columnconfigure(1, weight=1)

        # --- 6. Manual Axis Limits ---
        limit_frame = ttk.LabelFrame(
            parent, text="6. Manual Axis Limits", style="Card.TLabelframe",
            padding=card_padding
        )
        limit_frame.pack(fill="x", **section_pad)
        self.xmin_var = tk.StringVar()
        self.xmax_var = tk.StringVar()
        self.ymin_var = tk.StringVar()
        self.ymax_var = tk.StringVar()
        self.y2min_var = tk.StringVar()
        self.y2max_var = tk.StringVar()
        self.limit_entries: list[ttk.Entry] = []
        for row, (label, var) in enumerate([
            ("X min", self.xmin_var), ("X max", self.xmax_var),
            ("Primary Y min", self.ymin_var), ("Primary Y max", self.ymax_var),
            ("Secondary Y min", self.y2min_var), ("Secondary Y max", self.y2max_var),
        ]):
            ttk.Label(limit_frame, text=label).grid(row=row, column=0,
                                                     sticky="w", pady=(0, 10))
            entry = ttk.Entry(limit_frame, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=(0, 10))
            self.limit_entries.append(entry)
        limit_frame.columnconfigure(1, weight=1)
        ttk.Button(limit_frame, text="Fill Limits from Selected Data",
                   command=self.fill_axis_limits_from_data).grid(
                       row=6, column=0, columnspan=2, sticky="ew")


        self.range_preview_var = tk.StringVar(
            value="Load data and select columns to preview ranges.")
        ttk.Label(parent, textvariable=self.range_preview_var,
                  wraplength=380, style="Subtle.TLabel").pack(
                      fill="x", padx=18, pady=(0, 18))
        self.toggle_axis_entries()

    # ------------------------------------------------------------------
    # UI construction — right panel
    # ------------------------------------------------------------------
    def _build_right_panel(self, parent: ttk.Frame) -> None:
        vertical = ttk.PanedWindow(parent, orient="vertical")
        vertical.pack(fill="both", expand=True)

        plot_and_legend = ttk.PanedWindow(vertical, orient="horizontal")
        vertical.add(plot_and_legend, weight=6)

        plot_container = ttk.Frame(plot_and_legend, style="Card.TFrame", padding=8)
        plot_and_legend.add(plot_container, weight=4)

        profile_bar = ttk.Frame(plot_container, style="Card.TFrame")
        profile_bar.pack(fill="x", padx=4, pady=(2, 8))
        profile_bar.columnconfigure(0, weight=1)

        # Row 0: plot tabs use the full available width.
        self.plot_profile_notebook = ttk.Notebook(profile_bar)
        self.plot_profile_notebook.grid(row=0, column=0, sticky="ew")
        self.plot_profile_notebook.bind(
            "<<NotebookTabChanged>>",
            self.on_plot_profile_tab_changed
        )

        # Row 1: plot management buttons always remain visible.
        profile_button_bar = ttk.Frame(profile_bar, style="Card.TFrame")
        profile_button_bar.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        ttk.Button(
            profile_button_bar,
            text="+ New",
            command=self.add_plot_profile
        ).pack(side="left", padx=(0, 4))

        ttk.Button(
            profile_button_bar,
            text="Duplicate",
            command=self.duplicate_plot_profile
        ).pack(side="left", padx=(0, 4))

        ttk.Button(
            profile_button_bar,
            text="Rename",
            command=self.rename_plot_profile
        ).pack(side="left", padx=(0, 4))

        ttk.Button(
            profile_button_bar,
            text="Delete",
            command=self.delete_plot_profile
        ).pack(side="left", padx=(0, 4))

        self.plot_frame = ttk.Frame(plot_container, style="Card.TFrame")
        self.plot_frame.pack(fill="both", expand=True)

        self.legend_outer = ttk.LabelFrame(
            plot_and_legend, text="Legend", style="Card.TLabelframe",
            padding=(10, 8)
        )
        plot_and_legend.add(self.legend_outer, weight=1)

        self.legend_canvas = tk.Canvas(self.legend_outer, borderwidth=0, highlightthickness=0, bg=EATON_CARD_BG)
        self.legend_scrollbar = ttk.Scrollbar(self.legend_outer, orient="vertical", command=self.legend_canvas.yview)
        self.legend_inner = ttk.Frame(self.legend_canvas, style="Card.TFrame")
        self.legend_canvas_window = self.legend_canvas.create_window((0, 0), window=self.legend_inner, anchor="nw")
        self.legend_canvas.configure(yscrollcommand=self.legend_scrollbar.set)
        self.legend_inner.bind("<Configure>", lambda _e: self.legend_canvas.configure(scrollregion=self.legend_canvas.bbox("all")))
        self.legend_canvas.bind("<Configure>", lambda e: self.legend_canvas.itemconfigure(self.legend_canvas_window, width=e.width))
        self.legend_canvas.pack(side="left", fill="both", expand=True)
        self.legend_scrollbar.pack(side="right", fill="y")
        _bind_mousewheel_to_canvas(self.legend_canvas)

        bottom_container = ttk.Frame(vertical, style="Card.TFrame", padding=8)
        vertical.add(bottom_container, weight=0)
        bottom_tabs = ttk.Notebook(bottom_container, style="Hidden.TNotebook")
        self.bottom_tabs = bottom_tabs
        bottom_tabs.pack(fill="both", expand=True)
        stats_frame = ttk.Frame(bottom_tabs, style="Card.TFrame")
        bottom_tabs.add(stats_frame, text="Statistics")
        columns = ["Signal"] + self._configured_statistics_columns()
        self.stats_tree = ttk.Treeview(stats_frame, columns=columns, show="headings", height=7, style="Bordered.Treeview")
        self._configure_stats_tree_columns()
        self._configure_treeview_tags(self.stats_tree)
        stats_scroll = ttk.Scrollbar(stats_frame, orient="vertical", command=self.stats_tree.yview)
        self.stats_tree.configure(yscrollcommand=stats_scroll.set)
        self.stats_tree.pack(side="left", fill="both", expand=True)
        stats_scroll.pack(side="right", fill="y")

        raw_frame = ttk.Frame(bottom_tabs, style="Card.TFrame")
        bottom_tabs.add(raw_frame, text="Raw Data")
        raw_controls = ttk.Frame(raw_frame, style="Card.TFrame")
        raw_controls.pack(fill="x", padx=6, pady=(4, 2))
        ttk.Label(raw_controls, text="Rows to display:").pack(side="left")
        raw_limit_entry = ttk.Entry(raw_controls, textvariable=self.raw_data_row_limit_var, width=10)
        raw_limit_entry.pack(side="left", padx=(4, 8))
        raw_limit_entry.bind("<Return>", lambda _e: self.update_raw_data_view())
        ttk.Button(raw_controls, text="Refresh", command=self.update_raw_data_view).pack(side="left", padx=(0, 8))
        self.raw_undo_button = ttk.Button(raw_controls, text="Undo Edit", command=self.undo_raw_data_edit, state="disabled")
        self.raw_undo_button.pack(side="left", padx=(0, 8))
        ttk.Checkbutton(raw_controls, text="Apply Analysis Window", variable=self.raw_data_apply_window_var, command=self.update_raw_data_view).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(raw_controls, text="Hide rows with blank cells", variable=self.raw_data_drop_blank_rows_var, command=self.update_raw_data_view).pack(side="left")
        raw_status_frame = ttk.Frame(raw_frame, style="Card.TFrame")
        raw_status_frame.pack(fill="x", padx=6, pady=(0, 2))
        self.raw_status_var = tk.StringVar(value="Raw data will refresh when a plot is generated, or when Refresh is clicked.")
        ttk.Label(raw_status_frame, textvariable=self.raw_status_var).pack(side="left", anchor="w")
        raw_table_frame = ttk.Frame(raw_frame, style="Card.TFrame")
        raw_table_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        raw_table_frame.rowconfigure(0, weight=1)
        raw_table_frame.columnconfigure(0, weight=1)
        self.raw_tree = ttk.Treeview(raw_table_frame, show="headings", height=7, style="Bordered.Treeview")
        self._configure_treeview_tags(self.raw_tree)
        raw_y_scroll = ttk.Scrollbar(raw_table_frame, orient="vertical", command=self.raw_tree.yview)
        raw_x_scroll = ttk.Scrollbar(raw_table_frame, orient="horizontal", command=self.raw_tree.xview)
        self.raw_tree.configure(yscrollcommand=raw_y_scroll.set, xscrollcommand=raw_x_scroll.set)
        self.raw_tree.grid(row=0, column=0, sticky="nsew")
        raw_y_scroll.grid(row=0, column=1, sticky="ns")
        raw_x_scroll.grid(row=1, column=0, sticky="ew")
        _bind_mousewheel_to_treeview(self.raw_tree)

        maths_frame = ttk.Frame(bottom_tabs, style="Card.TFrame")
        bottom_tabs.add(maths_frame, text="Maths Channels")
        self._build_calculated_channels_tab(maths_frame)

        runs_frame = ttk.Frame(bottom_tabs, style="Card.TFrame")
        bottom_tabs.add(runs_frame, text="Runs / Comparison")
        self._build_runs_comparison_tab(runs_frame)

        notes_frame = ttk.Frame(bottom_tabs, style="Card.TFrame")
        bottom_tabs.add(notes_frame, text="Engineering Notes")
        self._build_structured_engineering_notes_tab(notes_frame)

        limits_frame = ttk.Frame(bottom_tabs, style="Card.TFrame")
        bottom_tabs.add(limits_frame, text="Requirements / Limits")
        self._build_requirements_limits_tab(limits_frame)

        margins_frame = ttk.Frame(bottom_tabs, style="Card.TFrame")
        bottom_tabs.add(margins_frame, text="Limit Margins")
        self._build_limit_margins_tab(margins_frame)

        cursor_frame = ttk.Frame(bottom_tabs, style="Card.TFrame")
        bottom_tabs.add(cursor_frame, text="Cursor Readout")
        cursor_controls = ttk.Frame(cursor_frame, style="Card.TFrame")
        cursor_controls.pack(fill="x", padx=6, pady=(4, 2))
        ttk.Button(cursor_controls, text="Use P1-P2 as Analysis Window", command=self.use_cursor_points_as_analysis_window).pack(side="left", padx=(0, 8))
        ttk.Button(cursor_controls, text="Clear Cursor Points", command=self._clear_cursor_points).pack(side="left")
        self.cursor_status_var = tk.StringVar(value="Generate a plot, then move the mouse over the graph to read the nearest X/Y values. Click to lock points; press ESC to clear.")
        ttk.Label(cursor_frame, textvariable=self.cursor_status_var).pack(fill="x", padx=6, pady=(0, 2), anchor="w")
        cursor_table_frame = ttk.Frame(cursor_frame, style="Card.TFrame")
        cursor_table_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        cursor_table_frame.rowconfigure(0, weight=1)
        cursor_table_frame.columnconfigure(0, weight=1)
        self.cursor_tree = ttk.Treeview(cursor_table_frame, show="headings", height=8, style="Bordered.Treeview")
        self._configure_treeview_tags(self.cursor_tree)
        cursor_y_scroll = ttk.Scrollbar(cursor_table_frame, orient="vertical", command=self.cursor_tree.yview)
        cursor_x_scroll = ttk.Scrollbar(cursor_table_frame, orient="horizontal", command=self.cursor_tree.xview)
        self.cursor_tree.configure(yscrollcommand=cursor_y_scroll.set, xscrollcommand=cursor_x_scroll.set)
        self.cursor_tree.grid(row=0, column=0, sticky="nsew")
        cursor_y_scroll.grid(row=0, column=1, sticky="ns")
        cursor_x_scroll.grid(row=1, column=0, sticky="ew")
        _bind_mousewheel_to_treeview(self.cursor_tree)
        self._set_cursor_text("Generate a plot, then move the mouse over the graph to read the nearest X/Y values. Click to lock points; press ESC to clear.")
        self.clear_plot()

    # ------------------------------------------------------------------
    # Analysis window helpers
    # ------------------------------------------------------------------
    def copy_axis_limits_to_analysis_window(self) -> None:
        self.analysis_xmin_var.set(self.xmin_var.get())
        self.analysis_xmax_var.set(self.xmax_var.get())
        self.update_range_preview()
        self.update_stats()

    def clear_analysis_window(self) -> None:
        self.analysis_xmin_var.set("")
        self.analysis_xmax_var.set("")
        self.update_range_preview()
        self.update_stats()

    def _set_text_widget(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _clear_treeview(self, tree: ttk.Treeview) -> None:
        children = tree.get_children()
        if children:
            tree.delete(*children)

    # ------------------------------------------------------------------
    # Axis-limit helpers
    # ------------------------------------------------------------------
    def parse_limit(self, value: str) -> Optional[float]:
        value = value.strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"Invalid axis limit: {value}") from exc

    def _axis_upper_margin(self, highest_value: float, lowest_value: Optional[float] = None) -> float:
        mode = str(self._setting("axis_scaling", "auto_scale_mode", "padded"))
        if mode == "tight":
            return float(highest_value)
        pad_percent = float(self._setting("axis_scaling", "auto_scale_pad_percent", 5) or 0)
        if pad_percent <= 0:
            return float(highest_value)
        margin = abs(float(highest_value)) * (pad_percent / 100.0)
        if margin == 0 and lowest_value is not None:
            margin = abs(float(highest_value) - float(lowest_value)) * (pad_percent / 100.0)
        if margin == 0:
            margin = 1.0
        return float(highest_value) + margin

    def manual_limits(self) -> Tuple[Optional[float], Optional[float],
                                     Optional[float], Optional[float]]:
        return (self.parse_limit(self.xmin_var.get()),
                self.parse_limit(self.xmax_var.get()),
                self.parse_limit(self.ymin_var.get()),
                self.parse_limit(self.ymax_var.get()))

    def secondary_manual_limits(self) -> Tuple[Optional[float], Optional[float]]:
        return (self.parse_limit(self.y2min_var.get()),
                self.parse_limit(self.y2max_var.get()))

    def limits_have_visible_data(self, data: PlotData, limits) -> bool:
        xmin, xmax, ymin, ymax = limits
        for label, y in data.y_map.items():
            x_for_label = data.x_map.get(label, data.x) if data.x_map else data.x
            frame = pd.DataFrame({"x": x_for_label, "y": y}).dropna()
            if frame.empty:
                continue
            mask = pd.Series(True, index=frame.index)
            if xmin is not None:
                mask &= frame["x"] >= xmin
            if xmax is not None:
                mask &= frame["x"] <= xmax
            if ymin is not None:
                mask &= frame["y"] >= ymin
            if ymax is not None:
                mask &= frame["y"] <= ymax
            if mask.any():
                return True
        return False

    def toggle_axis_entries(self) -> None:
        state = "disabled" if self.auto_fit_var.get() else "normal"
        for entry in self.limit_entries:
            entry.configure(state=state)

    def apply_auto_axis_limits(self, data: PlotData) -> None:
        """Apply the same limits shown in Section 6."""
        if self.axes is None:
            return
        self.fill_axis_limits_from_data()
        xmin = self.parse_limit(self.xmin_var.get())
        xmax = self.parse_limit(self.xmax_var.get())
        ymin = self.parse_limit(self.ymin_var.get())
        ymax = self.parse_limit(self.ymax_var.get())
        if xmin is not None or xmax is not None:
            self.axes.set_xlim(left=xmin, right=xmax)
        if ymin is not None or ymax is not None:
            self.axes.set_ylim(bottom=ymin, top=ymax)

