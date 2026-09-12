"""Matplotlib figure/axes lifecycle, plotting modes, and interaction.

Supports three layout modes:

* **Single axis** — one unit selected
* **Dual axis** — two units (overlay with ``twinx``)
* **Grouped by unit** — three or more units → stacked subplots
"""

from __future__ import annotations

import colorsys
import logging
from typing import TYPE_CHECKING

import matplotlib.colors as mcolors
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from data.downsampling import min_max_downsample
from data.sensors import Sensor

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.lines import Line2D

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Apple-inspired dark theme constants
# ---------------------------------------------------------------------------
BG_COLOR = "#0a0a0c"
SURFACE_COLOR = "#141416"
ELEVATED_COLOR = "#1c1c1e"
BORDER_COLOR = "#2a2a2e"
TEXT_COLOR = "#f5f5f7"
TEXT_SECONDARY = "#86868b"
GRID_COLOR = "#2a2a2e"
ACCENT_COLOR = "#0ea5e9"


# ---------------------------------------------------------------------------
# Colour generation
# ---------------------------------------------------------------------------

def generate_colors(n: int) -> list[tuple[float, float, float, float]]:
    """Return *n* visually distinct RGBA colours.

    Uses ``tab10`` for ≤ 10 items; golden-ratio HSV sampling beyond that
    to keep hues well-separated even for large *n*.
    """
    if n <= 0:
        return []
    if n <= 10:
        cmap = plt.cm.tab10  # type: ignore[attr-defined]
        return [cmap(i) for i in range(n)]

    colors: list[tuple[float, float, float, float]] = []
    phi = 0.618033988749895  # golden ratio conjugate
    for i in range(n):
        hue = (i * phi) % 1.0
        sat = 0.60 + (i % 3) * 0.12
        val = 0.78 + (i % 2) * 0.12
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
        colors.append((r, g, b, 1.0))
    return colors


# ---------------------------------------------------------------------------
# PlotManager
# ---------------------------------------------------------------------------

