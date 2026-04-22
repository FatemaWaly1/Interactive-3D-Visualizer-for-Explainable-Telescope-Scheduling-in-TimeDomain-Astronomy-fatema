"""
Evaluation script for GA vs brute-force optimal scheduling.

For each of N synthetic maps, and each deadline in 10–100 s and cutoff 1–50%:
- brute-force optimal FoM (deadlines shifted by the cutoff budget)
- GA FoM under the same shifted scoring

Output CSV columns:
  map_id, deadline, cutoff_perc, cutoff_budget_s, ga_fom, optimal_fom, gap_perc

Parallelises over maps (one process per map by default) so HPC / multi-core helps.

Example:
  python scripts/evaluation.py --maps 10 --workers 8
  python scripts/evaluation.py --maps 1000 --workers 64
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import random
import sys
import time
from pathlib import Path

# Allow `python scripts/evaluation.py` from repo root (imports models, services, ...)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import numpy as np

from models.coordinates import ra_dec_to_xyz
from models.telescope import Telescope
from services.ga_scheduler import (
    brute_force_best_order,
    fitness_function,
    run_ga,
    shift_deadlines,
)

# Defaults (overridden by CLI)
N_MAPS_DEFAULT = 1000
N_TILES = 7
DEADLINES_DEFAULT = list(range(10, 101, 10))
CUTOFF_PERC_DEFAULT = list(range(1, 51))
SEED = 42

GA_N_GENERATIONS = 200
GA_POP_SIZE = 40


@dataclass(frozen=True)
class EvalConfig:
    """Pickle-friendly bundle for worker processes."""

    n_tiles: int
    deadlines: tuple[int, ...]
    cutoffs: tuple[int, ...]
    seed: int
    slew_speed: float
    dwell_time: float


def _make_telescope(cfg: EvalConfig) -> Telescope:
    return Telescope(name="Eval", slew_speed=cfg.slew_speed, dwell_time=cfg.dwell_time)


def sample_hotspot_map(n_tiles: int, telescope: Telescope) -> list[dict[str, Any]]:
    """Generate one synthetic sky map with a single probability hotspot."""

    centre_ra = random.uniform(0.0, 360.0)
    centre_dec = random.uniform(-50.0, 50.0)
    sigma_ra = random.uniform(10.0, 35.0)
    sigma_dec = random.uniform(6.0, 25.0)

    tiles: list[dict[str, Any]] = []
    raw_probs: list[float] = []

    for tile_idx in range(n_tiles):
        ra = random.uniform(0.0, 360.0)
        dec = random.uniform(-70.0, 70.0)
        dra = min(abs(ra - centre_ra), 360 - abs(ra - centre_ra))
        ddec = abs(dec - centre_dec)
        exponent = -0.5 * ((dra / sigma_ra) ** 2 + (ddec / sigma_dec) ** 2)
        prob = math.exp(exponent) + random.uniform(0.0, 0.02)
        x, y, z = ra_dec_to_xyz(ra, dec)
        tiles.append({
            "tile_id": tile_idx,
            "ra": ra,
            "dec": dec,
            "prob": prob,
            "position": np.array([x, y, z]),
            "dwell_time": float(telescope.dwell_time),
        })
        raw_probs.append(prob)

    total = sum(raw_probs)
    if total <= 0.0:
        uniform = 1.0 / max(1, len(tiles))
        for tile in tiles:
            tile["prob"] = uniform
    else:
        for tile in tiles:
            tile["prob"] = float(tile["prob"]) / total

    return tiles


def evaluate_one_config(
    tiles: list[dict[str, Any]],
    telescope: Telescope,
    deadline: float,
    cutoff_budget: float,
    start_position: Any,
) -> tuple[float, float]:
    """Return (ga_fom, optimal_fom) under the same shifted deadlines."""

    deadlines_full = [float(deadline), float("inf")]
    merits = [1.0, 0.0]
    shifted = shift_deadlines(deadlines_full, cutoff_budget)

    _best_order_bf, best_fom_bf = brute_force_best_order(
        tiles=tiles,
        telescope=telescope,
        deadlines=deadlines_full,
        merits=merits,
        start_position=start_position,
        t_opt=cutoff_budget,
    )

    best_order_ga, _history = run_ga(
        tiles=tiles,
        telescope=telescope,
        deadlines=deadlines_full,
        merits=merits,
        start_position=start_position,
        n_generations=GA_N_GENERATIONS,
        pop_size=GA_POP_SIZE,
        time_points=None,
        progress_callback=None,
        planned_opt_seconds=cutoff_budget,
    )

    ga_fom = fitness_function(
        order=best_order_ga,
        tiles=tiles,
        telescope=telescope,
        deadlines=shifted,
        merits=merits,
        start_position=start_position,
    )

    return float(ga_fom), float(best_fom_bf)


def _run_single_map(payload: tuple[int, EvalConfig]) -> list[list[Any]]:
    """Process one map; designed for ProcessPoolExecutor (top-level for pickling)."""
    map_id, cfg = payload
    random.seed(cfg.seed + map_id)
    np.random.seed(cfg.seed + map_id)

    telescope = _make_telescope(cfg)
    start_position: Any = None
    tiles = sample_hotspot_map(cfg.n_tiles, telescope)

    rows: list[list[Any]] = []
    for deadline in cfg.deadlines:
        for cutoff_perc in cfg.cutoffs:
            cutoff_budget = deadline * (cutoff_perc / 100.0)
            ga_fom, optimal_fom = evaluate_one_config(
                tiles=tiles,
                telescope=telescope,
                deadline=float(deadline),
                cutoff_budget=cutoff_budget,
                start_position=start_position,
            )
            gap_perc = (
                100.0 * (optimal_fom - ga_fom) / optimal_fom
                if optimal_fom > 0.0
                else 0.0
            )
            rows.append([
                map_id,
                deadline,
                cutoff_perc,
                f"{cutoff_budget:.4f}",
                f"{ga_fom:.6f}",
                f"{optimal_fom:.6f}",
                f"{gap_perc:.4f}",
            ])
    return rows


def summarise(csv_path: Path, summary_path: Path | None = None) -> None:
    """Summary per (deadline, cutoff): mean FoMs, mean per-row gap, and gap-of-means."""

    summary_path = summary_path or csv_path.parent / "results_summary.csv"
    buckets: dict[tuple[int, int], list[tuple[float, float, float]]] = {}

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row["deadline"]), int(row["cutoff_perc"]))
            buckets.setdefault(key, []).append(
                (
                    float(row["ga_fom"]),
                    float(row["optimal_fom"]),
                    float(row["gap_perc"]),
                )
            )

    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "deadline",
            "cutoff_perc",
            "n",
            "mean_ga_fom",
            "mean_optimal_fom",
            "mean_gap_rowwise",
            "gap_of_means_pct",
        ])
        for (deadline, cutoff_perc), records in sorted(buckets.items()):
            gas = [r[0] for r in records]
            opts = [r[1] for r in records]
            gaps = [r[2] for r in records]
            mean_ga = sum(gas) / len(gas)
            mean_opt = sum(opts) / len(opts)
            mean_gap_row = sum(gaps) / len(gaps)
            gap_of_means = (
                100.0 * (mean_opt - mean_ga) / mean_opt if mean_opt > 0.0 else 0.0
            )
            writer.writerow([
                deadline,
                cutoff_perc,
                len(records),
                f"{mean_ga:.6f}",
                f"{mean_opt:.6f}",
                f"{mean_gap_row:.4f}",
                f"{gap_of_means:.4f}",
            ])
    print(f"[INFO] Summary written to {summary_path}", flush=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GA vs brute-force evaluation")
    parser.add_argument("--maps", type=int, default=N_MAPS_DEFAULT,
                        help="Number of synthetic maps to evaluate")
    parser.add_argument("--tiles", type=int, default=N_TILES,
                        help="Tiles per map (brute force is feasible up to ~8)")
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1),
                        help="Number of parallel worker processes")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--slew-speed", type=float, default=5.0)
    parser.add_argument("--dwell-time", type=float, default=1.0)
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path (default: <repo>/results/results.csv)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    output_path = (
        Path(args.output).resolve()
        if args.output is not None
        else _ROOT / "results" / "results.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    n_maps = args.maps
    n_tiles = args.tiles
    deadlines = tuple(DEADLINES_DEFAULT)
    cutoffs = tuple(CUTOFF_PERC_DEFAULT)
    workers = max(1, args.workers)

    total_runs = n_maps * len(deadlines) * len(cutoffs)
    print(f"[INFO] Writing results to {output_path}", flush=True)
    print(f"[INFO] Configuration: {n_maps} maps, {n_tiles} tiles, "
          f"{len(deadlines)} deadlines, {len(cutoffs)} cutoffs, "
          f"{workers} workers", flush=True)
    print(f"[INFO] Total (map, deadline, cutoff) combinations: {total_runs}",
          flush=True)

    expected_per_map = len(deadlines) * len(cutoffs)
    map_row_counts: dict[int, int] = {}
    if output_path.exists() and output_path.stat().st_size > 0:
        with output_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mid = int(row["map_id"])
                map_row_counts[mid] = map_row_counts.get(mid, 0) + 1
        fully_done = {
            m for m, c in map_row_counts.items() if c == expected_per_map
        }
        partial = {
            m for m, c in map_row_counts.items() if c != expected_per_map
        }
        print(f"[RESUME] {len(fully_done)} maps already complete; "
              f"{len(partial)} partial maps will be re-run.", flush=True)
        done_maps = fully_done
    else:
        done_maps = set()
        print("[INFO] No prior results; starting fresh.", flush=True)

    pending_map_ids = [m for m in range(n_maps) if m not in done_maps]
    if not pending_map_ids:
        print("[INFO] All maps already done; only summarising.", flush=True)
        summarise(output_path)
        return

    if output_path.exists() and any(
        c != expected_per_map for c in map_row_counts.values()
    ):
        print("[RESUME] Rewriting CSV to drop partial-map rows...", flush=True)
        _rewrite_keeping_only_complete_maps(output_path, expected_per_map)

    cfg = EvalConfig(
        n_tiles=n_tiles,
        deadlines=deadlines,
        cutoffs=cutoffs,
        seed=args.seed,
        slew_speed=args.slew_speed,
        dwell_time=args.dwell_time,
    )

    file_is_new = (not output_path.exists()) or output_path.stat().st_size == 0

    start_time = time.time()
    rows_written_this_run = 0
    maps_done_this_run = 0

    with output_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if file_is_new:
            writer.writerow([
                "map_id", "deadline", "cutoff_perc", "cutoff_budget_s",
                "ga_fom", "optimal_fom", "gap_perc",
            ])

        if workers == 1:
            # Serial fallback (useful for debugging)
            for map_id in pending_map_ids:
                rows = _run_single_map((map_id, cfg))
                writer.writerows(rows)
                f.flush()
                rows_written_this_run += len(rows)
                maps_done_this_run += 1
                _log_progress(start_time, maps_done_this_run, len(pending_map_ids),
                              rows_written_this_run, map_id)
        else:
            # Parallel: submit all pending maps, drain as they finish
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(_run_single_map, (map_id, cfg)): map_id
                    for map_id in pending_map_ids
                }
                for fut in as_completed(futures):
                    map_id = futures[fut]
                    try:
                        rows = fut.result()
                    except Exception as exc:
                        print(f"[ERROR] Map {map_id} failed: {exc}", flush=True)
                        continue
                    writer.writerows(rows)
                    f.flush()
                    rows_written_this_run += len(rows)
                    maps_done_this_run += 1
                    _log_progress(start_time, maps_done_this_run,
                                  len(pending_map_ids),
                                  rows_written_this_run, map_id)

    total_elapsed = time.time() - start_time
    print(f"[DONE] Wrote {rows_written_this_run} new rows across "
          f"{maps_done_this_run} maps in {total_elapsed / 3600.0:.2f} hours",
          flush=True)

    print("[INFO] Summarising by (deadline, cutoff_perc)...", flush=True)
    summarise(output_path)


def _rewrite_keeping_only_complete_maps(csv_path: Path, expected_per_map: int) -> None:
    """Keep only rows from maps that have the full expected row count."""
    rows_by_map: dict[int, list[list[str]]] = {}
    header: list[str] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            mid = int(row[0])
            rows_by_map.setdefault(mid, []).append(row)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for mid in sorted(rows_by_map):
            if len(rows_by_map[mid]) == expected_per_map:
                writer.writerows(rows_by_map[mid])


def _log_progress(
    start_time: float,
    maps_done: int,
    total_pending: int,
    rows_written: int,
    last_map_id: int,
) -> None:
    elapsed = time.time() - start_time
    rate_maps = maps_done / elapsed if elapsed > 0 else 0.0
    remaining = total_pending - maps_done
    eta_sec = remaining / rate_maps if rate_maps > 0 else 0.0
    eta_hours = eta_sec / 3600.0
    print(
        f"[PROGRESS] Map {last_map_id} done | "
        f"{maps_done}/{total_pending} maps this run | "
        f"Rate: {rate_maps * 60:.2f} maps/min | "
        f"Rows: {rows_written} | "
        f"ETA: {eta_hours:.1f} h",
        flush=True,
    )


if __name__ == "__main__":
    main()