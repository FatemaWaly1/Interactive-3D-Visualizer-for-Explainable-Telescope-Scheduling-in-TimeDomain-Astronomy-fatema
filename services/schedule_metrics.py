"""
Helpers to evaluate FoM, timing, CDF samples, and deadline-related stats for a fixed tile list and telescope.
Mirrors logic in ui.main_Window and services.ga_scheduler.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

from services.expected_merit import expected_FoM
from services.geometry import angdist_vec
from models.coordinates import ra_dec_to_xyz

@dataclass
class ScheduleMetric:
    """Numerical summary for one ordered schedule under fixed deadlines/merits."""

    fom: float # Expected FoM
    total_slew_s: float # Sum of per-leg slew durations
    total_time_s: float # Sum of slew + dwell for all tiles
    cdf_times: List[float] # End times t_i for step CDF
    cdf_cmv_prob: List[float] # Cumulative normalised probability at each t_i
    tile_end_times: List[float] # Per-tile completion times
    late_counts_by_deadline: List[Tuple[float, int]] # (deadlines_s, count of ends > D)
    cdf_at_deadlines: List[Tuple[float, float]] # (deadlines, F(D))

def _build_detection_cdf(
    tile_end_times: Sequence[float],
    cumulative_probs: Sequence[float],
) -> Callable[[float], float]:
    """Return a step-CDF callable F(t) matching main_window / ga_scheduler."""

    def detection_cdf(t: float) -> float:
        """Map wall time t to cumulative detection probability F(t)."""
        if t <= 0.0:
            return 0.0

        cdf_value = 0.0
        for end_time, cmv_prob in zip(tile_end_times, cumulative_probs):
            if t < end_time: # t before this tile finishes, stop at previous plateau
                break
            cdf_value = cmv_prob # At or past end_time, update plateau
        return min(cdf_value, 1.0) # Clam to valid CDF range

    return detection_cdf

def compute_merits_for_deadlines(deadlines_with_inf: Sequence[float]) -> List[float]:
    """
    Build merit ladder M_i for deadlines [D1..Dz, inf]
    """

    z = len(deadlines_with_inf)  # Number of bands including +inf
    if z <= 1:
        return [1.0]  # Single band merit 1
    return [1.0 - i / (z - 1) for i in range(z)]  # Linear decrease from 1 toward last finite band

def analyse_schedule(
        tiles: Sequence[dict[str, Any]],
        telescope: Any,
        start_position: Optional[Tuple[float, float, float]],
        deadlines_finite: Sequence[float]
) -> ScheduleMetric:
    """
    Compute FoM, slew totals, CDF arrays, and deadline-oriented stats.

    :param tiles: ordered tile dicts with position, prob, dwell_time
    :param telescope: Object with slew_speed
    :param start_position: Previous focus as 3-vector
    :param deadlines_finite: Strictly increasing finite deadlines (no +inf here)
    """

    prev_pos = start_position
    time_accum = 0.0
    total_slew = 0.0
    tile_end_times: list[float] = []  # Completion time per tile
    tile_probs: list[float] = []  # Row probas

    for tile in tiles:
        dwell = float(tile.get("dwell_time", 60.0))  # Seconds on source
        pos = tile.get("position")
        if pos is None:
            pos = tile.get("Position")
        if pos is None:
            ra = tile.get("RA") or tile.get("ra")
            dec = tile.get("Dec") or tile.get("dec")
            if ra is not None and dec is not None:
                pos = ra_dec_to_xyz(float(ra), float(dec))
        slew = 0.0  # Seconds to move
        if telescope is not None and prev_pos is not None and pos is not None:
            dist_rad = angdist_vec(prev_pos, pos)
            dist_deg = math.degrees(dist_rad)
            if getattr(telescope, "slew_speed", 0.0) > 0.0:  # Avoid div by 0
                slew = dist_deg / float(telescope.slew_speed)  # Time = angle / rate
        total_slew += slew
        time_accum += slew + dwell
        tile_end_times.append(time_accum)
        tile_probs.append(float(tile.get("prob", 0.0)))
        if pos is not None:
            prev_pos = pos

    total_prob = sum(tile_probs)  # Unnormalised mass
    if total_prob <= 0.0:  # Cannot normalise CDF or FoM
        empty_cdf: list[float] = []
        return ScheduleMetric(
            fom=0.0,
            total_slew_s=total_slew,
            total_time_s=time_accum,
            cdf_times=empty_cdf,
            cdf_cmv_prob=empty_cdf,
            tile_end_times=tile_end_times,
            late_counts_by_deadline=[(d, 0) for d in deadlines_finite],
            cdf_at_deadlines=[(d, 0.0) for d in deadlines_finite],
        )

    cumulative_probs: list[float] = []  # Normalised running sum
    running = 0.0  # Accumulator
    for p in tile_probs:
        running += p / total_prob  # Normalise
        cumulative_probs.append(running)

    # X for panel-style CDF
    cdf_times = list(tile_end_times)

    # Y after each tile
    cdf_cmv_pfobs = list(cumulative_probs)

    # FoM API expects inf endpoint
    deadlines_full = list(deadlines_finite) + [float("inf")]

    # Match evaluate dialog
    merits = compute_merits_for_deadlines(deadlines_full)

    # Step CDF callable
    det = _build_detection_cdf(tile_end_times, cumulative_probs)

    # expected_FoM may raise an inconsistent CDF
    try:
        fom_val = float(expected_FoM(deadlines_full, merits, det))
    except (ValueError, TypeError):
        fom_val = 0.0

    # Per deadline late tile counts
    late_counts: list[Tuple[float, int]] = []

    # F(D) for stakeholders
    cdf_at: list[Tuple[float, float]] = []

    for d in deadlines_finite:
        # Ends strictly after D
        late = sum(1 for t in tile_end_times if t > d)  # Ends strictly after D
        late_counts.append((float(d), int(late)))  # Store pair
        cdf_at.append((float(d), float(det(float(d)))))  # CDF value at D

    return ScheduleMetric(
        fom=fom_val,
        total_slew_s=total_slew,
        total_time_s=time_accum,
        cdf_times=cdf_times,
        cdf_cmv_prob=cdf_cmv_pfobs,
        tile_end_times=tile_end_times,
        late_counts_by_deadline=late_counts,
        cdf_at_deadlines=cdf_at
    )

