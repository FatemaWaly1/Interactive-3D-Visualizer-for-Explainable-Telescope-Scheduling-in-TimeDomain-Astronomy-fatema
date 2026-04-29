
"""
Tile data structure for telescope observations.
Represents a single sky tile with its properties.
"""

from typing import TypedDict, Tuple

class Tile(TypedDict, total=False):
    """
    Schema for tile dictionaries used throughout the application.

    Tiles are created as plain dicts in SkyVisualiser._create_tile
    and accessed via dictionary key lookup.
    """

    ra: float
    dec: float
    prob: float
    position: Tuple[float, float, float]
    source: str
    order: int
    dwell_time: float
    dwell_locked: bool