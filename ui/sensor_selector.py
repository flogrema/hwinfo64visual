"""Sensor selection widget with category pills, text search, and checkboxes."""

from __future__ import annotations

import logging
from typing import Callable

import customtkinter as ctk

from data.sensors import ALL_CATEGORIES, Sensor

logger = logging.getLogger(__name__)


class SensorSelector(ctk.CTkFrame):
    """Left-panel sensor selection with category filters and live search.

    Layout::

        ┌──────────────────────────┐
        │  🔍  Search sensors…     │
        ├──────────────────────────┤
        │ All CPU GPU Memory …     │  ← category pill buttons
        ├──────────────────────────┤
        │ 3 selected               │
        ├──────────────────────────┤
        │ ☑ CPU Temperature [°C]   │
        │ ☑ GPU Power [W]          │
        │ ☐ +12V [V]               │
        │ …                        │
        └──────────────────────────┘
    """

    def __init__(
        self,
        master,
        on_selection_changed: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)

        self._sensors: list[Sensor] = []
        self._checkboxes: dict[str, ctk.CTkCheckBox] = {}
        self._on_change = on_selection_changed
        self._active_cat: str = "All"
        self._filter_text: str = ""

        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- search entry ---------------------------------------------------
        self._search = ctk.CTkEntry(
            self,
            placeholder_text="Search sensors\u2026",
            height=32, corner_radius=8,
            font=ctk.CTkFont(size=12),
        )
        self._search.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        self._search.bind("<KeyRelease>", self._on_search)

        # --- category pill buttons ------------------------------------------
        cat_frame = ctk.CTkFrame(self, fg_color="transparent")
        cat_frame.grid(row=1, column=0, padx=4, pady=4, sticky="ew")

        self._cat_btns: dict[str, ctk.CTkButton] = {}
        cats = ["All"] + ALL_CATEGORIES
        for i, cat in enumerate(cats):
            btn = ctk.CTkButton(
                cat_frame,
                text=cat, width=50, height=26,
                corner_radius=13,
                font=ctk.CTkFont(size=11),
                fg_color=("#0ea5e9" if cat == "All" else "transparent"),
                text_color=("#f5f5f7" if cat == "All" else "#86868b"),
                hover_color="#1c1c1e",
                border_width=1,
                border_color="#2a2a2e",
                command=lambda c=cat: self._set_category(c),
            )
            btn.grid(row=i // 4, column=i % 4, padx=2, pady=2, sticky="ew")
            cat_frame.grid_columnconfigure(i % 4, weight=1)
            self._cat_btns[cat] = btn

        # --- count label ----------------------------------------------------
        self._count_lbl = ctk.CTkLabel(
            self, text="0 selected",
            font=ctk.CTkFont(size=11), text_color="#86868b",
        )
        self._count_lbl.grid(row=2, column=0, padx=10, pady=(2, 2), sticky="w")

        # --- scrollable checkbox list ---------------------------------------
        self._cb_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._cb_frame.grid(row=3, column=0, padx=4, pady=(0, 4), sticky="nsew")

    # --- public API --------------------------------------------------------

    def set_sensors(self, sensors: list[Sensor]) -> None:
        """Populate the widget with a new sensor list."""
        self._sensors = list(sensors)

        for cb in self._checkboxes.values():
            cb.destroy()
        self._checkboxes.clear()

        for sensor in self._sensors:
            cb = ctk.CTkCheckBox(
                self._cb_frame,
                text=sensor.column,
                command=self._on_toggle,
                font=ctk.CTkFont(size=11),
                height=24,
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=4,
            )
            self._checkboxes[sensor.column] = cb

        self._active_cat = "All"
        self._filter_text = ""
        self._search.delete(0, "end")
        self._refresh()

    def get_selected_columns(self) -> list[str]:
        """Return column names of checked sensors."""
        return [col for col, cb in self._checkboxes.items() if cb.get() == 1]

    def get_selected_sensors(self) -> list[Sensor]:
        """Return ``Sensor`` objects for all checked items."""
        sel = set(self.get_selected_columns())
        return [s for s in self._sensors if s.column in sel]

    def set_selected_columns(self, columns: list[str]) -> None:
        """Programmatically set the checked state from a column list."""
        col_set = set(columns)
        for col, cb in self._checkboxes.items():
            if col in col_set:
                cb.select()
            else:
                cb.deselect()
        self._refresh()

    def reset(self) -> None:
        """Deselect all sensors."""
        for cb in self._checkboxes.values():
            cb.deselect()
        self._refresh()

    # --- internal ----------------------------------------------------------

    def _set_category(self, cat: str) -> None:
        self._active_cat = cat
        for c, btn in self._cat_btns.items():
            if c == cat:
                btn.configure(fg_color="#0ea5e9", text_color="#f5f5f7")
            else:
                btn.configure(fg_color="transparent", text_color="#86868b")
        self._refresh()

    def _on_search(self, _event=None) -> None:
        self._filter_text = self._search.get().strip().lower()
        self._refresh()

    def _on_toggle(self) -> None:
        self._update_count()
        if self._on_change:
            self._on_change()

    def _refresh(self) -> None:
        """Re-layout checkboxes based on category / search / checked state."""
        for cb in self._checkboxes.values():
            cb.pack_forget()

        sensor_by_col = {s.column: s for s in self._sensors}

        visible: list[str] = []
        for s in self._sensors:
            if self._active_cat != "All" and s.category != self._active_cat:
                continue
            if self._filter_text and self._filter_text not in s.column.lower():
                continue
            visible.append(s.column)

        # Checked first, then alphabetical
        checked = sorted(c for c in visible
                         if c in self._checkboxes and self._checkboxes[c].get())
        unchecked = sorted(c for c in visible if c not in checked)

        for col in checked + unchecked:
            self._checkboxes[col].pack(anchor="w", padx=6, pady=1, fill="x")

        self._update_count()

    def _update_count(self) -> None:
        n = len(self.get_selected_columns())
        self._count_lbl.configure(text=f"{n} selected")
