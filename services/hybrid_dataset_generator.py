# import json
# import math
# import random
# from pathlib import Path
# from typing import Any, Dict, List, Tuple
#
# from pyqtgraph.examples.GLSurfacePlot import index
#
# from models.coordinates import ra_dec_to_xyz
# from services.ga_scheduler import brute_force_best_order
# from services.ga_scheduler import run_ga
# from services.schedule_metrics import compute_merits_for_deadlines
#
# class SyntheticSkyMapGenerator:
#     """Generate synthetic sky maps and optimal schedules for Pointer-Network training"""
#
#     def __init__(self, telescope: Any, start_position: Tuple[float, float, float] | None) -> None:
#         """Initialise the generator with the telescope model and schedule start position"""
#         self.telescope = telescope
#         self.start_position = start_position
#
#     def _sample_hotspot_map(self, n_tiles: int) -> List[Dict[str, Any]]:
#         """Create one random sky map as tile dictionaries"""
#
#         # Pick a random hotspot centre in RA/Dec (Fake likely source location for the GW event)
#         centre_ra = random.uniform(0.0, 360.0)
#         centre_dec = random.uniform(-50.0, 50.0)
#
#         # Choose random spread values (Control how concentrated or broad the sky localisation is)
#         sigma_ra = random.uniform(0.0, 35.0)
#         sigma_dec = random.uniform(6.0, 25.0)
#
#         # Create n_tiles random sky tiles (Each tile gets a random RA and Dec)
#         ra = random.uniform(0.0, 360.0)
#         dec = random.uniform(-70.0, 70.0)
#
#         tiles: List[Dict[str, Any]] = []  # List of synthetic tiles
#         raw_probs: List[float] = []  # Keep unnormalised probabilities so can be normalised later
#
#         for tile_index in range(n_tiles):  # Generate each tile independently
#
#             # Tiles near the hotspot get high probability, tiles far away get low probability
#             dra = min(abs(ra - centre_ra), 360 - abs(ra - centre_ra))  # Take the shortest angular distance in RA
#             ddec = abs(dec - centre_dec)  # How far up/down in declination is this tile from the event centre
#
#             # Small sigma -> tight event localisation / large sigma -> broader, more uncertain map
#             exponent = -0.5 * ((dra / sigma_ra) ** 2 + (ddec / sigma_dec) ** 2)
#
#             # Converts the exponent into a +ve score, then adds a little boise so the model doesn't overfit to unrealistically clean patters
#             prob = math.exp(exponent) + random.uniform(0.0, 0.02)
#
#             # Convert each tile to app's normal format
#             x, y, z = ra_dec_to_xyz(ra, dec)
#             tile = {
#                 "tile_id": tile_index,
#                 "ra": ra,
#                 "dec": dec,
#                 "prob": prob,
#                 "position": (x,y,z),
#                 "dwell_time": float(getattr(self.telescope, "dwell_time", 60.0)),
#                 "source": "synthetic"
#             }
#             tiles.append(tile)
#             raw_probs.append(prob)
#
#         total_prob = sum(raw_probs)  # Sum the raw probabilities across the map
#         if total_prob <= 0.0:
#             uniform_prob = 1.0 / max(1, len(tiles))
#             for tile in tiles:
#                 tile["prob"] = uniform_prob
#             return tiles
#
#         # Normalise map so probabilities sum to 1
#         for tile in tiles:
#             tile["prob"] = float(tile["prob"]) / float(total_prob)
#
#         return tiles  # Finished synthetic sky map
#
#     def _sample_deadlines(self, min_count: int = 3, max_count: int = 7) -> List[float]:
#         """Create a random increasing FoM deadline ladder for one synthetic example.
#
#         args:
#         min_count: Minimum number of deadlines to generate.
#         max_count: Maximum number of deadlines to generate.
#
#         returns: a list of increasing deadline values in seconds, ending with float("inf")."""
#
#         if min_count < 1:
#             raise ValueError("min_count must be at least 1.")
#
#         if max_count < min_count:
#             raise ValueError("max_count must be greater than or equal to min_count.")
#
#         # Randomly choose how many finite deadlines the example will use
#         n_deadlines = random.randint(min_count, max_count)
#
#         # List to store the deadline values
#         deadlines: List[float] = []
#
#         current_time = random.uniform(120.0, 600.0)
#
#         # Build each finite deadline one at a time
#         for _ in range(n_deadlines):
#             gap = random.uniform(120.0, 1200.0)  # Sample a +ve time gap to the next deadlines stays later than the previous one
#             current_time += gap  # Move forward in time by the sampled gap
#             deadlines.append(float(current_time))
#
#         deadlines.append(float("inf")) # Add the final open-ended deadline band expected by the FoM calculation
#         return deadlines
#
#     def _solve_reference_order(self, tiles: List[Dict[str, Any]], deadlines: List[float], merits: List[float]) -> List[int]:
#         """Generate the target order using brute force for small maps and GA otherwise."""
#         # Use exact optimisation while factorial growth is still manageable
#         if len(tiles) <= 8:
#             best_order, _best_fom = brute_force_best_order( # Solve exactly for smaller maps
#                 tiles=tiles,
#                 telescope=self.telescope,
#                 deadlines=deadlines,
#                 merits=merits,
#                 start_position=self.start_position,
#             )
#             return list(best_order) if best_order is not None else list(range(len(tiles)))
#
#         # Use the GA for larger maps
#         best_order, _history = run_ga(
#             tiles=tiles,
#             telescope=self.telescope,
#             deadlines=deadlines,
#             merits=merits,
#             start_position=self.start_position,
#             n_generations=180,
#             pop_size=96,
#             time_points=None
#         )
#         return list(best_order) if best_order is not None else list(range(len(tiles)))
#
#     def build_example(self, n_tiles: int) -> Dict[str, Any]:
#         """Create one synthetic sky map plus the reference ordering label."""
#         tiles = self._sample_hotspot_map(n_tiles=n_tiles)  # Generate one synthetic sky map
#         deadlines = self._sample_deadlines()  # Generate one matching deadline ladder
#         merits = compute_merits_for_deadlines(deadlines)  # Build the merit ladder from the deadlines
#         target_order = self._solve_reference_order(tiles=tiles, deadlines=deadlines, merits=merits)  # Solve for the target order
#
#         return {  # Package all into a serialisable dataset record
#             "tiles": [
#                 {
#                     "tile_id": int(tile["tile_id"]),
#                     "ra": float(tile["ra"]),
#                     "dec": float(tile["dec"]),
#                     "prob": float(tile["prob"]),
#                     "dwell_time": float(tile.get("dwell_time", 60.0)),
#                 }
#                 for tile in tiles
#             ],
#             "deadlines": [float(x) if x != float("inf") else "inf" for x in deadlines],
#             "target_order": [int(index) for index in target_order]
#         }
#
#     def generate_dataset(self, output_path: str, n_examples: int, min_tiles: int = 6, max_tiles: int = 18) -> None:
#         """Generate a JSON dataset for offline Pointer-Network training."""
#         output_file = Path(output_path)  # Convert the path string into a Path object
#         output_file.parent.mkdir(parents=True, exist_ok=True)  # Create parent folder if it does not already exist
#
#         with output_file.open("w", encoding="utf-8") as handle:  # open the dataset file for writing
#             for example_index in range(n_examples):
#                 n_tiles = random.randint(min_tiles, max_tiles)  # Randomise the map size so the model sees variable lengths
#                 record = self.build_example(n_tiles=n_tiles)  # Build one full synthetic training example
#                 handle.write(json.dumps(record) + "\n")
#
#                 if (example_index + 1) % 100 == 0:  # Print progress every hundred examples
#                     print(f"Generated {example_index+1}/{n_examples} training examples")
#
#
#
#
#
#
#
#
#
#
#
#
