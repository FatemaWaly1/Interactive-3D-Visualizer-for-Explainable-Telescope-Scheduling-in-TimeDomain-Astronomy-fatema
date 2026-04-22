import numpy as np

def angdist_vec(v1,v2) -> float:
    """
    Great-circle angular distance between two directions represented as vectors.
    Returns Angular separation in radians, in [0, pi].
    """

    # Convert inputs to nparrays (float) for consistent behavior
    v1 = np.asarray(v1, dtype=float)
    v2 = np.asarray(v2, dtype=float)

    # Dot product gives cos(γ) for unit vectors.
    dot = float(np.dot(v1, v2))
    dot_clip = float(np.clip(dot, -1.0, 1.0)) # Numerical safety

    # Norm of cross product gives sin(γ) for unit vectors
    cross_num = float(np.linalg.norm(np.cross(v1, v2)))

    # atan2(sin(γ), cos(γ)) returns γ in a stable way over the full range
    return float(np.arctan2(cross_num, dot_clip))

