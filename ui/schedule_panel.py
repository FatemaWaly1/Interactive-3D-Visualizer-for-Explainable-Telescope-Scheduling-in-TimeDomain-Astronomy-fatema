from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QAbstractItemView,
    QDoubleSpinBox, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
import json
import csv
import math
import os
from project_utils import prob_to_blue_rgb
from ui.cdf_plot_widget import CDFPlotWidget

class SchedulePanel(QWidget):
    """Right-side panel that shows the current observation schedule."""

    # Signals emitted when schedule(s) cleared, loaded from file, saved, or last file removed
    schedule_cleared = Signal()
    schedule_load_requested = Signal(str)
    tiles_load_requested = Signal(str)
    schedule_save_requested = Signal(str)
    remove_last_requested = Signal()
    row_selected = Signal(int)
    evaluate_schedule_requested = Signal()
    show_fom_history_requested = Signal()
    optimise_schedule_requested = Signal()
    dwell_manual_changed = Signal()
    #hide_panel_requested = Signal()

    def __init__(self, schedule):
        super().__init__()
        self.schedule = schedule
        self.max_prob = None
        self.main_window = None
        self.start_position = None # 3D vector for current telescope focus
        self._build_ui()
        self.update_schedule()

    def _build_ui(self):
        """Build the panel layout and widgets."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # # Header row: small close ('x') button at the top-left to hide the panel.
        # header_row = QHBoxLayout()
        # header_row.setContentsMargins(4, 4, 4, 0)
        # header_row.setSpacing(4)
        # self.close_btn = QPushButton("×")
        # self.close_btn.setToolTip("Hide schedule panel")
        # self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # self.close_btn.setFixedSize(22, 22)
        # self.close_btn.setStyleSheet(
        #     "QPushButton {"
        #     " background-color: transparent; color: #8b949e;"
        #     " border: 1px solid #30363d; border-radius: 4px;"
        #     " font-size: 13pt; font-weight: 600; padding: 0px;"
        #     "}"
        #     "QPushButton:hover { background-color: #21262d; color: #e6edf3; }"
        # )
        # self.close_btn.clicked.connect(self.hide_panel_requested.emit)
        # header_row.addWidget(self.close_btn)
        # header_row.addStretch(1)
        # main_layout.addLayout(header_row)



        # Compact stats bar — one unified style
        stats_grip = QHBoxLayout()
        stats_grip.setSpacing(16)
        _stat_style = "font-size: 10pt; font-weight: 600; color: #e6edf3;"

        self.total_tiles_label = QLabel("Tiles: 0")
        self.total_tiles_label.setStyleSheet(_stat_style)

        # FoM label
        self.fom_label = QLabel("FoM: 0.0")
        self.fom_label.setStyleSheet(_stat_style)

        self.total_prob_label = QLabel("Σp: 0.000")
        self.total_prob_label.setStyleSheet(_stat_style)

        self.total_time_label = QLabel("Total time: 0.0 s")
        self.total_time_label.setStyleSheet(_stat_style)

        stats_grip.addWidget(self.total_tiles_label)
        stats_grip.addWidget(self.total_prob_label)
        stats_grip.addWidget(self.total_time_label)
        stats_grip.addWidget(self.fom_label)
        main_layout.addLayout(stats_grip)

        # Which file the current schedule came from (set by MainWindow after load/save).
        self.schedule_file_label = QLabel("Schedule file: —")
        self.schedule_file_label.setStyleSheet(
            "font-size: 9pt; color: #8b949e; padding: 2px 0 6px 0;"
        )
        self.schedule_file_label.setWordWrap(True)
        self.schedule_file_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        main_layout.addWidget(self.schedule_file_label)

        # Manual dwell editing: multi-select rows, then apply a dwell time to all selected.
        dwell_row = QHBoxLayout()
        dwell_row.setSpacing(8)
        dwell_label = QLabel("Set dwell (s):")
        dwell_label.setStyleSheet("color: #e6edf3; font-size: 10pt;")
        self.dwell_spin = QDoubleSpinBox()
        self.dwell_spin.setRange(0.01, 1_000_000.0)
        self.dwell_spin.setDecimals(2)
        self.dwell_spin.setSuffix(" s")
        self.dwell_spin.setValue(60.0)
        self.dwell_spin.setToolTip(
            "Integration time per pointing for the next apply action."
        )
        self.apply_dwell_button = QPushButton("Apply to selected rows")
        self.apply_dwell_button.setObjectName("secondary")
        self.apply_dwell_button.setToolTip(
            "Select one or more schedule rows (click, Shift+click, Ctrl/Cmd+click), "
            "then click here to set the same dwell time on all selected tiles. "
            "Manual dwells are kept when you apply telescope defaults (unless you clear the lock in code)."
        )
        self.apply_dwell_button.clicked.connect(self._apply_dwell_to_selection)
        dwell_row.addWidget(dwell_label)
        dwell_row.addWidget(self.dwell_spin)
        dwell_row.addWidget(self.apply_dwell_button)
        dwell_row.addStretch(1)
        main_layout.addLayout(dwell_row)

        # Schedule table
        self.schedule_table = QTableWidget()
        self.schedule_table.setColumnCount(7)
        self.schedule_table.setHorizontalHeaderLabels([
            "Order", "Ra (°)", "Dec (°)", "Probability", "Dwell (s)", "Slew (°/s)", "End (s)"
        ])

        self.schedule_table.verticalHeader().setVisible(False)  # Hide row headers
        self.schedule_table.setAlternatingRowColors(True)  # Zebra stripes
        self.schedule_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)  # Full row select
        self.schedule_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # Multi-select
        self.schedule_table.setSortingEnabled(True)
        self.schedule_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.schedule_table.cellClicked.connect(self._on_row_clicked)
        self.schedule_table.setShowGrid(True)
        self.schedule_table.setWordWrap(False)

        header = self.schedule_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(1, 7):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)

        main_layout.addWidget(self.schedule_table, 4)
        # Allow the table to shrink freely when the splitter is dragged
        self.schedule_table.horizontalHeader().setMinimumSectionSize(30)

        # CDF plot widget (no timeline — was breaking layout)
        self.cdf_plot = CDFPlotWidget()
        self.cdf_plot.setMinimumHeight(200)
        self.cdf_plot.setMaximumHeight(320)
        main_layout.addWidget(self.cdf_plot, 3)

        self.deadlines_for_cdf = None

        # Bottom actions: visually group related controls to reduce scan time.
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        def make_button_group() -> tuple[QFrame, QHBoxLayout]:
            group = QFrame()
            group.setObjectName("scheduleActionGroup")
            group.setStyleSheet(
                """
                QFrame#scheduleActionGroup {
                    background-color: #161b22;
                    border: 1px solid #30363d;
                    border-radius: 8px;
                }
                """
            )
            group_layout = QHBoxLayout(group)
            group_layout.setContentsMargins(8, 8, 8, 8)
            group_layout.setSpacing(8)
            return group, group_layout

        self.load_button = QPushButton("Load Schedule")
        self.load_button.setObjectName("secondary")
        self.load_button.clicked.connect(self.on_load_schedule)

        # self.load_tiles_button = QPushButton("Load Tiles")
        # self.load_tiles_button.clicked.connect(self.on_load_tiles)
        # button_layout.addWidget(self.load_tiles_button)

        self.save_button = QPushButton("Save Schedule")
        self.save_button.clicked.connect(self._on_save_schedule)
        self.save_button.setObjectName("primary")

        self.remove_last_button = QPushButton("Remove Last")
        self.remove_last_button.setObjectName("secondary")
        self.remove_last_button.clicked.connect(self._on_remove_last)

        self.clear_button = QPushButton("Clear Schedule")
        self.clear_button.clicked.connect(self._on_clear_schedule)
        self.clear_button.setObjectName("danger")

        # Evaluate FoM button
        self.evaluate_button = QPushButton("Evaluate FoM")
        self.evaluate_button.setObjectName("secondary")
        self.evaluate_button.clicked.connect(self._on_evaluate_schedule)

        # History button
        self.fom_history_btn = QPushButton("FoM History")
        self.fom_history_btn.setObjectName("secondary")
        self.fom_history_btn.clicked.connect(self._on_show_fom_history)

        # Run GA
        self.run_GA_btn = QPushButton("Run GA")
        self.run_GA_btn.setObjectName("secondary")
        self.run_GA_btn.clicked.connect(self.on_run_GA)

        for btn in (
            self.load_button,
            self.save_button,
            self.remove_last_button,
            self.clear_button,
            self.evaluate_button,
            self.fom_history_btn,
            self.run_GA_btn,
        ):
            btn.setMinimumHeight(26)

        file_group, file_layout = make_button_group()
        for btn in (self.load_button, self.save_button):
            file_layout.addWidget(btn)

        edit_group, edit_layout = make_button_group()
        for btn in (self.remove_last_button, self.clear_button):
            edit_layout.addWidget(btn)

        analysis_group, analysis_layout = make_button_group()
        for btn in (self.evaluate_button, self.fom_history_btn, self.run_GA_btn):
            analysis_layout.addWidget(btn)

        actions_layout.addWidget(file_group)
        actions_layout.addWidget(edit_group)
        actions_layout.addWidget(analysis_group)
        actions_layout.addStretch(1)

        main_layout.addLayout(actions_layout)

    def _on_row_clicked(self, row, col):
        """Emit row index when user clicks schedule row."""
        self.row_selected.emit(row)

    def _schedule_index_for_table_row(self, table_row: int) -> int | None:
        """Return schedule order index for a visual table row (stable when sorting is on)."""
        item = self.schedule_table.item(table_row, 0)
        if item is None:
            return None
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None:
            return None
        return int(idx)

    def _apply_dwell_to_selection(self) -> None:
        """Set dwell time on all selected schedule rows and mark them telescope-resilient."""
        tiles = self.schedule.get_tiles()
        if not tiles:
            QMessageBox.information(
                self,
                "No schedule",
                "There are no tiles in the schedule.",
            )
            return
        selected = self.schedule_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(
                self,
                "No selection",
                "Select one or more rows in the schedule table, then click "
                '"Apply to selected rows".\n\n'
                "Use Ctrl+click or Shift+click to select multiple rows.",
            )
            return
        value = float(self.dwell_spin.value())
        indices: set[int] = set()
        for index in selected:
            table_row = index.row()
            si = self._schedule_index_for_table_row(table_row)
            if si is not None and 0 <= si < len(tiles):
                indices.add(si)
        if not indices:
            QMessageBox.warning(
                self,
                "Invalid selection",
                "Could not map the selection to schedule tiles. Try refreshing the schedule.",
            )
            return
        for si in sorted(indices):
            tile = tiles[si]
            tile["dwell_time"] = value
            tile["dwell_locked"] = True
        self.update_schedule()
        self.dwell_manual_changed.emit()
        if self.main_window is not None and hasattr(self.main_window, "_set_status"):
            n = len(indices)
            self.main_window._set_status(
                f"Dwell set to {value:.2f} s for {n} tile(s)."
            )

    def set_telescope_context(self, telescope, distance_func):
        """Store telescope and distance function for timing calculations."""
        self.telescope = telescope
        self.distance_func = distance_func

    def set_prob_context(self, max_prob):
        """Store max probability for consistent coloring."""
        self.max_prob = max_prob

    def set_start_position(self, position):
        """Set the telescope's current focus as a 3D (x, y, z) position."""
        self.start_position = position

    def set_schedule_file_status(
        self, full_path: str | None, modified: bool = False
    ) -> None:
        """
        Show which schedule file is associated with the current plan.

        :param full_path: Absolute path last used for load/save, or None if unknown.
        :param modified: True if the plan was edited after loading from that path.
        """
        if not full_path:
            self.schedule_file_label.setText("Schedule file: —")
            self.schedule_file_label.setToolTip(
                "No file on disk yet. Use Load Schedule or Save Schedule to track a path."
            )
            return
        name = os.path.basename(full_path)
        suffix = "  •  modified" if modified else ""
        self.schedule_file_label.setText(f"Schedule file: {name}{suffix}")
        self.schedule_file_label.setToolTip(full_path)

    def update_schedule(self):
        """Update the display with the current schedule data."""

        if self.schedule is None:
            return

        # Get current tiles
        tiles = self.schedule.get_tiles()

        # Clear and repopulate table
        self.schedule_table.setRowCount(0)  # Clear all rows

        prev_pos = self.start_position
        time_accum = 0.0
        total_prob = 0.0

        cdf_times =[]
        cdf_probs = []
        cumv_prob = 0.0

        if self.max_prob is not None:
            max_prob = self.max_prob
        else:
            max_prob = max((t.get("prob", 0.0) for t in tiles), default=1.0)

        for i, tile in enumerate(tiles):
            # Compute dwell/slew/time_accum
            dwell = tile.get("dwell_time", 60.0)
            slew = 0.0

            if self.telescope and prev_pos is not None and self.distance_func:
                dist_rad = self.distance_func(prev_pos, tile["position"])
                dist_deg = math.degrees(dist_rad)
                slew = dist_deg / self.telescope.slew_speed

            # Update cumulative time
            time_accum += slew + dwell
            total_prob += tile['prob']

            # CDF prob and end times
            cumv_prob += tile['prob']
            cdf_times.append(time_accum)
            cdf_probs.append(cumv_prob)

            # Probability column: blue accent (#58a6ff) by intensity
            prob = tile.get("prob", 0.0)
            norm = 0.0 if max_prob == 0 else prob / max_prob
            r, g, b = prob_to_blue_rgb(norm)
            prob_color = QColor(r, g, b, 200)

            # Add row with timing values
            self._add_tile_row(i, tile, slew, time_accum, prob_color)

            # Update previous position
            prev_pos = tile["position"]

        # Stats labels
        self.total_tiles_label.setText(f"Tiles: {len(tiles)}")
        self.total_prob_label.setText(f"Σp: {total_prob:.3f}")
        self.total_time_label.setText(f"Total time: {time_accum:.1f} s")

        # Status bar summary
        if self.main_window is not None:
            self.main_window.update_status_sch_summary(len(tiles), time_accum)

        self.cdf_plot.update_cdf(cdf_times, cdf_probs, self.deadlines_for_cdf)
        self._update_clear_button_state()

    def _add_tile_row(self, index, tile, slew=0.0, time_accum=0.0, prob_color=None):
        """
         Add a single tile to the table.

         Args:
             index (int): Row index.
             tile (dict): Tile data dictionary.
             optional slew & cumulative time.

        QColor(R, G, B, Alpha):
            Alpha set to 100 (semi-transparent so text is readable)
        """

        # Get current row count
        row = self.schedule_table.rowCount()
        self.schedule_table.insertRow(row)

        # Create items for each column

        # Order: first tile is current focus (slew 0)
        order_text = "1 (current)" if index == 0 else str(index + 1)
        order_item = QTableWidgetItem(order_text)
        order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        order_item.setData(Qt.ItemDataRole.UserRole, index)
        if index == 0:
            order_item.setBackground(QColor(40, 46, 56))  # Slightly lighter for current focus
        self.schedule_table.setItem(row, 0, order_item)

        # RA (get ra value and format with 2 decimals) and right align it
        ra_item = QTableWidgetItem(f"{tile['ra']:.2f}")
        ra_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.schedule_table.setItem(row, 1, ra_item)

        # Dec
        dec_item = QTableWidgetItem(f"{tile['dec']:.2f}")
        dec_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.schedule_table.setItem(row, 2, dec_item)

        # Probability
        prob_item = QTableWidgetItem(f"{tile['prob']:.4f}")
        prob_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if prob_color is not None:
            prob_item.setBackground(prob_color)
        else:
            prob_item.setBackground(QColor(88, 166, 255, 120))  # Blue fallback
        self.schedule_table.setItem(row, 3, prob_item)

        # Dwell time
        dwell = tile.get("dwell_time", 60.0)  # Default if missing
        dwell_item = QTableWidgetItem(f"{dwell:.2f}")
        dwell_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.schedule_table.setItem(row, 4, dwell_item)

        # Slew time
        slew_item = QTableWidgetItem(f"{slew:.2f}")
        slew_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.schedule_table.setItem(row, 5, slew_item)

        # End time (cumulative)
        end_item = QTableWidgetItem(f"{time_accum:.2f}")
        end_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.schedule_table.setItem(row, 6, end_item)

    def _on_clear_schedule(self):
        """Request clearing the current schedule."""
        if self.schedule:
            # self.schedule.clear()
            # self.update_schedule()
            self.schedule_cleared.emit()

    def _update_clear_button_state(self):
        """Enable/disable Clear button based on schedule content."""
        has_items = len(self.schedule.get_tiles()) > 0 # check schedule

        if has_items:
            self.clear_button.setEnabled(True)
            self.clear_button.setStyleSheet("")
        else:
            self.clear_button.setEnabled(False)
            self.clear_button.setStyleSheet("background-color: #ffcccc; color: #ffffff; border: none;")

        self.clear_button.style().unpolish(self.clear_button)
        self.clear_button.style().polish(self.clear_button)

    def _on_remove_last(self):
        """Remove the last tile."""
        self.remove_last_requested.emit()

    def on_load_schedule(self):
        """Open file dialog and load tiles."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Schedule",
            "",
            "Schedule Files (*.json *.csv)"
        )
        if path:
            self.schedule_load_requested.emit(path)

    def on_load_tiles(self):
        """Open file dialog and load tiles."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Tiles",
            "",
            "Tile Files (*.json *.csv)"
        )
        if path:
            self.tiles_load_requested.emit(path)

    def _on_save_schedule(self):
        """Open file dialog and emit save request."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Schedule",
            "",
            "Schedule Files (*.json *.csv)"
        )
        if path:
            self.schedule_save_requested.emit(path)

    def _on_evaluate_schedule(self) -> None:
        """Emit a request to evaluate the current schedule's FoM."""
        self.evaluate_schedule_requested.emit()

    def set_fom_value(self, value: float | None) -> None:
        """Update the displayed FoM in the stats bar."""

        if value is None:
            self.fom_label.setText("FoM: 0.0")
        else:
            self.fom_label.setText(f"FoM: {value:.3f}")

    def _on_show_fom_history(self) -> None:
        """Emit a request to show the FoM evaluation history."""
        self.show_fom_history_requested.emit()

    def set_deadlines_for_cdf(self, deadlines):
        """
        Set the list of deadline times to draw on the CDF plot.
        Called by the main window after the user evaluates FoM with given deadlines. Pass None to clear deadline lines.

        :param deadlines: list[float] | None
            Finite deadline values
        """
        self.deadlines_for_cdf = deadlines if deadlines is not None else None

    def on_run_GA(self):
        self.optimise_schedule_requested.emit()

    def set_ga_running(self, running: bool) -> None:
        """Reflect whether a GA optimisation is currently in progress."""
        self.run_GA_btn.setEnabled(not running)
        self.run_GA_btn.setText("Running GA..." if running else "Run GA")

