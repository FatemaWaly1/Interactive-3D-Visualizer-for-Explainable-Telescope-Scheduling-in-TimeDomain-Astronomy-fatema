"""
Schedule management for telescope observation planning.
Handles adding, removing, and querying selected tiles.
"""

class Schedule:
    """Manages the sequence of tiles selected for observation."""
    def __init__(self):
        """Initialize an empty schedule."""
        self.selected_tiles = []

    def add_tile(self, tile):
        """
        Add a tile to the schedule.

        :param tile: Tile object or tile dictionary to add
        :return:
            bool: True if added, False if already in schedule.
        """

        if tile in self.selected_tiles:
            return False
        self.selected_tiles.append(tile)
        return True

    def is_selected(self, tile):
        """
        Check if a tile already in the schedule.

        :param tile: Tile object or tile dictionary to check
        :return:
            bool: True if tile is selected
        """
        return tile in self.selected_tiles

    def get_count(self):
        """Get the number of tiles in the schedule.

        :returns
            int: Number of tiles
        """
        return len(self.selected_tiles)

    def get_tiles(self):
        """
        Get all tiles in the schedule.

        :return:
            list: List of selected tiles in order
        """

        return self.selected_tiles.copy()

    def clear(self):
        """Clear all tiles from the schedule."""
        self.selected_tiles.clear()

    def print_schedule(self):
        """Display the complete observation schedule to console."""

        if not self.selected_tiles:
            print("Schedule is empty - no tiles selected yet")
            return

        print("\n" + "="*60)
        print("OBSERVATION SCHEDULE")
        print("="*60)
        for i, tile in enumerate(self.selected_tiles, 1):
            print(f"{i}. RA={tile['ra']:6.2f}°, Dec={tile['dec']:6.2f}°, Prob={tile['prob']:3f}")
        print("="*60)
        print(f"Total tiles: {len(self.selected_tiles)}\n")