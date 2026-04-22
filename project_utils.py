import json
import logging


def load_json_file(filepath):
    """Load and return data from a JSON file.

    Args:
        filepath (str): Path to the JSON file to load.

    Returns:
        dict | list | None: Parsed JSON data, or None if an error occurs.
    """
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"File not found: {filepath}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON format: {e}")
        return None
    except IOError as e:
        logging.error(f"Error reading file: {e}")
        return None


def viridis_rgb(value):
    """Map a value in [0, 1] to a Viridis-like RGB tuple."""
    t = max(0.0, min(1.0, value))
    stops = [
        (0.0, (68, 1, 84)),
        (0.25, (59, 82, 139)),
        (0.5, (33, 145, 140)),
        (0.75, (94, 201, 98)),
        (1.0, (253, 231, 37)),
    ]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t0 <= t <= t1:
            if t1 == t0:
                return c0
            f = (t - t0) / (t1 - t0)
            r = int(c0[0] + f * (c1[0] - c0[0]))
            g = int(c0[1] + f * (c1[1] - c0[1]))
            b = int(c0[2] + f * (c1[2] - c0[2]))
            return (r, g, b)
    return (68, 1, 84)


def prob_to_blue_rgb(value):
    """Map 0..1 to a blue accent (#58a6ff) tint for table probability column."""
    t = max(0.0, min(1.0, value))
    # Dark #161b22 (22, 27, 34) -> accent #58a6ff (88, 166, 255)
    r = int(22 + t * (88 - 22))
    g = int(27 + t * (166 - 27))
    b = int(34 + t * (255 - 34))
    return (r, g, b)

