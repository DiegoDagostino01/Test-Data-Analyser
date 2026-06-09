from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional, cast
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from .settings_manager import SettingsManager
from .config import theme_palette


EATON_BLUE_DARK = "#005A8C"
EATON_BLUE_MID = "#007AB8"
EATON_BLUE_LIGHT = "#009ADE"
EATON_BLUE_PALE = "#D0E8F5"
EATON_WHITE = "#FFFFFF"
EATON_GREY_BG = "#F5F5F5"
EATON_GREY_TEXT = "#333333"
EATON_GREY_HELP = "#888888"
EATON_GREY_DISABLED = "#AAAAAA"
EATON_GREY_HELP_DISABLED = "#BBBBBB"

COMBOBOX_WIDTH = 22
SPINBOX_WIDTH = 10
ENTRY_WIDTH = 22
HELP_WRAP_LENGTH = 450

LABEL_PAD = {"padx": (16, 8), "pady": (8, 0), "sticky": "e"}
CONTROL_PAD = {"padx": (0, 16), "pady": (8, 0), "sticky": "w"}
HELP_PAD = {"padx": (16, 16), "pady": (0, 8), "sticky": "w", "columnspan": 2}

STATISTICS_COLUMNS = [
    "Count",
    "Min",
    "Max",
    "Mean",
    "Median",
    "Std Dev",
    "RMS",
    "Peak-to-Peak",
]

HELP_TEXT = {
    ("plot_appearance", "default_line_width"): "Thickness of plotted lines in points. Thicker lines are more visible but may overlap.",
    ("plot_appearance", "colour_cycle"): "The set of colours used when plotting multiple signals. 'eaton' uses Eaton brand colours.",
    ("plot_appearance", "default_marker_style"): "Shape used to mark individual data points. 'None' shows lines only.",
    ("plot_appearance", "grid_visible"): "Show or hide the background grid lines on plots.",
    ("plot_appearance", "font_size_title"): "Font size for the plot title text.",
    ("plot_appearance", "font_size_axis_label"): "Font size for the X-axis and Y-axis label text.",
    ("plot_appearance", "font_size_tick_label"): "Font size for the numbers along the axes.",
    ("plot_appearance", "font_size_legend"): "Font size for the legend entries.",
    ("plot_appearance", "plot_background_colour"): "Background colour of the plot area. Click to open the colour picker.",
    ("axis_scaling", "auto_scale_mode"): "Controls how axis ranges are calculated. Tight: exact data range. Padded: adds percentage margins. Manual: you set the limits.",
    ("axis_scaling", "auto_scale_pad_percent"): "Percentage of extra space added above and below the data range (only applies in Padded mode).",
    ("axis_scaling", "scientific_notation_enabled"): "Turn scientific notation on or off for plot axis values.",
    ("axis_scaling", "scientific_notation_threshold"): "Values larger than this threshold will be displayed in scientific notation (e.g. 1.0e+04).",
    ("axis_scaling", "decimal_places_statistics"): "Number of decimal places shown in the statistics table below the plot.",
    ("axis_scaling", "decimal_places_cursor"): "Number of decimal places shown in the cursor readout when inspecting data points.",
    ("data_import", "default_delimiter"): "Character that separates columns in CSV files. 'auto' will detect automatically.",
    ("data_import", "default_encoding"): "Text encoding of the data file. Use 'utf-8' unless you see garbled characters.",
    ("data_import", "header_row_index"): "Row number (0-based) that contains the column names.",
    ("data_import", "skip_rows"): "Number of metadata rows to skip at the top of the file before the header.",
    ("data_import", "decimal_separator"): "Character used as the decimal point. Use ',' for European-format data.",
    ("export", "default_image_format"): "File format for saved plot images. PNG for general use, SVG for scalable, PDF for reports.",
    ("export", "default_dpi"): "Resolution of exported images. 150 for screen, 300+ for print quality.",
    ("export", "default_export_directory"): "Folder where exported files are saved by default. Leave blank to use the last-used folder.",
    ("export", "include_statistics_in_export"): "When enabled, the statistics table is appended below the plot in exports.",
    ("export", "auto_timestamp_filenames"): "Automatically adds date and time to exported filenames to prevent overwriting.",
    ("general_ui", "theme"): "Switch between light and dark interface modes.",
    ("general_ui", "legend_threshold"): "Number of plotted signals required before the legend automatically appears.",
    ("general_ui", "startup_behaviour"): "What happens when the application starts. 'blank' opens an empty workspace.",
    ("general_ui", "auto_save_enabled"): "Automatically saves your session at regular intervals to prevent data loss.",
    ("general_ui", "auto_save_interval_minutes"): "How often the session is auto-saved (in minutes).",
    ("general_ui", "confirm_before_delete"): "Show a confirmation dialog before deleting a plot tab.",
    ("general_ui", "show_tooltips"): "Display helpful tooltip popups when hovering over buttons and controls.",
    ("engineering_analysis", "default_statistics_columns"): "Choose which columns are visible in the statistics table below the plot.",
    ("engineering_analysis", "fft_window_function"): "Windowing function applied before FFT to reduce spectral leakage.",
    ("engineering_analysis", "fft_overlap_percent"): "Percentage overlap between FFT segments. Higher values give smoother spectra.",
    ("engineering_analysis", "significant_figures_maths"): "Number of significant figures used in Maths channel calculations.",
}


