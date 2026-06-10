from __future__ import annotations

import re

__version__ = "1.00"

EATON_BLUE       = "#007AC2"

EATON_DARK_BLUE  = "#005A8C"

EATON_LIGHT_BLUE = "#E6F3FB"

EATON_WHITE      = "#FFFFFF"

EATON_DARK_GREY  = "#2D2D2D"

EATON_MID_GREY   = "#555555"

EATON_BG         = "#F5F7FA"

EATON_CARD_BG    = "#FFFFFF"

EATON_DARK_TEXT  = "#1E293B"

EATON_SECONDARY_TEXT = "#64748B"

EATON_BORDER     = "#E2E8F0"

EATON_HOVER      = "#EFF6FF"

EATON_SELECTED   = "#DBEAFE"

EATON_DIVIDER    = "#CBD5E1"

EATON_NAV_BLUE = "#003865"

EATON_HEADER_BLUE = "#005EB8"

EATON_PANEL_BORDER = "#D7DEE8"

EATON_RIBBON_BG = "#FFFFFF"

EATON_HOVER_BLUE = "#EAF4FC"

# ----------------------------------------------------------------------
# Central theme palettes
# ----------------------------------------------------------------------
# A single source of truth for light/dark UI colours. Keys cover the ttk
# surfaces (``bg`` .. ``button_fg``) and the matplotlib plot surfaces
# (``plot_*``). Eaton brand accents (header/nav blue, Generate/Danger
# buttons) are intentionally kept outside this palette so branding stays
# consistent in both themes.
LIGHT_THEME = {
    "bg": EATON_BG,
    "workspace": "#EDF3F8",
    "card": EATON_CARD_BG,
    "card_alt": "#F8FAFC",
    "text": EATON_DARK_TEXT,
    "secondary": EATON_SECONDARY_TEXT,
    "muted": "#94A3B8",
    "border": EATON_BORDER,
    "border_soft": "#EEF2F7",
    "hover": EATON_HOVER,
    "selected": EATON_SELECTED,
    "entry": EATON_WHITE,
    "tree_alt": "#F8FAFC",
    "button_fg": EATON_BLUE,
    "accent": EATON_BLUE,
    "accent_hover": EATON_DARK_BLUE,
    "accent_pressed": EATON_NAV_BLUE,
    "accent_soft": EATON_HOVER_BLUE,
    "success": "#2FB344",
    "warning": "#B7791F",
    "danger": "#C4262E",
    "plot_container": "#EAF0F6",
    "plot_bg": "#F8FAFC",
    "plot_text": EATON_DARK_BLUE,
    "plot_axis": EATON_DARK_GREY,
    "plot_spine": "#7C8798",
    "plot_grid": "#D2DAE5",
}

DARK_THEME = {
    "bg": "#0B1220",
    "workspace": "#111827",
    "card": "#162033",
    "card_alt": "#1B2A41",
    "text": "#E5EDF7",
    "secondary": "#AAB8CC",
    "muted": "#7F8DA3",
    "border": "#2A3A52",
    "border_soft": "#223047",
    "hover": "#23344F",
    "selected": "#0B3A5C",
    "entry": "#0F172A",
    "tree_alt": "#1B2A41",
    "button_fg": "#8CCBFF",
    "accent": "#0072CE",
    "accent_hover": "#1688E5",
    "accent_pressed": "#005EA8",
    "accent_soft": "#0B3A5C",
    "success": "#2FB344",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "plot_container": "#101A2B",
    "plot_bg": "#F4F6F8",
    "plot_text": "#1F2937",
    "plot_axis": "#253247",
    "plot_spine": "#748094",
    "plot_grid": "#D6DCE5",
}


def theme_palette(name: str) -> dict:
    """Return a copy of the palette for ``name`` ("dark" or "light")."""
    return dict(DARK_THEME if str(name).lower() == "dark" else LIGHT_THEME)


EATON_PLOT_COLORS = [
    "#007AC2", "#E87722", "#43B02A", "#C4262E", "#6F2DA8",
    "#00A3E0", "#F2A900", "#005A8C", "#7C878E", "#D4006A",
]

LIMIT_COLOR_PRESETS = {
    "Eaton Blue": "#007AC2",
    "Eaton Dark Blue": "#005A8C",
    "Orange": "#E87722",
    "Green": "#43B02A",
    "Red": "#C4262E",
    "Purple": "#6F2DA8",
    "Cyan": "#00A3E0",
    "Yellow": "#F2A900",
    "Grey": "#7C878E",
    "Magenta": "#D4006A",
    "Black": "#000000",
}

DOMAIN_CONFIG = {
    "Time":     ["time", "timer", "sec", "second", "seconds", "min", "minute", "timestamp", "elapsed"],
    "Flow":     ["flow", "flowrate", "flow_rate", "lpm", "gpm", "slpm", "pph", "gph", "litre", "liter"],
    "Pressure": ["pressure", "press", "psi", "psig", "psid", "bar", "kpa", "inhg", "hg"],
    "Current":  ["current", "amps", "amp", "a", "ma"],
    "Voltage":  ["voltage", "volt", "vdc", "vac", "v"],
    "Speed":    ["speed", "rpm", "rps"],
}

TEMPERATURE_KEYWORDS = ("temp", "temperature", "tc", "deg c", "degc", "°c")

COLUMN_GROUP_ORDER = (
    "Time", "Temperature", "Flow", "Pressure", "Current", "Voltage", "Speed",
    "Other Numeric", "Non-numeric / Metadata",
)

NUMERIC_EXTRACT_RE = re.compile(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")

EATON_LOGO_PNG_BASE64 = """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"""
