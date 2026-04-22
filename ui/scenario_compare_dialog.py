"""
Modal dialog: side-by-side scenario metrics and overlaid CDF for 2 schedules.
"""

from __future__ import annotations

import copy
from typing import Any, List, Optional, Sequence, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QWidget,
    QSizePolicy,
    QLineEdit,
)

from services.schedule_io import load_schedule_file, parse_deadlines_finite
from services.schedule_metrics import analyse_schedule, ScheduleMetric
from ui.cdf_plot_widget import CDFPlotWidget

class ScenarioCompareDialog(QDialog):
    """
    Load or pin 2 schedules and compare FoM, CDF, total slew, and deadline stats.

    Deadlines can be entered here (comma-separated seconds) or taken from the main window /
    loaded schedule JSON metadata; Evaluate FoM first is optional.
    """

    def __init__(
        self,
        parent,
        telescope: Any,
        start_position: Optional[tuple],
        deadlines_finite: Sequence[float],
        current_tiles_getter: Callable[[], list]
    ):
        """
        :param parent: QWidget parent for modality.
        :param telescope: Telescope instance or None.
        :param start_position: 3-tuple previous pointing; None matches evaluate behaviour.
        :param deadlines_finite: Finite deadlines (seconds); may be empty — user can type below.
        :param current_tiles_getter: Zero-arg callable returning list of tile dicts from live schedule
        """
        super().__init__(parent)
        self.setWindowTitle("Scenario Comparison")
        self.resize(940, 640)
        self._telescope = telescope
        self._start_pos = start_position
        self._deadlines = list(deadlines_finite)
        self._get_current_tiles = current_tiles_getter
        self._tiles_a: List[dict] = []
        self._tiles_b: List[dict] = []
        self._label_a = "A"
        self._label_b = "B"
        self._build_ui()  # Assemble widgets
        self._sync_deadline_line_edit()
        self._refresh_all()  # Initial metrics if tiles already set

    @staticmethod
    def _style_value_label(lbl: QLabel) -> None:
        """Readable multi-line metrics: spacing, wrap, selectable text."""
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lbl.setStyleSheet(
            "color: #e6edf3; font-size: 11pt; padding: 6px 4px; line-height: 1.35;"
        )

    def _build_ui(self) -> None:
        """Lay out controls, summary panels, and the dual CDF plot."""

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(18)

        hint = QLabel(
            "Enter <b>deadlines (seconds)</b> below, then load or pin scenarios. "
            "JSON schedules saved from this app can include deadlines automatically. "
            "Compare “before vs after GA” by pinning schedules to A and B."
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "color: #8b949e; font-size: 11pt; padding: 2px 4px 8px 4px; line-height: 1.45;"
        )
        root.addWidget(hint)

        dl_row = QHBoxLayout()
        dl_row.setSpacing(10)
        dl_label = QLabel("Deadlines (s):")
        dl_label.setStyleSheet("color: #8b949e; font-size: 10pt; font-weight: 500;")
        dl_row.addWidget(dl_label)
        self._deadline_edit = QLineEdit()
        self._deadline_edit.setPlaceholderText("e.g. 60, 120, 180")
        self._deadline_edit.setMinimumWidth(280)
        self._deadline_edit.setStyleSheet(
            "padding: 6px 10px; font-size: 10pt; background: #0d1117; color: #e6edf3; "
            "border: 1px solid #30363d; border-radius: 4px;"
        )
        dl_row.addWidget(self._deadline_edit, 1)
        self._btn_apply_dl = QPushButton("Apply deadlines")
        self._btn_apply_dl.setMinimumHeight(32)
        self._btn_apply_dl.clicked.connect(self._apply_deadlines_from_input)
        self._deadline_edit.returnPressed.connect(self._apply_deadlines_from_input)
        dl_row.addWidget(self._btn_apply_dl)
        root.addLayout(dl_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.setContentsMargins(0, 4, 0, 0)
        self._btn_load_a = QPushButton("Load A")
        self._btn_load_a.setMinimumHeight(32)
        self._btn_load_a.setMinimumWidth(100)
        self._btn_load_a.clicked.connect(self._on_load_a)
        btn_row.addWidget(self._btn_load_a)

        self._btn_pin_a = QPushButton("Current → A")
        self._btn_pin_a.setMinimumHeight(32)
        self._btn_pin_a.setMinimumWidth(120)
        self._btn_pin_a.clicked.connect(self._on_pin_a)
        btn_row.addWidget(self._btn_pin_a)

        self._btn_load_b = QPushButton("Load B")
        self._btn_load_b.setMinimumHeight(32)
        self._btn_load_b.setMinimumWidth(100)
        self._btn_load_b.clicked.connect(self._on_load_b)
        btn_row.addWidget(self._btn_load_b)

        self._btn_pin_b = QPushButton("Current → B")
        self._btn_pin_b.setMinimumHeight(32)
        self._btn_pin_b.setMinimumWidth(120)
        self._btn_pin_b.clicked.connect(self._on_pin_b)
        btn_row.addWidget(self._btn_pin_b)

        self._btn_swap = QPushButton("Swap A/B")
        self._btn_swap.setMinimumHeight(32)
        self._btn_swap.setMinimumWidth(96)
        self._btn_swap.clicked.connect(self._on_swap)
        btn_row.addWidget(self._btn_swap)

        btn_row.addStretch(1)
        root.addLayout(btn_row)

        mid = QHBoxLayout()
        mid.setSpacing(20)
        mid.setContentsMargins(0, 8, 0, 4)

        group_style = """
            QGroupBox {
                font-weight: 600;
                font-size: 11pt;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                margin-top: 12px;
                padding: 14px 14px 16px 14px;
                background-color: #161b22;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """

        self._box_a = QGroupBox("Scenario A")
        self._box_a.setStyleSheet(group_style)
        self._form_a = QFormLayout()
        self._form_a.setSpacing(12)
        self._form_a.setHorizontalSpacing(18)
        self._form_a.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self._form_a.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        self._box_a.setLayout(self._form_a)

        self._fom_a = QLabel("-")
        self._slew_a = QLabel("-")
        self._viol_a = QLabel("-")
        self._cdf_at_a = QLabel("-")
        for w in (self._fom_a, self._slew_a, self._viol_a, self._cdf_at_a):
            self._style_value_label(w)

        self._form_a.addRow(self._form_label("FoM:"), self._fom_a)
        self._form_a.addRow(self._form_label("Total slew:"), self._slew_a)
        self._form_a.addRow(self._form_label("Late tiles / deadline:"), self._viol_a)
        self._form_a.addRow(self._form_label("F(D) at deadlines:"), self._cdf_at_a)
        mid.addWidget(self._box_a, 1)

        self._box_b = QGroupBox("Scenario B")
        self._box_b.setStyleSheet(group_style)
        self._form_b = QFormLayout()
        self._form_b.setSpacing(12)
        self._form_b.setHorizontalSpacing(18)
        self._form_b.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self._form_b.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        self._box_b.setLayout(self._form_b)

        self._fom_b = QLabel("-")
        self._slew_b = QLabel("-")
        self._viol_b = QLabel("-")
        self._cdf_at_b = QLabel("-")
        for w in (self._fom_b, self._slew_b, self._viol_b, self._cdf_at_b):
            self._style_value_label(w)

        self._form_b.addRow(self._form_label("FoM:"), self._fom_b)
        self._form_b.addRow(self._form_label("Total slew:"), self._slew_b)
        self._form_b.addRow(self._form_label("Late tiles / deadline:"), self._viol_b)
        self._form_b.addRow(self._form_label("F(D) at deadlines:"), self._cdf_at_b)
        mid.addWidget(self._box_b, 1)

        root.addLayout(mid)

        self._plot = CDFPlotWidget()
        self._plot.setMinimumHeight(240)
        self._plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._plot, stretch=3)

        close_row = QHBoxLayout()
        close_row.setContentsMargins(0, 16, 0, 4)
        close_row.setSpacing(12)
        close_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(34)
        close_btn.setMinimumWidth(120)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

    @staticmethod
    def _form_label(text: str) -> QLabel:
        """Muted field label aligned with wrapped value rows."""
        lab = QLabel(text)
        lab.setStyleSheet(
            "color: #8b949e; font-size: 10pt; padding: 8px 8px 0 0; font-weight: 500;"
        )
        lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        return lab

    def _sync_deadline_line_edit(self) -> None:
        """Keep the line edit aligned with self._deadlines."""
        if self._deadlines:
            self._deadline_edit.setText(", ".join(str(d) for d in self._deadlines))
        else:
            self._deadline_edit.clear()

    def _apply_deadlines_from_input(self) -> None:
        """Parse deadlines from the text field and refresh metrics."""
        try:
            self._deadlines = parse_deadlines_finite(self._deadline_edit.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid deadlines", str(exc))
            return
        self._refresh_all()

    def _deadlines_ok(self) -> bool:
        """Return True if we have at least one finite deadline for comparison."""
        return bool(self._deadlines)

    def _on_load_a(self) -> None:
        """Load Scenario A tiles from JSON/CSV."""
        path, _ = QFileDialog.getOpenFileName(self, "Load schedule for A", "", "Schedule (*.json *.csv)")
        if not path:
            return
        try:
            self._tiles_a, meta = load_schedule_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return
        if isinstance(meta, dict) and meta.get("deadlines_finite"):
            try:
                self._deadlines = [float(x) for x in meta["deadlines_finite"]]
                self._sync_deadline_line_edit()
            except (TypeError, ValueError):
                pass
        self._label_a = "A (file)"
        self._refresh_all()

    def _on_load_b(self) -> None:
        """Load Scenario B tiles from JSON/CSV."""
        path, _ = QFileDialog.getOpenFileName(self, "Load schedule for B", "", "Schedule (*.json *.csv)")
        if not path:
            return
        try:
            self._tiles_b, meta = load_schedule_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return
        if isinstance(meta, dict) and meta.get("deadlines_finite"):
            try:
                self._deadlines = [float(x) for x in meta["deadlines_finite"]]
                self._sync_deadline_line_edit()
            except (TypeError, ValueError):
                pass
        self._label_b = "B (file)"
        self._refresh_all()

    def _on_pin_a(self) -> None:
        """Copy current main-window schedule into scenario A."""
        raw = self._get_current_tiles()
        self._tiles_a = copy.deepcopy(raw)
        self._label_a = "A (current)"
        self._refresh_all()

    def _on_pin_b(self) -> None:
        """Copy current main-window schedule into scenario B."""
        raw = self._get_current_tiles()
        self._tiles_b = copy.deepcopy(raw)
        self._label_b = "B (current)"
        self._refresh_all()

    def _on_swap(self) -> None:
        """Exchange scenario A and B tile lists and labels."""
        self._tiles_a, self._tiles_b = self._tiles_b, self._tiles_a  # Swap lists
        self._label_a, self._label_b = self._label_b, self._label_a  # Swap names
        self._refresh_all()

    @staticmethod
    def _format_metrics(m: Optional[ScheduleMetric]) -> tuple[str, str, str, str]:
        """
        Turn ScheduleMetrics into four short strings for the form rows.

        Returns (fom, slew, violations, cdf_at_deadlines).
        """
        if m is None:  # Missing computation
            return "-", "-", "-", "-"

        fom_s = f"{m.fom:.4f}"
        slew_s = (
            f"{m.total_slew_s:.2f} s (total time {m.total_time_s:.2f} s)"
        )
        viol_parts = [f"D={d:.1f}s: {c} late" for d, c in m.late_counts_by_deadline] # Per-D counts
        viol_s = "; ".join(viol_parts) if viol_parts else "-"
        cdf_parts = [f"D={d:.1f}s F={fv:.3f}" for d, fv in m.cdf_at_deadlines] # F(D) list
        cdf_s = "; ".join(cdf_parts) if cdf_parts else "-"
        return fom_s, slew_s, viol_s, cdf_s

    def _refresh_all(self) -> None:
        """Recompute metrics for A/B and refresh labels + plot."""
        if not self._deadlines_ok():
            dash = "—"
            for w in (
                self._fom_a,
                self._slew_a,
                self._viol_a,
                self._cdf_at_a,
                self._fom_b,
                self._slew_b,
                self._viol_b,
                self._cdf_at_b,
            ):
                w.setText(dash)
            self._plot.clear()
            return

        ma = None
        mb = None
        if self._tiles_a:
            ma = analyse_schedule(self._tiles_a, self._telescope, self._start_pos, self._deadlines)
        if self._tiles_b:
            mb = analyse_schedule(self._tiles_b, self._telescope, self._start_pos, self._deadlines)

        fa, sa, va, ca = self._format_metrics(ma)
        fb, sb, vb, cb = self._format_metrics(mb)

        self._fom_a.setText(fa)
        self._slew_a.setText(sa)
        self._viol_a.setText(va)
        self._cdf_at_a.setText(ca)
        self._fom_b.setText(fb)
        self._slew_b.setText(sb)
        self._viol_b.setText(vb)
        self._cdf_at_b.setText(cb)

        ta = ma.cdf_times if ma else []
        pa = ma.cdf_cmv_prob if ma else []
        tb = mb.cdf_times if mb else []
        pb = mb.cdf_cmv_prob if mb else []
        self._plot.update_cf_compare(
            ta,
            pa,
            tb,
            pb,
            deadlines=list(self._deadlines),
            label_a=self._label_a,
            label_b=self._label_b,
        )
