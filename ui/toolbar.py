"""Custom Matplotlib toolbar with styled CTk buttons."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


class CustomToolbar(ctk.CTkFrame):
    """Toolbar wrapping Matplotlib's NavigationToolbar with CTk styling.

    The native toolbar is hidden; its methods are called via CTk buttons.
    """

    def __init__(
        self,
        master,
        canvas: FigureCanvasTkAgg,
        on_toggle_data: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.canvas = canvas

        # Hidden native toolbar (provides Home/Back/Fwd/Pan/Zoom logic)
        self._nav = NavigationToolbar2Tk(canvas, self)
        self._nav.pack_forget()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(8, weight=1)

        kw = dict(height=28, corner_radius=6, font=ctk.CTkFont(size=12))

        ctk.CTkButton(self, text="Home", command=self._nav.home,
                       width=55, **kw).grid(row=0, column=1, padx=3, pady=4)
        ctk.CTkButton(self, text="Back", command=self._nav.back,
                       width=55, **kw).grid(row=0, column=2, padx=3, pady=4)
        ctk.CTkButton(self, text="Fwd", command=self._nav.forward,
                       width=55, **kw).grid(row=0, column=3, padx=3, pady=4)
        ctk.CTkButton(self, text="Pan", command=self._nav.pan,
                       width=55, **kw).grid(row=0, column=4, padx=3, pady=4)
        ctk.CTkButton(self, text="Zoom", command=self._nav.zoom,
                       width=55, **kw).grid(row=0, column=5, padx=3, pady=4)
        ctk.CTkButton(self, text="Save", command=self._nav.save_figure,
                       width=55, **kw).grid(row=0, column=6, padx=3, pady=4)

        self._data_btn = ctk.CTkButton(
            self, text="Data", command=on_toggle_data, width=55, **kw,
        )
        self._data_btn.grid(row=0, column=7, padx=3, pady=4)

    def activate_pan(self) -> None:
        """Enable pan mode by default."""
        self._nav.pan()

    def set_data_button_text(self, text: str) -> None:
        """Update the data-toggle button label."""
        self._data_btn.configure(text=text)
