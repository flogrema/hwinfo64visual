"""HWInfo64 Visualizer — main application window."""

from __future__ import annotations

import logging
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from config.presets import PresetManager
from data.loader import LoadResult, load_hwinfo_csv
from data.sensors import Sensor
from plotting.plot_manager import BG_COLOR, PlotManager
from ui.data_inspector import DataInspector
from ui.sensor_selector import SensorSelector
from ui.toolbar import CustomToolbar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class App(ctk.CTk):
    """Top-level window — orchestrates data loading, sensor selection,
    plotting, presets, and the data inspector.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("HWInfo64 Visualizer")
        self.geometry("1800x900")
        self.minsize(1000, 600)

        # state
        self._load_result: LoadResult | None = None
        self._loading = False
        self._data_visible = False

        # managers
        self._preset_mgr = PresetManager()

        # ttk dark theme (once)
        DataInspector.configure_dark_style()

        # build UI
        self._build_ui()
        self._refresh_preset_combo()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ============================== left panel ========================
        left = ctk.CTkFrame(self, width=340, corner_radius=0)
        left.grid(row=0, column=0, rowspan=2, sticky="nsw")
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        left.grid_propagate(False)

        # file button
        self._open_btn = ctk.CTkButton(
            left, text="Open CSV File", command=self._open_file,
            height=36, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._open_btn.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")

        # file info
        self._file_lbl = ctk.CTkLabel(
            left, text="No file loaded",
            font=ctk.CTkFont(size=11), text_color="#86868b", anchor="w",
        )
        self._file_lbl.grid(row=1, column=0, padx=12, pady=(0, 4), sticky="ew")

        # sensor selector
        self._selector = SensorSelector(left)
        self._selector.grid(row=2, column=0, padx=6, pady=4, sticky="nsew")

        # presets
        pf = ctk.CTkFrame(left, fg_color="transparent")
        pf.grid(row=3, column=0, padx=8, pady=(4, 4), sticky="ew")
        pf.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(pf, text="Presets",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, columnspan=3, padx=4, pady=(4, 2), sticky="w")

        self._preset_cb = ctk.CTkComboBox(
            pf, values=["No presets available"],
            height=30, corner_radius=6, font=ctk.CTkFont(size=11),
        )
        self._preset_cb.grid(row=1, column=0, columnspan=3, padx=4, pady=2, sticky="ew")

        bk = dict(height=28, corner_radius=6, font=ctk.CTkFont(size=11))
        pf.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(pf, text="Save",   command=self._save_preset,   **bk
                       ).grid(row=2, column=0, padx=(4, 2), pady=4, sticky="ew")
        ctk.CTkButton(pf, text="Apply",  command=self._apply_preset,  **bk
                       ).grid(row=2, column=1, padx=2,       pady=4, sticky="ew")
        ctk.CTkButton(pf, text="Delete", command=self._delete_preset, **bk
                       ).grid(row=2, column=2, padx=(2, 4),  pady=4, sticky="ew")

        # action buttons
        af = ctk.CTkFrame(left, fg_color="transparent")
        af.grid(row=4, column=0, padx=8, pady=(2, 10), sticky="ew")
        af.grid_columnconfigure((0, 1), weight=1)

        self._viz_btn = ctk.CTkButton(
            af, text="Visualize", command=self._visualize,
            height=36, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0ea5e9", hover_color="#0284c7",
        )
        self._viz_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        ctk.CTkButton(
            af, text="Reset", command=self._reset,
            height=36, corner_radius=8, font=ctk.CTkFont(size=13),
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # ============================ centre panel ========================
        self._right = ctk.CTkFrame(self, fg_color="transparent")
        self._right.grid(row=0, column=1, rowspan=2, sticky="nsew",
                         padx=(0, 6), pady=6)
        self._right.grid_rowconfigure(0, weight=1)
        self._right.grid_columnconfigure(0, weight=1)

        # plot frame
        pframe = ctk.CTkFrame(self._right, corner_radius=8)
        pframe.grid(row=0, column=0, sticky="nsew")
        pframe.grid_rowconfigure(0, weight=1)
        pframe.grid_columnconfigure(0, weight=1)

        self._fig = Figure(figsize=(5, 4), dpi=100, facecolor=BG_COLOR)
        self._canvas = FigureCanvasTkAgg(self._fig, master=pframe)
        self._canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self._plot = PlotManager(self._fig, self._canvas)
        self._plot.show_empty("Open a CSV file to begin")

        # bottom bar (toolbar + slider)
        bot = ctk.CTkFrame(self._right, fg_color="transparent")
        bot.grid(row=1, column=0, pady=(4, 0), sticky="ew")
        bot.grid_columnconfigure(1, weight=1)

        self._toolbar = CustomToolbar(bot, self._canvas,
                                       on_toggle_data=self._toggle_inspector)
        self._toolbar.grid(row=0, column=0, padx=(0, 8), pady=2)
        self._toolbar.activate_pan()

        self._slider = ctk.CTkSlider(bot, from_=1, to=100,
                                      command=self._on_slider, height=16)
        self._slider.set(100)
        self._slider.grid(row=0, column=1, padx=4, pady=2, sticky="ew")

        self._slider_lbl = ctk.CTkLabel(
            bot, text="100%", font=ctk.CTkFont(size=11),
            text_color="#86868b", width=45,
        )
        self._slider_lbl.grid(row=0, column=2, padx=(4, 8), pady=2)

        # inspector (hidden)
        self._inspector = DataInspector(self._right)

        # ============================== legend ============================
        self._legend = ctk.CTkScrollableFrame(self, width=200)
        self._legend.grid(row=0, column=2, rowspan=2,
                          padx=(0, 6), pady=6, sticky="nsew")
        self.grid_columnconfigure(2, weight=0)

    # --------------------------------------------------------------- file I/O

    def _open_file(self) -> None:
        if self._loading:
            return
        path = filedialog.askopenfilename(
            title="Select a HWiNFO64 CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        self._loading = True
        self._open_btn.configure(state="disabled")
        self._file_lbl.configure(text="Loading\u2026", text_color="#0ea5e9")
        threading.Thread(target=self._load_worker, args=(path,),
                         daemon=True).start()

    def _load_worker(self, path: str) -> None:
        try:
            result = load_hwinfo_csv(path)
            self.after(0, lambda: self._on_loaded(result))
        except Exception as exc:
            logger.exception("CSV load failed")
            msg = str(exc)
            self.after(0, lambda: self._on_load_error(msg))

    def _on_loaded(self, result: LoadResult) -> None:
        self._loading = False
        self._load_result = result
        self._open_btn.configure(state="normal")

        short = result.file_path
        if len(short) > 50:
            short = "\u2026" + short[-47:]
        self._file_lbl.configure(
            text=f"{short}  ({result.row_count} rows, "
                 f"{result.sensor_count} sensors)",
            text_color="#86868b",
        )
        self._selector.set_sensors(result.sensors)
        self._slider.set(100)
        self._slider_lbl.configure(text="100%")
        self._plot.show_empty("Select sensors and click Visualize")

        if result.skipped_columns:
            logger.info("Skipped %d non-numeric columns.",
                        len(result.skipped_columns))

    def _on_load_error(self, msg: str) -> None:
        self._loading = False
        self._open_btn.configure(state="normal")
        self._file_lbl.configure(text="Load failed", text_color="#ff6b6b")
        messagebox.showerror("Load Error",
                             f"Failed to load file:\n\n{msg}")

    # --------------------------------------------------------- visualisation

    def _visualize(self) -> None:
        if self._load_result is None:
            messagebox.showinfo("No Data", "Please load a CSV file first.")
            return

        selected = self._selector.get_selected_sensors()
        if not selected:
            self._plot.show_empty("Select sensors to visualize")
            self._update_legend([])
            return

        skipped = self._plot.plot_sensors(self._load_result.df, selected)
        self._update_legend(selected)

        if self._data_visible:
            cols = [s.column for s in selected]
            self._inspector.update_data(self._load_result.df, cols)

        if skipped:
            messagebox.showwarning(
                "Skipped Sensors",
                "The following sensors had no valid data:\n\n"
                + "\n".join(f"\u2022 {n}" for n in skipped),
            )

    def _update_legend(self, sensors: list[Sensor]) -> None:
        for w in self._legend.winfo_children():
            w.destroy()
        if not sensors:
            self._legend.grid_forget()
            return
        self._legend.grid(row=0, column=2, rowspan=2,
                          padx=(0, 6), pady=6, sticky="nsew")
        colors = self._plot.get_line_colors()
        for s in sensors:
            c = colors.get(s.name, "#f5f5f7")
            ctk.CTkLabel(
                self._legend, text=s.name,
                text_color=c, font=ctk.CTkFont(size=10), anchor="w",
            ).pack(anchor="w", padx=8, pady=1, fill="x")

    def _on_slider(self, value: float) -> None:
        pct = int(value)
        self._slider_lbl.configure(text=f"{pct}%")
        self._plot.update_x_range(pct)

    # ------------------------------------------------------------ inspector

    def _toggle_inspector(self) -> None:
        if self._data_visible:
            self._inspector.grid_forget()
            self._toolbar.set_data_button_text("Data")
            self._data_visible = False
            self._right.grid_columnconfigure(1, weight=0)
        else:
            self._right.grid_columnconfigure(1, weight=1)
            self._inspector.grid(row=0, column=1, rowspan=2,
                                  sticky="nsew", padx=(4, 0))
            self._toolbar.set_data_button_text("Hide")
            self._data_visible = True
            if self._load_result:
                cols = self._selector.get_selected_columns()
                if cols:
                    self._inspector.update_data(self._load_result.df, cols)

    # ----------------------------------------------------------- selections

    def _reset(self) -> None:
        self._selector.reset()
        self._slider.set(100)
        self._slider_lbl.configure(text="100%")
        msg = ("Select sensors to visualize"
               if self._load_result else "Open a CSV file to begin")
        self._plot.show_empty(msg)
        self._update_legend([])

    # -------------------------------------------------------------- presets

    def _refresh_preset_combo(self) -> None:
        names = self._preset_mgr.list_presets()
        if names:
            self._preset_cb.configure(values=["Select a preset\u2026"] + names)
            self._preset_cb.set("Select a preset\u2026")
        else:
            self._preset_cb.configure(values=["No presets available"])
            self._preset_cb.set("No presets available")

    def _save_preset(self) -> None:
        cols = self._selector.get_selected_columns()
        if not cols:
            messagebox.showwarning("No Selection",
                                   "Select at least one sensor first.")
            return
        dialog = ctk.CTkInputDialog(text="Enter preset name:",
                                     title="Save Preset")
        name = dialog.get_input()
        if name and name.strip():
            pct = int(self._slider.get())
            ok = self._preset_mgr.save_preset(name.strip(), cols,
                                               time_range=pct)
            if ok:
                self._refresh_preset_combo()
            else:
                messagebox.showerror("Save Error",
                                     "Failed to save preset to disk.")

    def _apply_preset(self) -> None:
        name = self._preset_cb.get()
        preset = self._preset_mgr.get_preset(name)
        if preset is None:
            messagebox.showwarning("Invalid Preset",
                                   "Please select a valid preset.")
            return
        self._selector.set_selected_columns(preset.columns)
        self._slider.set(preset.time_range)
        self._slider_lbl.configure(text=f"{preset.time_range}%")
        self._visualize()

    def _delete_preset(self) -> None:
        name = self._preset_cb.get()
        if self._preset_mgr.get_preset(name) is None:
            messagebox.showwarning("Invalid Preset",
                                   "Please select a valid preset to delete.")
            return
        if messagebox.askyesno("Delete Preset",
                               f"Delete preset '{name}'?"):
            self._preset_mgr.delete_preset(name)
            self._refresh_preset_combo()

    # ---------------------------------------------------------------- close

    def destroy(self) -> None:
        self._plot.cleanup()
        super().destroy()
