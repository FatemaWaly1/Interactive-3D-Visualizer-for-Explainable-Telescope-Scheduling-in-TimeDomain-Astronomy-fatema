"""
Main sky visualizer orchestrator.
Coordinates tile generation, visualization, and user interaction.
"""

import csv
import logging
import math
import os

import pyvista as pv
import numpy as np

from models.tile import Tile
from models.schedule import Schedule
from models.coordinates import ra_dec_to_xyz
from services.tiles_io import load_tiles_from_file, generate_test_tiles_data
#from services.map_generator import generate_map
from visualization.sphere_renderer import SphereRenderer
from visualization.styles import NODE_RADIUS
from controllers.interaction import InteractionController
from project_utils import load_json_file

class SkyVisualizer:
    def __init__(self, fov_size=15.0):
        """
            Initialize the sky visualizer.

            Args:
                fov_size (float): Field of view size for each tile in degrees
        """
        self.fov_size = fov_size
        self.tiles = []
        self.schedule = Schedule()
        self.renderer = SphereRenderer(fov_size=self.fov_size)
        self.controller = None

    def generate_test_tiles(self, center_ra, center_dec, radius, tiles_per_side):
        """
        Generate a grid of tiles with Gaussian probability distribution.

        Args:
            center_ra (float): Center Right Ascension in degrees
            center_dec (float): Center Declination in degrees
            radius (float): Radius of the tile region in degrees
            tiles_per_side (int): Number of tiles per side of the grid
        """

        grid_data = generate_test_tiles_data(center_ra, center_dec, radius, tiles_per_side=tiles_per_side)

        self.tiles = []
        # Second pass: create tiles with normalized probabilities
        for ra, dec, prob in grid_data:
            self._create_tile(ra, dec, prob, source="generated")

        print(f"Generated {tiles_per_side * tiles_per_side} tiles")

    def generate_map_tiles(
        self,
        *,
        map_type: str,
        n_tiles: int = 200,
        seed: int | None = None,
        clear_existing: bool = True,
        **kwargs,
    ) -> None:
        """
        Generate a probability map and populate `self.tiles`.

        This is a thin wrapper around `services.map_generator.generate_map`.
        """
        if clear_existing:
            self.tiles = []

        tiles = generate_map(map_type=map_type, n_tiles=n_tiles, seed=seed, **kwargs)
        for t in tiles:
            self._create_tile(t["ra"], t["dec"], float(t["prob"]), source=t.get("source", "generated"))

    def _create_tile(self, ra, dec, prob, source="generated"):
        """
        Create a single tile and add to tiles list.

        Args:
            ra (float): Right Ascension in degrees
            dec (float): Declination in degrees
            prob (float): Probability value (0-1)
            source (str): Origin of tile data ("file" or "generated")
        """

        x, y, z = ra_dec_to_xyz(ra, dec)

        tile_data = {
            'ra': ra,
            'dec': dec,
            'prob': prob,
            'position': (x,y,z),
            'source': source
        }

        self.tiles.append(tile_data)

    def load_tiles_from_file(self, filepath, normalize=True, clear_existing=True):
        """
        Load tiles from a JSON or CSV file and create nodes.

        JSON format:
            {"tiles": [{"ra": 0, "dec": 0, "prob": 0.25}, ...]}
        CSV format:
            ra,dec,prob
            0,0,0.25
        """
        # Clear any existing tiles unless caller wants to append
        if clear_existing:
            self.tiles = []

        # Parse and validate rows to (ra, dec, prob)
        parsed_tiles = load_tiles_from_file(filepath, normalize=normalize)
        if not parsed_tiles:
            return

        # Create tiles from parsed data
        for ra, dec, prob in parsed_tiles:
            self._create_tile(ra, dec, prob, source="file")

        print(f"Loaded {len(parsed_tiles)} tiles from {filepath}")