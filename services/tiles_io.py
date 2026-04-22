import csv
import logging
import math
import os
from typing import List, Tuple

import numpy as np

from project_utils import load_json_file


def load_tiles_from_fits(
        filepath: str,
        nside_new: int = 32,
        max_tiles: int = 500,
        normalize: bool = True
) -> List[Tuple[float, float, float]]:
    """
    Load tiles from a FITS-format HEALPix sky map.
    Supports both flat (single-NSIDE) and multi-order (NUNIQ) formats.
    Downsamples to nside_new and keeps the top max_tiles highest probability pixels.

    :return: list of (ra_deg, dec_deg, prob)
    requires: pip install astropy
    """
    try:
        from astropy.io import fits as pyfits
    except ImportError as e:
        logging.error("FITS skymaps need astropy")
        return []

    try:
        # Check file fomat
        with pyfits.open(filepath) as hdul:
            data = hdul[1].data
            cols = [c.name for c in hdul[1].columns]
            ordering = hdul[1].header.get('ORDERING', '')

            npix_new = 12 * nside_new ** 2

            # Multi-order format (new LIGO standard)
            if 'UNIQ' in cols and ordering == 'NUNIQ':
                uniq = np.array(data['UNIQ'])
                probdensity = np.array(data['PROBDENSITY']) # probability per unit area

                order = (np.log2(uniq // 4)).astype(int) // 2 # resolution level
                nside = 2 ** order
                ipix = uniq - 4 * nside ** 2 # specific pixel at that resolution
                pixel_area = np.pi / (3.0 * nside ** 2)
                probe_raw = probdensity * pixel_area

                # Flatten to uniform resolution
                prob_flat = np.zeros(npix_new)
                for i in range(len(uniq)):
                    ns = nside[i]
                    pix = ipix[i]
                    if ns <= nside_new:
                        # Coarse pixel, spread its probability into sub-pixels
                        ratio = (nside_new // ns) ** 2
                        start = pix * ratio
                        prob_flat[start:start + ratio] += probe_raw[i] / ratio
                    else:
                        # finer pixel, accumulate into its parent
                        ratio = (ns // nside_new) ** 2
                        parent = pix // ratio
                        prob_flat[parent] += probe_raw[i]
            # Flat format (old LIGO standard)
            else:
                prob = np.array(data['PROB']).byteswap().view(np.float64)
                nside = int(hdul[1].header['INSIDE'])
                ratio = (nside // nside_new) ** 2
                prob_flat = np.array([
                    prob[i * ratio:(i + 1) * ratio].sum()
                    for i in range(npix_new)
                ])
    except Exception as e:
        logging.error(f"Failed to read FITS file: {e}")
        return []

    # Convert HEALPix RING pixel indices to RA/Dec
    indices = np.arange(npix_new)
    ncap = 2 * nside_new * (nside_new - 1) # ncap is no. of pixels in the polar cap regions

    theta = np.zeros(npix_new)
    phi = np.zeros(npix_new)

    # North polar cap
    mask = indices < ncap
    ip = indices[mask]
    i_ring = (np.sqrt(ip / 2.0 + 0.5)).astype(int) + 1
    j_ring = ip - 2 * i_ring * (i_ring - 1)
    theta[mask] = np.arccos(1 - i_ring ** 2 / (3 * nside_new ** 2))
    phi[mask] = (j_ring + 0.5) * np.pi / (2 * i_ring)

    # Equatorial belt
    mask = (indices >= ncap) & (indices < npix_new - ncap)
    ip = indices[mask]
    i_ring = (ip - ncap) // (4 * nside_new) + nside_new
    j_ring = (ip - ncap) % (4 * nside_new)
    s = (i_ring - nside_new + 1) % 2
    theta[mask] = np.arccos((2 - i_ring / nside_new) * 2 / 3)
    phi[mask] = (j_ring + s / 2.0) * np.pi / (2 * nside_new)

    # South polar cap
    mask = indices >= npix_new - ncap
    ip = npix_new - indices[mask] - 1
    i_ring = (np.sqrt(ip / 2.0 + 0.5)).astype(int) + 1
    j_ring = ip - 2 * i_ring * (i_ring - 1)
    theta[mask] = np.arccos(-1 + i_ring ** 2 / (3 * nside_new ** 2))
    phi[mask] = (j_ring + 0.5) * np.pi / (2 * i_ring)

    ra = np.degrees(phi)
    dec = 90.0 - np.degrees(theta)

    # Keep only the top N pixels
    top_indices = np.argsort(prob_flat)[::-1][:max_tiles]
    parsed_tiles = [
        (float(ra[idx]), float(dec[idx]), float(prob_flat[idx]))
        for idx in top_indices
        if prob_flat[idx] > 0.0
    ]

    # Normalise
    if normalize and parsed_tiles:
        total = sum(p for _, _, p in parsed_tiles)
        if total > 0:
            parsed_tiles = [(r, d, p / total) for r, d, p in parsed_tiles]

    return parsed_tiles


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
    elif ext == ".fits" or filepath.lower().endswith(".fits.gz"):
        return load_tiles_from_fits(filepath, normalize=normalize)
    else:
        logging.error(f"Unsupported file type: {ext}. Use .json, .csv, or .fits.")
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

    # raw probabilities (unnormalized)
    grid_data = []
    for row in range(tiles_per_side):
        for col in range(tiles_per_side):
            ra = starting_ra + (col * spacing_between_tiles)
            dec = starting_dec + (row * spacing_between_tiles)
            distance = math.sqrt((center_ra - ra) ** 2 + (center_dec - dec) ** 2)
            prob = max(0.0, (1 - (distance / radius)))
            grid_data.append((ra, dec, prob))

    # Normalize
    total_prob = sum(p for _, _, p in grid_data)
    if total_prob > 0:
        for i, (ra, dec, p) in enumerate(grid_data):
            grid_data[i] = (ra, dec, p / total_prob)

    return grid_data