"""Guided application help window.

This dialog is intentionally self-contained UI help content. It lives in the Qt
layer so it can use PySide6 widgets without adding dependencies to services,
viewmodels, or domain code.
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...core.config import __version__, EATON_HEADER_BLUE, EATON_WHITE, theme_palette


HELP_PAGE_BODIES: dict[str, str] = {
    "Getting Started": """
        <p><b>Test Data Analyser</b> is used to load test data, select channels, generate plots,
        compare runs, review statistics, apply requirements, and prepare engineering notes.</p>
        <h2>Normal workflow</h2>
        <ol>
            <li>Open a data file.</li>
            <li>Choose the X-axis column.</li>
            <li>Select one or more Y-axis channels.</li>
            <li>Generate a plot.</li>
            <li>Review statistics, limits, margins, and notes.</li>
            <li>Save the plot, export data, or save the session.</li>
        </ol>
        <h2>Main areas</h2>
        <ul>
            <li><b>Top ribbon:</b> file, plot, analysis, requirements, and notes commands.</li>
            <li><b>Left plot-control panel:</b> data file controls, X-axis selection, and Y-axis channel selection.</li>
            <li><b>Central plot area:</b> the active chart and plot navigation tools.</li>
            <li><b>Right legend panel:</b> plotted series identification and legend visibility.</li>
            <li><b>Lower area:</b> run management, statistics, raw data, maths channels, limits, margins, and notes.</li>
        </ul>
        <div class="tip">Start with a data file and a simple plot. Add comparison runs, limits, notes,
        and exports once the basic view is clear.</div>
    """,
    "Typical Workflow": """
        <h2>Step 1 - Load Data</h2>
        <p>Use <b>Open Data</b> to load a CSV or Excel test data file.</p>
        <h2>Step 2 - Select Axes</h2>
        <p>Choose the X-axis column, then select primary and/or secondary Y-axis channels.</p>
        <h2>Step 3 - Generate Plot</h2>
        <p>Click <b>Generate Plot</b> to display the selected data.</p>
        <h2>Step 4 - Review Plot</h2>
        <p>Use home, back, forward, pan, zoom, legend, and axis editing tools to inspect the data.</p>
        <h2>Step 5 - Add Runs or Comparisons</h2>
        <p>Use the run-management tools to compare multiple data sets or repeated tests.</p>
        <h2>Step 6 - Analyse</h2>
        <p>Use <b>Statistics</b>, <b>Raw Data</b>, <b>Maths Channels</b>, and <b>Cursor</b> tools to inspect the data.</p>
        <h2>Step 7 - Document</h2>
        <p>Use <b>Engineering Notes</b> and <b>Copy Notes</b> to capture conclusions.</p>
        <h2>Step 8 - Save or Export</h2>
        <p>Use <b>Save Plot</b>, <b>Save Session</b>, <b>Load Session</b>, and <b>Export Data</b> as required.</p>
    """,
    "File Ribbon": """
        <h2>Open Data</h2>
        <p>Loads a new test data file into the application. Load data before selecting plot channels.</p>
        <h2>Save Session</h2>
        <p>Saves the current working session so it can be restored later. Where supported, this preserves the
        active setup, plot selections, notes, requirements, runs, and related state.</p>
        <h2>Load Session</h2>
        <p>Loads a previously saved session and restores the working context.</p>
        <h2>Export Data</h2>
        <p>Exports processed or selected data for use outside the application.</p>
        <div class="tip">Start with <b>Open Data</b>. Channel lists, plot generation, and most analysis tools depend
        on a loaded data file.</div>
    """,
    "Plot Ribbon": """
        <h2>Generate Plot</h2>
        <p>Generates the plot using the currently selected X-axis and Y-axis channels.</p>
        <h2>Clear Plot</h2>
        <p>Clears the current plot area.</p>
        <h2>Save Plot</h2>
        <p>Saves the current plot image after you have finalised the view, labels, axes, and legend.</p>
        <h2>Runs / Comparison</h2>
        <p>Opens or focuses tools related to comparing multiple runs.</p>
        <h2>What affects the plot?</h2>
        <ul>
            <li>Selected X-axis column.</li>
            <li>Selected primary Y-axis channels.</li>
            <li>Selected secondary Y-axis channels.</li>
            <li>Active and enabled runs.</li>
            <li>Current axis and legend options.</li>
        </ul>
    """,
    "Analysis Ribbon": """
        <h2>Statistics</h2>
        <p>Displays summary statistics for selected channels, such as count, minimum, maximum, mean, and
        standard deviation where available.</p>
        <h2>Raw Data</h2>
        <p>Shows the loaded raw data in table form for inspection, editing workflows, and export.</p>
        <h2>Maths Channels</h2>
        <p>Provides access to calculated or derived channels where supported by the current data and formulas.</p>
        <h2>Cursor</h2>
        <p>Enables cursor-based inspection of plotted data where supported.</p>
        <div class="tip">Analysis tools are most useful after you have selected channels and generated a plot.</div>
    """,
    "Requirements Ribbon": """
        <h2>Limits</h2>
        <p>Used to view or configure requirement limits for plotted or analysed channels.</p>
        <h2>Margins</h2>
        <p>Used to assess margin against limits where requirement data is available.</p>
        <h2>Refresh</h2>
        <p>Refreshes requirement-related display information and updates the relevant plot or summary views.</p>
        <div class="tip">Requirement tools help compare test data against engineering acceptance criteria. The user
        remains responsible for confirming that the correct limits, units, and test context are being used.</div>
    """,
    "Notes Ribbon": """
        <h2>Engineering Notes</h2>
        <p>Opens or focuses the engineering notes area.</p>
        <h2>Refresh Report Text</h2>
        <p>Refreshes generated report-style text based on the current plot, data, or analysis context.</p>
        <h2>Clear Notes</h2>
        <p>Clears the notes area after confirmation where required.</p>
        <h2>Copy Notes</h2>
        <p>Copies the notes text for use in reports, emails, or engineering summaries.</p>
        <div class="tip">Review notes before using them in formal documentation.</div>
    """,
    "Plot Controls": """
        <h2>X-axis column</h2>
        <p>Selects the data column used for the horizontal axis.</p>
        <h2>Channel group</h2>
        <p>Filters or groups available channels so selection is easier in large data files.</p>
        <h2>Primary Y-axis channels</h2>
        <p>Channels plotted against the left Y-axis.</p>
        <h2>Secondary Y-axis channels</h2>
        <p>Channels plotted against the right Y-axis.</p>
        <h2>Select All / Clear All</h2>
        <p>Quickly selects or clears channel selections within the current channel group.</p>
        <h2>Plot Options</h2>
        <p>Contains additional options affecting how plots are generated or displayed.</p>
        <h2>Best practice</h2>
        <ul>
            <li>Avoid plotting too many channels at once.</li>
            <li>Use meaningful X-axis channels.</li>
            <li>Use the secondary Y-axis when channels have different units or scales.</li>
            <li>Keep colour readability in mind when comparing multiple runs.</li>
        </ul>
    """,
    "Run Management": """
        <h2>Add Run</h2>
        <p>Adds another run or dataset to the comparison table.</p>
        <h2>Remove Run</h2>
        <p>Removes the selected run.</p>
        <h2>Duplicate Run</h2>
        <p>Duplicates an existing run setup.</p>
        <h2>Rename Run</h2>
        <p>Renames a run to make the comparison clearer.</p>
        <h2>Set Active</h2>
        <p>Sets the selected run as the active run.</p>
        <h2>Toggle Enabled</h2>
        <p>Includes or excludes a run from plotting or comparison without deleting it.</p>
        <h2>Generate Comparison Plot</h2>
        <p>Generates a plot comparing enabled runs.</p>
        <h2>Prefix legend labels with run name</h2>
        <p>Adds run names to legend labels. This is useful when the same channels are shown across multiple runs.</p>
        <h2>Use common X range only</h2>
        <p>Restricts comparison plots to the shared X-axis range between runs.</p>
        <div class="tip">Run comparison is useful for repeated tests, baseline versus modified configurations,
        and different operating conditions.</div>
    """,
    "Plot Interaction": """
        <h2>Home</h2>
        <p>Resets the plot view.</p>
        <h2>Back / Forward</h2>
        <p>Moves through previous plot view states.</p>
        <h2>Pan</h2>
        <p>Allows the user to drag the plot view.</p>
        <h2>Zoom</h2>
        <p>Allows the user to zoom into a region.</p>
        <h2>Edit Axis</h2>
        <p>Allows axis limits or labels to be adjusted where supported.</p>
        <h2>Legend Panel</h2>
        <p>Shows plotted series and helps identify channels.</p>
        <div class="tip">Combine zoom, pan, and axis editing to inspect local behaviour in the data.</div>
    """,
    "Exporting and Sessions": """
        <h2>Save Plot</h2>
        <p>Use this when you want an image of the current plot.</p>
        <h2>Export Data</h2>
        <p>Use this when you want data output for external analysis or reporting.</p>
        <h2>Save Session</h2>
        <p>Use this when you want to preserve the current working state.</p>
        <h2>Load Session</h2>
        <p>Use this when you want to continue from a previous working state.</p>
        <h2>Best practice</h2>
        <ul>
            <li>Save sessions before making major changes.</li>
            <li>Use clear filenames.</li>
            <li>Export data when traceability is needed outside the app.</li>
            <li>Save plots after finalising axis ranges, labels, and legend clarity.</li>
        </ul>
    """,
    "Troubleshooting": """
        <h2>No file loaded</h2>
        <p>Load a data file before selecting channels or generating plots.</p>
        <h2>No channels appear</h2>
        <p>Check that the file loaded correctly and that the correct channel group is selected.</p>
        <h2>Plot is blank</h2>
        <p>Confirm that an X-axis column and at least one Y-axis channel are selected.</p>
        <h2>Too many lines on the plot</h2>
        <p>Reduce the number of selected channels or use run comparison carefully.</p>
        <h2>Secondary axis is confusing</h2>
        <p>Use the secondary axis only for channels with different units or scales.</p>
        <h2>Legend is unclear</h2>
        <p>Enable run-name prefixes when comparing the same channels across multiple runs.</p>
        <h2>Export does not show expected data</h2>
        <p>Confirm that the correct run, channels, and plot configuration are active before exporting.</p>
    """,
    "About": f"""
        <p><b>Test Data Analyser - Eaton Edition</b></p>
        <p><b>Version:</b> {__version__}</p>
        <p>A desktop tool for loading, plotting, comparing, analysing, and documenting engineering test data.</p>
        <p>This Help window provides guidance on the main workflow, ribbon buttons, plot controls, run comparison,
        and analysis tools.</p>
    """,
}


class HelpDialog(QDialog):
    """Modeless help window for new Test Data Analyser users."""

    def __init__(self, parent: QWidget | None = None, theme_name: str = "light") -> None:
        super().__init__(parent)
        self._theme_name = theme_name
        self._pages = self._build_pages()
        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._select_initial_page()

    def apply_theme(self, theme_name: str) -> None:
        """Refresh dialog colours after the application theme changes."""
        self._theme_name = theme_name
        self._pages = self._build_pages()
        self._apply_styles()
        current = self.topic_list.currentItem()
        if current is not None:
            self._on_topic_selected(current, None)

    def _setup_window(self) -> None:
        self.setWindowTitle("Test Data Analyser Help")
        self.resize(1050, 720)
        self.setMinimumSize(850, 560)
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_navigation_panel())
        splitter.addWidget(self._build_content_panel())
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 790])
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("HelpCloseButton")
        footer.addWidget(self.close_button)
        root.addLayout(footer)

        self._apply_styles()

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HelpHeader")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)

        title = QLabel("Test Data Analyser Help")
        title.setObjectName("HelpTitle")
        subtitle = QLabel("Workflow guidance, ribbon reference, plotting help, and troubleshooting")
        subtitle.setObjectName("HelpSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    def _build_navigation_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("HelpNavigationPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("HelpSearchBox")
        self.search_box.setPlaceholderText("Search help topics...")
        layout.addWidget(self.search_box)

        self.topic_list = QListWidget()
        self.topic_list.setObjectName("HelpTopicList")
        for title in self._pages:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, title)
            item.setToolTip(title)
            self.topic_list.addItem(item)
        layout.addWidget(self.topic_list, 1)

        return panel

    def _build_content_panel(self) -> QTextBrowser:
        self.content_browser = QTextBrowser()
        self.content_browser.setObjectName("HelpContent")
        self.content_browser.setOpenExternalLinks(True)
        return self.content_browser

    def _connect_signals(self) -> None:
        self.topic_list.currentItemChanged.connect(self._on_topic_selected)
        self.search_box.textChanged.connect(self._filter_topics)
        self.close_button.clicked.connect(self.close)

    def _select_initial_page(self) -> None:
        if self.topic_list.count() > 0:
            self.topic_list.setCurrentRow(0)

    def _on_topic_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is None:
            return
        title = str(current.data(Qt.ItemDataRole.UserRole) or current.text())
        self.content_browser.setHtml(self._pages.get(title, ""))

    def _filter_topics(self, text: str) -> None:
        query = text.strip().lower()
        first_visible_row = -1
        for row in range(self.topic_list.count()):
            item = self.topic_list.item(row)
            title = str(item.data(Qt.ItemDataRole.UserRole) or item.text())
            hidden = bool(query) and query not in self._searchable_page_text(title)
            item.setHidden(hidden)
            if not hidden and first_visible_row < 0:
                first_visible_row = row

        current = self.topic_list.currentItem()
        if current is not None and not current.isHidden():
            return
        if first_visible_row >= 0:
            self.topic_list.setCurrentRow(first_visible_row)
            return
        if query:
            self.content_browser.setHtml(
                self._html_page(
                    "No Matching Topics",
                    "<p>No help topics matched the current search. Clear the search box to show all topics.</p>",
                )
            )

    def _searchable_page_text(self, title: str) -> str:
        html = self._pages.get(title, "")
        plain_text = re.sub(r"<[^>]+>", " ", html)
        return f"{title} {plain_text}".lower()

    def _build_pages(self) -> dict[str, str]:
        return {title: self._html_page(title, body) for title, body in HELP_PAGE_BODIES.items()}

    def _html_page(self, title: str, body: str) -> str:
        palette = theme_palette(self._theme_name)
        text = palette["text"]
        secondary = palette["secondary"]
        border = palette["border"]
        card = palette["card"]
        accent = palette["accent"]
        accent_hover = palette["accent_hover"]
        accent_soft = palette["accent_soft"]
        return f"""
        <html>
        <head>
            <style>
                body {{
                    background-color: {card};
                    color: {text};
                    font-family: Segoe UI, Arial, sans-serif;
                    font-size: 10.5pt;
                    line-height: 1.45;
                }}
                h1 {{
                    color: {accent};
                    border-bottom: 2px solid {border};
                    padding-bottom: 6px;
                    margin-top: 0;
                }}
                h2 {{ color: {accent_hover}; margin-top: 18px; }}
                h3 {{ color: {accent_hover}; margin-top: 14px; margin-bottom: 4px; }}
                p {{ margin: 8px 0; }}
                ul, ol {{ margin-left: 18px; }}
                li {{ margin-bottom: 4px; }}
                .tip {{
                    background-color: {accent_soft};
                    border-left: 4px solid {accent};
                    color: {text};
                    padding: 8px 10px;
                    margin: 12px 0;
                }}
                .muted {{ color: {secondary}; }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            {body}
        </body>
        </html>
        """

    def _apply_styles(self) -> None:
        palette = theme_palette(self._theme_name)
        bg = palette["bg"]
        card = palette["card"]
        card_alt = palette["card_alt"]
        text = palette["text"]
        border = palette["border"]
        border_soft = palette["border_soft"]
        hover = palette["hover"]
        selected = palette["selected"]
        entry = palette["entry"]
        accent = palette["accent"]
        accent_hover = palette["accent_hover"]
        accent_pressed = palette["accent_pressed"]

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {bg};
                color: {text};
            }}
            QWidget#HelpNavigationPanel {{
                background-color: transparent;
            }}
            QLabel#HelpTitle {{
                font-size: 20px;
                font-weight: bold;
                color: {EATON_WHITE};
            }}
            QLabel#HelpSubtitle {{
                color: {EATON_WHITE};
            }}
            QFrame#HelpHeader {{
                background-color: {EATON_HEADER_BLUE};
                border: none;
                border-radius: 4px;
            }}
            QLineEdit#HelpSearchBox {{
                padding: 6px;
                border: 1px solid {border};
                border-radius: 4px;
                background-color: {entry};
                color: {text};
            }}
            QListWidget#HelpTopicList {{
                background-color: {card};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px;
                color: {text};
            }}
            QListWidget#HelpTopicList::item {{
                padding: 8px;
                border-radius: 4px;
            }}
            QListWidget#HelpTopicList::item:hover {{
                background-color: {hover};
            }}
            QListWidget#HelpTopicList::item:selected {{
                background-color: {accent};
                color: {EATON_WHITE};
            }}
            QTextBrowser#HelpContent {{
                background-color: {card};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 14px;
                color: {text};
            }}
            QPushButton#HelpCloseButton {{
                background-color: {card_alt};
                color: {text};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 6px 14px;
                min-height: 22px;
            }}
            QPushButton#HelpCloseButton:hover {{
                background-color: {hover};
                border-color: {accent};
            }}
            QPushButton#HelpCloseButton:pressed {{
                background-color: {selected};
                border-color: {accent_pressed};
            }}
            QSplitter::handle {{
                background-color: {border_soft};
            }}
            QSplitter::handle:hover {{
                background-color: {accent_hover};
            }}
            """
        )