class PlotManager:
    """Owns the Matplotlib *Figure* lifecycle and all plotting logic.

    Responsibilities:

    * Apply the dark theme to every ``Axes``.
    * Decide overlay vs. grouped-by-unit layout.
    * Downsample each series for rendering.
    * Manage the pick-event tooltip annotation.
    * Provide ``update_x_range`` for the time slider.
    """

    def __init__(self, fig: Figure, canvas: FigureCanvasTkAgg) -> None:
        self.fig = fig
        self.canvas = canvas

        self.axes: list[Axes] = []
        self.lines: list[Line2D] = []
        self.annot = None
        self._cb_ids: list[int] = []
        self._full_x_range: tuple[float, float] | None = None
        self._current_sensors: list[Sensor] = []

        self._setup_figure()
        self._connect_events()

    # --- figure setup / teardown -------------------------------------------

    def _setup_figure(self) -> None:
        self.fig.set_facecolor(BG_COLOR)
        self.fig.subplots_adjust(hspace=0.35)

    def _connect_events(self) -> None:
        """Register pick / motion handlers (idempotent — disconnects first)."""
        self._disconnect_events()
        c1 = self.fig.canvas.mpl_connect("pick_event", self._on_pick)
        c2 = self.fig.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._cb_ids = [c1, c2]

    def _disconnect_events(self) -> None:
        for cid in self._cb_ids:
            self.fig.canvas.mpl_disconnect(cid)
        self._cb_ids.clear()

    def _style_axes(self, ax: Axes, title: str = "", ylabel: str = "") -> None:
        ax.set_facecolor(SURFACE_COLOR)
        if title:
            ax.set_title(title, color=TEXT_COLOR, fontsize=13,
                         fontweight="bold", pad=8)
        if ylabel:
            ax.set_ylabel(ylabel, color=TEXT_COLOR, fontsize=11)
        ax.set_xlabel("Time", color=TEXT_SECONDARY, fontsize=10)
        ax.tick_params(axis="x", colors=TEXT_SECONDARY, labelsize=9)
        ax.tick_params(axis="y", colors=TEXT_SECONDARY, labelsize=9)
        for sp in ax.spines.values():
            sp.set_color(BORDER_COLOR)
        ax.grid(True, which="major", ls="--", lw=0.4,
                color=GRID_COLOR, alpha=0.6)

    def _create_annotation(self, ax: Axes) -> None:
        """Create (or recreate) the tooltip annotation on *ax*."""
        self.annot = ax.annotate(
            "", xy=(0, 0), xytext=(20, 20),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.4", fc=ELEVATED_COLOR,
                      ec=BORDER_COLOR, lw=1, alpha=0.95),
            arrowprops=dict(arrowstyle="->",
                            connectionstyle="arc3,rad=0.1",
                            color=TEXT_SECONDARY),
            color=TEXT_COLOR, fontsize=9,
        )
        self.annot.set_visible(False)

    # --- public API --------------------------------------------------------

    def clear(self) -> None:
        """Remove all artists and reset internal state."""
        self.fig.clear()
        self.axes.clear()
        self.lines.clear()
        self.annot = None
        self._current_sensors.clear()

    def show_empty(self, message: str = "HWInfo64 Visualizer") -> None:
        """Render an empty plot with a centred message."""
        self.clear()
        ax = self.fig.add_subplot(111)
        self._style_axes(ax)
        ax.text(0.5, 0.5, message, transform=ax.transAxes,
                ha="center", va="center", fontsize=14,
                color=TEXT_SECONDARY, style="italic")
        ax.set_xticks([])
        ax.set_yticks([])
        self._create_annotation(ax)
        self.axes = [ax]
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def plot_sensors(
        self,
        df: pd.DataFrame,
        sensors: list[Sensor],
        max_points: int = 2000,
    ) -> list[str]:
        """Plot the requested sensors — auto-selects layout mode.

        Returns a list of sensor display-names that were skipped because
        they contained no valid numeric data.
        """
        if not sensors:
            self.show_empty("Select sensors to visualize")
            return []

        self.clear()
        self._current_sensors = list(sensors)

        # Group by unit
        unit_groups: dict[str, list[Sensor]] = {}
        for s in sensors:
            unit_groups.setdefault(s.unit or "N/A", []).append(s)

        # Colour map
        colors = generate_colors(len(sensors))
        color_map = {s.column: colors[i] for i, s in enumerate(sensors)}

        time_data = df["Timestamp"]
        time_numeric = mdates.date2num(time_data)

        n_units = len(unit_groups)
        if n_units <= 2:
            skipped = self._plot_overlay(
                df, sensors, unit_groups, color_map,
                time_data, time_numeric, max_points,
            )
        else:
            skipped = self._plot_grouped(
                df, sensors, unit_groups, color_map,
                time_data, time_numeric, max_points,
            )

        # X range for slider
        if len(time_numeric) > 0:
            self._full_x_range = (float(time_numeric.min()),
                                  float(time_numeric.max()))

        # Annotation on first axes
        if self.axes:
            self._create_annotation(self.axes[0])

        self.fig.tight_layout()
        self.canvas.draw_idle()
        return skipped

    def update_x_range(self, percentage: float) -> None:
        """Set the visible X-axis to *percentage* of the full range."""
        if self._full_x_range is None or not self.axes:
            return
        xmin, xmax = self._full_x_range
        if percentage >= 100:
            xlim = (xmin, xmax)
        else:
            duration = (xmax - xmin) * percentage / 100.0
            xlim = (xmin, xmin + duration)
        for ax in self.axes:
            ax.set_xlim(xlim)
        self.canvas.draw_idle()

    def get_line_colors(self) -> dict[str, str]:
        """Map sensor display-name → hex colour string."""
        out: dict[str, str] = {}
        for line in self.lines:
            out[line.get_label()] = mcolors.to_hex(line.get_color())
        return out

    def cleanup(self) -> None:
        """Release resources (call before widget destruction)."""
        self._disconnect_events()
        self.clear()

    # --- layout modes ------------------------------------------------------

    def _plot_overlay(
        self, df, sensors, unit_groups, color_map,
        time_data, time_numeric, max_points,
    ) -> list[str]:
        """Single / dual Y-axis overlay."""
        skipped: list[str] = []
        units = list(unit_groups.keys())

        ax1 = self.fig.add_subplot(111)
        self._style_axes(ax1, title="Sensor Data", ylabel=f"[{units[0]}]")
        self.axes = [ax1]

        for s in unit_groups[units[0]]:
            sk = self._plot_one(ax1, df, s, color_map, time_data,
                                time_numeric, max_points)
            if sk:
                skipped.append(sk)

        if len(units) > 1:
            ax2 = ax1.twinx()
            ax2.set_ylabel(f"[{units[1]}]", color=TEXT_COLOR, fontsize=11)
            ax2.tick_params(axis="y", colors=TEXT_SECONDARY, labelsize=9)
            ax2.spines["right"].set_color(BORDER_COLOR)
            self.axes.append(ax2)
            for s in unit_groups[units[1]]:
                sk = self._plot_one(ax2, df, s, color_map, time_data,
                                    time_numeric, max_points)
                if sk:
                    skipped.append(sk)

        # Overlay legend on the primary axes
        handles = [l for l in self.lines]
        if handles:
            ax1.legend(
                handles=handles,
                fontsize=8, facecolor=ELEVATED_COLOR,
                edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR,
                loc="upper right", framealpha=0.9,
            )

        return skipped

    def _plot_grouped(
        self, df, sensors, unit_groups, color_map,
        time_data, time_numeric, max_points,
    ) -> list[str]:
        """Stacked subplots — one per unit."""
        skipped: list[str] = []
        units = list(unit_groups.keys())
        n = len(units)

        for i, unit in enumerate(units):
            ax = self.fig.add_subplot(n, 1, i + 1)
            ylabel = f"[{unit}]"
            title = "Sensor Data — Grouped by Unit" if i == 0 else ""
            self._style_axes(ax, title=title, ylabel=ylabel)

            if i < n - 1:
                ax.set_xlabel("")
                ax.tick_params(axis="x", labelbottom=False)

            for s in unit_groups[unit]:
                sk = self._plot_one(ax, df, s, color_map, time_data,
                                    time_numeric, max_points)
                if sk:
                    skipped.append(sk)

            ax.legend(fontsize=8, facecolor=ELEVATED_COLOR,
                      edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR,
                      loc="upper right", framealpha=0.9)
            self.axes.append(ax)

        return skipped

    def _plot_one(
        self, ax, df, sensor, color_map, time_data, time_numeric, max_points,
    ) -> str | None:
        """Plot a single sensor on *ax*.  Returns name if skipped."""
        if sensor.column not in df.columns:
            return sensor.name

        y = df[sensor.column].values.astype(float)
        valid = ~np.isnan(y)
        if not valid.any():
            return sensor.name

        x_valid = time_numeric[valid]
        y_valid = y[valid]

        x_ds, y_ds = min_max_downsample(x_valid, y_valid, max_points)

        color = color_map.get(sensor.column, (0.5, 0.5, 0.5, 1.0))
        line, = ax.plot(
            mdates.num2date(x_ds), y_ds,
            label=sensor.name,
            color=color, lw=1.2,
            picker=True, pickradius=5,
        )
        self.lines.append(line)
        return None

    # --- events ------------------------------------------------------------

    def _on_pick(self, event) -> None:
        if self.annot is None:
            return
        if not hasattr(event, "ind") or len(event.ind) == 0:
            return

        line = event.artist
        ind = event.ind[0]
        xd, yd = line.get_data()
        if ind >= len(xd):
            return

        x_pt, y_pt = xd[ind], yd[ind]
        try:
            x_num = mdates.date2num(x_pt)
            ts = mdates.num2date(x_num).strftime("%H:%M:%S.%f")[:-3]
        except Exception:
            ts = str(x_pt)

        self.annot.set_visible(True)
        self.annot.xy = (mdates.date2num(x_pt), y_pt)
        self.annot.set_text(
            f"{line.get_label()}\nTime: {ts}\nValue: {y_pt:.2f}"
        )
        bbox = self.annot.get_bbox_patch()
        bbox.set_facecolor(line.get_color())
        bbox.set_alpha(0.85)
        self.canvas.draw_idle()

    def _on_motion(self, event) -> None:
        if self.annot is None or not self.annot.get_visible():
            return
        if event.inaxes is None or event.inaxes not in self.axes:
            self.annot.set_visible(False)
            self.canvas.draw_idle()
