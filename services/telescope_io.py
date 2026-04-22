import json
import os
from typing import Dict, List


TELESCOPE_DB_PATH = os.path.join("data", "telescopes.json")


def load_telescopes(path: str = TELESCOPE_DB_PATH) -> Dict:
    """Load telescope store JSON, returning a dict with 'telescopes' list."""
    if not os.path.exists(path):
        return {"telescopes": []}

    with open(path, "r") as f:
        data = json.load(f)
        if isinstance(data, dict) and "telescopes" in data:
            return data
        # Fallback: wrap raw list/dict
        if isinstance(data, list):
            return {"telescopes": data}
        return {"telescopes": []}


def save_telescope(data: Dict, path: str = TELESCOPE_DB_PATH) -> None:
    """Create or update a telescope entry on disk."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    store = load_telescopes(path)

    tel_list: List[Dict] = store.get("telescopes", [])
    updated = False
    for t in tel_list:
        if t.get("name") == data.get("name"):
            t.update(data)
            updated = True
            break
    if not updated:
        tel_list.append(data)

    store["telescopes"] = tel_list

    with open(path, "w") as f:
        json.dump(store, f, indent=2)

