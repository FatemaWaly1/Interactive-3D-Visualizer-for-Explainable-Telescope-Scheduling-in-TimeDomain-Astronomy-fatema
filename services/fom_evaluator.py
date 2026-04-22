"""
Shared FoM evaluation helpers used by UI and reporting paths.

`evaluate_schedule_fom` delegates timeline + CDF + FoM to `analyse_schedule` so GA,
fitness, and reporting share one implementation. Callers that need slew / late counts
should use `analyse_schedule` directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from services.schedule_metrics import analyse_schedule, compute_merits_for_deadlines


@dataclass
class FoMEvaluationResult:
    """Structured result of one schedule FoM evaluation."""

    fom: float
    deadlines_full: list[float]
    merits: list[float]
    tile_end_times: list[float]
    cumulative_probs: list[float]


def _total_tile_probability(tiles: Sequence[dict[str, Any]]) -> float:
    return sum(float(t.get("prob", 0.0)) for t in tiles)


def evaluate_schedule_fom(
    tiles: Sequence[dict[str, Any]],
    telescope: Any,
    start_position,
    deadlines_finite: Sequence[float],
) -> FoMEvaluationResult:
    """
    Evaluate FoM for an ordered schedule and finite deadline list.

    Uses the same timeline and CDF construction as `analyse_schedule` (including
    resolving `position` from RA/Dec when `position` is absent).

    Raises:
        ValueError: If the sum of tile probabilities is zero (cannot normalise).
    """
    if _total_tile_probability(tiles) <= 0.0:
        raise ValueError("Cannot evaluate FoM: total tile probability is zero.")

    deadlines_full = list(deadlines_finite) + [float("inf")]
    merits = compute_merits_for_deadlines(deadlines_full)
    metric = analyse_schedule(tiles, telescope, start_position, list(deadlines_finite))

    return FoMEvaluationResult(
        fom=float(metric.fom),
        deadlines_full=deadlines_full,
        merits=merits,
        tile_end_times=list(metric.tile_end_times),
        cumulative_probs=list(metric.cdf_cmv_prob),
    )