class SidebarItem(tk.Frame):
    """A clickable sidebar category item with hover and selection states."""

    def __init__(self, parent: tk.Widget, text: str, command=None) -> None:
        super().__init__(parent, bg=EATON_BLUE_DARK)
        self.command = command
        self._selected = False

        self.accent = tk.Frame(self, width=3, bg=EATON_BLUE_DARK)
        self.accent.pack(side="left", fill="y")

        self.label = tk.Label(
            self,
            text=text,
            font=("Segoe UI", 11),
            bg=EATON_BLUE_DARK,
            fg=EATON_WHITE,
            anchor="w",
            padx=12,
            pady=10,
            cursor="hand2",
        )
        self.label.pack(side="left", fill="both", expand=True)

        for widget in (self, self.label):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<Button-1>", self._on_click)
            widget.configure(cursor="hand2")

    def _on_enter(self, _event: Optional[tk.Event] = None) -> None:
        if not self._selected:
            self.label.configure(bg=EATON_BLUE_MID)
            self.configure(bg=EATON_BLUE_MID)

    def _on_leave(self, _event: Optional[tk.Event] = None) -> None:
        if not self._selected:
            self.label.configure(bg=EATON_BLUE_DARK)
            self.configure(bg=EATON_BLUE_DARK)

    def _on_click(self, _event: Optional[tk.Event] = None) -> None:
        if self.command:
            self.command()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        if selected:
            self.label.configure(
                bg=EATON_BLUE_PALE,
                fg=EATON_BLUE_DARK,
                font=("Segoe UI", 11, "bold"),
            )
            self.configure(bg=EATON_BLUE_PALE)
            self.accent.configure(bg=EATON_BLUE_LIGHT)
        else:
            self.label.configure(
                bg=EATON_BLUE_DARK,
                fg=EATON_WHITE,
                font=("Segoe UI", 11),
            )
            self.configure(bg=EATON_BLUE_DARK)
            self.accent.configure(bg=EATON_BLUE_DARK)


