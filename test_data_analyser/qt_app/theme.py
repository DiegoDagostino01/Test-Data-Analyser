"""Eaton theme for the PySide6 shell.

Centralises the Qt stylesheet and palette generation, sourcing the Eaton brand
colours from :mod:`test_data_analyser.config` as the single source of truth. This
preserves the Eaton blue palette and the dark/light theme concept used by the
Tkinter UI. Styling stays centralised here rather than being scattered across
widgets.
"""
from __future__ import annotations

from ..core.config import (
    EATON_BLUE,
    EATON_DARK_BLUE,
    EATON_HEADER_BLUE,
    EATON_NAV_BLUE,
    EATON_WHITE,
    theme_palette,
)


def build_stylesheet(theme_name: str = "light") -> str:
    """Return a centralised Qt stylesheet for the given theme name."""
    palette = theme_palette(theme_name)
    bg = palette["bg"]
    card = palette["card"]
    text = palette["text"]
    secondary = palette["secondary"]
    border = palette["border"]
    hover = palette["hover"]
    selected = palette["selected"]
    entry = palette["entry"]

    return f"""
    QMainWindow, QWidget {{
        background-color: {bg};
        color: {text};
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 10pt;
    }}
    QFrame#EatonHeader {{
        background-color: {EATON_HEADER_BLUE};
    }}
    QLabel#EatonHeaderTitle {{
        color: {EATON_WHITE};
        font-size: 16pt;
        font-weight: 600;
    }}
    QLabel#EatonHeaderSubtitle {{
        color: {EATON_WHITE};
        font-size: 9pt;
    }}
    QFrame#EatonCard, QFrame#EatonPanel {{
        background-color: {card};
        border: 1px solid {border};
        border-radius: 6px;
    }}
    QLabel#PanelHeading {{
        color: {EATON_DARK_BLUE};
        font-size: 11pt;
        font-weight: 600;
    }}
    QLabel#PlaceholderText {{
        color: {secondary};
    }}
    QPushButton {{
        background-color: {card};
        color: {EATON_BLUE};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{
        background-color: {hover};
    }}
    QPushButton#PrimaryButton {{
        background-color: {EATON_BLUE};
        color: {EATON_WHITE};
        border: none;
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: {EATON_DARK_BLUE};
    }}
    QComboBox, QLineEdit, QPlainTextEdit, QTextEdit {{
        background-color: {entry};
        color: {text};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 4px 6px;
    }}
    QTableView, QTreeView, QListView {{
        background-color: {card};
        alternate-background-color: {palette['tree_alt']};
        color: {text};
        gridline-color: {border};
        border: 1px solid {border};
        selection-background-color: {selected};
        selection-color: {text};
    }}
    QHeaderView::section {{
        background-color: {EATON_NAV_BLUE};
        color: {EATON_WHITE};
        padding: 4px 8px;
        border: none;
    }}
    QTabWidget::pane {{
        border: 1px solid {border};
        background-color: {card};
    }}
    QTabBar::tab {{
        background-color: {bg};
        color: {text};
        padding: 6px 14px;
        border: 1px solid {border};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected {{
        background-color: {EATON_BLUE};
        color: {EATON_WHITE};
    }}
    QStatusBar {{
        background-color: {card};
        color: {secondary};
        border-top: 1px solid {border};
    }}
    QMenuBar, QMenu {{
        background-color: {card};
        color: {text};
    }}
    QMenuBar::item:selected, QMenu::item:selected {{
        background-color: {hover};
    }}
    """
