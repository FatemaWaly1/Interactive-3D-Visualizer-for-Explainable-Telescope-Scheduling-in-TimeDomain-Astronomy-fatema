from collections.abc import Sequence, Callable
from typing import Protocol

class CumulativeDistribution(Protocol):
    """Protocol describing a callable cumulative distribution function.

    Any callable that takes a single float (time) and returns a float in [0.0, 1.0]
    (the probability of detecting by that time) will satisfy this protocol.
    """

    def __call__(self, t: float) -> float:
        ...

def expected_FoM(
        deadlines: Sequence[float],
        merits: Sequence[float],
        cdf: CumulativeDistribution
) -> float:
    """
    Compute expected FoM for a search policy.

    :param deadlines:
        Increasing sequence of deadlines.
        D1 must be >= 0.0.
        Dz may be float('inf').
        D0 = 0.0.
    :param merits:
        Sequence of merit values, one per deadline interval (D_{i-1}, Di].
        Must have the same length as deadlines.
        M1 >= M2 >= ... >= Mz, function doesn't enforce ordering, it uses given values.
    :param cdf:
        A callable object s.t cdf(t) returns F(t) = P(R <= t),
        the cumulative probability of detection time t for the search policy
        being evaluated.
    :return float:
        Expected FoM E[M] for the given deadlines, merits, and detection-time distribution.
    """

    # Every deadline interval must have an associated merit
    if len(deadlines) != len(merits):
        raise ValueError(
            f"deadlines and merit must have same length; "
        f"got {len(deadlines)} deadlines and {len(merits)} merits."
        )

    if not deadlines:
        raise ValueError("deadline and merits must not be empty.")

    # Check that deadlines are strictly increasing
    for i in range(1, len(deadlines)):
        if deadlines[i] < deadlines[i - 1]:
            raise ValueError(
                "deadlines must be strictly increasing; "
                f"found {deadlines[i]} < {deadlines[i - 1]} at positions"
                f"{i} and {i - 1}."
            )

    # E[M] accumulator
    expected_merit = 0.0

    previous_cdf = 0.0

    # Iterate over each band i = 1...z, pairing (Di, Mi)
    for deadline, merit in zip(deadlines, merits):
        # Handle final deadline being +inf: F(+inf) = 1.0
        if deadline == float("inf"):
            current_cdf = 1.0
        else:
            current_cdf = float(cdf(deadline))

        # Enforce the CDF property: F must be non-dec in t.
        if current_cdf < previous_cdf:
            raise ValueError(
                "CDF values must be non-decreasing at the given deadlines; "
                f"got F({deadline}) = {current_cdf} < previous value {previous_cdf}."
            )

        # Probability that detection occurs in this band (D_{i-1}, Di]
        band_proba = current_cdf - previous_cdf

        # Add this band's contribution to the FoM
        expected_merit += merit * band_proba

        # Update
        previous_cdf = current_cdf
    return expected_merit
