# Architecture and Invariants

## Core flow

1. Tiles are loaded/created in the visualizer.
2. A schedule is an ordered subset of those tiles.
3. Timing uses per-tile dwell plus inter-tile slew.
4. FoM is evaluated from a detection-time CDF over deadline bands.
5. GA searches permutations of schedule order.

## Domain invariants

- Tile dictionaries should expose `ra`, `dec`, `prob`, and `dwell_time`.
- Runtime scheduling paths expect a 3D `position` vector on each tile.
- Deadline lists used by FoM are finite, strictly increasing values, then `+inf`.
- Merit ladders are one value per deadline interval.
- CDF used for FoM must be non-decreasing on sampled deadlines.

## Deadline semantics

- Deadlines represent total mission budget windows.
- Optimization time can consume part of that budget.
- Effective deadlines are computed by `shift_deadlines(D, t_opt)`.

## UI state and persistence

- Main window tracks last loaded/saved schedule file and dirty state.
- Schedule JSON may include `fom_metadata` with:
  - `deadlines_finite`
  - `last_fom`
  - optional GA summary fields
- CSV stores tile rows only (no metadata block).

## Naming compatibility

- `analyse_schedule` remains supported.
- `ui.scenario_compare_dialog` is the canonical import path.
- `ui.scneraio_compare_dialog` remains as legacy compatibility.

## Quality tooling

- Formatting: Black
- Linting + import cleanup: Ruff
- Import sorting: isort
- Pre-commit hooks are configured in `.pre-commit-config.yaml`.
