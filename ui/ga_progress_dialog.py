from __future__ import annotations

from pyqtgraph import PlotWidget, mkBrush, mkPen
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class GAProgressDialog(QDialog):
    """Live progress panel for GA optimisation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: list[tuple[int, float]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("GA Progress")
        self.resize(560, 360)
        self.setModal(False)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0d1117;
                color: #e6edf3;
            }
            QLabel#gaHint {
                color: #8b949e;
            }
            QFrame#gaStatCard {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            QLabel#gaStatTitle {
                color: #8b949e;
                font-size: 10pt;
            }
            QLabel#gaStatValue {
                color: #e6edf3;
                font-size: 12pt;
                font-weight: 600;
            }
            QFrame#gaFooter {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.status_label = QLabel("Running genetic algorithm...")
        self.status_label.setObjectName("gaHint")
        root.addWidget(self.status_label)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(12)
        stats_grid.setVerticalSpacing(12)

        self.generation_value = self._make_stat_card(stats_grid, 0, 0, "Generation")
        self.elapsed_value = self._make_stat_card(stats_grid, 0, 1, "Elapsed")
        self.best_fom_value = self._make_stat_card(stats_grid, 0, 2, "Best FoM")
        self.delta_value = self._make_stat_card(stats_grid, 0, 3, "Improvement")
        root.addLayout(stats_grid)

        self.plot = PlotWidget()
        self.plot.setBackground("#0d1117")
        self.plot.showGrid(x=True, y=True, alpha=0.08)
        self.plot.setLabel("bottom", "Generation", color="#8b949e")
        self.plot.setLabel("left", "Best FoM", color="#8b949e")
        self.plot.getAxis("left").setPen("#8b949e")
        self.plot.getAxis("bottom").setPen("#8b949e")
        self.plot.getAxis("left").setTextPen("#8b949e")
        self.plot.getAxis("bottom").setTextPen("#8b949e")
        self.plot.getPlotItem().layout.setContentsMargins(60, 10, 16, 26)
        root.addWidget(self.plot, stretch=1)

        footer = QFrame()
        footer.setObjectName("gaFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 10, 12, 10)
        footer_layout.setSpacing(8)

        self.phase_label = QLabel("Initialising population...")
        self.phase_label.setObjectName("gaHint")
        footer_layout.addWidget(self.phase_label)
        footer_layout.addStretch(1)

        self.close_btn = QPushButton("Close")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.close_btn)
        root.addWidget(footer)

    def _make_stat_card(self, grid: QGridLayout, row: int, col: int, title: str) -> QLabel:
        card = QFrame()
        card.setObjectName("gaStatCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("gaStatTitle")
        value_label = QLabel("—")
        value_label.setObjectName("gaStatValue")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        grid.addWidget(card, row, col)
        return value_label

    def set_started(self, baseline_fom: float) -> None:
        self._points = [(0, float(baseline_fom))]
        self._render_curve()
        self.generation_value.setText("0")
        self.elapsed_value.setText("0.0 s")
        self.best_fom_value.setText(f"{baseline_fom:.3f}")
        self.delta_value.setText("+0.000")
        self.phase_label.setText("Evaluating generations...")
        self.status_label.setText("Running genetic algorithm...")
        self.close_btn.setEnabled(False)

    def update_progress(self, generation: int, elapsed_s: float, best_fom: float, baseline_fom: float) -> None:
        self._points.append((int(generation), float(best_fom)))
        self._render_curve()
        self.generation_value.setText(str(generation))
        self.elapsed_value.setText(f"{elapsed_s:.1f} s")
        self.best_fom_value.setText(f"{best_fom:.3f}")
        self.delta_value.setText(f"{best_fom - baseline_fom:+.3f}")
        self.phase_label.setText("Evolution in progress...")

    def mark_finished(self, final_generation: int, final_fom: float, baseline_fom: float) -> None:
        final_generation = max(final_generation, self._points[-1][0] if self._points else 0)
        self.generation_value.setText(str(final_generation))
        self.best_fom_value.setText(f"{final_fom:.3f}")
        self.delta_value.setText(f"{final_fom - baseline_fom:+.3f}")
        self.phase_label.setText("Optimisation complete")
        self.status_label.setText("Best-so-far FoM by generation")
        self.close_btn.setEnabled(True)

    def mark_failed(self, message: str) -> None:
        self.phase_label.setText("Optimisation failed")
        self.status_label.setText(message)
        self.close_btn.setEnabled(True)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.close_btn.isEnabled():
            super().closeEvent(event)
            return
        event.ignore()

    def _render_curve(self) -> None:
        self.plot.clear()
        if not self._points:
            return

        x = [p[0] for p in self._points]
        y = [p[1] for p in self._points]
        curve = self.plot.plot(
            x,
            y,
            pen=mkPen("#58a6ff", width=3),
            symbol="o",
            symbolSize=6,
            symbolBrush=mkBrush("#58a6ff"),
            symbolPen=mkPen("#58a6ff"),
        )
        if curve is not None:
            curve.setFillLevel(min(y))
            curve.setBrush("#58a6ff22")

        max_generation = max(x) if x else 1
        min_fom = min(y)
        max_fom = max(y)
        padding = max((max_fom - min_fom) * 0.15, 0.01)
        self.plot.setXRange(0, max(max_generation, 1) * 1.05, padding=0.0)
        self.plot.setYRange(min_fom - padding, max_fom + padding, padding=0.0)
