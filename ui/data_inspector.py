"""Paginated data inspector using ttk.Treeview.

Renders up to ``PAGE_SIZE`` rows at a time with Prev / Next navigation,
avoiding the pathological performance of inserting hundreds of thousands
of Treeview items.
"""

from __future__ import annotations

import logging
from tkinter import ttk

import customtkinter as ctk
import pandas as pd

logger = logging.getLogger(__name__)

PAGE_SIZE = 500


class DataInspector(ctk.CTkFrame):
    """Tabular data view with pagination for large DataFrames."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._df: pd.DataFrame | None = None
        self._display_cols: list[str] = []
        self._page = 0
        self._total_pages = 0

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Treeview -------------------------------------------------------
        self._tree = ttk.Treeview(self, show="headings")
        self._tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self._tree.configure(xscrollcommand=hsb.set)

        # --- Pagination bar -------------------------------------------------
        nav = ctk.CTkFrame(self, height=36)
        nav.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        nav.grid_columnconfigure(2, weight=1)

        bkw = dict(width=70, height=26, corner_radius=4,
                    font=ctk.CTkFont(size=11))

        self._prev_btn = ctk.CTkButton(nav, text="\u25c0 Prev",
                                        command=self._prev, **bkw)
        self._prev_btn.grid(row=0, column=0, padx=4, pady=4)

        self._next_btn = ctk.CTkButton(nav, text="Next \u25b6",
                                        command=self._next, **bkw)
        self._next_btn.grid(row=0, column=1, padx=4, pady=4)

        self._info = ctk.CTkLabel(nav, text="No data",
                                   font=ctk.CTkFont(size=11),
                                   text_color="#86868b")
        self._info.grid(row=0, column=2, padx=8, pady=4, sticky="e")

    # --- public API ---------------------------------------------------------

    def update_data(
        self,
        df: pd.DataFrame | None,
        columns: list[str] | None = None,
    ) -> None:
        """Replace the displayed data.

        Args:
            df: Source DataFrame (must contain ``Timestamp``).
            columns: Sensor column names to show.  ``None`` → all.
        """
        if df is None or df.empty:
            self._df = None
            self._clear()
            self._info.configure(text="No data")
            return

        self._df = df
        ts_col = df.columns[0]
        if columns:
            self._display_cols = [ts_col] + [c for c in columns
                                              if c in df.columns]
        else:
            self._display_cols = list(df.columns)

        self._total_pages = max(1, -(-len(df) // PAGE_SIZE))  # ceil div
        self._page = 0

        self._tree["columns"] = self._display_cols
        for col in self._display_cols:
            w = 170 if col == ts_col else 130
            self._tree.heading(col, text=col, anchor="w")
            self._tree.column(col, width=w, anchor="w", minwidth=80)

        self._render()

    # --- pagination ---------------------------------------------------------

    def _render(self) -> None:
        self._tree.delete(*self._tree.get_children())
        if self._df is None:
            return

        start = self._page * PAGE_SIZE
        end = min(start + PAGE_SIZE, len(self._df))
        chunk = self._df.iloc[start:end]
        ts_col = self._display_cols[0] if self._display_cols else None

        for _, row in chunk.iterrows():
            vals: list[str] = []
            for col in self._display_cols:
                v = row[col]
                if col == ts_col and hasattr(v, "strftime"):
                    vals.append(v.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
                elif pd.isna(v):
                    vals.append("")
                else:
                    try:
                        vals.append(f"{float(v):.3f}")
                    except (ValueError, TypeError):
                        vals.append(str(v))
            self._tree.insert("", "end", values=vals)

        total = len(self._df)
        self._info.configure(
            text=(f"Rows {start + 1}\u2013{end} of {total}  |  "
                  f"Page {self._page + 1}/{self._total_pages}")
        )
        self._prev_btn.configure(
            state="normal" if self._page > 0 else "disabled")
        self._next_btn.configure(
            state="normal" if self._page < self._total_pages - 1 else "disabled")

    def _prev(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._render()

    def _next(self) -> None:
        if self._page < self._total_pages - 1:
            self._page += 1
            self._render()

    def _clear(self) -> None:
        self._tree.delete(*self._tree.get_children())
        self._tree["columns"] = []

    # --- Treeview dark-mode style (call once at app startup) ----------------

    @staticmethod
    def configure_dark_style() -> None:
        """Apply Apple-inspired dark theme to ttk Treeview globally."""
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#141416",
            foreground="#f5f5f7",
            fieldbackground="#141416",
            borderwidth=0,
            rowheight=24,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#1c1c1e",
            foreground="#f5f5f7",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Treeview.Heading", background=[("active", "#2a2a2e")])
        style.map("Treeview", background=[("selected", "#0ea5e9")])
