"""
Publication-style vertical probability colorbar (matplotlib-backed).

Drawn with a real rectangle border + tick marks + across-the-bar grid lines,
so it does not depend on matplotlib's `Colorbar.outline` or axes spines (which
behave differently between matplotlib versions).
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib import cm
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget


# Theme colors
BG = "#0d1117"
FG = "#e6edf3"
DIM_GREY = "#8b949e"


class ProbabilityColorBar(QWidget):
    """Thin vertical colorbar with explicit border + tick lines across the bar."""

    def __init__(
        self,
        cmap_name: str = "viridis",
        title: str = "Probability",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._fig = Figure(figsize=(1.0, 4.0), dpi=100)
        self._fig.patch.set_facecolor(BG)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setStyleSheet(f"background-color: {BG};")

        self._ax = self._fig.add_axes([0.22, 0.08, 0.28, 0.84])
        self.setMinimumWidth(120)
        self._ax.set_facecolor(BG)

        self._cmap = cm.get_cmap(cmap_name)
        self._norm = Normalize(vmin=0.0, vmax=1.0)

        self._cb = self._fig.colorbar(
            cm.ScalarMappable(norm=self._norm, cmap=self._cmap),
            cax=self._ax,
            orientation="vertical",
        )
        self._cb.ax.set_title(title, color=FG, fontsize=10, pad=8)

        self._cb.ax.yaxis.set_tick_params(
            which="major",
            length=6,
            width=1.0,
            color=FG,
            labelsize=9,
            labelcolor=FG,
            direction="out",
        )

        for spine in self._cb.ax.spines.values():
            spine.set_visible(False)
        if getattr(self._cb, "outline", None) is not None:
            try:
                self._cb.outline.set_visible(False)
            except Exception:
                pass

        self._border = Rectangle(
            (0.0, 0.0),
            1.0,
            1.0,
            transform=self._cb.ax.transAxes,
            linewidth=0.9,
            edgecolor=DIM_GREY,
            facecolor="none",
            clip_on=False,
            zorder=5,
        )
        self._cb.ax.add_patch(self._border)

        self._grid_lines: list = []
        self._draw_grid_lines()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setMinimumWidth(100)

        self._canvas.draw_idle()

    def _draw_grid_lines(self) -> None:
        """Thin horizontal lines crossing the bar at each tick position."""
        for ln in self._grid_lines:
            try:
                ln.remove()
            except Exception:
                pass
        self._grid_lines = []

        ticks = list(self._cb.get_ticks())
        for t in ticks:
            line = self._cb.ax.axhline(
                y=t,
                color=DIM_GREY,
                linewidth=0.6,
                alpha=0.5,
                zorder=3,
            )
            self._grid_lines.append(line)


    def set_range(self, vmin: float, vmax: float, n_ticks: int = 7) -> None:
        """Update displayed range, tick labels and across-the-bar grid lines."""
        if vmax <= vmin:
            vmax = vmin + 1e-9
        self._norm.vmin = float(vmin)
        self._norm.vmax = float(vmax)
        self._cb.mappable.set_norm(self._norm)

        from numpy import linspace
        ticks = list(linspace(vmin, vmax, max(2, int(n_ticks))))
        self._cb.set_ticks(ticks)

        fmt = "%.3f" if (vmax - vmin) < 0.1 else "%.2f"
        self._cb.set_ticklabels([fmt % t for t in ticks])

        self._draw_grid_lines()
        self._canvas.draw_idle()