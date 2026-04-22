import csv
import logging
import math
import os
from typing import List, Tuple
from project_utils import load_json_file


def load_tiles_from_file(
        filepath: str,
        normalize: bool = True
) -> List[Tuple[float, float, float]]:
    """
    Load tiles from a JSON or CSV file and create nodes.

    JSON format:
        {"tiles": [{"ra": 0, "dec": 0, "prob": 0.25}, ...]}
    CSV format:
        ra,dec,prob
        0,0,0.25
    """
    # Determine file type from extension
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    raw_tiles = []
    # Read raw rows from JSON or CSV
    if ext == ".json":
        data = load_json_file(filepath)
        if data is None:
            return []
        if isinstance(data, dict):
            raw_tiles = data.get("tiles", [])
        elif isinstance(data, list):
            raw_tiles = data
        else:
            logging.error("JSON format not recognized; expected list or dict with 'tiles'.")
            return []
    elif ext == ".csv":
        try:
            with open(filepath, "r", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                raw_tiles = list(reader)
        except FileNotFoundError:
            logging.error(f"File not found: {filepath}")
            return []
        except IOError as e:
            logging.error(f"Error reading file: {e}")
            return []
    else:
        logging.error(f"Unsupported file type: {ext}. Use .json or .csv.")
        return []

    # Parse and validate rows to (ra, dec, prob)
    parsed_tiles = []
    for i, tile in enumerate(raw_tiles):
        try:
            ra = float(tile["ra"])
            dec = float(tile["dec"])
            prob = float(tile.get("prob", 0.0))
        except (KeyError, TypeError, ValueError):
            logging.warning(f"Skipping invalid tile at index {i}: {tile}")
            continue
        parsed_tiles.append((ra, dec, prob))

    if not parsed_tiles:
        logging.warning("No valid tiles found in file.")
        return []

    # normalization to enforce total probability = 1
    if normalize:
        total_prob = sum(p for _, _, p in parsed_tiles)
        if total_prob > 0:
            parsed_tiles = [(ra, dec, p / total_prob) for ra, dec, p in parsed_tiles]

    return parsed_tiles

def generate_test_tiles_data(
        center_ra: float,
        center_dec: float,
        radius: float,
        tiles_per_side: int
) -> List[Tuple[float, float, float]]:
    """
    Generate a grid of tiles with Gaussian probability distribution.

    Args:
        center_ra (float): Center Right Ascension in degrees
        center_dec (float): Center Declination in degrees
        radius (float): Radius of the tile region in degrees
        tiles_per_side (int): Number of tiles per side of the grid
    """
    # Calculate grid parameters
    width = radius * 2
    spacing_between_tiles = width / tiles_per_side
    starting_ra = center_ra - radius
    starting_dec = center_dec - radius

    # First pass: compute raw probabilities (unnormalized)
    grid_data = []
    for row in range(tiles_per_side):
        for col in range(tiles_per_side):
            ra = starting_ra + (col * spacing_between_tiles)
            dec = starting_dec + (row * spacing_between_tiles)
            distance = math.sqrt((center_ra - ra) ** 2 + (center_dec - dec) ** 2)
            prob = max(0.0, (1 - (distance / radius)))
            grid_data.append((ra, dec, prob))

    # Normalize so probabilities sum to 1
    total_prob = sum(p for _, _, p in grid_data)
    if total_prob > 0:
        for i, (ra, dec, p) in enumerate(grid_data):
            grid_data[i] = (ra, dec, p / total_prob)
    # else: leave as-is (all zeros); tiles would get 0 prob

    return grid_data