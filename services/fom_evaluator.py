"""
Shared FoM evaluation helpers used by UI and reporting paths.

This module centralizes the schedule -> timeline -> CDF -> expected_FoM pipeline so
the application has one source of truth for FoM calculations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from services.expected_merit import expected_FoM
from services.schedule_metrics import compute_merits_for_deadlines
from services.geometry import angdist_vec


@dataclass
class FoMEvaluationResult:
    """Structured result of one schedule FoM evaluation."""

    fom: float
    deadlines_full: list[float]
    merits: list[float]
    tile_end_times: list[float]
    cumulative_probs: list[float]


def evaluate_schedule_fom(
    tiles: Sequence[dict[str, Any]],
    telescope: Any,
    start_position,
    deadlines_finite: Sequence[float],
) -> FoMEvaluationResult:
    """
    Evaluate FoM for an ordered schedule and finite deadline list.

    Raises ValueError when inputs are invalid or probabilities cannot be normalized.
    """
    deadlines_full = list(deadlines_finite) + [float("inf")]
    merits = compute_merits_for_deadlines(deadlines_full)

    prev_pos = start_position
    time_accum = 0.0
    tile_end_times: list[float] = []
    tile_probs: list[float] = []
    total_prob = 0.0

    for tile in tiles:
        dwell = float(tile.get("dwell_time", 60.0))
        slew = 0.0
        if telescope and prev_pos is not None:
            dist_rad = angdist_vec(prev_pos, tile["position"])
            dist_deg = math.degrees(dist_rad)
            if telescope.slew_speed > 0.0:
                slew = dist_deg / telescope.slew_speed
        time_accum += slew + dwell
        prob = float(tile.get("prob", 0.0))
        total_prob += prob
        tile_end_times.append(time_accum)
        tile_probs.append(prob)
        prev_pos = tile["position"]

    if total_prob <= 0.0:
        raise ValueError("Cannot evaluate FoM: total tile probability is zero.")

    cumulative_probs: list[float] = []
    running = 0.0
    for p in tile_probs:
        running += p / total_prob
        cumulative_probs.append(running)

    def detection_cdf(t: float) -> float:
        if t <= 0.0:
            return 0.0
        cdf_value = 0.0
        for end_time, cum_prob in zip(tile_end_times, cumulative_probs):
            if t < end_time:
                break
            cdf_value = cum_prob
        return min(cdf_value, 1.0)

    fom_value = float(expected_FoM(deadlines_full, merits, detection_cdf))
    return FoMEvaluationResult(
        fom=fom_value,
        deadlines_full=deadlines_full,
        merits=merits,
        tile_end_times=tile_end_times,
        cumulative_probs=cumulative_probs,
    )
