"""
Interaction controller for handling user input.
Coordinates between UI events, data models, and visualization updates.
"""

import numpy as np
from models.coordinates import calculate_distance_3d

class InteractionController:
    """Interaction user interactions and coordinate updates."""

    def __init__(self, tiles, schedule, renderer, max_pick_distance=0.02, schedule_panel=None, main_window=None):
        """
        Initialize the interaction controller.

        Args:
            tiles (list): List of all tile dictionaries
            schedule (Schedule): Schedule object for managing selections
            renderer (SphereRenderer): Renderer for visual updates
            max_pick_distance (float): Max distance to accept selection
            schedule_window (ScheduleWindow): Optional UI window to update
        """
        self.tiles = tiles
        self.schedule = schedule
        self.renderer = renderer
        # Distance threshold to prevent selecting when clicking empty space
        self.max_pick_distance = max_pick_distance
        self.schedule_panel = schedule_panel
        self.main_window = main_window

    def find_closest_tile(self, clicked_xyz):
        """
            Find the tile closest to the clicked 3D coordinates.

            Args:
                clicked_xyz (array-like): (x, y, z) coordinates of click

            Returns:
                dict or None: Closest tile dictionary, or None if no tiles exist
        """

        if clicked_xyz is None or not self.tiles:
            return None

        min_distance = float('inf')
        closest_tile = None

        for tile in self.tiles:
            tile_center = tile['position']
            distance = calculate_distance_3d(clicked_xyz, tile_center)

            if distance < min_distance:
                min_distance = distance
                closest_tile = tile

        if min_distance > self.max_pick_distance:
            print("Click ignored: no nearby tile")
            return None

        print(f"Closest tile found at distance {min_distance:.4f}")
        return closest_tile

    def handle_tile_click(self, picked_point):
        """
        Handle a tile click event.

        :param picked_point (array-like): (x, y, z) coordinates of click
        """

        # Find closest tile
        closest_tile = self.find_closest_tile(picked_point)

        if closest_tile is None:
            print("No tile found")
            return

        # Only allow selection if tile came from a file
        if closest_tile.get("source") != "file":
            print("Selection ignored: tile was not loaded from file")
            return

        schedule_list = self.schedule.selected_tiles

        # Insert mode, read flags from main window
        if (
            self.main_window is not None
            and getattr(self.main_window, "insert_mode", False)
            and getattr(self.main_window, "insert_index", None) is not None
        ):
            # Check for duplicate
            if closest_tile in schedule_list:
                print("Tile already in schedule.")

            insert_index = self.main_window.insert_index
            schedule_list.insert(insert_index, closest_tile)

            # reset insert mode flags on main window
            self.main_window.insert_mode = False
            self.main_window.insert_index = None

        # Normal mode
        else:
            if closest_tile in schedule_list:
                print("Tile already in schedule.")
                return
            schedule_list.append(closest_tile)

        # Renumber order field
        for idx, t in enumerate(schedule_list, start=1):
            t["order"] = idx

        # Ensure dwell time exists
        if "dwell_time" not in closest_tile:
            closest_tile["dwell_time"] = 60.0

        # Tell renderer to update
        tile_index = self.tiles.index(closest_tile)
        self.renderer.highlight_selected_tile(closest_tile, tile_index)
        self.renderer.draw_schedule_labels(schedule_list)
        self.renderer.draw_schedule_path(schedule_list)

        # Update schedule UI if available
        if self.schedule_panel:
            self.schedule_panel.update_schedule()
        if self.main_window is not None and hasattr(
            self.main_window, "mark_schedule_file_modified"
        ):
            self.main_window.mark_schedule_file_modified()

        self._print_selection_feedback(closest_tile)

    def _print_selection_feedback(self, tile):
        """
        Print console feedback about the selection.

        :param tile (dict): The selected tile.
        """

        selection_num = len(self.schedule.selected_tiles)
        print(f"\n{'=' * 50}")
        print(f"Selection #{selection_num}")
        print(f"    RA:       {tile['ra']:.2f}°")
        print(f"    Dec:      {tile['dec']:.2f}°")
        print(f"    Prob:     {tile['prob']:.3f}")
        print(f"Total tiles in schedule: {selection_num}")
        print(f"{'=' * 50}\n")

    def toggle_nodes_visibility(self, flag):
        """
        Toggle visibility of node point cloud.

        :param flag (bool): True to show nodes, False to hide
        """

        actor = self.renderer.plotter.renderer.actors.get('all_nodes')
        if actor:
            actor.SetVisibility(flag)
        print(f"Nodes {'visible' if flag else 'hidden'}")