from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .config import EATON_BG

def _bind_mousewheel_to_canvas(canvas: tk.Canvas) -> None:
    """Attach Enter / Leave mousewheel scrolling to *canvas*."""
    def _on_mousewheel(event) -> str:
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = int(-1 * (event.delta / 120))
        canvas.yview_scroll(delta, "units")
        return "break"

    def _bind(_event=None) -> None:
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

    def _unbind(_event=None) -> None:
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", _bind)
    canvas.bind("<Leave>", _unbind)

def _bind_mousewheel_to_treeview(tree: ttk.Treeview) -> None:
    """Attach mouse-wheel scrolling to a Treeview."""
    def _on_mousewheel(event) -> str:
        if getattr(event, "num", None) == 4:
            delta = -3
        elif getattr(event, "num", None) == 5:
            delta = 3
        else:
            delta = int(-1 * (event.delta / 120)) * 3
        tree.yview_scroll(delta, "units")
        return "break"
    def _bind(_event=None) -> None:
        tree.bind_all("<MouseWheel>", _on_mousewheel)
        tree.bind_all("<Button-4>", _on_mousewheel)
        tree.bind_all("<Button-5>", _on_mousewheel)
    def _unbind(_event=None) -> None:
        tree.unbind_all("<MouseWheel>")
        tree.unbind_all("<Button-4>")
        tree.unbind_all("<Button-5>")
    tree.bind("<Enter>", _bind)
    tree.bind("<Leave>", _unbind)

class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, width: int = 380):
        super().__init__(parent, style="Workspace.TFrame")
        self.canvas = tk.Canvas(self, borderwidth=0, width=width,
                                 highlightthickness=0, bg=EATON_BG)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical",
                                       command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="Workspace.TFrame")
        self.window_id = self.canvas.create_window((0, 0), window=self.inner,
                                                   anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.inner.bind("<Configure>",
                        lambda _e: self.canvas.configure(
                            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(
                             self.window_id, width=e.width))
        _bind_mousewheel_to_canvas(self.canvas)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
