from __future__ import annotations

import tkinter as tk

from .gui import TestDataAnalyserGUI

def main() -> None:
    root = tk.Tk()
    TestDataAnalyserGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
