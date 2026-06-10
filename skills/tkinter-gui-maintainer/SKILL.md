---
name: tkinter-gui-maintainer
description: Use this when modifying Tkinter UI layout, widgets, callbacks, tabs, notebooks, treeviews, canvas scrolling, or GUI state.
---

# Tkinter GUI Maintainer

This project uses **Tkinter** and **ttk**.

## Rules

- Do not replace Tkinter with another UI framework.
- Preserve existing widget names and state variables unless intentionally refactoring them.
- Keep callback wiring explicit and readable.
- Avoid circular dependencies between GUI modules.
- When moving GUI methods into mixins, assume widgets are created in `gui_base.py` unless moved in the same refactor.
- Preserve user-facing behaviour unless the prompt explicitly asks for a change.
- Keep Eaton branding and styling constants as currently implemented.
- Be careful with:
  - `ttk.Notebook`
  - `ttk.Treeview`
  - `tk.Canvas` scrolling
  - Tk variables
  - trace callbacks
  - command callbacks
