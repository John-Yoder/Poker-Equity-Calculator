#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
from gui_equity import EquityGUI
from gui_range import RangeComparisonTab

def main():
    root = tk.Tk()
    root.title("Texas Hold'em Equity & Range Comparator")
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True)
    
    frame1 = tk.Frame(notebook)
    EquityGUI(frame1)
    notebook.add(frame1, text="Equity Calculator")
    
    frame2 = tk.Frame(notebook)
    RangeComparisonTab(frame2)
    notebook.add(frame2, text="Range Comparison")
    
    root.mainloop()

if __name__ == '__main__':
    main()