class SettingsWindow(tk.Toplevel):
    """Modal Settings dialog for Test Data Analyser."""

    CATEGORIES = [
        ("Plot Appearance", "plot_appearance"),
        ("Axis & Scaling", "axis_scaling"),
        ("Data Import", "data_import"),
        ("Export", "export"),
        ("General / UI", "general_ui"),
        ("Engineering / Analysis", "engineering_analysis"),
    ]

    def __init__(self, parent: tk.Misc, settings_manager: SettingsManager) -> None:
        super().__init__(parent)
        self.parent = parent
        self.settings_manager = settings_manager
        self._pal = self._resolve_palette()
        self._defaults = settings_manager.defaults()
        self._working_settings = settings_manager.as_dict()
        self._variables: dict[tuple[str, str], tk.Variable] = {}
        self._colour_swatches: dict[tuple[str, str], tk.Frame] = {}
        self._widgets_by_key: dict[tuple[str, str], tk.Widget] = {}
        self._labels_by_key: dict[tuple[str, str], tk.Label] = {}
        self._help_by_key: dict[tuple[str, str], tk.Label] = {}
        self._sidebar_items: list[SidebarItem] = []
        self._loading_controls = False
        self._dirty = False
        self._current_section = self.CATEGORIES[0][1]
        self.btn_apply: Optional[tk.Button] = None

        self.title("Settings — Test Data Analyser")
        self.geometry("850x580")
        self.minsize(750, 500)
        self.configure(bg=self._pal["window_bg"])
        self.transient(cast(tk.Wm, parent.winfo_toplevel()))
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._configure_style()
        self._build_layout()
        self._select_category(0)
        self.after_idle(self.focus_force)

    def _resolve_palette(self) -> dict[str, str]:
        try:
            theme_name = str(self.settings_manager.get("general_ui", "theme"))
        except Exception:
            theme_name = "light"
        base = theme_palette(theme_name)
        if theme_name.lower() == "dark":
            return {
                "window_bg": base["bg"],
                "panel_bg": base["card"],
                "text": base["text"],
                "text_disabled": "#64748B",
                "help_text": base["secondary"],
                "help_disabled": "#475569",
                "section_label": "#60A5FA",
            }
        return {
            "window_bg": EATON_GREY_BG,
            "panel_bg": EATON_WHITE,
            "text": EATON_GREY_TEXT,
            "text_disabled": EATON_GREY_DISABLED,
            "help_text": EATON_GREY_HELP,
            "help_disabled": EATON_GREY_HELP_DISABLED,
            "section_label": EATON_BLUE_DARK,
        }

    def _configure_style(self) -> None:
        pal = self._pal
        style = ttk.Style(self)
        style.configure("Settings.TFrame", background=pal["panel_bg"])
        style.configure("SettingsBody.TFrame", background=pal["window_bg"])
        style.configure("Settings.TLabelframe", background=pal["panel_bg"], relief="groove", borderwidth=1)
        style.configure(
            "Settings.TLabelframe.Label",
            font=("Segoe UI", 12, "bold"),
            foreground=pal["section_label"],
            background=pal["panel_bg"],
        )
        style.configure("Settings.TCheckbutton", background=pal["panel_bg"], foreground=pal["text"], font=("Segoe UI", 9))
        style.configure("Secondary.TButton", font=("Segoe UI", 9), padding=(12, 6))

    def _build_layout(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = tk.Frame(self, bg=EATON_BLUE_DARK, height=50)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        tk.Label(
            header,
            text="Settings",
            bg=EATON_BLUE_DARK,
            fg=EATON_WHITE,
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left", padx=18)

        body = ttk.Frame(self, style="SettingsBody.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        nav_frame = tk.Frame(body, bg=EATON_BLUE_DARK, width=200)
        nav_frame.grid(row=0, column=0, sticky="ns")
        nav_frame.grid_propagate(False)
        for index, (label, _section) in enumerate(self.CATEGORIES):
            item = SidebarItem(nav_frame, label, command=lambda i=index: self._select_category(i))
            item.pack(fill="x")
            self._sidebar_items.append(item)

        content_shell = ttk.Frame(body, style="Settings.TFrame", padding=(16, 16, 12, 0))
        content_shell.grid(row=0, column=1, sticky="nsew")
        content_shell.grid_rowconfigure(0, weight=1)
        content_shell.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(content_shell, bg=self._pal["panel_bg"], highlightthickness=0)
        self.content_scrollbar = ttk.Scrollbar(content_shell, orient="vertical", command=self.canvas.yview)
        self.scroll_inner = ttk.Frame(self.canvas, style="Settings.TFrame")
        self.scroll_window = self.canvas.create_window((0, 0), window=self.scroll_inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.content_scrollbar.set)
        self.scroll_inner.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.content_scrollbar.grid(row=0, column=1, sticky="ns")
        self._bind_mousewheel_to_canvas(self.canvas)

        footer = ttk.Frame(self, style="Settings.TFrame", padding=(12, 10))
        footer.grid(row=2, column=0, sticky="ew")
        self.btn_apply = tk.Button(
            footer,
            text="Apply",
            font=("Segoe UI", 10, "bold"),
            bg=EATON_BLUE_LIGHT,
            fg=EATON_WHITE,
            activebackground=EATON_BLUE_MID,
            activeforeground=EATON_WHITE,
            disabledforeground=EATON_BLUE_PALE,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._apply,
        )
        self.btn_apply.pack(side="left")
        ttk.Button(footer, text="Reset Section", command=self._reset_section, style="Secondary.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(footer, text="Reset All", command=self._reset_all, style="Secondary.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(footer, text="Close", command=self._on_close, style="Secondary.TButton").pack(side="right")
        self._set_dirty_state(False)

    def _bind_mousewheel_to_canvas(self, canvas: tk.Canvas) -> None:
        def _on_mousewheel(event: tk.Event) -> str:
            if getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            else:
                delta = int(-1 * (event.delta / 120))
            canvas.yview_scroll(delta, "units")
            return "break"

        def _bind(_event: Optional[tk.Event] = None) -> None:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind(_event: Optional[tk.Event] = None) -> None:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind)
        canvas.bind("<Leave>", _unbind)

    def _on_content_configure(self, _event: Optional[tk.Event] = None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.scroll_window, width=event.width)
        self._update_scrollbar_visibility()

    def _update_scrollbar_visibility(self) -> None:
        bbox = self.canvas.bbox("all")
        if bbox is not None and bbox[3] > max(1, self.canvas.winfo_height()):
            self.content_scrollbar.grid()
        else:
            self.content_scrollbar.grid_remove()

    def _select_category(self, index: int) -> None:
        for item_index, item in enumerate(self._sidebar_items):
            item.set_selected(item_index == index)
        self._current_section = self.CATEGORIES[index][1]
        self._load_category_controls(self._current_section)

    def _load_category_controls(self, section: str) -> None:
        self._loading_controls = True
        try:
            for child in self.scroll_inner.winfo_children():
                child.destroy()
            self._variables.clear()
            self._colour_swatches.clear()
            self._widgets_by_key.clear()
            self._labels_by_key.clear()
            self._help_by_key.clear()

            builder = {
                "plot_appearance": self._build_plot_appearance,
                "axis_scaling": self._build_axis_scaling,
                "data_import": self._build_data_import,
                "export": self._build_export,
                "general_ui": self._build_general_ui,
                "engineering_analysis": self._build_engineering_analysis,
            }[section]
            builder()
            self.canvas.yview_moveto(0)
        finally:
            self._loading_controls = False
            self._set_dirty_state(self._dirty)

    def _section_frame(self, title: str) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(
            self.scroll_inner,
            text=title,
            style="Settings.TLabelframe",
            padding=(16, 12, 16, 12),
        )
        frame.pack(fill="x", expand=True, pady=(0, 16))
        frame.columnconfigure(0, weight=0, minsize=200)
        frame.columnconfigure(1, weight=1)
        return frame

    def _value(self, section: str, key: str) -> Any:
        return deepcopy(self._working_settings.get(section, {}).get(key, self._defaults[section][key]))

    def _help(self, section: str, key: str) -> str:
        return HELP_TEXT.get((section, key), "")

    def _set_working_value(self, section: str, key: str, value: Any) -> None:
        self._working_settings.setdefault(section, {})[key] = deepcopy(value)
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        if not self._loading_controls:
            self._set_dirty_state(True)

    def _set_dirty_state(self, dirty: bool) -> None:
        self._dirty = dirty
        self.title("Settings — Test Data Analyser *" if dirty else "Settings — Test Data Analyser")
        if self.btn_apply is not None:
            self.btn_apply.configure(state="normal" if dirty else "disabled")

    def _new_var(self, section: str, key: str, value: Any) -> tk.Variable:
        if isinstance(value, bool):
            var: tk.Variable = tk.BooleanVar(value=value)
        elif isinstance(value, int) and not isinstance(value, bool):
            var = tk.IntVar(value=value)
        elif isinstance(value, float):
            var = tk.DoubleVar(value=value)
        else:
            var = tk.StringVar(value=str(value))
        self._variables[(section, key)] = var
        var.trace_add("write", lambda *_args, s=section, k=key, v=var: self._on_variable_changed(s, k, v))
        return var

    def _on_variable_changed(self, section: str, key: str, var: tk.Variable) -> None:
        if self._loading_controls:
            return
        try:
            value = var.get()
        except tk.TclError:
            value = ""
        self._working_settings.setdefault(section, {})[key] = value
        self._mark_dirty()
        if section == "axis_scaling" and key == "auto_scale_mode":
            self._update_padded_state()
        if section == "axis_scaling" and key == "scientific_notation_enabled":
            self._update_scientific_notation_state()
        if section == "general_ui" and key == "auto_save_enabled":
            self._update_auto_save_state()

    def _validate_float(self, proposed: str) -> bool:
        if proposed in {"", "+", "-", ".", "+.", "-."}:
            return True
        try:
            float(proposed)
            return True
        except ValueError:
            return False

    def _validate_int(self, proposed: str) -> bool:
        if proposed in {"", "+", "-"}:
            return True
        try:
            int(proposed)
            return True
        except ValueError:
            return False

    def _float_vcmd(self) -> tuple[str, str]:
        return (self.register(self._validate_float), "%P")

    def _int_vcmd(self) -> tuple[str, str]:
        return (self.register(self._validate_int), "%P")

    def _add_label(self, parent: ttk.LabelFrame, row: int, section: str, key: str, text: str) -> None:
        label = tk.Label(parent, text=text, font=("Segoe UI", 9), fg=self._pal["text"], bg=self._pal["panel_bg"], anchor="e", justify="right")
        label.grid(row=row, column=0, **LABEL_PAD)
        self._labels_by_key[(section, key)] = label

    def _add_help_text(self, parent: ttk.LabelFrame, row: int, section: str, key: str, text: str) -> None:
        help_label = tk.Label(
            parent,
            text=text,
            font=("Segoe UI", 8),
            fg=self._pal["help_text"],
            bg=self._pal["panel_bg"],
            anchor="w",
            justify="left",
            wraplength=HELP_WRAP_LENGTH,
        )
        help_label.grid(row=row, column=0, **HELP_PAD)
        self._help_by_key[(section, key)] = help_label

    def _add_spinbox(self, parent: ttk.LabelFrame, row: int, section: str, key: str, label: str, from_: float, to: float, increment: float, numeric_type: type[int] | type[float] = int) -> int:
        self._add_label(parent, row, section, key, label)
        value = self._value(section, key)
        var = self._new_var(section, key, value)
        validatecommand = self._int_vcmd() if numeric_type is int else self._float_vcmd()
        spinbox = ttk.Spinbox(parent, from_=from_, to=to, increment=increment, textvariable=var, validate="key", validatecommand=validatecommand, width=SPINBOX_WIDTH)
        spinbox.grid(row=row, column=1, **CONTROL_PAD)
        self._widgets_by_key[(section, key)] = spinbox
        self._add_help_text(parent, row + 1, section, key, self._help(section, key))
        return row + 2

    def _add_entry(self, parent: ttk.LabelFrame, row: int, section: str, key: str, label: str, validate_float: bool = False) -> int:
        self._add_label(parent, row, section, key, label)
        var = self._new_var(section, key, self._value(section, key))
        kwargs: dict[str, Any] = {"textvariable": var, "width": ENTRY_WIDTH}
        if validate_float:
            kwargs.update({"validate": "key", "validatecommand": self._float_vcmd()})
        entry = ttk.Entry(parent, **kwargs)
        entry.grid(row=row, column=1, **CONTROL_PAD)
        self._widgets_by_key[(section, key)] = entry
        self._add_help_text(parent, row + 1, section, key, self._help(section, key))
        return row + 2

    def _add_combo(self, parent: ttk.LabelFrame, row: int, section: str, key: str, label: str, values: list[Any]) -> int:
        self._add_label(parent, row, section, key, label)
        var = self._new_var(section, key, self._value(section, key))
        combo = ttk.Combobox(parent, textvariable=var, values=[str(value) for value in values], state="readonly", width=COMBOBOX_WIDTH)
        combo.grid(row=row, column=1, **CONTROL_PAD)
        self._widgets_by_key[(section, key)] = combo
        self._add_help_text(parent, row + 1, section, key, self._help(section, key))
        return row + 2

    def _add_checkbutton(self, parent: ttk.LabelFrame, row: int, section: str, key: str, label: str) -> int:
        self._add_label(parent, row, section, key, label)
        var = self._new_var(section, key, bool(self._value(section, key)))
        checkbutton = ttk.Checkbutton(parent, text="", variable=var, style="Settings.TCheckbutton")
        checkbutton.grid(row=row, column=1, **CONTROL_PAD)
        self._widgets_by_key[(section, key)] = checkbutton
        self._add_help_text(parent, row + 1, section, key, self._help(section, key))
        return row + 2

    def _build_plot_appearance(self) -> None:
        section = "plot_appearance"
        line_frame = self._section_frame("Lines And Grid")
        row = 0
        row = self._add_spinbox(line_frame, row, section, "default_line_width", "Default Line Width", 0.5, 5.0, 0.5, float)
        row = self._add_combo(line_frame, row, section, "colour_cycle", "Colour Cycle", self._value(section, "available_colour_cycles"))
        row = self._add_combo(line_frame, row, section, "default_marker_style", "Default Marker Style", ["None", "o", "s", "^", "D", "x", "+"])
        self._add_checkbutton(line_frame, row, section, "grid_visible", "Grid Visible")

        font_frame = self._section_frame("Fonts")
        row = 0
        row = self._add_spinbox(font_frame, row, section, "font_size_title", "Font Size - Title", 6, 28, 1, int)
        row = self._add_spinbox(font_frame, row, section, "font_size_axis_label", "Font Size - Axis Label", 6, 28, 1, int)
        row = self._add_spinbox(font_frame, row, section, "font_size_tick_label", "Font Size - Tick Label", 6, 28, 1, int)
        self._add_spinbox(font_frame, row, section, "font_size_legend", "Font Size - Legend", 6, 28, 1, int)

        colour_frame = self._section_frame("Colours")
        key = "plot_background_colour"
        self._add_label(colour_frame, 0, section, key, "Plot Background Colour")
        colour_var = self._new_var(section, key, self._value(section, key))
        control_row = ttk.Frame(colour_frame, style="Settings.TFrame")
        control_row.grid(row=0, column=1, **CONTROL_PAD)
        ttk.Button(control_row, text="Choose Colour", command=lambda: self._choose_colour(section, key)).pack(side="left")
        swatch = tk.Frame(control_row, width=24, height=24, bg=str(colour_var.get()), relief="solid", bd=1)
        swatch.pack(side="left", padx=(8, 0))
        swatch.pack_propagate(False)
        self._colour_swatches[(section, key)] = swatch
        self._add_help_text(colour_frame, 1, section, key, self._help(section, key))

    def _build_axis_scaling(self) -> None:
        section = "axis_scaling"
        axis_frame = self._section_frame("Auto Scaling")
        row = 0
        row = self._add_combo(axis_frame, row, section, "auto_scale_mode", "Auto-Scale Mode", ["tight", "padded", "manual"])
        self._add_spinbox(axis_frame, row, section, "auto_scale_pad_percent", "Pad Percent", 0, 50, 1, int)
        self._update_padded_state()

        format_frame = self._section_frame("Numeric Format")
        row = 0
        row = self._add_checkbutton(format_frame, row, section, "scientific_notation_enabled", "Use Scientific Notation")
        row = self._add_entry(format_frame, row, section, "scientific_notation_threshold", "Scientific Notation Threshold", validate_float=True)
        row = self._add_spinbox(format_frame, row, section, "decimal_places_statistics", "Decimal Places - Statistics", 0, 10, 1, int)
        self._add_spinbox(format_frame, row, section, "decimal_places_cursor", "Decimal Places - Cursor", 0, 10, 1, int)
        self._update_scientific_notation_state()

    def _build_data_import(self) -> None:
        section = "data_import"
        import_frame = self._section_frame("CSV And Excel Defaults")
        row = 0
        row = self._add_combo(import_frame, row, section, "default_delimiter", "Default Delimiter", self._value(section, "available_delimiters"))
        row = self._add_combo(import_frame, row, section, "default_encoding", "Default Encoding", self._value(section, "available_encodings"))
        row = self._add_spinbox(import_frame, row, section, "header_row_index", "Header Row Index", 0, 20, 1, int)
        row = self._add_spinbox(import_frame, row, section, "skip_rows", "Skip Rows", 0, 100, 1, int)
        self._add_combo(import_frame, row, section, "decimal_separator", "Decimal Separator", [".", ","])

    def _build_export(self) -> None:
        section = "export"
        export_frame = self._section_frame("Plot Export")
        row = 0
        row = self._add_combo(export_frame, row, section, "default_image_format", "Default Image Format", self._value(section, "available_image_formats"))
        row = self._add_combo(export_frame, row, section, "default_dpi", "Default DPI", [72, 100, 150, 300, 600])

        key = "default_export_directory"
        self._add_label(export_frame, row, section, key, "Default Export Directory")
        directory_var = self._new_var(section, key, self._value(section, key))
        directory_row = ttk.Frame(export_frame, style="Settings.TFrame")
        directory_row.grid(row=row, column=1, **CONTROL_PAD)
        ttk.Entry(directory_row, textvariable=directory_var, width=ENTRY_WIDTH).pack(side="left")
        ttk.Button(directory_row, text="Browse...", command=lambda: self._browse_directory(section, key)).pack(side="left", padx=(8, 0))
        self._add_help_text(export_frame, row + 1, section, key, self._help(section, key))
        row += 2
        row = self._add_checkbutton(export_frame, row, section, "include_statistics_in_export", "Include Statistics In Export")
        self._add_checkbutton(export_frame, row, section, "auto_timestamp_filenames", "Auto-Timestamp Filenames")

    def _build_general_ui(self) -> None:
        section = "general_ui"
        display_frame = self._section_frame("Display")
        row = 0
        row = self._add_combo(display_frame, row, section, "theme", "Theme", ["light", "dark"])
        row = self._add_spinbox(display_frame, row, section, "legend_threshold", "Legend Threshold", 1, 20, 1, int)
        row = self._add_combo(display_frame, row, section, "startup_behaviour", "Startup Behaviour", self._value(section, "available_startup_behaviours"))
        self._add_checkbutton(display_frame, row, section, "show_tooltips", "Show Tooltips")

        safety_frame = self._section_frame("Safety And Auto-Save")
        row = 0
        row = self._add_checkbutton(safety_frame, row, section, "auto_save_enabled", "Auto-Save Enabled")
        row = self._add_spinbox(safety_frame, row, section, "auto_save_interval_minutes", "Auto-Save Interval (Min)", 1, 60, 1, int)
        self._add_checkbutton(safety_frame, row, section, "confirm_before_delete", "Confirm Before Delete")
        self._update_auto_save_state()

    def _build_engineering_analysis(self) -> None:
        section = "engineering_analysis"
        stats_frame = self._section_frame("Statistics Columns")
        key = "default_statistics_columns"
        self._add_label(stats_frame, 0, section, key, "Statistics Columns")
        checklist = ttk.Frame(stats_frame, style="Settings.TFrame")
        checklist.grid(row=0, column=1, **CONTROL_PAD)
        selected = set(self._value(section, key))
        for index, column in enumerate(STATISTICS_COLUMNS):
            var = tk.BooleanVar(value=column in selected)
            self._variables[(section, f"stats::{column}")] = var
            var.trace_add("write", lambda *_args, c=column, v=var: self._on_statistics_column_changed(c, v))
            checkbutton = ttk.Checkbutton(checklist, text=column, variable=var, style="Settings.TCheckbutton")
            checkbutton.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 18), pady=2)
        self._add_help_text(stats_frame, 1, section, key, self._help(section, key))

        fft_frame = self._section_frame("FFT And Maths")
        row = 0
        row = self._add_combo(fft_frame, row, section, "fft_window_function", "FFT Window Function", self._value(section, "available_fft_windows"))
        row = self._add_spinbox(fft_frame, row, section, "fft_overlap_percent", "FFT Overlap %", 0, 90, 5, int)
        self._add_spinbox(fft_frame, row, section, "significant_figures_maths", "Significant Figures - Maths", 1, 15, 1, int)

    def _on_statistics_column_changed(self, column: str, var: tk.BooleanVar) -> None:
        selected = list(self._working_settings["engineering_analysis"].get("default_statistics_columns", []))
        if var.get() and column not in selected:
            selected.append(column)
        if not var.get() and column in selected:
            selected.remove(column)
        selected = [column_name for column_name in STATISTICS_COLUMNS if column_name in selected]
        self._set_working_value("engineering_analysis", "default_statistics_columns", selected)

    def _choose_colour(self, section: str, key: str) -> None:
        current = str(self._value(section, key))
        _rgb, colour = colorchooser.askcolor(color=current, parent=self, title="Choose Plot Background Colour")
        if not colour:
            return
        self._set_working_value(section, key, colour)
        swatch = self._colour_swatches.get((section, key))
        if swatch is not None:
            swatch.configure(bg=colour)

    def _browse_directory(self, section: str, key: str) -> None:
        initialdir = str(self._value(section, key) or "") or None
        directory = filedialog.askdirectory(parent=self, initialdir=initialdir)
        if not directory:
            return
        var = self._variables[(section, key)]
        var.set(directory)

    def _set_control_enabled(self, section: str, key: str, enabled: bool) -> None:
        widget = self._widgets_by_key.get((section, key))
        if widget is not None:
            state = "readonly" if enabled and isinstance(widget, ttk.Combobox) else "normal"
            widget.configure(**{"state": state if enabled else "disabled"})
        label = self._labels_by_key.get((section, key))
        if label is not None:
            label.configure(fg=self._pal["text"] if enabled else self._pal["text_disabled"])
        help_label = self._help_by_key.get((section, key))
        if help_label is not None:
            help_label.configure(fg=self._pal["help_text"] if enabled else self._pal["help_disabled"])

    def _update_padded_state(self) -> None:
        mode = self._working_settings.get("axis_scaling", {}).get("auto_scale_mode", "padded")
        self._set_control_enabled("axis_scaling", "auto_scale_pad_percent", mode == "padded")

    def _update_scientific_notation_state(self) -> None:
        enabled = bool(self._working_settings.get("axis_scaling", {}).get("scientific_notation_enabled", True))
        self._set_control_enabled("axis_scaling", "scientific_notation_threshold", enabled)

    def _update_auto_save_state(self) -> None:
        enabled = bool(self._working_settings.get("general_ui", {}).get("auto_save_enabled", False))
        self._set_control_enabled("general_ui", "auto_save_interval_minutes", enabled)

    def _apply(self) -> bool:
        if not self._validate_required_values():
            return False
        normalised = self._normalised_working_settings()
        try:
            for section, values in normalised.items():
                for key, value in values.items():
                    if key.startswith("available_"):
                        continue
                    self.settings_manager.set(section, key, value)
            self.settings_manager.save()
        except Exception as exc:
            messagebox.showerror("Settings", f"Could not save settings:\n\n{exc}", parent=self)
            return False
        self._working_settings = self.settings_manager.as_dict()
        self._set_dirty_state(False)
        messagebox.showinfo("Settings", "Settings applied.", parent=self)
        self._load_category_controls(self._current_section)
        return True

    def _validate_required_values(self) -> bool:
        checks = [
            ("plot_appearance", "default_line_width", float, "Default Line Width"),
            ("plot_appearance", "font_size_title", int, "Font Size - Title"),
            ("plot_appearance", "font_size_axis_label", int, "Font Size - Axis Label"),
            ("plot_appearance", "font_size_tick_label", int, "Font Size - Tick Label"),
            ("plot_appearance", "font_size_legend", int, "Font Size - Legend"),
            ("axis_scaling", "auto_scale_pad_percent", int, "Pad Percent"),
            ("axis_scaling", "scientific_notation_threshold", float, "Scientific Notation Threshold"),
            ("axis_scaling", "decimal_places_statistics", int, "Decimal Places - Statistics"),
            ("axis_scaling", "decimal_places_cursor", int, "Decimal Places - Cursor"),
            ("data_import", "header_row_index", int, "Header Row Index"),
            ("data_import", "skip_rows", int, "Skip Rows"),
            ("export", "default_dpi", int, "Default DPI"),
            ("general_ui", "legend_threshold", int, "Legend Threshold"),
            ("general_ui", "auto_save_interval_minutes", int, "Auto-Save Interval"),
            ("engineering_analysis", "fft_overlap_percent", int, "FFT Overlap %"),
            ("engineering_analysis", "significant_figures_maths", int, "Significant Figures - Maths"),
        ]
        for section, key, caster, label in checks:
            value = self._working_settings.get(section, {}).get(key, "")
            try:
                caster(value)
            except (TypeError, ValueError):
                messagebox.showerror("Settings", f"{label} must be numeric.", parent=self)
                widget = self._widgets_by_key.get((section, key))
                if widget is not None:
                    widget.focus_set()
                return False
        if not self._working_settings["engineering_analysis"].get("default_statistics_columns"):
            messagebox.showerror("Settings", "Select at least one Statistics Column.", parent=self)
            return False
        return True

    def _normalised_working_settings(self) -> dict[str, dict[str, Any]]:
        settings = deepcopy(self._working_settings)
        settings["plot_appearance"]["default_line_width"] = float(settings["plot_appearance"]["default_line_width"])
        for key in ("font_size_title", "font_size_axis_label", "font_size_tick_label", "font_size_legend"):
            settings["plot_appearance"][key] = int(settings["plot_appearance"][key])
        settings["axis_scaling"]["auto_scale_pad_percent"] = int(settings["axis_scaling"]["auto_scale_pad_percent"])
        settings["axis_scaling"]["scientific_notation_enabled"] = bool(settings["axis_scaling"].get("scientific_notation_enabled", True))
        settings["axis_scaling"]["scientific_notation_threshold"] = float(settings["axis_scaling"]["scientific_notation_threshold"])
        settings["axis_scaling"]["decimal_places_statistics"] = int(settings["axis_scaling"]["decimal_places_statistics"])
        settings["axis_scaling"]["decimal_places_cursor"] = int(settings["axis_scaling"]["decimal_places_cursor"])
        settings["data_import"]["header_row_index"] = int(settings["data_import"]["header_row_index"])
        settings["data_import"]["skip_rows"] = int(settings["data_import"]["skip_rows"])
        settings["export"]["default_dpi"] = int(settings["export"]["default_dpi"])
        settings["general_ui"]["legend_threshold"] = int(settings["general_ui"]["legend_threshold"])
        settings["general_ui"]["auto_save_interval_minutes"] = int(settings["general_ui"]["auto_save_interval_minutes"])
        settings["engineering_analysis"]["fft_overlap_percent"] = int(settings["engineering_analysis"]["fft_overlap_percent"])
        settings["engineering_analysis"]["significant_figures_maths"] = int(settings["engineering_analysis"]["significant_figures_maths"])
        return settings

    def _reset_section(self) -> None:
        self._working_settings[self._current_section] = deepcopy(self._defaults[self._current_section])
        self._set_dirty_state(True)
        self._load_category_controls(self._current_section)

    def _reset_all(self) -> None:
        if not messagebox.askyesno("Reset Settings", "Reset all settings to defaults?", parent=self):
            return
        self._working_settings = deepcopy(self._defaults)
        self._set_dirty_state(True)
        self._load_category_controls(self._current_section)

    def _on_close(self) -> None:
        if self._dirty:
            answer = messagebox.askyesnocancel("Settings", "You have unsaved changes - apply them?", parent=self)
            if answer is None:
                return
            if answer and not self._apply():
                return
        self.grab_release()
        self.destroy()
