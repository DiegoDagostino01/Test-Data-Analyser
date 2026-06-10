"""Eaton theme for the PySide6 shell.

Centralises the Qt stylesheet and palette generation, sourcing the Eaton brand
colours from :mod:`test_data_analyser.config` as the single source of truth. This
preserves the Eaton blue palette and the dark/light theme concept. Styling stays
centralised here rather than being scattered across widgets.
"""
from __future__ import annotations

from ..core.config import (
    EATON_HEADER_BLUE,
    EATON_NAV_BLUE,
    EATON_WHITE,
    theme_palette,
)


def build_stylesheet(theme_name: str = "light") -> str:
    """Return a centralised Qt stylesheet for the given theme name."""
    palette = theme_palette(theme_name)
    bg = palette["bg"]
    workspace = palette["workspace"]
    card = palette["card"]
    card_alt = palette["card_alt"]
    text = palette["text"]
    secondary = palette["secondary"]
    muted = palette["muted"]
    border = palette["border"]
    border_soft = palette["border_soft"]
    hover = palette["hover"]
    selected = palette["selected"]
    entry = palette["entry"]
    tree_alt = palette["tree_alt"]
    accent = palette["accent"]
    accent_hover = palette["accent_hover"]
    accent_pressed = palette["accent_pressed"]
    accent_soft = palette["accent_soft"]
    plot_container = palette["plot_container"]
    plot_bg = palette["plot_bg"]
    table_header_bg = card_alt if str(theme_name).lower() == "dark" else EATON_NAV_BLUE

    return f"""
    QMainWindow, QWidget {{
        background-color: {bg};
        color: {text};
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 10pt;
    }}
    QWidget:disabled {{
        color: {muted};
    }}
    QLabel {{
        background-color: transparent;
        color: {text};
    }}
    QFrame#EatonHeader {{
        background-color: {EATON_HEADER_BLUE};
    }}
    QFrame#EatonHeader QLabel {{
        background-color: {EATON_HEADER_BLUE};
        border: none;
    }}
    QFrame#RibbonBar {{
        background-color: {workspace};
        border-top: 1px solid {border_soft};
        border-bottom: 1px solid {border};
    }}
    QFrame#CollapsedRibbonBar {{
        background-color: {workspace};
        border-top: 1px solid {border_soft};
        border-bottom: 1px solid {border};
    }}
    QFrame#RibbonGroup {{
        background-color: {card};
        border: 1px solid {border_soft};
        border-radius: 6px;
    }}
    QLabel#RibbonGroupLabel {{
        color: {secondary};
        font-size: 7.5pt;
        font-weight: 700;
        letter-spacing: 0px;
    }}
    QLabel#EatonHeaderTitle {{
        background-color: {EATON_HEADER_BLUE};
        color: {EATON_WHITE};
        font-size: 16pt;
        font-weight: 600;
    }}
    QLabel#EatonHeaderSubtitle {{
        background-color: {EATON_HEADER_BLUE};
        color: {EATON_WHITE};
        font-size: 9pt;
    }}
    QFrame#EatonCard, QFrame#EatonPanel {{
        background-color: {card};
        border: 1px solid {border};
        border-radius: 6px;
    }}
    QFrame#PlotTabsBar {{
        background-color: {workspace};
        border: none;
    }}
    QStackedWidget#AnalysisStack, QStackedWidget#RibbonPanelStack {{
        background-color: {card};
        border: none;
    }}
    QLabel#PanelHeading {{
        color: {accent_hover};
        font-size: 11pt;
        font-weight: 600;
    }}
    QLabel#PlaceholderText {{
        color: {secondary};
    }}
    QGroupBox {{
        background-color: {card_alt};
        border: 1px solid {border_soft};
        border-radius: 6px;
        margin-top: 12px;
        padding: 10px 9px 8px 9px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 6px;
        color: {accent_hover};
        background-color: {card_alt};
    }}
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}
    QSplitter::handle {{
        background-color: {border_soft};
    }}
    QSplitter::handle:hover {{
        background-color: {accent_soft};
    }}
    QPushButton {{
        background-color: {card_alt};
        color: {palette['button_fg']};
        border: 1px solid {border};
        border-radius: 5px;
        padding: 6px 13px;
        min-height: 22px;
    }}
    QPushButton:hover {{
        background-color: {hover};
        border-color: {accent};
    }}
    QPushButton:pressed {{
        background-color: {selected};
        border-color: {accent_pressed};
    }}
    QPushButton:disabled {{
        background-color: {bg};
        color: {muted};
        border-color: {border_soft};
    }}
    QPushButton#PrimaryButton {{
        background-color: {accent};
        color: {EATON_WHITE};
        border: 1px solid {accent};
        font-weight: 600;
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: {accent_hover};
        border-color: {accent_hover};
    }}
    QPushButton#PrimaryButton:pressed {{
        background-color: {accent_pressed};
        border-color: {accent_pressed};
    }}
    QPushButton#RibbonButton {{
        background-color: {entry};
        color: {text};
        border: 1px solid {border_soft};
        min-width: 62px;
        padding: 2px 7px;
        font-size: 8.5pt;
        border-radius: 4px;
        min-height: 19px;
    }}
    QPushButton#RibbonButton:hover {{
        background-color: {accent_soft};
        color: {text};
        border-color: {accent};
    }}
    QPushButton#RibbonButton:pressed {{
        background-color: {accent_pressed};
        color: {EATON_WHITE};
    }}
    QPushButton#RibbonButton[ribbonPrimary="true"] {{
        background-color: {accent};
        color: {EATON_WHITE};
        border-color: {accent};
        font-weight: 600;
    }}
    QPushButton#RibbonButton[ribbonPrimary="true"]:hover {{
        background-color: {accent_hover};
        border-color: {accent_hover};
    }}
    QPushButton#RibbonButton:disabled {{
        color: {secondary};
        background-color: {bg};
    }}
    QToolBar {{
        background-color: {plot_container};
        border: none;
        padding: 4px;
        spacing: 3px;
    }}
    QToolButton {{
        background-color: {card_alt};
        color: {text};
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 4px;
    }}
    QToolButton:hover {{
        background-color: {hover};
        border-color: {border};
    }}
    QToolButton:pressed, QToolButton:checked {{
        background-color: {selected};
        border-color: {accent};
    }}
    QComboBox, QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {entry};
        color: {text};
        border: 1px solid {border};
        border-radius: 5px;
        padding: 5px 7px;
        selection-background-color: {selected};
        selection-color: {text};
    }}
    QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {accent};
    }}
    QComboBox:disabled, QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled,
    QSpinBox:disabled, QDoubleSpinBox:disabled {{
        background-color: {bg};
        color: {muted};
        border-color: {border_soft};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px;
        border-left: 1px solid {border_soft};
        border-top-right-radius: 5px;
        border-bottom-right-radius: 5px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {entry};
        color: {text};
        border: 1px solid {border};
        selection-background-color: {selected};
        selection-color: {text};
        outline: none;
    }}
    QCheckBox {{
        color: {text};
        spacing: 7px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        background-color: {entry};
        border: 1px solid {border};
        border-radius: 3px;
    }}
    QCheckBox::indicator:hover {{
        border-color: {accent};
    }}
    QCheckBox::indicator:checked {{
        background-color: {accent};
        border-color: {accent_hover};
    }}
    QTableView, QTableWidget, QTreeView, QListView, QListWidget {{
        background-color: {card};
        alternate-background-color: {tree_alt};
        color: {text};
        gridline-color: {border_soft};
        border: 1px solid {border};
        border-radius: 5px;
        selection-background-color: {accent_soft};
        selection-color: {text};
        outline: none;
    }}
    QTableView::item, QTableWidget::item, QListView::item, QListWidget::item {{
        padding: 3px 6px;
        border: none;
    }}
    QTableView::item:hover, QTableWidget::item:hover, QListView::item:hover, QListWidget::item:hover {{
        background-color: {hover};
    }}
    QTableView::item:selected, QTableWidget::item:selected, QListView::item:selected, QListWidget::item:selected {{
        background-color: {selected};
        color: {text};
    }}
    QHeaderView::section {{
        background-color: {table_header_bg};
        color: {EATON_WHITE};
        padding: 5px 8px;
        border: none;
        border-right: 1px solid {border};
        border-bottom: 1px solid {border};
        font-weight: 600;
    }}
    QTableCornerButton::section {{
        background-color: {table_header_bg};
        border: none;
        border-right: 1px solid {border};
        border-bottom: 1px solid {border};
    }}
    QTabWidget::pane {{
        border: 1px solid {border};
        background-color: {card};
        border-radius: 6px;
        top: -2px;
    }}
    QTabBar::tab {{
        background-color: {card_alt};
        color: {text};
        padding: 7px 14px;
        border: 1px solid {border_soft};
        border-bottom-color: {border};
        border-top-left-radius: 5px;
        border-top-right-radius: 5px;
        margin-right: 2px;
    }}
    QTabBar::tab:hover {{
        background-color: {hover};
        border-color: {border};
    }}
    QTabBar::tab:selected {{
        background-color: {card};
        color: {text};
        border-color: {accent};
        border-bottom-color: {card};
        border-top: 2px solid {accent};
    }}
    QTabBar::tab:disabled {{
        color: {muted};
    }}
    QTabBar#PlotProfileTabs::tab {{
        background-color: {entry};
        color: {secondary};
        padding: 6px 14px;
        border: 1px solid {border_soft};
        border-radius: 5px;
        margin-right: 4px;
    }}
    QTabBar#PlotProfileTabs::tab:selected {{
        background-color: {card};
        color: {text};
        border-color: {accent};
        border-top: 2px solid {accent};
    }}
    QWidget#MatplotlibCanvas {{
        background-color: {plot_container};
        border: 1px solid {border};
        border-radius: 6px;
    }}
    QWidget#MatplotlibFigureCanvas {{
        background-color: {plot_bg};
        border: 1px solid {border_soft};
        border-radius: 4px;
    }}
    QSplitter#PlotLegendSplitter::handle {{
        background-color: {border};
        width: 5px;
    }}
    QStatusBar {{
        background-color: {card};
        color: {secondary};
        border-top: 1px solid {border};
    }}
    QMenuBar, QMenu {{
        background-color: {card};
        color: {text};
        border: 1px solid {border_soft};
    }}
    QMenuBar::item {{
        background-color: transparent;
        padding: 4px 8px;
    }}
    QMenu::item {{
        padding: 5px 24px 5px 22px;
    }}
    QMenuBar::item:selected, QMenu::item:selected {{
        background-color: {hover};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {border_soft};
        margin: 4px 8px;
    }}
    QScrollBar:vertical {{
        background-color: {bg};
        width: 12px;
        margin: 0;
    }}
    QScrollBar:horizontal {{
        background-color: {bg};
        height: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background-color: {border};
        border-radius: 5px;
        min-height: 24px;
        min-width: 24px;
    }}
    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
        background-color: {accent_soft};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        width: 0px;
        height: 0px;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
    }}
    """
