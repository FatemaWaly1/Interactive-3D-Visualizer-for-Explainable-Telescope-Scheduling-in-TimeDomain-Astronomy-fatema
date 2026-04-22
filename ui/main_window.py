import os
import math

from PySide6.QtGui import QAction

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QToolBar,
    QDockWidget,
    QFileDialog,
    QMenu,
    QInputDialog,
    QStatusBar,
    QMessageBox, QDialog, QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QFrame,
)

from PySide6.QtCore import QObject, QThread, QTimer, Qt, QSize, Signal, Slot
from pyvistaqt import QtInteractor

from controllers.interaction import InteractionController
from controllers.schedule_controller import ScheduleController
from sky_visualizer import SkyVisualizer
from ui.schedule_panel import SchedulePanel
from visualization.styles import NODE_RADIUS
from models.telescope import Telescope
from ui.telescope_panel import TelescopeDialog
from ui.fom_deadlines_dialog import FoMDeadlinesDialog
# from ui.coordinate_dialog import CoordinateDialog
from services.geometry import angdist_vec
from services.schedule_io import (
    load_schedule_file,
    parse_deadlines_finite,
    save_schedule_file,
)
from services.schedule_metrics import compute_merits_for_deadlines
from services.telescope_io import save_telescope
from services.fom_evaluator import evaluate_schedule_fom
from services.ga_scheduler import fitness_function, run_ga, shift_deadlines

from datetime import datetime

from ui.ga_progress_dialog import GAProgressDialog
from ui.scenario_compare_dialog import ScenarioCompareDialog

import numpy as np


