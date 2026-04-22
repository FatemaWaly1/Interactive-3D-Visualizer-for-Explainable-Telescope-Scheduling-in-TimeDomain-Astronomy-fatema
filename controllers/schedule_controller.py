from typing import Dict, List, Callable, Optional

from models.schedule import Schedule


class ScheduleController:
    """Encapsulates non-UI schedule operations."""

    def __init__(self, schedule: Schedule, all_tiles: List[Dict], renderer):
        self.schedule = schedule
        self.all_tiles = all_tiles
        self.renderer = renderer

    @property
    def selected(self) -> List[Dict]:
        return self.schedule.selected_tiles

    def clear(self) -> None:
        self.schedule.clear()

    def remove_tile(self, tile: Dict) -> Optional[Dict]:
        """Remove a tile from the schedule and return it if removed."""
        if tile in self.selected:
            self.selected.remove(tile)
            self._reorder()
            return tile
        return None

    def remove_last(self) -> Optional[Dict]:
        """Pop the last scheduled tile, or None."""
        if not self.selected:
            return None
        tile = self.selected.pop()
        self._reorder()
        return tile

    def load_from_data(self, tiles_data: List[Dict], finder: Callable[[float, float], Optional[Dict]]):
        """
        Replace current schedule with tiles loaded from serialized data.

        tiles_data: list of dicts containing at least ra, dec, prob, dwell_time.
        finder: function (ra, dec) -> tile dict in current tiles.
        """
        self.clear()
        for tile in tiles_data:
            match = finder(tile["ra"], tile["dec"])
            if match:
                self.schedule.add_tile(match)
                match["order"] = len(self.selected)
                match["dwell_time"] = float(tile.get("dwell_time", 60.0))

    def _reorder(self) -> None:
        for idx, t in enumerate(self.selected, start=1):
            t["order"] = idx

