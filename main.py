import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import threading
from queue import Queue, Empty
import re
import json
import os

# Set the appearance mode
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class CustomToolbar(ctk.CTkFrame):
    def __init__(self, master, canvas, app, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = canvas
        self.app = app
        self.toolbar = NavigationToolbar2Tk(canvas, self)
        self.toolbar.pack_forget()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(8, weight=1)

        self.home_button = ctk.CTkButton(self, text="Home", command=self.toolbar.home, width=60)
        self.home_button.grid(row=0, column=1, padx=5, pady=5)

        self.back_button = ctk.CTkButton(self, text="Back", command=self.toolbar.back, width=60)
        self.back_button.grid(row=0, column=2, padx=5, pady=5)

        self.forward_button = ctk.CTkButton(self, text="Forward", command=self.toolbar.forward, width=70)
        self.forward_button.grid(row=0, column=3, padx=5, pady=5)

        self.pan_button = ctk.CTkButton(self, text="Pan", command=self.toolbar.pan, width=60)
        self.pan_button.grid(row=0, column=4, padx=5, pady=5)

        self.zoom_button = ctk.CTkButton(self, text="Zoom", command=self.toolbar.zoom, width=60)
        self.zoom_button.grid(row=0, column=5, padx=5, pady=5)

        self.save_button = ctk.CTkButton(self, text="Save", command=self.toolbar.save_figure, width=60)
        self.save_button.grid(row=0, column=6, padx=5, pady=5)
        
        self.data_toggle_button = ctk.CTkButton(self, text="Show Data", command=self.app.toggle_data_panel, width=90)
        self.data_toggle_button.grid(row=0, column=7, padx=5, pady=5)

class DataInspectorPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(self, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=hsb.set)

    def update_data(self, df, lines):
        self.tree.delete(*self.tree.get_children())
        
        if df is None or df.empty:
            self.tree["columns"] = []
            return

        df_display = df.copy()
        time_col = df_display.columns[0]
        df_display[time_col] = df_display[time_col].dt.strftime('%Y-%m-%d %H:%M:%S.%f').str[:-3]

        self.tree["columns"] = list(df_display.columns)
        
        color_map = {line.get_label(): line.get_color() for line in lines}

        for col in df_display.columns:
            if col == time_col:
                self.tree.heading(col, text=col, anchor="w")
                self.tree.column(col, width=160, anchor="w")
            else:
                self.tree.heading(col, text="", anchor="w")
                self.tree.column(col, width=150, anchor="w")

        for index, row in df_display.iterrows():
            values = list(row)
            item_tags = []
            for i, val in enumerate(values):
                col_name = df_display.columns[i]
                if col_name != time_col:
                    color = color_map.get(col_name, "#FFFFFF")
                    hex_color = mcolors.to_hex(color)
                    tag_name = f"color_{hex_color.replace('#', '')}"
                    self.tree.tag_configure(tag_name, foreground=hex_color)
                    item_tags.append(tag_name)
                else:
                    item_tags.append("")
            self.tree.insert("", "end", values=values, tags=item_tags)

class CheckboxList(ctk.CTkScrollableFrame):
    def __init__(self, master, columns, **kwargs):
        super().__init__(master, **kwargs)
        self.checkboxes = {}
        self.all_columns = sorted(columns)
        self.display_columns(self.all_columns)

    def display_columns(self, columns_to_display):
        for cb in self.checkboxes.values():
            cb.grid_forget()

        for i, col in enumerate(columns_to_display):
            if col not in self.checkboxes:
                cb = ctk.CTkCheckBox(self, text=col, command=self.sort_list)
                self.checkboxes[col] = cb
            else:
                cb = self.checkboxes[col]
            cb.grid(row=i, column=0, padx=10, pady=5, sticky="w")

    def filter(self, filter_text):
        if not filter_text:
            self.sort_list()
        else:
            checked = {col for col, cb in self.checkboxes.items() if cb.get() == 1}
            filtered_cols = [col for col in self.all_columns if filter_text.lower() in col.lower()]
            
            checked_and_filtered = sorted([col for col in filtered_cols if col in checked])
            unchecked_and_filtered = sorted([col for col in filtered_cols if col not in checked])
            
            self.display_columns(checked_and_filtered + unchecked_and_filtered)

    def get_checked_columns(self):
        return [col for col, cb in self.checkboxes.items() if cb.winfo_ismapped() and cb.get() == 1]

    def sort_list(self):
        checked = sorted([col for col, cb in self.checkboxes.items() if cb.get() == 1])
        unchecked = sorted([col for col in self.all_columns if col not in checked])
        self.display_columns(checked + unchecked)

    def reset(self):
        for cb in self.checkboxes.values():
            cb.deselect()
        self.display_columns(self.all_columns)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("HWInfo64 Visualizer")
        self.geometry("1800x900")
        self.df = None
        self.lines = []
        self.queue = Queue()
        self.loaded_file_path = ""
        self.presets_file = "presets.json"
        self.presets = {}
        self.full_x_range_numeric = None
        self.data_panel_visible = False

        # --- Matplotlib and Style Setup ---
        self.setup_dark_plot_style()
        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor=self.bg_color)
        self.ax = self.fig.add_subplot(111)

        # --- UI Setup ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Frame for Controls
        left_frame = ctk.CTkFrame(self, width=400)
        left_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsw")
        left_frame.grid_rowconfigure(3, weight=1)

        self.open_button = ctk.CTkButton(left_frame, text="Open CSV File", command=self.open_file)
        self.open_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.file_path_label = ctk.CTkLabel(left_frame, text="No file selected", anchor="w")
        self.file_path_label.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.filter_entry = ctk.CTkEntry(left_frame, placeholder_text="Filter columns...")
        self.filter_entry.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.filter_entry.bind("<KeyRelease>", self.on_filter_change)

        self.column_frame = CheckboxList(left_frame, [])
        self.column_frame.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")

        # Preset Frame
        preset_frame = ctk.CTkFrame(left_frame)
        preset_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        preset_frame.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(preset_frame, text="Presets").grid(row=0, column=0, columnspan=3, padx=10, pady=5)

        self.preset_combo = ctk.CTkComboBox(preset_frame, values=[])
        self.preset_combo.grid(row=1, column=0, columnspan=3, padx=10, pady=5, sticky="ew")

        self.save_preset_button = ctk.CTkButton(preset_frame, text="Save", command=self.save_preset)
        self.save_preset_button.grid(row=2, column=0, padx=(10,5), pady=5, sticky="ew")

        self.apply_preset_button = ctk.CTkButton(preset_frame, text="Apply", command=self.apply_preset_selection)
        self.apply_preset_button.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        self.delete_preset_button = ctk.CTkButton(preset_frame, text="Delete", command=self.delete_preset)
        self.delete_preset_button.grid(row=2, column=2, padx=(5,10), pady=5, sticky="ew")

        # Button Frame (Visualize/Reset Selections)
        button_frame = ctk.CTkFrame(left_frame)
        button_frame.grid(row=5, column=0, padx=10, pady=10, sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        self.visualize_button = ctk.CTkButton(button_frame, text="Visualize", command=self.visualize_data)
        self.visualize_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.reset_button = ctk.CTkButton(button_frame, text="Reset Selections", command=self.reset_selections)
        self.reset_button.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # Right Frame for Plot and its controls
        self.right_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 10), pady=10)
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        plot_frame = ctk.CTkFrame(self.right_frame)
        plot_frame.grid(row=0, column=0, sticky="nsew")
        plot_frame.grid_rowconfigure(0, weight=1)
        plot_frame.grid_columnconfigure(0, weight=1)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Bottom controls (Toolbar and Slider)
        bottom_controls_frame = ctk.CTkFrame(self.right_frame)
        bottom_controls_frame.grid(row=1, column=0, pady=(5,0), sticky="ew")
        bottom_controls_frame.grid_columnconfigure(1, weight=1)

        self.toolbar = CustomToolbar(bottom_controls_frame, self.canvas, app=self)
        self.toolbar.grid(row=0, column=0, padx=(0,10), pady=5)
        self.toolbar.toolbar.pan()

        self.x_axis_slider = ctk.CTkSlider(bottom_controls_frame, from_=1, to=100, command=self.update_x_axis_range)
        self.x_axis_slider.set(100)
        self.x_axis_slider.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        self.x_axis_label = ctk.CTkLabel(bottom_controls_frame, text="100%")
        self.x_axis_label.grid(row=0, column=2, padx=10, pady=5)

        # Data Inspector Panel (initially hidden)
        self.data_panel = DataInspectorPanel(self.right_frame)
        
        # Legend Frame
        self.legend_frame = ctk.CTkScrollableFrame(self, width=250)
        self.legend_frame.grid(row=0, column=2, rowspan=2, padx=(0,10), pady=10, sticky="nsew")
        self.grid_columnconfigure(2, weight=0) # Legend column

        self.annot = self.ax.annotate("", xy=(0,0), xytext=(20,20), textcoords="offset points",
                                     bbox=dict(boxstyle="round", fc="#2B2B2B", ec=self.text_color, lw=1),
                                     arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color=self.text_color))
        self.annot.set_visible(False)
        self.fig.canvas.mpl_connect("pick_event", self.on_pick)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)

        self.load_presets()
        self.initialize_plot()

    def toggle_data_panel(self):
        if self.data_panel_visible:
            self.data_panel.grid_forget()
            self.toolbar.data_toggle_button.configure(text="Show Data")
            self.data_panel_visible = False
            self.right_frame.grid_columnconfigure(1, weight=0)
        else:
            self.right_frame.grid_columnconfigure(1, weight=1)
            self.data_panel.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5,0))
            self.toolbar.data_toggle_button.configure(text="Hide Data")
            self.data_panel_visible = True
            selected_columns = self.column_frame.get_checked_columns()
            if selected_columns and self.df is not None:
                time_col = self.df.columns[0]
                self.data_panel.update_data(self.df[[time_col] + selected_columns], self.lines)

    def on_filter_change(self, event):
        filter_text = self.filter_entry.get()
        self.column_frame.filter(filter_text)

    def reset_selections(self):
        self.column_frame.reset()
        self.x_axis_slider.set(100)
        self.update_x_axis_range(100)
        self.visualize_data()

    def setup_dark_plot_style(self):
        self.bg_color = "#2B2B2B"
        self.text_color = "#DCE4EE"
        self.grid_color = "#565B5E"
        self.line_colors = plt.get_cmap('tab10')(np.linspace(0, 1, 10))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=self.bg_color, foreground=self.text_color, fieldbackground=self.bg_color, borderwidth=0)
        style.configure("Treeview.Heading", background="#242424", foreground=self.text_color, relief="flat")
        style.map('Treeview.Heading', background=[('active','#313131')])

    def initialize_plot(self):
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(self.bg_color)
        self.ax.set_title("HWInfo64 Visualizer", color=self.text_color, fontsize=16, fontweight='bold')
        self.ax.set_xlabel("Time", color=self.text_color, fontsize=12)
        self.ax.set_ylabel("Value", color=self.text_color, fontsize=12)
        self.ax.tick_params(axis='x', colors=self.text_color)
        self.ax.tick_params(axis='y', colors=self.text_color)
        self.ax.spines['top'].set_color(self.grid_color)
        self.ax.spines['bottom'].set_color(self.grid_color)
        self.ax.spines['left'].set_color(self.grid_color)
        self.ax.spines['right'].set_color(self.grid_color)
        self.ax.grid(True, which='major', linestyle='--', linewidth='0.5', color=self.grid_color)
        self.annot.set_visible(False)
        self.fig.tight_layout()
        self.canvas.draw()

    def open_file(self):
        file_path = filedialog.askopenfilename(title="Select a HWInfo64 CSV file", filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))
        if file_path:
            self.loaded_file_path = file_path
            self.file_path_label.configure(text="Loading, please wait...")
            self.open_button.configure(state="disabled")
            threading.Thread(target=self.load_csv_worker, args=(file_path,), daemon=True).start()
            self.after(100, self.process_queue)

    def load_csv_worker(self, file_path):
        try:
            df_raw = pd.read_csv(file_path, header=0, encoding='latin1', on_bad_lines='skip', low_memory=False)
            if len(df_raw.columns) < 2: raise ValueError("CSV must have at least Date and Time columns.")
            date_col, time_col = df_raw.columns[0], df_raw.columns[1]
            df_raw['Timestamp'] = pd.to_datetime(df_raw[date_col].astype(str) + ' ' + df_raw[time_col].astype(str), errors='coerce', dayfirst=True)
            df_raw = df_raw.dropna(subset=['Timestamp'])
            data_cols = list(df_raw.columns[2:-1])
            final_df = df_raw[['Timestamp'] + data_cols]
            self.queue.put(final_df)
        except Exception as e:
            self.queue.put(e)

    def process_queue(self):
        try:
            result = self.queue.get_nowait()
            self.open_button.configure(state="normal")
            if isinstance(result, pd.DataFrame):
                self.df = result
                self.file_path_label.configure(text=self.loaded_file_path)
                self.populate_column_list()
                self.full_x_range_numeric = (mdates.date2num(self.df['Timestamp'].min()), mdates.date2num(self.df['Timestamp'].max()))
                self.x_axis_slider.set(100)
                self.x_axis_label.configure(text="100%")
            elif isinstance(result, Exception):
                messagebox.showerror("Error", f"Failed to load file: {result}")
                self.file_path_label.configure(text="Failed to load file.")
        except Empty:
            self.after(100, self.process_queue)

    def populate_column_list(self):
        self.column_frame.destroy()
        columns = list(self.df.columns[1:])
        left_frame = self.grid_slaves(row=0, column=0)[0]
        self.column_frame = CheckboxList(left_frame, columns)
        self.column_frame.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")
        self.filter_entry.bind("<KeyRelease>", self.on_filter_change)

    def get_unit_from_column(self, col_name):
        match = re.search(r'\[([^\]]+)\]', col_name)
        return match.group(1) if match else 'N/A'

    def visualize_data(self, event=None):
        selected_columns = self.column_frame.get_checked_columns()
        if not selected_columns or self.df is None: 
            self.initialize_plot()
            return

        grouped_by_unit = {}
        for col in selected_columns:
            unit = self.get_unit_from_column(col)
            if unit not in grouped_by_unit:
                grouped_by_unit[unit] = []
            grouped_by_unit[unit].append(col)

        if len(grouped_by_unit) > 2:
            messagebox.showwarning("Too many units", "Please select columns with a maximum of two different units (e.g., [MB] and [V]).")
            return

        self.initialize_plot()
        self.lines.clear()

        time_col = self.df.columns[0]
        ax1 = self.ax
        ax2 = None

        units = list(grouped_by_unit.keys())
        color_idx = 0

        for col in grouped_by_unit[units[0]]:
            numeric_data = pd.to_numeric(self.df[col], errors='coerce').dropna()
            line, = ax1.plot(self.df.loc[numeric_data.index, time_col], numeric_data, label=col, picker=True, pickradius=5, color=self.line_colors[color_idx])
            self.lines.append(line)
            color_idx += 1

        if len(units) > 1:
            ax2 = ax1.twinx()
            ax2.set_ylabel(f"[{units[1]}]", color=self.text_color, fontsize=12)
            ax2.tick_params(axis='y', colors=self.text_color)
            ax2.spines['right'].set_color(self.grid_color)
            for col in grouped_by_unit[units[1]]:
                numeric_data = pd.to_numeric(self.df[col], errors='coerce').dropna()
                line, = ax2.plot(self.df.loc[numeric_data.index, time_col], numeric_data, label=col, picker=True, pickradius=5, color=self.line_colors[color_idx])
                self.lines.append(line)
                color_idx += 1

        ax1.set_ylabel(f"[{units[0]}]", color=self.text_color, fontsize=12)
        self.ax.set_title("Sensor Data", fontsize=16, fontweight='bold', color=self.text_color)
        self.update_legend()
        self.update_x_axis_range(self.x_axis_slider.get())
        self.fig.tight_layout()
        self.canvas.draw()
        
        if self.data_panel_visible:
            self.data_panel.update_data(self.df[[time_col] + selected_columns], self.lines)

    def update_legend(self):
        for widget in self.legend_frame.winfo_children():
            widget.destroy()

        if self.lines:
            self.right_frame.grid_columnconfigure(2, weight=0)
            self.legend_frame.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(5,0))
            max_width = 0
            font = ctk.CTkFont()
            for line in self.lines:
                color = mcolors.to_hex(line.get_color())
                label_text = line.get_label()
                legend_item = ctk.CTkLabel(self.legend_frame, text=label_text, text_color=color)
                legend_item.pack(anchor="w", padx=10, pady=2)
                max_width = max(max_width, font.measure(label_text))
            self.legend_frame.configure(width=max_width + 30)
        else:
            self.legend_frame.grid_forget()

    def update_x_axis_range(self, value):
        if self.full_x_range_numeric is None: return
        percentage = int(value)
        self.x_axis_label.configure(text=f"{percentage}%")
        if percentage == 100:
            self.ax.set_xlim(self.full_x_range_numeric)
        else:
            total_duration = self.full_x_range_numeric[1] - self.full_x_range_numeric[0]
            new_duration = total_duration * (percentage / 100.0)
            self.ax.set_xlim(self.full_x_range_numeric[0], self.full_x_range_numeric[0] + new_duration)
        self.canvas.draw_idle()

    def on_pick(self, event):
        line = event.artist
        ind = event.ind[0]
        x_data, y_data = line.get_data()
        x_point, y_point = x_data[ind], y_data[ind]

        self.annot.set_visible(True)
        self.annot.xy = (mdates.date2num(x_point), y_point)
        time_str = pd.to_datetime(x_point).strftime('%H:%M:%S.%f')[:-3]
        value_str = f"{y_point:.2f}"
        self.annot.set_text(f"{line.get_label()}\nTime: {time_str}\nValue: {value_str}")
        self.annot.get_bbox_patch().set_facecolor(line.get_color())
        self.annot.get_bbox_patch().set_alpha(0.7)
        self.canvas.draw_idle()

    def on_motion(self, event):
        if self.annot.get_visible() and event.inaxes != self.ax:
            self.annot.set_visible(False)
            self.canvas.draw_idle()

    def save_preset(self):
        checked_columns = self.column_frame.get_checked_columns()
        if not checked_columns:
            messagebox.showwarning("No Selection", "Please select at least one column to save as a preset.")
            return

        dialog = ctk.CTkInputDialog(text="Enter preset name:", title="Save Preset")
        preset_name = dialog.get_input()

        if preset_name:
            self.presets[preset_name] = checked_columns
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f, indent=4)
            self.update_preset_combo()

    def load_presets(self):
        if os.path.exists(self.presets_file):
            with open(self.presets_file, 'r') as f:
                self.presets = json.load(f)
        self.update_preset_combo()

    def apply_preset_selection(self):
        preset_name = self.preset_combo.get()
        placeholder = "Please select a preset"
        no_presets_text = "No presets available"
        if preset_name == placeholder or preset_name == no_presets_text or preset_name not in self.presets:
            messagebox.showwarning("Invalid Preset", "Please select a valid preset to apply.")
            return

        for cb in self.column_frame.checkboxes.values():
            cb.deselect()
        for col in self.presets[preset_name]:
            if col in self.column_frame.checkboxes:
                self.column_frame.checkboxes[col].select()
        self.column_frame.sort_list()
        self.visualize_data()

    def delete_preset(self):
        preset_name = self.preset_combo.get()
        placeholder = "Please select a preset"
        no_presets_text = "No presets available"
        if preset_name == placeholder or preset_name == no_presets_text or preset_name not in self.presets:
            messagebox.showwarning("Invalid Selection", "Please select a valid preset to delete.")
            return

        if messagebox.askyesno("Delete Preset", f"Are you sure you want to delete the preset '{preset_name}'?"):
            del self.presets[preset_name]
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f, indent=4)
            self.update_preset_combo()

    def update_preset_combo(self):
        preset_names = list(self.presets.keys())
        placeholder = "Please select a preset"
        no_presets_text = "No presets available"
        
        if preset_names:
            self.preset_combo.configure(values=[placeholder] + preset_names)
            self.preset_combo.set(placeholder)
        else:
            self.preset_combo.configure(values=[no_presets_text])
            self.preset_combo.set(no_presets_text)

if __name__ == "__main__":
    app = App()
    app.mainloop()
