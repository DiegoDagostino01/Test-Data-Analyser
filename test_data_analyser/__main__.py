"""Package entry point — launches the PySide6 application.

``python -m test_data_analyser`` starts the Qt UI. The legacy Tkinter app was
retired once the PySide6 path reached feature parity (Phase 5).
"""
from .qt_app.main_qt import main

raise SystemExit(main())