class GAWorker(QObject):
    """Run GA in the background and emit generation-by-generation progress."""

    progress = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        tiles,
        telescope,
        deadlines,
        merits,
        start_position,

        time_points,
        n_generations: int = 100,
        pop_size: int = 50,
        max_opt_seconds: float | None = None,  # runtime cap
        planned_opt_seconds: float | None = None  # objective planning budget
    ):
        super().__init__()
        self.tiles = list(tiles)
        self.telescope = telescope
        self.deadlines = list(deadlines)
        self.merits = list(merits)
        self.start_position = start_position
        self.time_points = list(time_points)
        self.n_generations = n_generations
        self.pop_size = pop_size
        self.max_opt_seconds = max_opt_seconds
        self.planned_opt_seconds = planned_opt_seconds

    @Slot()
    def run(self) -> None:
        try:
            best_order, history = run_ga(
                tiles=self.tiles,
                telescope=self.telescope,
                deadlines=self.deadlines,
                merits=self.merits,
                start_position=self.start_position,
                n_generations=self.n_generations,
                pop_size=self.pop_size,
                time_points=self.time_points,
                progress_callback=self.progress.emit,
                max_opt_seconds=self.max_opt_seconds,
                planned_opt_seconds=self.planned_opt_seconds,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.finished.emit({"best_order": best_order, "history": history})

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GW Follow-up Telescope Scheduler")
        self.resize(1200, 800)

        # Central widget and layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter (left (sphere), right(schedule))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter)

        # left
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.vtk_widget = QtInteractor()
        left_layout.addWidget(self.vtk_widget)
        splitter.addWidget(left_container)

        self.visualizer = SkyVisualizer(fov_size=1.5)
        self.visualizer.renderer.plotter = self.vtk_widget

        # Right: schedule dashboard
        self.schedule_panel = SchedulePanel(self.visualizer.schedule)
        splitter.addWidget(self.schedule_panel)
        splitter.setSizes([800, 520])

        # Store current telescope
        self.telescope = None

        # Controller for schedule-related logic
        self.schedule_controller = ScheduleController(
            self.visualizer.schedule,
            self.visualizer.tiles,
            self.visualizer.renderer,
        )

        # Connect schedule signals
        self.schedule_panel.schedule_cleared.connect(self.on_schedule_cleared)
        self.schedule_panel.remove_last_requested.connect(self._on_remove_last)
        self.schedule_panel.schedule_load_requested.connect(self.on_load_schedule)
        self.schedule_panel.schedule_save_requested.connect(self.on_save_schedule)
        self.schedule_panel.tiles_load_requested.connect(self.on_load_tiles)
    #    self.schedule_panel.set_start_position(chosen_tile["positions"])
        self.schedule_panel.row_selected.connect(self._on_schedule_row_selected)
        self.schedule_panel.set_telescope_context(self.telescope, angdist_vec)
        self.schedule_panel.set_prob_context(None)
        self.schedule_panel.evaluate_schedule_requested.connect(
            self.on_evaluate_schedule_clicked
        )
        self.schedule_panel.show_fom_history_requested.connect(
            self.on_show_fom_history_clicked
        )
        self.schedule_panel.optimise_schedule_requested.connect(
            self.on_optimise_sch_clicked
        )
        self.schedule_panel.dwell_manual_changed.connect(self.mark_schedule_file_modified)

        # Give schedule panel a handle back to the main window (for status updates)
        self.schedule_panel.main_window = self

        # Insert-mode state
        self.insert_mode = False
        self.insert_index = None

        self._path_anim_timer = QTimer(self)
        self._path_anim_timer.setSingleShot(False)
        self._path_anim_timer.timeout.connect(self._on_path_anim_tick)
        self._path_anim_tiles = []
        self._path_anim_path = None
        self._path_anim_brightness = None
        self._path_anim_total_points = 0
        self._path_anim_total_frames = 0
        self._path_anim_frame = 0

        self.refresh_scene()

        # Listen for right-click using Qt context menu
        self.vtk_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.vtk_widget.customContextMenuRequested.connect(self.on_right_click)

        # Telescope settings dialog
        self.telescope_dialog = TelescopeDialog()
        self.telescope_dialog.telescope_saved.connect(self.on_telescope_saved)
        self.telescope_dialog.telescope_applied.connect(self.on_apply_telescope)

        # Toolbar
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(toolbar)

        load_tiles = QAction("Load Tiles", self)
        load_tiles.triggered.connect(lambda: self._open_tiles_dialog())
        toolbar.addAction(load_tiles)

        # Telescope settings button
        open_tel = QAction("Telescope Settings", self)
        open_tel.triggered.connect(self._open_tele_dialog)
        toolbar.addAction(open_tel)

        toolbar.addSeparator()

        # Read-only “active telescope” label on the toolbar
        self.toolbar_telescope_label = QLabel("🔭 No active telescope")
        self.toolbar_telescope_label.setObjectName("toolbarTelescopeLabel")
        self.toolbar_telescope_label.setStyleSheet("color: #8b949e; margin-left: 8px;")
        toolbar.addWidget(self.toolbar_telescope_label)

        # Menu bar
        menubar = self.menuBar()
        menubar.setStyleSheet("""
                    QMenuBar {
                        background-color: #0d1117;
                        color: #ffffff;
                        padding-left: 4px;
                        padding-right: 12px;
                    }
                    QMenuBar::item {
                        background: transparent;
                        padding: 4px 10px;
                    }
                    QMenuBar::item:selected {
                        background-color: #21262d;
                    }
                    QMenuBar::item:pressed {
                        background-color: #30363d;
                    }
                    QMenu {
                        background-color: #0d1117;
                        color: #ffffff;
                        border: 1px solid #30363d;
                        padding: 4px 2px;
                    }
                    QMenu::item {
                        padding: 4px 20px 4px 12px;
                    }
                    QMenu::item:selected {
                        background-color: #21262d;
                    }
                """)

        file_menu = menubar.addMenu("File")
        file_menu.addAction("Load Tiles", self._open_tiles_dialog)
        file_menu.addAction("Load Schedule", self._open_sch_dialog)
        file_menu.addAction("Save Schedule", self._save_sch_dialog)

        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction("Scenario compare", self._open_scenario_compare)

        # Keep the last menu item away from the window edge (avoids flush/overlap on resize).
        mb_right_pad = QWidget(menubar)
        mb_right_pad.setFixedWidth(10)
        mb_right_pad.setStyleSheet("background: transparent;")
        menubar.setCornerWidget(mb_right_pad, Qt.Corner.TopRightCorner)

        # Status bar: tele & sch summary
        status = QStatusBar(self)
        self.setStatusBar(status)

        self.status_telescope_label = QLabel("Telescope: None")
        self.status_telescope_label.setStyleSheet("color: #8b949e;")
        self.statues_sch_label = QLabel("Status: 0 tiles | 0.0 s")
        self.statues_sch_label.setStyleSheet("color: #8b949e; padding-right: 10px;")

        status.addWidget(self.status_telescope_label)
        status.addPermanentWidget(self.statues_sch_label)

        self.fom_history: list[dict] = []
        self.ga_fom_history: list[dict] = []
        # Last deadlines/merits from FoM dialog; used by GA. None until user evaluates FoM.
        self.curr_deadlines = None
        self.curr_merits = None
        self._ga_thread: QThread | None = None
        self._ga_worker: GAWorker | None = None
        self._ga_progress_dialog: GAProgressDialog | None = None
        self._ga_baseline_fom: float = 0.0
        self._ga_input_tiles = []
        self._ga_start_position = None
        # Last FoM computed for the current schedule (Evaluate FoM or GA); used when saving JSON metadata.
        self._last_schedule_fom: float | None = None

        # Last schedule file path (load/save); "modified" after edits so user knows disk may differ.
        self._schedule_file_path: str | None = None
        self._schedule_file_dirty: bool = False
        self._refresh_schedule_file_indicator()

    def _refresh_schedule_file_indicator(self) -> None:
        """Update the schedule panel line showing the active file path."""
        self.schedule_panel.set_schedule_file_status(
            self._schedule_file_path, self._schedule_file_dirty
        )

    def mark_schedule_file_modified(self) -> None:
        """Call when the plan diverges from the last loaded/saved file (e.g. add/remove/edit)."""
        if self._schedule_file_path:
            self._schedule_file_dirty = True
        self._refresh_schedule_file_indicator()

    def _set_schedule_file_from_disk(self, path: str | None) -> None:
        """Record a path after load or save; clears the modified flag."""
        if path:
            self._schedule_file_path = os.path.normpath(os.path.abspath(path))
        else:
            self._schedule_file_path = None
        self._schedule_file_dirty = False
        self._refresh_schedule_file_indicator()

    def _open_tele_dialog(self):
        self.telescope_dialog.show()
        self.telescope_dialog.raise_()
        self.telescope_dialog.activateWindow()

    def _on_schedule_row_selected(self, row):
        """Highlight node on sphere when row is clicked."""
        tiles = self.visualizer.schedule.selected_tiles
        if row < 0 or row >= len(tiles):
            return
        tile = tiles[row]
        tile_idx = self.visualizer.tiles.index(tile)
        self.visualizer.renderer.highlight_selected_tile(tile, tile_idx)

    def _open_tiles_dialog(self):
        """Open file dialog to load tiles."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Tiles",
            "",
            "Tile Files (*.json *.csv)"
        )
        if path:
            self.on_load_tiles(path)

    def _open_sch_dialog(self):
        """Open file dialog to load schedule."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Schedule",
            "",
            "Schedule Files (*.json *.csv)"
        )
        if path:
            self.on_load_schedule(path)

    def _save_sch_dialog(self):
        """Open file dialog to save schedule."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Schedule",
            "",
            "Schedule Files (*.json *.csv)"
        )
        if path:
            self.on_save_schedule(path)

    def on_right_click(self, pos):
        """
        Handle right-click on the sphere. IF a scheduled node is clicked,
        show a context menu: Remove, Edit dwell time, Insert before/after.
        """

        picker = self.visualizer.renderer.plotter.picker
        if picker is None:
            return

        # Convert Qt widget coords to vtk coors
        x = pos.x()
        y = self.vtk_widget.height() - pos.y()

        # Pick at that position
        picker.Pick(x, y, 0, self.visualizer.renderer.plotter.renderer)
        point_id = picker.GetPointId()

        # Stop if nothing picked, stop
        if point_id == -1:
            return

        # Find corresponding tile from point index (assumes node order == tiles list order)
        picked_tile = self.visualizer.tiles[point_id]

        # Only allow right-click menu for scheduled tiles
        if picked_tile not in self.visualizer.schedule.selected_tiles:
            return

        # Build context menu
        menu = QMenu(self)
        action_remove = menu.addAction("Remove")
        action_edit = menu.addAction("Edit dwell time")
        action_insert_before = menu.addAction("Insert before")
        action_insert_after = menu.addAction("Insert after")

        # Show menu at mouse cursor
        action = menu.exec_(self.mapToGlobal(pos))
        if action is None:
            return

        # Handle actions
        if action == action_remove:
            self.remove_tile(picked_tile)
        elif action == action_edit:
            self._edit_dwell_time(picked_tile)
        elif action == action_insert_before:
            self._insert_relative(picked_tile, before=True)
        elif action == action_insert_after:
            self._insert_relative(picked_tile, before=False)

    def remove_tile(self, tile):
        """Remove a tile from the schedule."""
        removed = self.schedule_controller.remove_tile(tile)
        if removed is None:
            return

        # Remove red marker for this tile index
        tile_idx = self.visualizer.tiles.index(removed)
        self.visualizer.renderer.remove_selected_tile_marker(tile_idx)

        # Update labels & UI
        self.visualizer.renderer.draw_schedule_labels(
            self.visualizer.schedule.selected_tiles
        )
        self.schedule_panel.update_schedule()
        self.mark_schedule_file_modified()

    def _edit_dwell_time(self, tile):
        """Prompt user to update dwell time."""
        current = tile.get("dwell_time", 60.0)
        value, ok = QInputDialog.getDouble(
            self,
            "Edit dwell time",
            "Dwell time (s):",
            current,
            1.0,
            100000.0,
            1
        )
        if ok:
            tile["dwell_time"] = value
            tile["dwell_locked"] = True
            self.schedule_panel.update_schedule()
            self.mark_schedule_file_modified()

    def _insert_relative(self, tile, before=True):
        """
        Start insert mode. The next left-click will insert tile before/after the given tile.
        """
        schedule = self.visualizer.schedule.selected_tiles

        if tile not in schedule:
            return

        idx = schedule.index(tile)
        self.insert_index = idx if before else idx + 1
        self.insert_mode = True

        print("Insert mode active: click a node to insert.")

    def refresh_scene(self):
        """Clear and redraw the scene using current tiles."""
        self._stop_path_animation()
        plotter = self.visualizer.renderer.plotter
        plotter.clear()

        # Add sphere, tiles, and nodes
        self.visualizer.renderer.add_sphere_wireframe()
        if self.visualizer.tiles:
            self.visualizer.renderer.add_tile_patches(self.visualizer.tiles)
            self.visualizer.renderer.add_node_point_cloud(self.visualizer.tiles)

        # Recreate controller and picking
        self.visualizer.controller = InteractionController(
            self.visualizer.tiles,
            self.visualizer.schedule,
            self.visualizer.renderer,
            max_pick_distance=NODE_RADIUS * 1.25,
            schedule_panel=self.schedule_panel,
            main_window=self
        )
        self.visualizer.renderer.enable_picking(
            self.visualizer.controller.handle_tile_click
        )

        plotter.reset_camera()
        plotter.render()

    def on_schedule_cleared(self):
        self._set_schedule_file_from_disk(None)
        self._last_schedule_fom = None
        self._stop_path_animation()
        self.schedule_controller.clear()
        self.visualizer.renderer.clear_selected_tiles()
        for tile in self.visualizer.tiles:
            tile.pop("order", None)
        self.visualizer.renderer.clear_schedule_labels()
        self.visualizer.renderer.clear_schedule_path()
        self.schedule_panel.update_schedule()
        self.schedule_panel.set_fom_value(None)
        self.schedule_panel.set_deadlines_for_cdf(None)
        self.refresh_scene()

    def _on_remove_last(self):
        """Remove the last scheduled tile."""
        last_tile = self.schedule_controller.remove_last()
        if last_tile is None:
            return

        self.schedule_panel.update_schedule()
        tile_index = self.visualizer.tiles.index(last_tile)
        self.visualizer.renderer.remove_selected_tile_marker(tile_index)

        self._render_schedule_overlays(
            self.visualizer.schedule.selected_tiles,
            animate_path=False,
        )
        self.mark_schedule_file_modified()

    def _apply_fom_metadata_from_file(self, meta: dict) -> None:
        """Restore deadlines, merits, and optional FoM display from saved JSON metadata."""
        dfin = meta.get("deadlines_finite")
        if isinstance(dfin, list) and dfin:
            try:
                deadlines_finite = [float(x) for x in dfin]
            except (TypeError, ValueError):
                return
            if len(deadlines_finite) < 1:
                return
            deadlines = list(deadlines_finite) + [float("inf")]
            self.curr_deadlines = deadlines
            self.curr_merits = compute_merits_for_deadlines(deadlines)
            self.schedule_panel.set_deadlines_for_cdf(list(deadlines_finite))
        lf = meta.get("last_fom")
        if lf is not None:
            try:
                self._last_schedule_fom = float(lf)
                self.schedule_panel.set_fom_value(self._last_schedule_fom)
            except (TypeError, ValueError):
                pass

    def _build_fom_metadata_for_save(self) -> dict | None:
        """Embed FoM/deadline context in JSON schedule files when available."""
        if not getattr(self, "curr_deadlines", None):
            return None
        dfin = [x for x in self.curr_deadlines if x != float("inf")]
        if not dfin:
            return None
        meta: dict = {"deadlines_finite": dfin}
        last_fom = self._last_schedule_fom
        if last_fom is None and self.fom_history:
            last_fom = float(self.fom_history[-1]["FoM"])
        if last_fom is not None:
            meta["last_fom"] = last_fom
        if self.ga_fom_history:
            h = self.ga_fom_history[-1]
            meta["ga"] = {
                "fom_before": float(self._ga_baseline_fom),
                "fom_after": float(h.get("FoM", 0.0)),
                "t_opt": float(h.get("t_opt", 0.0)),
            }
        return meta

    def on_load_schedule(self, path):
        """Load schedule from file."""
        tiles_data, fom_meta = load_schedule_file(path)
        if not tiles_data:
            return
        if isinstance(fom_meta, dict):
            self._apply_fom_metadata_from_file(fom_meta)

        def _finder(ra, dec, tol=1e-3):
            for tile in self.visualizer.tiles:
                if math.isclose(tile["ra"], ra, abs_tol=tol) and math.isclose(
                    tile["dec"], dec, abs_tol=tol
                ):
                    return tile
            return None

        self.schedule_controller.load_from_data(tiles_data, _finder)

        # Highlight all scheduled tiles
        for tile in self.visualizer.schedule.selected_tiles:
            tile_index = self.visualizer.tiles.index(tile)
            self.visualizer.renderer.highlight_selected_tile(tile, tile_index)

        self.schedule_panel.update_schedule()
        self._render_schedule_overlays(self.visualizer.schedule.selected_tiles, animate_path=True)
        self._set_schedule_file_from_disk(path)

    def on_load_tiles(self, path):
        """Load tiles from file and redraw the scene."""
        self.visualizer.load_tiles_from_file(path, normalize=True, clear_existing=True)
        self.visualizer.schedule.clear()
        self._set_schedule_file_from_disk(None)
        max_prob = max((t.get("prob", 0.0) for t in self.visualizer.tiles), default=1.0)
        self.schedule_panel.set_prob_context(max_prob)
        self.schedule_panel.update_schedule()
        self.refresh_scene()
        self._set_status(f"Loaded {len(self.visualizer.tiles)} tiles")

    def on_save_schedule(self, path):
        """Save schedule to a file (JSON may include FoM/deadline metadata)."""
        tiles = self.visualizer.schedule.get_tiles()
        data = [{"ra": t["ra"], "dec": t["dec"], "prob": t["prob"], "dwell_time": t.get("dwell_time", 60.0)} for t in tiles]
        meta = self._build_fom_metadata_for_save()
        save_schedule_file(path, data, fom_metadata=meta)
        self._set_schedule_file_from_disk(path)
        extra = " (with FoM metadata)" if meta and path.lower().endswith(".json") else ""
        self._set_status(f"Schedule saved — {os.path.basename(path)}{extra}")

    def _find_tile_by_radec(self, ra, dec, tol=1e-3):
        """Find a tile in current tiles list."""
        for tile in self.visualizer.tiles:
            if math.isclose(tile["ra"], ra, abs_tol=tol) and math.isclose(tile["dec"], dec, abs_tol=tol):
                return tile
        return None

    def closeEvent(self, event):
        # Close schedule window when main window closes
        super().closeEvent(event)

    def on_telescope_saved(self, data):
        """Save telescope to disk."""
        save_telescope(data)
        self.statusBar().showMessage(
            f"Saved Telescope: {data['name']}", 3000
        )

    def on_apply_telescope(self):
        """Recompute schedule timing using current telescope settings."""
        data = self._read_telescope_inputs()
        if data is None:
            self._set_status("Invalid telescope values — check name, slew speed, and dwell time.")
            return
        self._apply_telescope_settings(data, update_tile_dwell=True)

    def _read_telescope_inputs(self):
        """Read current telescope inputs from the telescope dialog."""
        try:
            return {
                "name": self.telescope_dialog.name_input.text().strip(),
                "slew_speed": float(self.telescope_dialog.speed_input.value()),
                "dwell_time": float(self.telescope_dialog.dwell_time_input.value()),
            }
        except ValueError:
            return None

    def _apply_telescope_settings(self, data, update_tile_dwell=True):
        """Store telescope settings and optionally update tile dwell times."""
        self.telescope = Telescope(
            name=data["name"],
            slew_speed=data["slew_speed"],
            dwell_time=data["dwell_time"],
        )
        self.status_telescope_label.setText(
            f"Telescope: {self.telescope.name} | {self.telescope.slew_speed:.3f} °/s | {self.telescope.dwell_time:.1f} s"
        )
        self.toolbar_telescope_label.setText(
            f"🔭 Telescope : {self.telescope.name}"
        )
        self._set_status(f"Telescope applied: {self.telescope.name}")
        if update_tile_dwell:
            for tile in self.visualizer.schedule.selected_tiles:
                if not tile.get("dwell_locked"):
                    tile["dwell_time"] = self.telescope.dwell_time
        self.schedule_panel.set_telescope_context(self.telescope, angdist_vec)
        self.schedule_panel.update_schedule()

    def _set_status(self, text):
        """Update status bar text."""
        self.statusBar().showMessage(text)

    def update_status_sch_summary(self, tile_count: int, total_time: float):
        self.statues_sch_label.setText(
            f"Schedule: {tile_count} tiles | {total_time:.1f} s"
        )

    def on_evaluate_schedule_clicked(self) -> None:
        """Evaluate current schedule's FoM. Opens one dialog: enter deadlines, then see FoM details in the same window."""
        tiles = self.visualizer.schedule.get_tiles()
        if not tiles:
            self._set_status("Cannot evaluate FoM: schedule is empty.")
            return

        dialog = FoMDeadlinesDialog(self)
        dialog.setWindowTitle("Calculate expected Figure of Merit")

        def on_deadlines_submitted(text: str) -> None:
            try:
                deadlines_finite = parse_deadlines_finite(text)
                evaluation = evaluate_schedule_fom(
                    tiles=tiles,
                    telescope=self.telescope,
                    start_position=self.schedule_panel.start_position,
                    deadlines_finite=deadlines_finite,
                )
            except ValueError as exc:
                dialog.set_error(str(exc))
                return

            self.fom_history.append({
                "FoM": evaluation.fom,
                "Deadlines": list(deadlines_finite),
                "Timestamps": datetime.now(),
            })
            self._set_status(
                f"Expected Figure of Merit: {evaluation.fom:.3f} "
                f"(deadlines: {', '.join(f'{d:.1f}' for d in deadlines_finite)})"
            )
            if self.schedule_panel is not None:
                self.schedule_panel.set_fom_value(evaluation.fom)

            dialog.set_fom_results(
                evaluation.deadlines_full,
                evaluation.merits,
                evaluation.fom,
            )

            self.curr_deadlines = evaluation.deadlines_full
            self.curr_merits = evaluation.merits
            self._last_schedule_fom = float(evaluation.fom)

            # So the CDF plot can draw vertical lines at these deadlines.
            self.schedule_panel.set_deadlines_for_cdf(list(deadlines_finite))
            self.schedule_panel.update_schedule()

        dialog.deadlines_submitted.connect(on_deadlines_submitted)
        dialog.exec()

    def on_show_fom_history_clicked(self) -> None:
        """Show a simple dialog with the history of FoM evaluations."""
        if not self.fom_history:
            self._set_status("No FoM history yet. Evaluate a schedule first.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("FoM History")
        dialog.resize(720, 420)
        dialog.setStyleSheet(
            """
            QDialog {
                background-color: #0d1117;
                color: #e6edf3;
            }
            QTableWidget {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 8px;
                gridline-color: #30363d;
                selection-background-color: #1f6feb;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                border: 0;
                border-bottom: 1px solid #30363d;
                padding: 8px;
                font-weight: 600;
            }
            QLabel {
                color: #8b949e;
            }
            QFrame#historyToolbar {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            """
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        summary = QLabel(
            f"{len(self.fom_history)} evaluation{'s' if len(self.fom_history) != 1 else ''} recorded"
        )
        layout.addWidget(summary)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Time", "FoM", "Deadlines"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        table.setRowCount(len(self.fom_history))
        for row, entry in enumerate(self.fom_history):
            ts_str = entry["Timestamps"].strftime("%Y-%m-%d %H:%M:%S")
            fom_str = f"{entry['FoM']:.3f}"
            deadlines_str = ", ".join(f"{d:.1f}" for d in entry["Deadlines"])

            table.setItem(row, 0, QTableWidgetItem(ts_str))
            table.setItem(row, 1, QTableWidgetItem(fom_str))
            table.setItem(row, 2, QTableWidgetItem(deadlines_str))

        table.resizeColumnsToContents()
        layout.addWidget(table)

        toolbar = QFrame()
        toolbar.setObjectName("historyToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 10, 12, 10)
        toolbar_layout.setSpacing(8)
        toolbar_layout.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(96)
        close_btn.clicked.connect(dialog.accept)
        toolbar_layout.addWidget(close_btn)
        toolbar_layout.addStretch(1)
        layout.addWidget(toolbar)

        dialog.exec()

    def on_optimise_sch_clicked(self):
        """Run GA in the background and show live FoM progress."""
        if self._ga_thread is not None:
            self._set_status("GA optimisation is already running.")
            if self._ga_progress_dialog is not None:
                self._ga_progress_dialog.raise_()
                self._ga_progress_dialog.activateWindow()
            return

        tiles = self.visualizer.schedule.get_tiles()
        if not tiles:
            self._set_status("Cannot optimise: schedule is empty.")
            return

        if not getattr(self, "curr_deadlines", None) or not getattr(self, "curr_merits", None):
            self._set_status("Cannot optimise: define deadlines/FoM first (Evaluate FoM).")
            return

        budget_s = self._choose_ga_budget_seconds()
        if budget_s is None:
            self._set_status("GA cancelled.")
            return

        # Bild logging checkpoints up to selected GA budget
        time_points = list(range(1, max(2, int(math.ceil(budget_s)) + 1)))

        self._set_status(
            f"GA started (budget {budget_s:.1f}s). "
            f"Objective uses deadlines shifted by planned optimization time."
        )

        start_position = self.schedule_panel.start_position

        # FoM for the current (pre-GA) schedule at optimization time 0
        current_order = list(range(len(tiles)))
        fom_before = fitness_function(
            order=current_order,
            tiles=tiles,
            telescope=self.telescope,
            deadlines=self.curr_deadlines,
            merits=self.curr_merits,
            start_position=start_position
        )

        #time_points = list(range(1, 21))
        self._ga_input_tiles = list(tiles)
        self._ga_start_position = start_position
        self._ga_baseline_fom = float(fom_before)

        self._ga_progress_dialog = GAProgressDialog(self)
        self._ga_progress_dialog.set_started(self._ga_baseline_fom)
        self._ga_progress_dialog.show()
        self._ga_progress_dialog.raise_()
        self._ga_progress_dialog.activateWindow()

        self.schedule_panel.set_ga_running(True)
        self._set_status("GA optimisation started. Streaming live FoM progress...")

        self._ga_thread = QThread(self)
        self._ga_worker = GAWorker(
            tiles=tiles,
            telescope=self.telescope,
            deadlines=self.curr_deadlines,
            merits=self.curr_merits,
            start_position=start_position,
            time_points=time_points,
            max_opt_seconds=budget_s, # actual runtime cutoff
            planned_opt_seconds=budget_s  # objective shift uses remaining-time policy
        )
        self._ga_worker.moveToThread(self._ga_thread)
        self._ga_thread.started.connect(self._ga_worker.run)
        self._ga_worker.progress.connect(self._on_ga_progress)
        self._ga_worker.finished.connect(self._on_ga_finished)
        self._ga_worker.failed.connect(self._on_ga_failed)
        self._ga_worker.finished.connect(self._ga_thread.quit)
        self._ga_worker.failed.connect(self._ga_thread.quit)
        self._ga_thread.finished.connect(self._cleanup_ga_worker)
        self._ga_thread.start()

    @Slot(dict)
    def _on_ga_progress(self, payload: dict) -> None:
        """Update the live GA chart with best-so-far FoM."""
        if self._ga_progress_dialog is None:
            return
        self._ga_progress_dialog.update_progress(
            generation=int(payload.get("generation", 0)),
            elapsed_s=float(payload.get("elapsed_s", 0.0)),
            best_fom=float(payload.get("best_fom", 0.0)),
            baseline_fom=self._ga_baseline_fom,
        )

    @Slot(dict)
    def _on_ga_finished(self, payload: dict) -> None:
        """Apply the best GA schedule and finalise the progress panel."""
        best_order = payload.get("best_order", [])
        history = payload.get("history", [])
        tiles = self._ga_input_tiles
        start_position = self._ga_start_position

        if not best_order:
            self.schedule_panel.set_ga_running(False)
            self._set_status("GA did not return a valid order.")
            if self._ga_progress_dialog is not None:
                self._ga_progress_dialog.mark_failed("GA did not return a valid order.")
            return

        # Use the GA's final returned best order to update the visible schedule
        best_tiles = [tiles[i] for i in best_order]

        # Clear existing schedule and rebuild with GA order
        self.on_schedule_cleared()

        # Assign explicit 'order' indices so renderer can label tiles
        for idx, tile in enumerate(best_tiles, start=1):
            tile["order"] = idx
            self.visualizer.schedule.add_tile(tile)

        # Update schedule panel timing/table
        self.schedule_panel.update_schedule()

        # Redraw base scene (sphere + nodes)
        self.refresh_scene()

        # Highlight scheduled tiles and draw path/labels
        for tile in self.visualizer.schedule.selected_tiles:
            tile_idx = self.visualizer.tiles.index(tile)
            self.visualizer.renderer.highlight_selected_tile(tile, tile_idx)

        self._render_schedule_overlays(self.visualizer.schedule.selected_tiles, animate_path=True)

        # Report FoM at the last requested cutoff (typically 20s)
        if history:
            t_last = float(history[-1]["t_opt"])
            fom_after = float(history[-1]["FoM"])
        else:
            t_last = 0.0
            fom_after = fitness_function(
                order=best_order,
                tiles=tiles,
                telescope=self.telescope,
                deadlines=self.curr_deadlines,
                merits=self.curr_merits,
                start_position=start_position,
            )

        # Deadlines shown on the CDF should reflect remaining time after optimization.
        shifted_deadlines = shift_deadlines(self.curr_deadlines, t_last)
        finite_deadlines = [d for d in shifted_deadlines if d != float("inf")]

        self._set_status(
            f"GA optimisation (t={t_last:.0f}s): FoM {self._ga_baseline_fom:.3f} → {fom_after:.3f} "
            f"(effective deadlines: {', '.join(f'{d:.1f}' for d in finite_deadlines)})"
        )

        # Store GA snapshots for possible thesis/UI reporting later.
        self.ga_fom_history = history
        self._last_schedule_fom = float(fom_after)

        if self.schedule_panel is not None:
            self.schedule_panel.set_fom_value(fom_after)
            self.schedule_panel.set_deadlines_for_cdf(finite_deadlines)
            self.schedule_panel.update_schedule()
            self.schedule_panel.set_ga_running(False)

        if self._ga_progress_dialog is not None:
            self._ga_progress_dialog.mark_finished(len(history), fom_after, self._ga_baseline_fom)

    @Slot(str)
    def _on_ga_failed(self, message: str) -> None:
        """Show background GA failures without leaving the UI stuck."""
        self.schedule_panel.set_ga_running(False)
        self._set_status(f"GA optimisation failed: {message}")
        if self._ga_progress_dialog is not None:
            self._ga_progress_dialog.mark_failed(f"GA optimisation failed: {message}")

    @Slot()
    def _cleanup_ga_worker(self) -> None:
        """Release background GA objects once the run completes."""
        if self._ga_worker is not None:
            self._ga_worker.deleteLater()
            self._ga_worker = None
        if self._ga_thread is not None:
            self._ga_thread.deleteLater()
            self._ga_thread = None

    def _first_finite_deadline(self) -> float | None:
        """Return the first finite FoM deadline, or None if missing."""
        if not self.curr_deadlines:
            return None
        finite = [float(d) for d in self.curr_deadlines if d != float("inf")]
        return finite[0] if finite else None

    def _default_ga_budget_seconds(self) -> float:
        """
        Auto policy for GA planning budget
        """

        first_deadline = self._first_finite_deadline()
        if first_deadline is None:
            return 10.0  # fallback when unavailable deadlines

        return max(2.0, min(30.0, 0.10 * first_deadline))

    def _choose_ga_budget_seconds(self) -> float | None:
        """
        Optional manual override.
        if blank input, use auto policy
        return none if user cancels
        """
        auto_budget = self._default_ga_budget_seconds()
        first_deadline = self._first_finite_deadline()

        text, ok = QInputDialog.getText(
            self,
            "GA planning budget",
            (
                f"GA budget in seconds (blank = auto policy).\n"
                f"Auto currently: {auto_budget:.1f}s"
                + (f" | First deadline: {first_deadline:.1f}s" if first_deadline is not None else "")
            ),
            text=""
        )
        if not ok:
            return None  # user cancelled

        if not text.strip():
            budget = auto_budget
        else:
            try:
                budget = float(text.strip())
            except ValueError:
                QMessageBox.warning(self, "Invalid budget", "Please enter a numeric value in seconds.")
                return None
            if budget <= 0.0:
                QMessageBox.warning(self, "Invalid budget", "GA budget must be > 0.")
                return None

        # Guardrail: planning budget must be > first deadline
        if first_deadline is not None and budget >=first_deadline:
            QMessageBox.warning(
                self,
                "Budget too high",
                f"GA budget ({budget:.1f}s) must be < first deadline ({first_deadline:.1f}s)"
            )
            return None

        return budget

    def _render_schedule_overlays(self, tiles, animate_path: bool = False) -> None:
        """Draw labels immediately and path either instantly or via adaptive animation."""
        self.visualizer.renderer.draw_schedule_labels(tiles)
        if animate_path:
            self._start_path_animation(tiles)
        else:
            self._stop_path_animation()
            self.visualizer.renderer.draw_schedule_path(tiles)

    def _start_path_animation(self, tiles) -> None:
        """Animate the schedule path as one continuous flowing stroke."""
        self._stop_path_animation()
        ordered_tiles = list(tiles)
        n_tiles = len(ordered_tiles)
        if n_tiles < 2:
            self.visualizer.renderer.draw_schedule_path(ordered_tiles)
            return

        duration_ms = self._adaptive_path_duration_ms(n_tiles)
        if duration_ms <= 0:
            self.visualizer.renderer.draw_schedule_path(ordered_tiles)
            return

        self._path_anim_tiles = ordered_tiles
        self._path_anim_path, self._path_anim_brightness = self.visualizer.renderer.build_schedule_path_geometry(
            ordered_tiles
        )
        if self._path_anim_path is None or len(self._path_anim_path) < 2:
            self.visualizer.renderer.draw_schedule_path(ordered_tiles)
            self._stop_path_animation()
            return

        self._path_anim_total_points = len(self._path_anim_path)
        frame_interval_ms = 33
        self._path_anim_total_frames = max(1, int(round(duration_ms / frame_interval_ms)))
        self._path_anim_frame = 0
        self.visualizer.renderer.begin_schedule_path_flow(
            self._path_anim_path, self._path_anim_brightness
        )
        self._path_anim_timer.start(frame_interval_ms)

    def _stop_path_animation(self) -> None:
        """Stop any in-progress schedule path animation."""
        if self._path_anim_timer.isActive():
            self._path_anim_timer.stop()
        self.visualizer.renderer.clear_schedule_path_head(render=False)
        self._path_anim_tiles = []
        self._path_anim_path = None
        self._path_anim_brightness = None
        self._path_anim_total_points = 0
        self._path_anim_total_frames = 0
        self._path_anim_frame = 0

    def _adaptive_path_duration_ms(self, n_tiles: int) -> int:
        """Choose a total stroke duration that scales down with schedule size."""
        if n_tiles >= 51:
            return 0
        if n_tiles <= 10:
            return 1400

        span = 50 - 10
        fraction = (n_tiles - 10) / span
        return int(round(1400 + (260 - 1400) * fraction))

    def _on_path_anim_tick(self) -> None:
        """Reveal more of the already-computed path on each timer tick."""
        if len(self._path_anim_tiles) < 2:
            self._stop_path_animation()
            return

        self._path_anim_frame += 1
        if self._path_anim_frame >= self._path_anim_total_frames:
            self.visualizer.renderer.update_schedule_path_flow(
                self._path_anim_path,
                self._path_anim_brightness,
                self._path_anim_total_points,
            )
            self.visualizer.renderer.clear_schedule_path_head()
            self._stop_path_animation()
            return

        progress = self._path_anim_frame / self._path_anim_total_frames
        progress = 1.0 - (1.0 - progress) * (1.0 - progress)
        n_visible = 2 + int(
            round((self._path_anim_total_points - 2) * progress)
        )
        n_visible = max(2, min(n_visible, self._path_anim_total_points))
        self.visualizer.renderer.update_schedule_path_flow(
            self._path_anim_path,
            self._path_anim_brightness,
            n_visible,
        )

    def _open_scenario_compare(self) -> None:
        """Open side-by-side FoM/CDF/slew/deadline comparison for two schedules."""
        dfin: list[float] = []
        if getattr(self, "curr_deadlines", None):
            dfin = [x for x in self.curr_deadlines if x != float("inf")]
        dlg = ScenarioCompareDialog(
            self,
            telescope=self.telescope,
            start_position=self.schedule_panel.start_position,
            deadlines_finite=dfin,
            current_tiles_getter=lambda: self.visualizer.schedule.get_tiles(),
        )
        dlg.exec()