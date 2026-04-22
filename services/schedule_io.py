import csv
import json
from typing import Any, Dict, List, Optional, Tuple

# JSON root key for optional FoM / evaluation metadata (deadlines, last FoM, GA summary).
FOM_METADATA_KEY = "fom_metadata"


def parse_deadlines_finite(text: str) -> List[float]:
    """
    Parse a comma-separated list of strictly increasing positive deadlines.

    Raises ValueError with a user-facing message if invalid.
    """
    raw_parts = [p.strip() for p in text.split(",") if p.strip()]
    if not raw_parts:
        raise ValueError("Enter at least one deadline.")
    try:
        deadlines_finite = [float(p) for p in raw_parts]
    except ValueError as exc:
        raise ValueError("Deadlines must be numeric values separated by commas.") from exc
    if any(d <= 0.0 for d in deadlines_finite):
        raise ValueError("All deadlines must be > 0.")
    for i in range(1, len(deadlines_finite)):
        if deadlines_finite[i] <= deadlines_finite[i - 1]:
            raise ValueError("Deadlines must be strictly increasing.")
    return deadlines_finite


def load_schedule_file(path: str) -> Tuple[List[Dict], Optional[Dict[str, Any]]]:
    """
    Load schedule tiles from JSON or CSV.

    JSON may be:
      - {"tiles": [...], "fom_metadata": {...}}  (recommended)
      - {"tiles": [...]}
      - [...]  (tiles only, legacy)

    FoM metadata is only read from JSON; CSV returns (rows, None).

    Returns (tile_dicts, fom_metadata_or_none).
    """
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            tiles = data.get("tiles", [])
            if not isinstance(tiles, list):
                tiles = []
            meta = data.get(FOM_METADATA_KEY)
            if meta is not None and not isinstance(meta, dict):
                meta = None
            return tiles, meta
        if isinstance(data, list):
            return data, None
        return [], None

    if path.lower().endswith(".csv"):
        rows: List[Dict] = []
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows, None

    raise ValueError(f"Unsupported schedule file type: {path}")


def save_schedule_file(
    path: str,
    tiles: List[Dict],
    fom_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Save schedule tiles to JSON or CSV.

    For JSON, if ``fom_metadata`` is provided, it is stored under the key
    ``fom_metadata`` next to ``tiles``. CSV does not support this block; pass
    metadata only when saving as ``.json``.
    """
    if path.lower().endswith(".json"):
        payload: Dict[str, Any] = {"tiles": tiles}
        if fom_metadata:
            payload[FOM_METADATA_KEY] = fom_metadata
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return

    if path.lower().endswith(".csv"):
        if not tiles:
            fieldnames = ["ra", "dec", "prob"]
        else:
            fieldnames = list(tiles[0].keys())
            for key in ("ra", "dec", "prob"):
                if key not in fieldnames:
                    fieldnames.append(key)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(tiles)
        return

    raise ValueError(f"Unsupported schedule file type: {path}")
